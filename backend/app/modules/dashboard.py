"""Role-aware dashboard KPIs (§9).  Phase 0 exposes the maintenance-planning
view; work-order-driven KPIs (MTBF/MTTR/Downtime) activate with Phase 1."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db, naive_utcnow
from ..models import Equipment, MaintenancePlan, User, WorkOrder, WorkRequest
from ..rbac import require

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis")
def kpis(_: User = Depends(require("dashboard.view")), db: Session = Depends(get_db)):
    now = naive_utcnow()  # naive: SQLite stores tz-less datetimes
    eq = db.query(Equipment).filter(Equipment.deleted_at.is_(None))
    total_equipment = eq.count()

    by_crit = dict(
        db.query(Equipment.criticality, func.count(Equipment.id))
        .filter(Equipment.deleted_at.is_(None))
        .group_by(Equipment.criticality).all()
    )
    by_status = dict(
        db.query(Equipment.status, func.count(Equipment.id))
        .filter(Equipment.deleted_at.is_(None))
        .group_by(Equipment.status).all()
    )

    plans_q = db.query(MaintenancePlan).filter(
        MaintenancePlan.is_active.is_(True), MaintenancePlan.deleted_at.is_(None)
    )
    total_plans = plans_q.count()
    overdue = plans_q.filter(MaintenancePlan.next_due.is_not(None),
                             MaintenancePlan.next_due < now).count()
    due_7 = plans_q.filter(MaintenancePlan.next_due.is_not(None),
                           MaintenancePlan.next_due >= now,
                           MaintenancePlan.next_due <= now + timedelta(days=7)).count()
    no_baseline = plans_q.filter(MaintenancePlan.last_execution.is_(None)).count()

    planned_done = total_plans - overdue - no_baseline
    pm_compliance = round(planned_done * 100 / total_plans, 1) if total_plans else None

    return {
        "equipment": {
            "total": total_equipment,
            "by_criticality": by_crit,
            "critical_count": by_crit.get("critical", 0),
            "high_count": by_crit.get("high", 0),
            "by_status": by_status,
            "active": by_status.get("active", 0),
            "under_maintenance": by_status.get("under_maintenance", 0),
        },
        "pm": {
            "total_plans": total_plans,
            "overdue": overdue,
            "due_next_7_days": due_7,
            "without_baseline": no_baseline,
            "pm_compliance_pct": pm_compliance,
        },
        "work_orders": {
            "open": db.query(WorkOrder).filter(WorkOrder.status.in_(
                ["created", "pending_permit", "ready", "in_progress", "paused",
                 "awaiting_confirmation", "final_approval"])).count(),
            "in_progress": db.query(WorkOrder).filter(
                WorkOrder.status.in_(["in_progress", "paused"])).count(),
            "closed": db.query(WorkOrder).filter(WorkOrder.status == "closed").count(),
            "backlog": db.query(WorkOrder).filter(WorkOrder.status.in_(
                ["created", "pending_permit", "ready"])).count(),
        },
        "requests": {
            "open": db.query(WorkRequest).filter(WorkRequest.status.in_(
                ["pending_supervisor", "pending_manager"])).count(),
            "converted": db.query(WorkRequest).filter(
                WorkRequest.status == "converted").count(),
        },
        "availability": {"pct": None, "note": "نیازمند داده توقفات فاز ۱ (در دست ساخت)"},
        "mtbf": None,
        "mttr": None,
        "maintenance_cost": None,
    }


@router.get("/critical-equipment")
def critical_equipment(_: User = Depends(require("dashboard.view")),
                       db: Session = Depends(get_db)):
    items = (
        db.query(Equipment)
        .filter(Equipment.deleted_at.is_(None),
                Equipment.criticality.in_(["critical", "high"]),
                Equipment.level == "equipment")
        .order_by(Equipment.criticality.desc(), Equipment.code)
        .limit(50).all()
    )
    return {
        "items": [
            {"id": e.id, "code": e.code, "name": e.name,
             "criticality": e.criticality, "status": e.status,
             "factory": e.factory.name if e.factory else None}
            for e in items
        ]
    }
