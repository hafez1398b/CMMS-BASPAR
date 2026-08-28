"""Calibration management (§29)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db, naive_utcnow, to_naive, utcnow
from ..jalali import parse_jalali
from ..models import CalibrationItem, Equipment, User
from ..rbac import require

router = APIRouter(prefix="/calibration", tags=["calibration"])


class CalibrationIn(BaseModel):
    equipment_id: int
    standard: str | None = None
    last_calibration_jalali: str | None = None
    interval_days: int = Field(default=365, ge=1, le=3650)
    result: str | None = None  # pass | fail | adjusted
    certificate_file_id: int | None = None
    notes: str | None = None
    status: str = "active"
    version: int | None = None


def _out(c: CalibrationItem) -> dict:
    overdue = bool(c.next_due and to_naive(c.next_due) < naive_utcnow())
    return {
        "id": c.id, "equipment_id": c.equipment_id,
        "equipment_name": c.equipment.name if c.equipment else None,
        "equipment_code": c.equipment.code if c.equipment else None,
        "standard": c.standard,
        "last_calibration": c.last_calibration.isoformat() if c.last_calibration else None,
        "interval_days": c.interval_days,
        "next_due": c.next_due.isoformat() if c.next_due else None,
        "overdue": overdue,
        "result": c.result, "certificate_file_id": c.certificate_file_id,
        "notes": c.notes, "status": c.status,
    }


def _apply(db: Session, c: CalibrationItem, body: CalibrationIn) -> None:
    eq = db.get(Equipment, body.equipment_id)
    if eq is None or eq.deleted_at is not None:
        raise HTTPException(status_code=400, detail="تجهیز وجود ندارد")
    c.equipment_id = body.equipment_id
    c.standard = body.standard
    c.last_calibration = (
        datetime.combine(parse_jalali(body.last_calibration_jalali),
                         datetime.min.time(), tzinfo=timezone.utc)
        if body.last_calibration_jalali else None)
    c.interval_days = body.interval_days
    c.next_due = (c.last_calibration + timedelta(days=body.interval_days)
                  if c.last_calibration else None)
    if body.result and body.result not in ("pass", "fail", "adjusted"):
        raise HTTPException(status_code=400, detail="نتیجه کالیبراسیون نامعتبر است")
    c.result = body.result
    c.certificate_file_id = body.certificate_file_id
    c.notes = body.notes
    c.status = body.status


@router.get("")
def list_calibration(equipment_id: int | None = None,
                     _: User = Depends(require("calibration.view")),
                     db: Session = Depends(get_db)):
    q = db.query(CalibrationItem)
    if equipment_id:
        q = q.filter(CalibrationItem.equipment_id == equipment_id)
    items = q.order_by(CalibrationItem.id).all()
    return {"items": [_out(c) for c in items]}


@router.post("", status_code=201)
def create_calibration(body: CalibrationIn, request: Request,
                       user: User = Depends(require("calibration.manage")),
                       db: Session = Depends(get_db)):
    c = CalibrationItem(created_by=user.id)
    _apply(db, c, body)
    db.add(c)
    db.flush()
    audit.record(db, user_id=user.id, action="calibration.created",
                 entity_type="calibration_item", entity_id=c.id,
                 new=_out(c), request=request)
    db.commit()
    return _out(c)


@router.put("/{cid}")
def update_calibration(cid: int, body: CalibrationIn, request: Request,
                       user: User = Depends(require("calibration.manage")),
                       db: Session = Depends(get_db)):
    c = db.get(CalibrationItem, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="مورد کالیبراسیون یافت نشد")
    before = _out(c)
    _apply(db, c, body)
    audit.record(db, user_id=user.id, action="calibration.updated",
                 entity_type="calibration_item", entity_id=c.id,
                 old=before, new=_out(c), request=request)
    db.commit()
    return _out(c)


@router.delete("/{cid}")
def delete_calibration(cid: int, request: Request,
                       user: User = Depends(require("calibration.manage")),
                       db: Session = Depends(get_db)):
    c = db.get(CalibrationItem, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="مورد یافت نشد")
    c.status = "inactive"
    audit.record(db, user_id=user.id, action="calibration.deactivated",
                 entity_type="calibration_item", entity_id=c.id, request=request)
    db.commit()
    return {"ok": True}
