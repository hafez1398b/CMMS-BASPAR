"""Reporting (§26/§27): filtered work-order/cost report + CSV export,
plus the standard CMMS KPI set computed from real data."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db, naive_utcnow, to_naive
from ..jalali import parse_jalali
from ..models import MaintenancePlan, Part, WorkOrder, WorkOrderCost
from ..rbac import require

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/work-orders")
def work_order_report(
    from_jalali: str | None = None,
    to_jalali: str | None = None,
    status: str | None = None,
    work_class: str | None = None,
    factory_id: int | None = None,
    category_id: int | None = None,
    equipment_id: int | None = None,
    component_type: str | None = None,
    dept: str | None = None,
    priority: str | None = None,
    _: object = Depends(require("reports.view")),
    db: Session = Depends(get_db),
):
    from ..models import Equipment
    q = db.query(WorkOrder)
    if any([factory_id, category_id, component_type, dept, equipment_id]):
        q = q.join(Equipment, WorkOrder.equipment_id == Equipment.id)
        if equipment_id:
            q = q.filter(WorkOrder.equipment_id == equipment_id)
        if factory_id:
            q = q.filter(Equipment.factory_id == factory_id)
        if category_id:
            q = q.filter(Equipment.category_id == category_id)
        if component_type:
            q = q.filter(Equipment.component_type == component_type)
        if dept:
            q = q.filter(Equipment.dept == dept)
    if from_jalali:
        d = datetime.combine(parse_jalali(from_jalali), datetime.min.time(), tzinfo=timezone.utc)
        q = q.filter(WorkOrder.created_at >= d)
    if to_jalali:
        d = datetime.combine(parse_jalali(to_jalali), datetime.max.time(), tzinfo=timezone.utc)
        q = q.filter(WorkOrder.created_at <= d)
    if status:
        q = q.filter(WorkOrder.status == status)
    if work_class:
        q = q.filter(WorkOrder.work_class == work_class)
    if priority:
        q = q.filter(WorkOrder.priority == priority)
    items = q.order_by(WorkOrder.id.desc()).all()

    from .workorders import compute_active_minutes

    rows = []
    for w in items:
        cost = db.query(func.coalesce(func.sum(WorkOrderCost.amount), 0)) \
            .filter(WorkOrderCost.work_order_id == w.id).scalar()
        rows.append({
            "id": w.id, "code": w.code, "title": w.title, "status": w.status,
            "work_class": w.work_class,
            "equipment_name": w.equipment.name if w.equipment else None,
            "assignee_name": w.assignee.full_name if w.assignee else None,
            "duration_minutes": compute_active_minutes(w),
            "cost": float(cost or 0),
            "created_at": w.created_at.isoformat() if w.created_at else None,
        })
    by_status = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {"rows": rows, "total": len(rows),
            "total_cost": sum(r["cost"] for r in rows),
            "total_duration_minutes": sum(r["duration_minutes"] for r in rows),
            "by_status": by_status}


@router.get("/equipment")
def equipment_report(
    factory_id: int | None = None,
    category_id: int | None = None,
    component_type: str | None = None,
    dept: str | None = None,
    hall: str | None = None,
    criticality: str | None = None,
    status: str | None = None,
    q: str | None = None,
    _: object = Depends(require("reports.view")),
    db: Session = Depends(get_db),
):
    """Report Builder for equipment (§27/§28): filter by factory, category
    (across all factories), component type (پمپ/تابلو برق/دینام…), section, etc."""
    from sqlalchemy import or_ as or__
    from ..models import Equipment
    qy = db.query(Equipment).filter(Equipment.deleted_at.is_(None))
    if factory_id:
        qy = qy.filter(Equipment.factory_id == factory_id)
    if category_id:
        qy = qy.filter(Equipment.category_id == category_id)
    if component_type:
        qy = qy.filter(Equipment.component_type == component_type)
    if dept:
        qy = qy.filter(Equipment.dept == dept)
    if hall:
        qy = qy.filter(Equipment.hall == hall)
    if criticality:
        qy = qy.filter(Equipment.criticality == criticality)
    if status:
        qy = qy.filter(Equipment.status == status)
    if q:
        like = f"%{q}%"
        qy = qy.filter(or__(Equipment.code.ilike(like), Equipment.name.ilike(like),
                            Equipment.serial_number.ilike(like)))
    items = qy.order_by(Equipment.code).all()
    return {"rows": [
        {"code": e.code, "name": e.name,
         "factory": e.factory.name if e.factory else "",
         "category": e.category.name if e.category else "",
         "component_type": e.component_type or "", "dept": e.dept or "",
         "hall": e.hall or "", "criticality": e.criticality, "status": e.status,
         "manufacturer": e.manufacturer or "", "model": e.model or ""}
        for e in items], "total": len(items)}


@router.get("/equipment/export.csv")
def equipment_csv(factory_id: int | None = None, category_id: int | None = None,
                  component_type: str | None = None, dept: str | None = None,
                  hall: str | None = None, criticality: str | None = None,
                  status: str | None = None, q: str | None = None,
                  _: object = Depends(require("reports.view")),
                  db: Session = Depends(get_db)):
    data = equipment_report(factory_id=factory_id, category_id=category_id,
                            component_type=component_type, dept=dept, hall=hall,
                            criticality=criticality, status=status, q=q, db=db)
    buf = io.StringIO(); buf.write("\ufeff")
    w = csv.writer(buf)
    w.writerow(["code", "name", "factory", "category", "component_type", "dept",
                "hall", "criticality", "status", "manufacturer", "model"])
    for r in data["rows"]:
        w.writerow([r["code"], r["name"], r["factory"], r["category"], r["component_type"],
                    r["dept"], r["hall"], r["criticality"], r["status"],
                    r["manufacturer"], r["model"]])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=equipment-report.csv"})


@router.get("/work-orders/export.csv")
def work_order_csv(from_jalali: str | None = None, to_jalali: str | None = None,
                   status: str | None = None,
                   _: object = Depends(require("reports.view")),
                   db: Session = Depends(get_db)):
    # reuse the report endpoint logic (keyword args to match current signature)
    data = work_order_report(from_jalali=from_jalali, to_jalali=to_jalali,
                             status=status, db=db)
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM for Excel UTF-8
    w = csv.writer(buf)
    w.writerow(["code", "title", "status", "work_class", "equipment",
                "assignee", "duration_minutes", "cost", "created_at"])
    for r in data["rows"]:
        w.writerow([r["code"], r["title"], r["status"], r["work_class"],
                    r["equipment_name"], r["assignee_name"],
                    r["duration_minutes"], r["cost"], r["created_at"]])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=work-orders-report.csv"})


@router.get("/kpis-advanced")
def advanced_kpis(_: object = Depends(require("reports.view")),
                  db: Session = Depends(get_db)):
    """§27 KPI set.  Values are computed from live data; those needing
    dedicated downtime accounting expose null with a reason."""
    from .workorders import compute_active_minutes

    now = naive_utcnow()
    window_start = now - timedelta(days=90)

    closed = (
        db.query(WorkOrder)
        .filter(WorkOrder.status == "closed",
                WorkOrder.created_at >= window_start.replace(tzinfo=timezone.utc))
        .all()
    )
    durations = [compute_active_minutes(w) for w in closed]
    mttr = round(sum(durations) / len(durations), 1) if durations else None

    # MTBF proxy: per critical equipment, window hours / failure count
    failures = {w.equipment_id for w in closed if (w.work_class or "cm") in ("cm", "em")}
    active_eq = db.query(WorkOrder.equipment_id).filter(
        WorkOrder.created_at >= window_start.replace(tzinfo=timezone.utc),
        WorkOrder.equipment_id.is_not(None)).distinct().count()
    mtbf = round((90 * 24) / (len(failures) / active_eq), 1) if failures and active_eq else None

    total_wo = db.query(WorkOrder).count()
    closed_total = db.query(WorkOrder).filter(WorkOrder.status == "closed").count()
    em = db.query(WorkOrder).filter(WorkOrder.priority == "emergency").count()
    pm_plans = db.query(MaintenancePlan).filter(
        MaintenancePlan.is_active.is_(True), MaintenancePlan.deleted_at.is_(None)).count()
    overdue = db.query(MaintenancePlan).filter(
        MaintenancePlan.is_active.is_(True), MaintenancePlan.deleted_at.is_(None),
        MaintenancePlan.next_due.is_not(None), MaintenancePlan.next_due < now).count()
    total_cost = db.query(func.coalesce(func.sum(WorkOrderCost.amount), 0)).scalar()
    low_stock = sum(1 for p in db.query(Part).all() if p.stock_qty <= (p.min_qty or 0))

    return {
        "window_days": 90,
        "mttr_minutes": mttr,
        "mtbf_hours_per_failure": mtbf,
        "availability_pct": None,  # needs dedicated downtime data (§27)
        "pm_compliance_pct": round((pm_plans - overdue) * 100 / pm_plans, 1) if pm_plans else None,
        "schedule_compliance_pct": None,
        "backlog": total_wo - closed_total,
        "emergency_pct": round(em * 100 / total_wo, 1) if total_wo else None,
        "maintenance_cost_total": float(total_cost or 0),
        "critical_parts_low_stock": low_stock,
        "note": "MTBF/MTTR از داده واقعی دستورکارهای بسته‌شده محاسبه می‌شوند؛ برای دسترس‌پذیری دقیق، ثبت توقفات لازم است.",
    }


@router.get("/maintenance-history")
def maintenance_history_report(
    from_jalali: str | None = None,
    to_jalali: str | None = None,
    factory_id: int | None = None,
    category_id: int | None = None,
    equipment_id: int | None = None,
    work_type: str | None = None,
    technician_id: int | None = None,
    _: object = Depends(require("reports.view")),
    db: Session = Depends(get_db),
):
    """§28: گزارش سوابق نت — یک تجهیز / یک دسته / یک کارخانه / یک دسته در
    چند کارخانه، با بازه تاریخ شمسی."""
    from ..models import Equipment, MaintenanceHistory

    q = db.query(MaintenanceHistory).join(
        Equipment, MaintenanceHistory.equipment_id == Equipment.id)
    if equipment_id:
        q = q.filter(MaintenanceHistory.equipment_id == equipment_id)
    if factory_id:
        q = q.filter(Equipment.factory_id == factory_id)
    if category_id:
        q = q.filter(Equipment.category_id == category_id)
    if work_type:
        q = q.filter(MaintenanceHistory.work_type == work_type)
    if technician_id:
        q = q.filter(MaintenanceHistory.technician_id == technician_id)
    if from_jalali:
        d = datetime.combine(parse_jalali(from_jalali), datetime.min.time(), tzinfo=timezone.utc)
        q = q.filter(MaintenanceHistory.finished_at >= d)
    if to_jalali:
        d = datetime.combine(parse_jalali(to_jalali), datetime.max.time(), tzinfo=timezone.utc)
        q = q.filter(MaintenanceHistory.finished_at <= d)

    rows = []
    for hh in q.order_by(MaintenanceHistory.finished_at.desc()).all():
        rows.append({
            "id": hh.id, "title": hh.title, "work_type": hh.work_type,
            "equipment_code": hh.equipment.code if hh.equipment else None,
            "equipment_name": hh.equipment.name if hh.equipment else None,
            "factory_name": hh.equipment.factory.name if hh.equipment and hh.equipment.factory else None,
            "category_name": hh.equipment.category.name if hh.equipment and hh.equipment.category else None,
            "technician_name": hh.technician.full_name if hh.technician else None,
            "duration_minutes": hh.duration_minutes,
            "finished_at": hh.finished_at.isoformat() if hh.finished_at else None,
        })
    by_type = {}
    for r in rows:
        by_type[r["work_type"]] = by_type.get(r["work_type"], 0) + 1
    return {"rows": rows, "total": len(rows), "by_type": by_type}


@router.get("/maintenance-history/export.csv")
def maintenance_history_csv(
    from_jalali: str | None = None, to_jalali: str | None = None,
    factory_id: int | None = None, category_id: int | None = None,
    equipment_id: int | None = None, work_type: str | None = None,
    technician_id: int | None = None,
    user=Depends(require("reports.view")), db: Session = Depends(get_db),
):
    data = maintenance_history_report(
        from_jalali=from_jalali, to_jalali=to_jalali, factory_id=factory_id,
        category_id=category_id, equipment_id=equipment_id, work_type=work_type,
        technician_id=technician_id, _=user, db=db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["کد تجهیز", "نام تجهیز", "کارخانه", "دسته", "عنوان", "نوع",
                "تکنسین", "مدت (دقیقه)", "تاریخ"])
    for r in data["rows"]:
        w.writerow([r["equipment_code"], r["equipment_name"], r["factory_name"],
                    r["category_name"], r["title"], r["work_type"],
                    r["technician_name"], r["duration_minutes"] or "",
                    r["finished_at"] or ""])
    out = io.BytesIO("\ufeff" .encode("utf-8") + buf.getvalue().encode("utf-8"))
    out.seek(0)
    return StreamingResponse(
        out, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=maintenance-history.csv"})
