"""SELEN AI endpoints (§21/§22, §3B, §5B) — advisor only, permission-gated, audited."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit
from ..ai import get_provider
from ..ai.rule_based import RuleBasedProvider
from ..ai.structure_kb import suggest_checklist_items, suggest_structure
from ..db import get_db
from ..events import bus
from ..models import Equipment, MaintenancePlan, MaintenanceHistory, Part, User
from ..rbac import require

router = APIRouter(prefix="/selen", tags=["selen"])


class DiagnoseIn(BaseModel):
    equipment_id: int
    description: str = Field(min_length=3, max_length=2000)


class StructureSuggestIn(BaseModel):
    name: str | None = None
    category: str | None = None
    component_type: str | None = None
    model: str | None = None


class ChecklistSuggestIn(BaseModel):
    name: str | None = None
    category: str | None = None
    component_type: str | None = None


def _build_ctx(db: Session, eq: Equipment, description: str) -> dict:
    from ..db import naive_utcnow

    history = (
        db.query(MaintenanceHistory)
        .filter(MaintenanceHistory.equipment_id == eq.id).count()
    )
    overdue = (
        db.query(MaintenancePlan)
        .filter(MaintenancePlan.equipment_id == eq.id,
                MaintenancePlan.is_active.is_(True),
                MaintenancePlan.next_due.is_not(None),
                MaintenancePlan.next_due < naive_utcnow())
        .count()
    )
    return {
        "description": description,
        "equipment": {
            "id": eq.id, "code": eq.code, "name": eq.name, "level": eq.level,
            "criticality": eq.criticality,
            "category": {"name": eq.category.name} if eq.category else None,
            "technical_specs": eq.technical_specs or {},
        },
        "recent_history": history,
        "overdue_plans": overdue,
    }


@router.post("/diagnose")
def diagnose(body: DiagnoseIn, request: Request,
             user: User = Depends(require("selen.use")),
             db: Session = Depends(get_db)):
    eq = db.get(Equipment, body.equipment_id)
    if eq is None or eq.deleted_at is not None:
        raise HTTPException(status_code=404, detail="تجهیز یافت نشد")

    ctx = _build_ctx(db, eq, body.description)
    provider = get_provider()
    try:
        result = provider.diagnose(ctx)
        used = provider.name
    except Exception:
        # Provider outage must never block advice — fall back transparently.
        result = RuleBasedProvider().diagnose(ctx)
        used = f"{provider.name}→fallback:rule-based"

    audit.record(db, user_id=user.id, action="selen.diagnose", entity_type="equipment",
                 entity_id=eq.id, new={"provider": used}, request=request)
    db.commit()
    bus.publish("selen.diagnosed", {"equipment_id": eq.id})
    return {"equipment_id": eq.id, "provider": used, **result}


@router.get("/spare-suggestions")
def spare_suggestions(_: User = Depends(require("selen.use")),
                      db: Session = Depends(get_db)):
    """§24 — SELEN ranks parts; authorized users may add/edit/delete/override."""
    parts = [
        {"id": p.id, "code": p.code, "name": p.name, "unit": p.unit,
         "stock_qty": p.stock_qty, "min_qty": p.min_qty,
         "criticality": p.criticality, "lead_time_days": p.lead_time_days,
         "supplier": p.supplier, "alternative_part": p.alternative_part,
         "equipment_id": p.equipment_id}
        for p in db.query(Part).all()
    ]
    equipment = [
        {"id": e.id, "criticality": e.criticality}
        for e in db.query(Equipment).filter(Equipment.deleted_at.is_(None)).all()
    ]
    rows = get_provider().spare_part_advice(parts, equipment)
    return {"items": rows}


@router.post("/structure-suggestions")
def structure_suggestions(body: StructureSuggestIn, request: Request,
                          user: User = Depends(require("selen.use")),
                          db: Session = Depends(get_db)):
    """§3B — SELEN suggests subsystems/components for the equipment wizard.

    Advisor only (§14): nothing is added to the structure without an
    explicit user «+» click.
    """
    result = suggest_structure(name=body.name, category=body.category,
                               component_type=body.component_type, model=body.model)
    audit.record(db, user_id=user.id, action="selen.structure_suggested",
                 entity_type="equipment", new={"basis": result["basis"]}, request=request)
    db.commit()
    return {"provider": "rule-based-kb", **result}


@router.post("/checklist-suggestions")
def checklist_suggestions(body: ChecklistSuggestIn, request: Request,
                          user: User = Depends(require("selen.use")),
                          db: Session = Depends(get_db)):
    """§5B — SELEN suggests inspection items for a checklist template."""
    result = suggest_checklist_items(name=body.name, category=body.category,
                                     component_type=body.component_type)
    audit.record(db, user_id=user.id, action="selen.checklist_suggested",
                 entity_type="checklist_template", new={"basis": result["basis"]},
                 request=request)
    db.commit()
    return {"provider": "rule-based-kb", **result}
