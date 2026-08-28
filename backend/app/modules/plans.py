"""Maintenance Plan — Phase 0 basic version (§14).

Activity types & intervals are data-driven lookup lists; `next_due` is
computed server-side from `last_execution + interval_days`.  Advanced PM
automation lands in Phase 1 without schema changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db, naive_utcnow, to_naive, utcnow
from ..events import bus
from ..jalali import parse_jalali
from ..models import Equipment, LookupItem, MaintenancePlan, PMConsumable, User
from ..rbac import require

router = APIRouter(tags=["maintenance-plans"])


def _interval_days(db: Session, interval_code: str) -> int:
    item = (
        db.query(LookupItem)
        .filter(LookupItem.list_code == "interval", LookupItem.code == interval_code,
                LookupItem.is_active.is_(True))
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=400, detail="دوره تکرار نامعتبر است")
    return int((item.extra or {}).get("days", 30))


def _compute_next_due(last_execution: datetime | None, interval_days: int) -> datetime | None:
    if last_execution is None:
        return None
    return last_execution + timedelta(days=interval_days)


class PlanIn(BaseModel):
    equipment_id: int
    work_class: str | None = None
    work_title: str = Field(min_length=2, max_length=190)
    target_id: int | None = None          # subsystem/component this plan targets
    activity_description: str | None = None
    activity_type: str = "inspection"
    net_activity: bool = False
    stop_required: bool = False
    interval_code: str = "monthly"
    performer: str | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=100000)
    last_execution_jalali: str | None = None  # e.g. "1404/05/01"
    is_active: bool = True
    version: int | None = None


def _plan_out(p: MaintenancePlan) -> dict:
    return {
        "id": p.id,
        "equipment_id": p.equipment_id,
        "work_class": p.work_class,
        "work_title": p.work_title,
        "target_id": p.target_id,
        "target_name": p.target.name if p.target else None,
        "activity_description": p.activity_description,
        "activity_type": p.activity_type,
        "net_activity": p.net_activity,
        "stop_required": p.stop_required,
        "interval_code": p.interval_code,
        "interval_days": p.interval_days,
        "performer": p.performer,
        "duration_minutes": p.duration_minutes,
        "last_execution": p.last_execution.isoformat() if p.last_execution else None,
        "next_due": p.next_due.isoformat() if p.next_due else None,
        "is_active": p.is_active,
        "version": p.version,
        "overdue": bool(p.next_due and to_naive(p.next_due) < naive_utcnow()),
    }


@router.get("/equipment/{eid}/plans")
def list_plans(eid: int, _: User = Depends(require("plans.view")),
               db: Session = Depends(get_db)):
    plans = (
        db.query(MaintenancePlan)
        .filter(MaintenancePlan.equipment_id == eid, MaintenancePlan.deleted_at.is_(None))
        .order_by(MaintenancePlan.id).all()
    )
    return {"items": [_plan_out(p) for p in plans]}


@router.post("/plans", status_code=201)
def create_plan(body: PlanIn, request: Request,
                user: User = Depends(require("plans.create")),
                db: Session = Depends(get_db)):
    eq = db.get(Equipment, body.equipment_id)
    if eq is None or eq.deleted_at is not None:
        raise HTTPException(status_code=404, detail="تجهیز یافت نشد")

    # Activity type must exist in the (extensible) lookup list §14.
    at = (
        db.query(LookupItem)
        .filter(LookupItem.list_code == "activity_type", LookupItem.code == body.activity_type,
                LookupItem.is_active.is_(True))
        .one_or_none()
    )
    if at is None:
        raise HTTPException(status_code=400, detail="نوع فعالیت نامعتبر است")

    interval_days = _interval_days(db, body.interval_code)
    last_exec = None
    if body.last_execution_jalali:
        last_exec = datetime.combine(parse_jalali(body.last_execution_jalali),
                                     datetime.min.time(), tzinfo=timezone.utc)

    plan = MaintenancePlan(
        equipment_id=body.equipment_id,
        work_class=body.work_class,
        work_title=body.work_title,
        target_id=body.target_id,
        activity_description=body.activity_description,
        activity_type=body.activity_type,
        net_activity=body.net_activity,
        stop_required=body.stop_required,
        interval_code=body.interval_code,
        interval_days=interval_days,
        performer=body.performer,
        duration_minutes=body.duration_minutes,
        last_execution=last_exec,
        next_due=_compute_next_due(last_exec, interval_days),
        is_active=body.is_active,
        created_by=user.id,
    )
    db.add(plan)
    db.flush()
    audit.record(db, user_id=user.id, action="plan.created", entity_type="maintenance_plan",
                 entity_id=plan.id, new=_plan_out(plan), request=request)
    db.commit()
    bus.publish("pm.created", {"id": plan.id, "equipment_id": eq.id})
    return _plan_out(plan)


@router.put("/plans/{pid}")
def update_plan(pid: int, body: PlanIn, request: Request,
                user: User = Depends(require("plans.edit")),
                db: Session = Depends(get_db)):
    plan = db.get(MaintenancePlan, pid)
    if plan is None or plan.deleted_at is not None:
        raise HTTPException(status_code=404, detail="برنامه نت یافت نشد")
    if body.version is None or body.version != plan.version:
        raise HTTPException(status_code=409, detail={
            "error": "version_conflict",
            "message": "این رکورد توسط کاربر دیگری تغییر کرده است",
            "server_version": plan.version,
        })

    interval_days = _interval_days(db, body.interval_code)
    last_exec = None
    if body.last_execution_jalali:
        last_exec = datetime.combine(parse_jalali(body.last_execution_jalali),
                                     datetime.min.time(), tzinfo=timezone.utc)

    before = _plan_out(plan)
    plan.work_class = body.work_class
    plan.work_title = body.work_title
    plan.target_id = body.target_id
    plan.activity_description = body.activity_description
    plan.activity_type = body.activity_type
    plan.net_activity = body.net_activity
    plan.stop_required = body.stop_required
    plan.interval_code = body.interval_code
    plan.interval_days = interval_days
    plan.performer = body.performer
    plan.duration_minutes = body.duration_minutes
    plan.last_execution = last_exec
    plan.next_due = _compute_next_due(last_exec, interval_days)
    plan.is_active = body.is_active
    plan.version += 1
    plan.updated_by = user.id
    plan.updated_at = utcnow()

    audit.record(db, user_id=user.id, action="plan.updated", entity_type="maintenance_plan",
                 entity_id=plan.id, old=before, new=_plan_out(plan), request=request)
    db.commit()
    bus.publish("pm.updated", {"id": plan.id})
    return _plan_out(plan)


@router.delete("/plans/{pid}")
def delete_plan(pid: int, request: Request,
                user: User = Depends(require("plans.delete")),
                db: Session = Depends(get_db)):
    plan = db.get(MaintenancePlan, pid)
    if plan is None or plan.deleted_at is not None:
        raise HTTPException(status_code=404, detail="برنامه نت یافت نشد")
    plan.deleted_at = utcnow()
    plan.updated_by = user.id
    audit.record(db, user_id=user.id, action="plan.deleted", entity_type="maintenance_plan",
                 entity_id=plan.id, request=request)
    db.commit()
    return {"ok": True}


@router.get("/plans/due")
def due_plans(days: int = 30, _: User = Depends(require("plans.view")),
              db: Session = Depends(get_db)):
    """Upcoming / overdue preventive activities (drives dashboard & PM KPI)."""
    now = naive_utcnow()
    horizon = now + timedelta(days=days)
    plans = (
        db.query(MaintenancePlan)
        .filter(MaintenancePlan.is_active.is_(True), MaintenancePlan.deleted_at.is_(None),
                MaintenancePlan.next_due.is_not(None))
        .all()
    )
    items = []
    for p in plans:
        if to_naive(p.next_due) <= horizon:
            out = _plan_out(p)
            out["equipment_code"] = p.equipment.code if p.equipment else None
            out["equipment_name"] = p.equipment.name if p.equipment else None
            items.append(out)
    items.sort(key=lambda x: (x["next_due"] is None, x["next_due"] or ""))
    return {"items": items}


# ---------------------------------------------------------------------------
# PM consumables (برنامه نت با قطعات مصرفی)
# ---------------------------------------------------------------------------


class ConsumableIn(BaseModel):
    part_name: str = Field(min_length=1, max_length=190)
    quantity: float | None = None
    unit: str | None = Field(default=None, max_length=32)
    part_id: int | None = None
    note: str | None = None


def _consumable_out(c: PMConsumable) -> dict:
    return {
        "id": c.id, "plan_id": c.plan_id, "equipment_id": c.equipment_id,
        "part_id": c.part_id, "part_name": c.part_name, "quantity": c.quantity,
        "unit": c.unit, "note": c.note,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/plans/{pid}/consumables")
def list_consumables(pid: int, _: User = Depends(require("plans.view")),
                     db: Session = Depends(get_db)):
    plan = db.get(MaintenancePlan, pid)
    if plan is None or plan.deleted_at is not None:
        raise HTTPException(status_code=404, detail="برنامه یافت نشد")
    rows = db.query(PMConsumable).filter(PMConsumable.plan_id == pid).all()
    return {"items": [_consumable_out(c) for c in rows]}


@router.post("/plans/{pid}/consumables", status_code=201)
def add_consumable(pid: int, body: ConsumableIn, request: Request,
                   user: User = Depends(require("plans.create")),
                   db: Session = Depends(get_db)):
    plan = db.get(MaintenancePlan, pid)
    if plan is None or plan.deleted_at is not None:
        raise HTTPException(status_code=404, detail="برنامه یافت نشد")
    c = PMConsumable(
        plan_id=pid, equipment_id=plan.equipment_id, part_id=body.part_id,
        part_name=body.part_name.strip(), quantity=body.quantity,
        unit=(body.unit or "").strip() or None, note=body.note,
        created_by=user.id,
    )
    db.add(c)
    audit.record(db, user_id=user.id, action="plan.consumable_added",
                 entity_type="maintenance_plan", entity_id=pid,
                 new={"part_name": c.part_name, "quantity": c.quantity, "unit": c.unit},
                 request=request)
    db.commit(); db.refresh(c)
    return _consumable_out(c)


@router.delete("/plans/consumables/{cid}")
def delete_consumable(cid: int, request: Request,
                      user: User = Depends(require("plans.edit")),
                      db: Session = Depends(get_db)):
    c = db.get(PMConsumable, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="یافت نشد")
    before = _consumable_out(c)
    db.delete(c)
    audit.record(db, user_id=user.id, action="plan.consumable_removed",
                 entity_type="maintenance_plan", entity_id=c.plan_id,
                 old=before, request=request)
    db.commit()
    return {"ok": True}


@router.get("/equipment/{eid}/pm-consumables")
def equipment_pm_consumables(eid: int, _: User = Depends(require("plans.view")),
                             db: Session = Depends(get_db)):
    """All PM consumables of one equipment, grouped per plan (پرونده دیجیتال)."""
    eq = db.get(Equipment, eid)
    if eq is None or eq.deleted_at is not None:
        raise HTTPException(status_code=404, detail="تجهیز یافت نشد")
    rows = (
        db.query(PMConsumable, MaintenancePlan)
        .join(MaintenancePlan, PMConsumable.plan_id == MaintenancePlan.id)
        .filter(MaintenancePlan.equipment_id == eid,
                MaintenancePlan.deleted_at.is_(None))
        .all()
    )
    items = []
    for c, p in rows:
        out = _consumable_out(c)
        out["plan_title"] = p.work_title
        out["interval_code"] = p.interval_code
        items.append(out)
    return {"items": items}
