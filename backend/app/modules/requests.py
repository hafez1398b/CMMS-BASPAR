"""Work Request module (§17, §18 step 1–2).

Flow: requester creates → supervisor approval → technical-manager
approval → conversion into a Work Order.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db, utcnow
from ..events import bus
from ..models import Equipment, User, WorkRequest
from ..notify import notify_users, users_with_roles
from ..rbac import require

router = APIRouter(prefix="/requests", tags=["requests"])

REQUEST_TYPES = {"repair", "service", "modification", "inspection",
                 "improvement", "emergency", "other"}
PRIORITIES = {"low", "normal", "high", "emergency"}

# role fallback chain for the two approval steps (§18)
SUPERVISOR_ROLES = ["supervisor", "maintenance_manager"]
MANAGER_ROLES = ["technical_manager"]


class RequestIn(BaseModel):
    title: str = Field(min_length=3, max_length=190)
    description: str | None = None
    request_type: str = "repair"
    priority: str = "normal"
    equipment_id: int | None = None


def _out(r: WorkRequest) -> dict:
    return {
        "id": r.id, "title": r.title, "description": r.description,
        "request_type": r.request_type, "priority": r.priority,
        "equipment_id": r.equipment_id,
        "equipment_name": r.equipment.name if r.equipment else None,
        "equipment_code": r.equipment.code if r.equipment else None,
        "status": r.status, "decision_note": r.decision_note,
        "requested_by": r.requested_by,
        "requester_name": r.requester.full_name if r.requester else None,
        "version": r.version,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _get(db: Session, rid: int) -> WorkRequest:
    r = db.get(WorkRequest, rid)
    if r is None:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")
    return r


@router.get("")
def list_requests(
    status: str | None = None,
    mine: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    user: User = Depends(require("requests.view")),
    db: Session = Depends(get_db),
):
    q = db.query(WorkRequest)
    if status:
        q = q.filter(WorkRequest.status == status)
    if mine:
        q = q.filter(WorkRequest.requested_by == user.id)
    total = q.count()
    items = q.order_by(WorkRequest.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_out(r) for r in items], "total": total, "page": page}


@router.post("", status_code=201)
def create_request(body: RequestIn, request: Request,
                   user: User = Depends(require("requests.create")),
                   db: Session = Depends(get_db)):
    if body.request_type not in REQUEST_TYPES:
        raise HTTPException(status_code=400, detail="نوع درخواست نامعتبر است")
    if body.priority not in PRIORITIES:
        raise HTTPException(status_code=400, detail="اولویت نامعتبر است")
    if body.equipment_id and not db.get(Equipment, body.equipment_id):
        raise HTTPException(status_code=400, detail="تجهیز انتخاب‌شده وجود ندارد")

    r = WorkRequest(
        **body.model_dump(), requested_by=user.id, status="pending_supervisor",
    )
    db.add(r)
    db.flush()

    supervisors = users_with_roles(db, SUPERVISOR_ROLES) or users_with_roles(db, MANAGER_ROLES)
    notify_users(db, supervisors, kind="request",
                 title=f"درخواست جدید: {r.title}",
                 body=f"نوع: {r.request_type} · نیازمند بررسی سرپرست",
                 link=f"#/requests/{r.id}")

    audit.record(db, user_id=user.id, action="request.created", entity_type="work_request",
                 entity_id=r.id, new=_out(r), request=request)
    db.commit()
    bus.publish("request.created", {"id": r.id, "title": r.title})
    return _out(r)


class DecisionIn(BaseModel):
    approve: bool
    note: str | None = None


@router.post("/{rid}/supervisor-decision")
def supervisor_decision(rid: int, body: DecisionIn, request: Request,
                        user: User = Depends(require("requests.approve")),
                        db: Session = Depends(get_db)):
    """§18 step 2 — Requester Supervisor."""
    r = _get(db, rid)
    if r.status != "pending_supervisor":
        raise HTTPException(status_code=400, detail="این درخواست در وضعیت بررسی سرپرست نیست")
    before = r.status
    r.decision_note = body.note
    r.version += 1
    r.updated_at = utcnow()

    if body.approve:
        r.status = "pending_manager"
        managers = users_with_roles(db, MANAGER_ROLES)
        notify_users(db, managers, kind="request",
                     title=f"درخواست تأیید سرپرست شد: {r.title}",
                     body="نیازمند تصمیم مدیر فنی", link=f"#/requests/{r.id}")
        bus.publish("request.approved", {"id": r.id, "step": "supervisor"})
    else:
        r.status = "rejected"
        if r.requested_by:
            notify_users(db, [r.requested_by], kind="request",
                         title=f"درخواست شما رد شد: {r.title}", body=body.note,
                         link=f"#/requests/{r.id}")
        bus.publish("request.rejected", {"id": r.id, "step": "supervisor"})

    audit.record(db, user_id=user.id, action=f"request.supervisor_{'approved' if body.approve else 'rejected'}",
                 entity_type="work_request", entity_id=r.id,
                 old={"status": before}, new={"status": r.status}, request=request)
    db.commit()
    return _out(r)


@router.post("/{rid}/manager-decision")
def manager_decision(rid: int, body: DecisionIn, request: Request,
                     user: User = Depends(require("requests.approve")),
                     db: Session = Depends(get_db)):
    """§18 step 3 — Technical Manager; approval converts to Work Order."""
    from .workorders import create_from_request

    r = _get(db, rid)
    if r.status != "pending_manager":
        raise HTTPException(status_code=400, detail="این درخواست در وضعیت بررسی مدیر فنی نیست")
    before = r.status
    r.decision_note = body.note
    r.version += 1
    r.updated_at = utcnow()

    if body.approve:
        wo = create_from_request(db, r, user)
        r.status = "converted"
        if r.requested_by:
            notify_users(db, [r.requested_by], kind="workorder",
                         title=f"برای درخواست شما دستور کار {wo.code} ایجاد شد",
                         link=f"#/work-orders/{wo.id}")
        bus.publish("request.approved", {"id": r.id, "step": "manager", "work_order_id": wo.id})
        audit.record(db, user_id=user.id, action="request.manager_approved",
                     entity_type="work_request", entity_id=r.id,
                     old={"status": before}, new={"status": r.status, "work_order": wo.code},
                     request=request)
        db.commit()
        return {**_out(r), "work_order_id": wo.id, "work_order_code": wo.code}
    else:
        r.status = "rejected"
        if r.requested_by:
            notify_users(db, [r.requested_by], kind="request",
                         title=f"درخواست شما رد شد: {r.title}", body=body.note,
                         link=f"#/requests/{r.id}")
        bus.publish("request.rejected", {"id": r.id, "step": "manager"})
        audit.record(db, user_id=user.id, action="request.manager_rejected",
                     entity_type="work_request", entity_id=r.id,
                     old={"status": before}, new={"status": r.status}, request=request)
        db.commit()
        return _out(r)
