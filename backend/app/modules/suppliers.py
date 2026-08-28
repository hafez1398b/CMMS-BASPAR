"""Suppliers (تأمین‌کنندگان) — بخش ۴.۵ سند بارگذاری نهایی.

جدول 40 رکوردی supplier در اکسس. قطعات یدکی به تأمین‌کننده لینک می‌شوند.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Part, Supplier, User
from ..rbac import require

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


class SupplierIn(BaseModel):
    name: str = Field(min_length=2, max_length=190)
    contact: str | None = None
    phone: str | None = Field(default=None, max_length=64)
    notes: str | None = None
    is_active: bool = True


def _out(s: Supplier) -> dict:
    return {
        "id": s.id, "name": s.name, "contact": s.contact, "phone": s.phone,
        "notes": s.notes, "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
def list_suppliers(q: str | None = None,
                   _: User = Depends(require("parts.view")),
                   db: Session = Depends(get_db)):
    query = db.query(Supplier)
    if q:
        like = f"%{q}%"
        query = query.filter(Supplier.name.ilike(like) | Supplier.contact.ilike(like))
    items = query.order_by(Supplier.name).all()
    return {"items": [_out(s) for s in items], "total": len(items)}


@router.post("", status_code=201)
def create_supplier(body: SupplierIn, request: Request,
                    user: User = Depends(require("parts.manage")),
                    db: Session = Depends(get_db)):
    dup = db.query(Supplier).filter(Supplier.name == body.name.strip()).one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="تأمین‌کننده‌ای با این نام وجود دارد")
    s = Supplier(name=body.name.strip(), contact=body.contact, phone=body.phone,
                 notes=body.notes, is_active=body.is_active, created_by=user.id)
    db.add(s)
    audit.record(db, user_id=user.id, action="supplier.created",
                 entity_type="supplier", entity_id=None,
                 new={"name": s.name}, request=request)
    db.commit(); db.refresh(s)
    return _out(s)


@router.put("/{sid}")
def update_supplier(sid: int, body: SupplierIn, request: Request,
                    user: User = Depends(require("parts.manage")),
                    db: Session = Depends(get_db)):
    s = db.get(Supplier, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="تأمین‌کننده یافت نشد")
    dup = db.query(Supplier).filter(Supplier.name == body.name.strip(),
                                    Supplier.id != sid).one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="تأمین‌کننده‌ای با این نام وجود دارد")
    before = _out(s)
    s.name = body.name.strip(); s.contact = body.contact; s.phone = body.phone
    s.notes = body.notes; s.is_active = body.is_active
    audit.record(db, user_id=user.id, action="supplier.updated",
                 entity_type="supplier", entity_id=s.id,
                 old=before, new=_out(s), request=request)
    db.commit(); db.refresh(s)
    return _out(s)


@router.delete("/{sid}")
def delete_supplier(sid: int, request: Request,
                    user: User = Depends(require("parts.manage")),
                    db: Session = Depends(get_db)):
    s = db.get(Supplier, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="تأمین‌کننده یافت نشد")
    linked = db.query(Part).filter(Part.supplier_id == sid).count()
    if linked:
        raise HTTPException(status_code=400,
                            detail=f"{linked} قطعه به این تأمین‌کننده مرتبط است؛ ابتدا آن‌ها را جدا کنید")
    db.delete(s)
    audit.record(db, user_id=user.id, action="supplier.deleted",
                 entity_type="supplier", entity_id=sid,
                 old={"name": s.name}, request=request)
    db.commit()
    return {"ok": True}
