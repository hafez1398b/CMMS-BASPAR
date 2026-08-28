"""Equipment module (§11 + MODULE EQUIPMENT — BASPAR document).

* Hierarchy: Company → Factory → Category → Equipment → Subsystem →
  Component → Subcomponent
* Digital file data, optimistic concurrency (§35), soft delete (§58)
* Equipment Passport aggregation (§13)
* Bulk Data Charge: Excel upload → preview/validate → confirm → rollback
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, Request, UploadFile,
)
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import audit, storage
from ..db import get_db, utcnow
from ..events import bus
from ..models import (
    EQUIPMENT_LEVELS, Equipment, EquipmentCategory, Factory, FileObject,
    ImportBatch, ImportBatchRow, MaintenancePlan, User,
)
from ..rbac import require

router = APIRouter(prefix="/equipment", tags=["equipment"])

LEVEL_PARENT = {
    "equipment": None,
    "subsystem": "equipment",
    "component": "subsystem",
    "subcomponent": "component",
}

CRITICALITY_LABELS = {
    "low": "کم", "medium": "متوسط", "high": "زیاد", "critical": "بحرانی",
}


def _eq_out(e: Equipment, with_extra: bool = False) -> dict:
    out = {
        "id": e.id,
        "code": e.code,
        "name": e.name,
        "level": e.level,
        "factory": {"id": e.factory.id, "name": e.factory.name, "code": e.factory.code}
        if e.factory else None,
        "category": {"id": e.category.id, "name": e.category.name, "code": e.category.code}
        if e.category else None,
        "parent_id": e.parent_id,
        "location": e.location,
        "hall": e.hall, "dept": e.dept, "line": e.line,
        "position": e.position, "location_notes": e.location_notes,
        "component_type": e.component_type,
        "criticality_score": e.criticality_score,
        "archived_at": e.archived_at.isoformat() if e.archived_at else None,
        "manufacturer": e.manufacturer,
        "model": e.model,
        "serial_number": e.serial_number,
        "year": e.year,
        "criticality": e.criticality,
        "criticality_fa": CRITICALITY_LABELS.get(e.criticality, e.criticality),
        "status": e.status,
        "version": e.version,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }
    if with_extra:
        out["technical_specs"] = e.technical_specs or {}
        out["dynamic_fields"] = e.dynamic_fields or {}
        out["children"] = [_eq_out(c) for c in (e.children or []) if c.deleted_at is None]
        out["files"] = [
            {"id": f.id, "name": f.original_name, "size": f.size, "mime": f.mime_type,
             "created_at": f.created_at.isoformat() if f.created_at else None}
            for f in (e.files or [])
        ]
    return out


def _get_active(db: Session, eid: int) -> Equipment:
    e = db.get(Equipment, eid)
    if e is None or e.deleted_at is not None:
        raise HTTPException(status_code=404, detail="تجهیز یافت نشد")
    return e


class EquipmentIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=190)
    level: str = "equipment"
    factory_id: int | None = None
    category_id: int | None = None
    parent_id: int | None = None
    location: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    year: int | None = Field(default=None, ge=1800, le=2200)
    criticality: str = "medium"
    status: str = "active"
    technical_specs: dict | None = None
    dynamic_fields: dict | None = None
    hall: str | None = None
    dept: str | None = None
    line: str | None = None
    position: str | None = None
    location_notes: str | None = None
    component_type: str | None = None
    version: int | None = None  # required for updates (§35)


def _validate_hierarchy(db: Session, data: dict) -> None:
    level = data.get("level", "equipment")
    if level not in EQUIPMENT_LEVELS:
        raise HTTPException(status_code=400, detail="سطح تجهیز نامعتبر است")
    expected_parent = LEVEL_PARENT[level]
    parent_id = data.get("parent_id")

    if level == "equipment":
        if parent_id:
            raise HTTPException(status_code=400, detail="تجهیز اصلی نمی‌تواند والد داشته باشد")
        if not data.get("factory_id") or not data.get("category_id"):
            raise HTTPException(status_code=400,
                                detail="برای تجهیز اصلی، کارخانه و دسته‌بندی الزامی است")
        if not db.get(Factory, data["factory_id"]):
            raise HTTPException(status_code=400, detail="کارخانه انتخاب‌شده وجود ندارد")
        if not db.get(EquipmentCategory, data["category_id"]):
            raise HTTPException(status_code=400, detail="دسته‌بندی انتخاب‌شده وجود ندارد")
    else:
        if not parent_id:
            raise HTTPException(status_code=400,
                                detail=f"برای «{level}» انتخاب والد ({expected_parent}) الزامی است")
        parent = db.get(Equipment, parent_id)
        if parent is None or parent.deleted_at is not None:
            raise HTTPException(status_code=400, detail="والد انتخاب‌شده وجود ندارد")
        if parent.level != expected_parent:
            raise HTTPException(
                status_code=400,
                detail=f"والد «{level}» باید از نوع «{expected_parent}» باشد",
            )


# ---------------------------------------------------------------------------
# List / tree / read
# ---------------------------------------------------------------------------


@router.get("")
def list_equipment(
    q: str | None = None,
    factory_id: int | None = None,
    category_id: int | None = None,
    criticality: str | None = None,
    status: str | None = None,
    component_type: str | None = None,
    dept: str | None = None,
    hall: str | None = None,
    level: str = "equipment",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    _: User = Depends(require("equipment.view")),
    db: Session = Depends(get_db),
):
    query = db.query(Equipment).filter(Equipment.deleted_at.is_(None))
    if level and level != "all":
        query = query.filter(Equipment.level == level)
    if factory_id:
        query = query.filter(Equipment.factory_id == factory_id)
    if category_id:
        query = query.filter(Equipment.category_id == category_id)
    if criticality:
        query = query.filter(Equipment.criticality == criticality)
    if status:
        query = query.filter(Equipment.status == status)
    if component_type:
        query = query.filter(Equipment.component_type == component_type)
    if dept:
        query = query.filter(Equipment.dept == dept)
    if hall:
        query = query.filter(Equipment.hall == hall)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Equipment.code.ilike(like), Equipment.name.ilike(like),
            Equipment.serial_number.ilike(like), Equipment.location.ilike(like),
        ))
    total = query.count()
    items = (
        query.order_by(Equipment.code)
        .offset((page - 1) * page_size).limit(page_size).all()
    )
    return {"items": [_eq_out(e) for e in items], "total": total,
            "page": page, "page_size": page_size}


@router.get("/tree")
def equipment_tree(
    factory_id: int | None = None,
    _: User = Depends(require("equipment.view")),
    db: Session = Depends(get_db),
):
    """Factory → Category → Equipment → (Subsystem → Component → …)."""
    factories = db.query(Factory).filter(Factory.is_active.is_(True)).order_by(Factory.name).all()
    cats = db.query(EquipmentCategory).filter(EquipmentCategory.is_active.is_(True)).all()
    roots = (
        db.query(Equipment)
        .filter(Equipment.deleted_at.is_(None), Equipment.level == "equipment")
    )
    if factory_id:
        roots = roots.filter(Equipment.factory_id == factory_id)
    roots = roots.order_by(Equipment.code).all()

    def nest(e: Equipment) -> dict:
        return {
            "id": e.id, "code": e.code, "name": e.name, "level": e.level,
            "criticality": e.criticality, "status": e.status,
            "children": [nest(c) for c in sorted(
                [x for x in (e.children or []) if x.deleted_at is None],
                key=lambda c: c.code)],
        }

    by_factory_cat: dict[tuple, list] = {}
    for e in roots:
        by_factory_cat.setdefault((e.factory_id, e.category_id), []).append(e)

    tree = []
    for f in factories:
        if factory_id and f.id != factory_id:
            continue
        f_cats = []
        for c in sorted(cats, key=lambda c: c.name):
            eqs = by_factory_cat.get((f.id, c.id), [])
            if eqs:
                f_cats.append({"id": c.id, "name": c.name, "code": c.code,
                               "equipment": [nest(e) for e in eqs]})
        uncat = by_factory_cat.get((f.id, None), [])
        if uncat:
            f_cats.append({"id": None, "name": "بدون دسته‌بندی", "code": "-",
                           "equipment": [nest(e) for e in uncat]})
        if f_cats or not factory_id:
            tree.append({"id": f.id, "name": f.name, "code": f.code, "categories": f_cats})
    return {"tree": tree}


@router.get("/export/csv")
def export_equipment_csv(factory_id: int | None = None, category_id: int | None = None,
                         criticality: str | None = None, status: str | None = None,
                         _: User = Depends(require("equipment.export")),
                         db: Session = Depends(get_db)):
    """§31 Export — server-side filtered CSV (UTF-8 BOM for Excel)."""
    import csv as _csv

    q = db.query(Equipment).filter(Equipment.deleted_at.is_(None),
                                   Equipment.level == "equipment")
    if factory_id:
        q = q.filter(Equipment.factory_id == factory_id)
    if category_id:
        q = q.filter(Equipment.category_id == category_id)
    if criticality:
        q = q.filter(Equipment.criticality == criticality)
    if status:
        q = q.filter(Equipment.status == status)

    buf = io.StringIO()
    buf.write("\ufeff")
    w = _csv.writer(buf)
    w.writerow(["code", "name", "category", "factory", "manufacturer", "model",
                "serial_number", "year", "criticality", "status", "location",
                "hall", "dept", "line"])
    for e in q.order_by(Equipment.code).all():
        w.writerow([e.code, e.name, e.category.name if e.category else "",
                    e.factory.name if e.factory else "", e.manufacturer or "",
                    e.model or "", e.serial_number or "", e.year or "",
                    e.criticality, e.status, e.location or "",
                    e.hall or "", e.dept or "", e.line or ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=equipment-export.csv"})



@router.get("/{eid}")
def get_equipment(eid: int, _: User = Depends(require("equipment.view")),
                  db: Session = Depends(get_db)):
    return _eq_out(_get_active(db, eid), with_extra=True)


@router.get("/{eid}/passport")
def equipment_passport(eid: int, _: User = Depends(require("equipment.view")),
                       db: Session = Depends(get_db)):
    """Equipment Passport (§13): one aggregated printable document."""
    e = _get_active(db, eid)

    def collect(node: Equipment, depth: int = 0) -> list[dict]:
        rows = [{"id": node.id, "code": node.code, "name": node.name,
                 "level": node.level, "depth": depth}]
        for c in sorted([x for x in (node.children or []) if x.deleted_at is None],
                        key=lambda c: c.code):
            rows.extend(collect(c, depth + 1))
        return rows

    structure = []
    for c in sorted([x for x in (e.children or []) if x.deleted_at is None],
                    key=lambda c: c.code):
        structure.extend(collect(c, 1))

    plans = [
        {
            "id": p.id, "work_title": p.work_title, "activity_type": p.activity_type,
            "interval_code": p.interval_code, "interval_days": p.interval_days,
            "performer": p.performer,
            "last_execution": p.last_execution.isoformat() if p.last_execution else None,
            "next_due": p.next_due.isoformat() if p.next_due else None,
            "is_active": p.is_active,
        }
        for p in (e.plans or []) if p.deleted_at is None
    ]

    # §16 real maintenance history + §25 cost summary (Phase 1 data).
    from ..models import MaintenanceHistory, WorkOrder, WorkOrderCost
    from sqlalchemy import func

    history = (
        db.query(MaintenanceHistory)
        .filter(MaintenanceHistory.equipment_id == e.id)
        .order_by(MaintenanceHistory.id.desc()).limit(30).all()
    )
    wo_ids = [
        row[0] for row in db.query(WorkOrder.id)
        .filter(WorkOrder.equipment_id == e.id).all()
    ]
    cost_rows = (
        db.query(WorkOrderCost.cost_type, func.sum(WorkOrderCost.amount))
        .filter(WorkOrderCost.work_order_id.in_(wo_ids or [-1]))
        .group_by(WorkOrderCost.cost_type).all()
    ) if wo_ids else []

    return {
        "equipment": _eq_out(e, with_extra=True),
        "structure": structure,
        "maintenance_plans": plans,
        "maintenance_history": [
            {"id": hh.id, "title": hh.title, "work_type": hh.work_type,
             "technician_name": hh.technician.full_name if hh.technician else None,
             "finished_at": hh.finished_at.isoformat() if hh.finished_at else None,
             "duration_minutes": hh.duration_minutes}
            for hh in history
        ],
        "documents": [
            {"id": f.id, "name": f.original_name, "size": f.size} for f in (e.files or [])
        ],
        "calibration": None,  # Phase 2
        "cost_summary": {
            "by_type": {ct: float(total) for ct, total in cost_rows},
            "total": float(sum(t for _, t in cost_rows)) if cost_rows else 0.0,
        },
        "generated_at": utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Create / update / delete
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
def create_equipment(body: EquipmentIn, request: Request,
                     user: User = Depends(require("equipment.create")),
                     db: Session = Depends(get_db)):
    data = body.model_dump()
    if db.query(Equipment).filter(Equipment.code == data["code"]).one_or_none():
        raise HTTPException(status_code=409, detail="کد تجهیز تکراری است")
    _validate_hierarchy(db, data)

    e = Equipment(
        **{k: v for k, v in data.items() if k != "version"},
        created_by=user.id,
    )
    db.add(e)
    db.flush()
    audit.record(db, user_id=user.id, action="equipment.created", entity_type="equipment",
                 entity_id=e.id, new=_eq_out(e), request=request)
    db.commit()
    bus.publish("equipment.created", {"id": e.id, "code": e.code, "name": e.name})
    return _eq_out(e, with_extra=True)


@router.put("/{eid}")
def update_equipment(eid: int, body: EquipmentIn, request: Request,
                     user: User = Depends(require("equipment.edit")),
                     db: Session = Depends(get_db)):
    e = _get_active(db, eid)

    # Optimistic concurrency (§35): silent overwrite is forbidden.
    if body.version is None or body.version != e.version:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "version_conflict",
                "message": "این رکورد توسط کاربر دیگری تغییر کرده است؛ آخرین نسخه را بازبینی کنید",
                "server_version": e.version,
            },
        )

    data = body.model_dump(exclude={"version"})
    before = _eq_out(e)

    if data["level"] != e.level or data["parent_id"] != e.parent_id:
        _validate_hierarchy(db, data)

    dup = (
        db.query(Equipment)
        .filter(Equipment.code == data["code"], Equipment.id != eid)
        .one_or_none()
    )
    if dup:
        raise HTTPException(status_code=409, detail="کد تجهیز تکراری است")

    for k, v in data.items():
        setattr(e, k, v)
    e.version += 1
    e.updated_by = user.id
    e.updated_at = utcnow()

    audit.record(db, user_id=user.id, action="equipment.updated", entity_type="equipment",
                 entity_id=e.id, old=before, new=_eq_out(e), request=request)
    db.commit()
    bus.publish("equipment.updated", {"id": e.id, "code": e.code, "name": e.name})
    return _eq_out(e, with_extra=True)


@router.delete("/{eid}")
def delete_equipment(eid: int, request: Request,
                     user: User = Depends(require("equipment.delete")),
                     db: Session = Depends(get_db)):
    """§34 MODULE EQUIPMENT: direct deletion is forbidden — this endpoint
    only ARCHIVES (deactivates).  History is never destroyed."""
    e = _get_active(db, eid)
    live_children = [c for c in (e.children or []) if c.deleted_at is None]
    if live_children:
        raise HTTPException(status_code=400,
                            detail="این تجهیز دارای زیرسیستم/جزء فعال است؛ ابتدا آن‌ها را آرشیو کنید")
    e.archived_at = utcnow()
    e.deleted_at = utcnow()  # soft delete §58 — archives remain queryable
    e.status = "inactive"
    e.updated_by = user.id
    audit.record(db, user_id=user.id, action="equipment.archived", entity_type="equipment",
                 entity_id=e.id, old={"archived_at": None},
                 new={"archived_at": e.archived_at.isoformat()}, request=request)
    db.commit()
    bus.publish("equipment.deleted", {"id": e.id, "code": e.code})
    return {"ok": True, "archived": True}


@router.post("/{eid}/archive")
def archive_equipment(eid: int, request: Request,
                      user: User = Depends(require("equipment.edit")),
                      db: Session = Depends(get_db)):
    """Explicit archive/restore toggle (§34)."""
    e = db.get(Equipment, eid)
    if e is None:
        raise HTTPException(status_code=404, detail="تجهیز یافت نشد")
    if e.archived_at is None:
        live_children = [c for c in (e.children or []) if c.deleted_at is None]
        if live_children:
            raise HTTPException(status_code=400,
                                detail="ابتدا زیرسیستم‌ها/اجزای فعال این تجهیز را آرشیو کنید")
        e.archived_at = utcnow()
        e.deleted_at = utcnow()
        e.status = "inactive"
        new_state = "archived"
    else:
        e.archived_at = None
        e.deleted_at = None
        e.status = "active"
        new_state = "restored"
    e.updated_by = user.id
    audit.record(db, user_id=user.id, action=f"equipment.{new_state}",
                 entity_type="equipment", entity_id=e.id, request=request)
    db.commit()
    bus.publish("equipment.updated", {"id": e.id, "code": e.code})
    return {"ok": True, "state": new_state}


@router.patch("/{eid}")
def patch_equipment(eid: int, body: dict, request: Request,
                    user: User = Depends(require("equipment.edit")),
                    db: Session = Depends(get_db)):
    """Partial update (§42 PATCH) with optimistic concurrency (§35)."""
    e = _get_active(db, eid)
    if body.get("version") is None or body.get("version") != e.version:
        raise HTTPException(status_code=409, detail={
            "error": "version_conflict", "server_version": e.version,
            "message": "رکورد توسط کاربر دیگری تغییر کرده است"})
    allowed = {"code", "name", "location", "hall", "dept", "line", "position",
               "location_notes", "manufacturer", "model", "serial_number",
               "year", "criticality", "status", "technical_specs", "dynamic_fields",
               "component_type"}
    before = {k: getattr(e, k) for k in allowed}
    changed = {}
    for k, v in body.items():
        if k in allowed:
            setattr(e, k, v)
            changed[k] = v
    e.version += 1
    e.updated_by = user.id
    e.updated_at = utcnow()
    audit.record(db, user_id=user.id, action="equipment.updated", entity_type="equipment",
                 entity_id=e.id, old=before, new=changed, request=request)
    db.commit()
    bus.publish("equipment.updated", {"id": e.id, "code": e.code})
    return _eq_out(e, with_extra=True)


class BulkStatusIn(BaseModel):
    ids: list[int]
    status: str


@router.post("/bulk/status")
def bulk_status(body: BulkStatusIn, request: Request,
                user: User = Depends(require("equipment.edit")),
                db: Session = Depends(get_db)):
    """§31 limited bulk action: status change for authorized users."""
    updated = 0
    for eid in body.ids[:200]:
        e = db.get(Equipment, eid)
        if e is None or e.deleted_at is not None:
            continue
        e.status = body.status
        e.version += 1
        e.updated_by = user.id
        updated += 1
    audit.record(db, user_id=user.id, action="equipment.bulk_status",
                 entity_type="equipment", new={"ids": body.ids, "status": body.status},
                 request=request)
    db.commit()
    bus.publish("equipment.updated", {"bulk": True})
    return {"ok": True, "updated": updated}


# ---------------------------------------------------------------------------
# Files (§45)
# ---------------------------------------------------------------------------


@router.post("/{eid}/files", status_code=201)
async def upload_file(eid: int, request: Request,
                      file: UploadFile = File(...),
                      user: User = Depends(require("files.upload")),
                      db: Session = Depends(get_db)):
    e = _get_active(db, eid)
    meta = await storage.save_upload(file, entity_type="equipment", entity_id=e.id)
    f = FileObject(entity_type="equipment", entity_id=e.id, created_by=user.id, **meta)
    db.add(f)
    db.flush()
    audit.record(db, user_id=user.id, action="file.uploaded", entity_type="equipment",
                 entity_id=e.id, new={"file": f.original_name, "size": f.size},
                 request=request)
    db.commit()
    return {"id": f.id, "name": f.original_name, "size": f.size}


# ---------------------------------------------------------------------------
# Equipment-level aggregates (§42): costs, KPI, checklists, parts
# ---------------------------------------------------------------------------


@router.get("/{eid}/costs")
def equipment_costs(eid: int, _: User = Depends(require("equipment.view")),
                    db: Session = Depends(get_db)):
    """§22 MODULE EQUIPMENT — all costs tied to this equipment via its WOs."""
    from ..models import WorkOrder, WorkOrderCost
    from sqlalchemy import func

    e = _get_active(db, eid)
    wo_ids = [w.id for w in db.query(WorkOrder).filter(WorkOrder.equipment_id == eid).all()]
    rows = []
    total = 0.0
    if wo_ids:
        q = (db.query(WorkOrderCost.cost_type, func.sum(WorkOrderCost.amount))
             .filter(WorkOrderCost.work_order_id.in_(wo_ids))
             .group_by(WorkOrderCost.cost_type).all())
        for ct, amt in q:
            rows.append({"cost_type": ct, "amount": float(amt or 0)})
            total += float(amt or 0)
    return {"equipment_id": eid, "equipment_code": e.code,
            "total": total, "by_type": rows}


@router.get("/{eid}/kpi")
def equipment_kpi(eid: int, _: User = Depends(require("equipment.view")),
                  db: Session = Depends(get_db)):
    """§25 MODULE EQUIPMENT — per-equipment KPIs from real data."""
    from datetime import timedelta
    from ..db import naive_utcnow
    from ..models import WorkOrder, WorkOrderCost
    from sqlalchemy import func

    e = _get_active(db, eid)
    now = naive_utcnow()
    window_start = now - timedelta(days=365)

    wos = db.query(WorkOrder).filter(WorkOrder.equipment_id == eid).all()
    closed = [w for w in wos if w.status == "closed"]
    corrective = [w for w in closed if (w.work_class or "cm") in ("cm", "em")]

    from .workorders import compute_active_minutes
    durations = [compute_active_minutes(w) for w in corrective]
    mttr = round(sum(durations) / len(durations), 1) if durations else None

    failure_count = len(corrective)
    mtbf = round((365 * 24) / failure_count, 1) if failure_count else None

    wo_count = len(wos)
    emergency = len([w for w in wos if w.priority == "emergency"])
    emergency_pct = round(emergency * 100 / wo_count, 1) if wo_count else None

    cost = (db.query(func.coalesce(func.sum(WorkOrderCost.amount), 0))
            .filter(WorkOrderCost.work_order_id.in_([w.id for w in wos] or [-1]))
            .scalar())

    plans = db.query(MaintenancePlan).filter(
        MaintenancePlan.equipment_id == eid, MaintenancePlan.is_active.is_(True),
        MaintenancePlan.deleted_at.is_(None)).all()
    overdue = [p for p in plans if p.next_due and p.next_due < now]
    pm_compliance = round((len(plans) - len(overdue)) * 100 / len(plans), 1) if plans else None

    return {
        "equipment_id": eid, "equipment_code": e.code,
        "window_days": 365,
        "mtbf_hours": mtbf, "mttr_minutes": mttr,
        "availability_pct": None,  # needs dedicated downtime data
        "downtime_minutes": None,
        "pm_compliance_pct": pm_compliance,
        "failure_count": failure_count, "work_order_count": wo_count,
        "maintenance_cost": float(cost or 0),
        "emergency_pct": emergency_pct,
    }


@router.get("/{eid}/checklists")
def equipment_checklists(eid: int, _: User = Depends(require("equipment.view")),
                         db: Session = Depends(get_db)):
    """§16/§19 — inspection checklist runs for this equipment (separate from
    main Maintenance History)."""
    from ..models import ChecklistRun

    _get_active(db, eid)
    runs = (db.query(ChecklistRun)
            .filter(ChecklistRun.equipment_id == eid)
            .order_by(ChecklistRun.id.desc()).all())
    return {"items": [
        {"id": r.id, "template_name": r.template.name if r.template else None,
         "status": r.status, "result_summary": r.result_summary,
         "run_date": r.run_date.isoformat() if r.run_date else None,
         "technician_name": r.technician.full_name if r.technician else None}
        for r in runs]}


@router.get("/{eid}/parts")
def equipment_parts(eid: int, _: User = Depends(require("equipment.view")),
                    db: Session = Depends(get_db)):
    """§21 — parts linked to this equipment (from Inventory module)."""
    from ..models import Part

    _get_active(db, eid)
    parts = db.query(Part).filter(Part.equipment_id == eid).all()
    return {"items": [
        {"id": p.id, "part_number": p.code, "name": p.name,
         "quantity": p.stock_qty, "min_stock": p.min_qty,
         "current_stock": p.stock_qty, "criticality": p.criticality,
         "alternative_part": p.alternative_part, "supplier": p.supplier}
        for p in parts]}


# ---------------------------------------------------------------------------
# Maintenance history (§16) — real records produced by closed work orders
# ---------------------------------------------------------------------------


@router.get("/{eid}/history")
def equipment_history(eid: int, _: User = Depends(require("equipment.view")),
                      db: Session = Depends(get_db)):
    from ..models import MaintenanceHistory

    e = _get_active(db, eid)
    items = (
        db.query(MaintenanceHistory)
        .filter(MaintenanceHistory.equipment_id == e.id)
        .order_by(MaintenanceHistory.id.desc()).all()
    )
    return {
        "items": [
            {"id": it.id, "work_order_id": it.work_order_id, "work_type": it.work_type,
             "title": it.title, "description": it.description,
             "technician_name": it.technician.full_name if it.technician else None,
             "started_at": it.started_at.isoformat() if it.started_at else None,
             "finished_at": it.finished_at.isoformat() if it.finished_at else None,
             "duration_minutes": it.duration_minutes}
            for it in items
        ]
    }


# File download/delete live on the dedicated /files router (modules/files.py)
# to avoid route shadowing by /equipment/{eid}.
