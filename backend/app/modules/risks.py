"""Risk & Opportunity register (§28)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db, utcnow
from ..jalali import parse_jalali
from ..models import Equipment, RiskItem, User
from ..rbac import require

router = APIRouter(prefix="/risks", tags=["risks"])


class RiskIn(BaseModel):
    scope_type: str = "equipment"  # equipment | process
    kind: str = "risk"             # risk | opportunity
    equipment_id: int | None = None
    title: str = Field(min_length=3, max_length=190)
    description: str | None = None
    probability: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    mitigation: str | None = None
    owner_id: int | None = None
    due_date_jalali: str | None = None
    status: str = "open"  # open | mitigating | closed | realized


def _out(r: RiskItem) -> dict:
    return {
        "id": r.id, "scope_type": r.scope_type, "kind": r.kind,
        "equipment_id": r.equipment_id,
        "equipment_name": r.equipment.name if r.equipment else None,
        "title": r.title, "description": r.description,
        "probability": r.probability, "impact": r.impact, "risk_score": r.risk_score,
        "mitigation": r.mitigation,
        "owner_id": r.owner_id,
        "owner_name": r.owner.full_name if r.owner else None,
        "due_date": r.due_date.isoformat() if r.due_date else None,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _get(db: Session, rid: int) -> RiskItem:
    r = db.get(RiskItem, rid)
    if r is None:
        raise HTTPException(status_code=404, detail="مورد یافت نشد")
    return r


def _apply(db: Session, r: RiskItem, body: RiskIn) -> None:
    if body.scope_type not in ("equipment", "process"):
        raise HTTPException(status_code=400, detail="دامنه نامعتبر است")
    if body.kind not in ("risk", "opportunity"):
        raise HTTPException(status_code=400, detail="نوع مورد نامعتبر است")
    if body.scope_type == "equipment" and body.equipment_id:
        eq = db.get(Equipment, body.equipment_id)
        if eq is None or eq.deleted_at is not None:
            raise HTTPException(status_code=400, detail="تجهیز وجود ندارد")
    r.scope_type = body.scope_type
    r.kind = body.kind
    r.equipment_id = body.equipment_id
    r.title = body.title
    r.description = body.description
    r.probability = body.probability
    r.impact = body.impact
    r.risk_score = body.probability * body.impact  # §28 risk score
    r.mitigation = body.mitigation
    r.owner_id = body.owner_id
    r.due_date = (datetime.combine(parse_jalali(body.due_date_jalali),
                                   datetime.min.time(), tzinfo=timezone.utc)
                  if body.due_date_jalali else None)
    r.status = body.status


@router.get("")
def list_risks(kind: str | None = None, equipment_id: int | None = None,
               status: str | None = None,
               _: User = Depends(require("risks.view")), db: Session = Depends(get_db)):
    q = db.query(RiskItem)
    if kind:
        q = q.filter(RiskItem.kind == kind)
    if equipment_id:
        q = q.filter(RiskItem.equipment_id == equipment_id)
    if status:
        q = q.filter(RiskItem.status == status)
    items = q.order_by(RiskItem.risk_score.desc(), RiskItem.id.desc()).all()
    return {"items": [_out(r) for r in items]}


@router.post("", status_code=201)
def create_risk(body: RiskIn, request: Request,
                user: User = Depends(require("risks.manage")),
                db: Session = Depends(get_db)):
    r = RiskItem(created_by=user.id)
    _apply(db, r, body)
    db.add(r)
    db.flush()
    audit.record(db, user_id=user.id, action=f"{r.kind}.created",
                 entity_type="risk_item", entity_id=r.id, new=_out(r), request=request)
    db.commit()
    return _out(r)


@router.put("/{rid}")
def update_risk(rid: int, body: RiskIn, request: Request,
                user: User = Depends(require("risks.manage")),
                db: Session = Depends(get_db)):
    r = _get(db, rid)
    before = _out(r)
    _apply(db, r, body)
    audit.record(db, user_id=user.id, action=f"{r.kind}.updated",
                 entity_type="risk_item", entity_id=r.id,
                 old=before, new=_out(r), request=request)
    db.commit()
    return _out(r)


@router.delete("/{rid}")
def close_risk(rid: int, request: Request,
               user: User = Depends(require("risks.manage")),
               db: Session = Depends(get_db)):
    r = _get(db, rid)
    r.status = "closed"
    audit.record(db, user_id=user.id, action=f"{r.kind}.closed",
                 entity_type="risk_item", entity_id=r.id, request=request)
    db.commit()
    return {"ok": True}
