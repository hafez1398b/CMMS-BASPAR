"""Inspection Checklists (§15).

Templates (monthly/yearly/custom) hold items; runs capture per-item
results (OK / Not OK / N/A / Requires Action) by technician + date +
comment + attachments.  Any Not-OK can spawn a Work Request directly.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db, utcnow
from ..events import bus
from ..jalali import parse_jalali
from ..models import (ChecklistItem, ChecklistRun, ChecklistRunItem,
                      ChecklistTemplate, Equipment, User)
from ..notify import notify_users, users_with_roles
from ..rbac import require

router = APIRouter(prefix="/checklists", tags=["checklists"])

PERIODS = {"monthly": 30, "yearly": 365}
RESULTS = {"ok", "not_ok", "na", "requires_action"}


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

class TemplateIn(BaseModel):
    name: str = Field(min_length=3, max_length=190)
    period_code: str = "monthly"
    custom_days: int | None = Field(default=None, ge=1, le=3650)
    equipment_id: int | None = None
    items: list[str] = []
    version: int | None = None


def _tpl_out(t: ChecklistTemplate) -> dict:
    return {
        "id": t.id, "name": t.name, "period_code": t.period_code,
        "custom_days": t.custom_days, "equipment_id": t.equipment_id,
        "equipment_name": t.equipment.name if t.equipment else None,
        "is_active": t.is_active, "version": t.version,
        "items": [{"id": i.id, "text": i.text, "sort_order": i.sort_order}
                  for i in t.items if i.is_active],
    }


@router.get("/templates")
def list_templates(_: User = Depends(require("checklist.view")),
                   db: Session = Depends(get_db)):
    tpls = db.query(ChecklistTemplate).filter(ChecklistTemplate.is_active.is_(True)).all()
    return {"items": [_tpl_out(t) for t in tpls]}


@router.post("/templates", status_code=201)
def create_template(body: TemplateIn, request: Request,
                    user: User = Depends(require("checklist.manage")),
                    db: Session = Depends(get_db)):
    if body.period_code not in PERIODS and body.period_code != "custom":
        raise HTTPException(status_code=400, detail="دوره چک‌لیست نامعتبر است")
    if body.period_code == "custom" and not body.custom_days:
        raise HTTPException(status_code=400, detail="برای دوره سفارشی، تعداد روز الزامی است")
    if not body.items:
        raise HTTPException(status_code=400, detail="حداقل یک آیتم چک‌لیست لازم است")
    t = ChecklistTemplate(name=body.name, period_code=body.period_code,
                          custom_days=body.custom_days, equipment_id=body.equipment_id,
                          created_by=user.id)
    db.add(t)
    db.flush()
    for idx, text in enumerate(body.items):
        db.add(ChecklistItem(template_id=t.id, text=text.strip(), sort_order=idx))
    audit.record(db, user_id=user.id, action="checklist.template_created",
                 entity_type="checklist_template", entity_id=t.id,
                 new=_tpl_out(t), request=request)
    db.commit()
    return _tpl_out(t)


@router.put("/templates/{tid}")
def update_template(tid: int, body: TemplateIn, request: Request,
                    user: User = Depends(require("checklist.manage")),
                    db: Session = Depends(get_db)):
    t = db.get(ChecklistTemplate, tid)
    if t is None or not t.is_active:
        raise HTTPException(status_code=404, detail="قالب یافت نشد")
    if body.version is None or body.version != t.version:
        raise HTTPException(status_code=409, detail={"error": "version_conflict",
                            "server_version": t.version})
    t.name = body.name
    t.period_code = body.period_code
    t.custom_days = body.custom_days
    t.equipment_id = body.equipment_id
    t.version += 1
    for i in t.items:
        i.is_active = False
    for idx, text in enumerate(body.items):
        db.add(ChecklistItem(template_id=t.id, text=text.strip(), sort_order=idx))
    audit.record(db, user_id=user.id, action="checklist.template_updated",
                 entity_type="checklist_template", entity_id=t.id, request=request)
    db.commit()
    db.refresh(t)
    return _tpl_out(t)


# ---------------------------------------------------------------------------
# Runs (§15 execution)
# ---------------------------------------------------------------------------

class RunIn(BaseModel):
    template_id: int
    equipment_id: int
    run_date_jalali: str | None = None  # e.g. 1405/05/26


def _run_out(r: ChecklistRun) -> dict:
    return {
        "id": r.id, "template_id": r.template_id, "template_name": r.template.name,
        "equipment_id": r.equipment_id,
        "equipment_name": r.equipment.name if r.equipment else None,
        "equipment_code": r.equipment.code if r.equipment else None,
        "technician_name": r.technician.full_name if r.technician else None,
        "run_date": r.run_date.isoformat() if r.run_date else None,
        "status": r.status, "result_summary": r.result_summary,
        "general_comment": r.general_comment,
        "items": [
            {"id": ri.id, "item_id": ri.item_id, "text": ri.item.text,
             "result": ri.result, "comment": ri.comment}
            for ri in r.items
        ],
    }


@router.get("/runs")
def list_runs(equipment_id: int | None = None,
              _: User = Depends(require("checklist.view")),
              db: Session = Depends(get_db)):
    q = db.query(ChecklistRun)
    if equipment_id:
        q = q.filter(ChecklistRun.equipment_id == equipment_id)
    items = q.order_by(ChecklistRun.id.desc()).limit(100).all()
    return {"items": [_run_out(r) for r in items]}


@router.post("/runs", status_code=201)
def start_run(body: RunIn, request: Request,
              user: User = Depends(require("checklist.execute")),
              db: Session = Depends(get_db)):
    tpl = db.get(ChecklistTemplate, body.template_id)
    if tpl is None or not tpl.is_active:
        raise HTTPException(status_code=404, detail="قالب چک‌لیست یافت نشد")
    eq = db.get(Equipment, body.equipment_id)
    if eq is None or eq.deleted_at is not None:
        raise HTTPException(status_code=404, detail="تجهیز یافت نشد")

    run_date = utcnow()
    if body.run_date_jalali:
        run_date = datetime.combine(parse_jalali(body.run_date_jalali),
                                    datetime.min.time(), tzinfo=timezone.utc)
    run = ChecklistRun(template_id=tpl.id, equipment_id=eq.id, technician_id=user.id,
                       run_date=run_date)
    db.add(run)
    db.flush()
    for item in tpl.items:
        if item.is_active:
            db.add(ChecklistRunItem(run_id=run.id, item_id=item.id))
    audit.record(db, user_id=user.id, action="checklist.run_started",
                 entity_type="checklist_run", entity_id=run.id, request=request)
    db.commit()
    db.refresh(run)
    return _run_out(run)


class ItemResultIn(BaseModel):
    result: str
    comment: str | None = None


@router.post("/runs/{rid}/items/{riid}")
def set_item_result(rid: int, riid: int, body: ItemResultIn, request: Request,
                    user: User = Depends(require("checklist.execute")),
                    db: Session = Depends(get_db)):
    run = db.get(ChecklistRun, rid)
    if run is None:
        raise HTTPException(status_code=404, detail="اجرا یافت نشد")
    if run.status == "complete":
        raise HTTPException(status_code=400, detail="این اجرا بسته شده است")
    ri = db.get(ChecklistRunItem, riid)
    if ri is None or ri.run_id != run.id:
        raise HTTPException(status_code=404, detail="آیتم یافت نشد")
    if body.result not in RESULTS:
        raise HTTPException(status_code=400, detail="نتیجه نامعتبر است")
    ri.result = body.result
    ri.comment = body.comment
    audit.record(db, user_id=user.id, action="checklist.item_result",
                 entity_type="checklist_run", entity_id=run.id,
                 new={"item": ri.item.text, "result": body.result}, request=request)
    db.commit()
    return {"ok": True}


class FinishRunIn(BaseModel):
    general_comment: str | None = None


@router.post("/runs/{rid}/finish")
def finish_run(rid: int, body: FinishRunIn, request: Request,
               user: User = Depends(require("checklist.execute")),
               db: Session = Depends(get_db)):
    run = db.get(ChecklistRun, rid)
    if run is None:
        raise HTTPException(status_code=404, detail="اجرا یافت نشد")
    if run.status == "complete":
        raise HTTPException(status_code=400, detail="قبلاً بسته شده است")
    pending = [ri for ri in run.items if ri.result == "pending"]
    if pending:
        raise HTTPException(status_code=400,
                            detail=f"{len(pending)} آیتم هنوز بی‌پاسخ است")
    run.general_comment = body.general_comment
    run.status = "complete"
    run.completed_at = utcnow()
    has_not_ok = any(ri.result in ("not_ok", "requires_action") for ri in run.items)
    run.result_summary = "fail" if has_not_ok else "pass"
    audit.record(db, user_id=user.id, action="checklist.run_completed",
                 entity_type="checklist_run", entity_id=run.id,
                 new={"result": run.result_summary}, request=request)
    if has_not_ok:
        notify_users(db, users_with_roles(db, ["technical_manager", "supervisor"]),
                     kind="system",
                     title=f"نتیجه بازرسی «{run.template.name}» دارای مورد نامطلوب است",
                     body=f"تجهیز: {run.equipment.name}", link=f"#/checklists/{run.id}")
    bus.publish("pm.completed", {"checklist_run": run.id})
    db.commit()
    return _run_out(run)


@router.post("/runs/{rid}/to-request", status_code=201)
def run_to_request(rid: int, request: Request,
                   user: User = Depends(require("requests.create")),
                   db: Session = Depends(get_db)):
    """§15: Not-OK inspection results escalate into a Work Request/WO."""
    from ..models import WorkRequest

    run = db.get(ChecklistRun, rid)
    if run is None:
        raise HTTPException(status_code=404, detail="اجرا یافت نشد")
    bad = [ri.item.text for ri in run.items if ri.result in ("not_ok", "requires_action")]
    req = WorkRequest(
        title=f"اقدام اصلاحی بازرسی: {run.template.name}",
        description="موارد نامطلوب چک‌لیست:\n" + "\n".join(f"- {b}" for b in bad) +
        (f"\nتوضیحات: {run.general_comment}" if run.general_comment else ""),
        request_type="inspection", priority="high",
        equipment_id=run.equipment_id, status="pending_supervisor",
        requested_by=user.id,
    )
    db.add(req)
    db.flush()
    notify_users(db, users_with_roles(db, ["supervisor", "maintenance_manager"]),
                 kind="request", title=f"درخواست جدید از چک‌لیست: {req.title}",
                 link=f"#/requests/{req.id}")
    audit.record(db, user_id=user.id, action="checklist.escalated_to_request",
                 entity_type="checklist_run", entity_id=run.id,
                 new={"request_id": req.id}, request=request)
    db.commit()
    bus.publish("request.created", {"id": req.id, "title": req.title})
    return {"request_id": req.id, "title": req.title}


@router.post("/runs/{rid}/to-workorder", status_code=201)
def run_to_workorder(rid: int, request: Request,
                     user: User = Depends(require("workorders.create")),
                     db: Session = Depends(get_db)):
    """§17: Not-OK results may spawn a Work ORDER directly (user chooses
    between request and work order)."""
    from ..models import WorkOrder

    run = db.get(ChecklistRun, rid)
    if run is None:
        raise HTTPException(status_code=404, detail="اجرا یافت نشد")
    bad = [ri.item.text for ri in run.items if ri.result in ("not_ok", "requires_action")]
    if not bad:
        raise HTTPException(status_code=400, detail="مورد نامطلوبی برای ایجاد دستورکار وجود ندارد")
    wo = WorkOrder(
        code=f"CHK-{run.id}-WO",
        title=f"اقدام اصلاحی بازرسی: {run.template.name}",
        description="موارد نامطلوب چک‌لیست:\n" + "\n".join(f"- {b}" for b in bad) +
        (f"\nتوضیحات: {run.general_comment}" if run.general_comment else ""),
        equipment_id=run.equipment_id, status="created",
        work_class="cm", priority="high",
        assigned_to=user.id, created_by=user.id,
    )
    db.add(wo); db.flush()
    notify_users(db, users_with_roles(db, ["supervisor", "maintenance_manager"]),
                 kind="work_order", title=f"دستورکار جدید از چک‌لیست: {wo.title}",
                 link=f"#/work-orders/{wo.id}")
    audit.record(db, user_id=user.id, action="checklist.escalated_to_workorder",
                 entity_type="checklist_run", entity_id=run.id,
                 new={"work_order_id": wo.id}, request=request)
    db.commit()
    bus.publish("workorder.created", {"id": wo.id, "title": wo.title})
    return {"work_order_id": wo.id, "code": wo.code, "title": wo.title}


# ---------------------------------------------------------------------------
# Checklist generation from PM plans (بند ۶ سند بارگذاری نهایی)
# ---------------------------------------------------------------------------


@router.post("/from-plans/{eid}", status_code=201)
def checklist_from_plans(eid: int, request: Request,
                         user: User = Depends(require("checklist.manage")),
                         db: Session = Depends(get_db)):
    """هر آیتم چک‌لیست مستقیماً از یک ردیف برنامه نت همان تجهیز مشتق می‌شود
    (نه متن آزاد). آیتم‌ها به ترتیب تناوب (روزانه‌ها اول) چیده می‌شوند."""
    from ..models import MaintenancePlan

    eq = db.get(Equipment, eid)
    if eq is None or eq.deleted_at is not None:
        raise HTTPException(status_code=404, detail="تجهیز یافت نشد")
    plans = (
        db.query(MaintenancePlan)
        .filter(MaintenancePlan.equipment_id == eid,
                MaintenancePlan.is_active.is_(True),
                MaintenancePlan.deleted_at.is_(None))
        .all()
    )
    if not plans:
        raise HTTPException(status_code=400, detail="این تجهیز برنامه نت فعالی ندارد")

    name = f"چک‌لیست چکاپ {eq.name} ({eq.code})"
    if db.query(ChecklistTemplate).filter(ChecklistTemplate.name == name).first():
        raise HTTPException(status_code=409, detail="این چک‌لیست قبلاً از برنامه نت ساخته شده است")

    ordered = sorted(plans, key=lambda p: (p.interval_days or 9999, p.id))
    tpl = ChecklistTemplate(name=name, period_code="custom", custom_days=1,
                            equipment_id=eq.id, created_by=user.id)
    db.add(tpl); db.flush()
    for i, p in enumerate(ordered, start=1):
        db.add(ChecklistItem(template_id=tpl.id, text=p.work_title, sort_order=i))
    audit.record(db, user_id=user.id, action="checklist.generated_from_plans",
                 entity_type="checklist_template", entity_id=tpl.id,
                 new={"equipment_id": eq.id, "items": len(ordered)}, request=request)
    db.commit(); db.refresh(tpl)
    return _tpl_out(tpl)
