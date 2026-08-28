"""Work Order module (§18–§20B, §25).

Workflow states:
    created → pending_permit → ready → in_progress ⇄ paused
            → awaiting_confirmation → final_approval → closed
(with `rejected` / `cancelled` side states).

Every transition: optimistic-concurrency version bump (§35), audit row,
notification, real-time event (§59 `workorder.status_changed`).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit, storage
from ..db import get_db, naive_utcnow, to_naive, utcnow
from ..events import bus
from ..models import (
    Equipment, FileObject, MaintenanceHistory, SyncConflict, User, WorkOrder,
    WorkOrderApproval, WorkOrderCost, WorkOrderNote, WorkOrderTimeLog,
    WorkRequest,
)
from ..notify import notify_users, users_with_roles
from ..rbac import require

router = APIRouter(prefix="/work-orders", tags=["work-orders"])

STATUSES_FA = {
    "created": "ایجاد شده", "pending_permit": "در انتظار Permit/HSE",
    "ready": "آماده اجرا", "in_progress": "در حال اجرا", "paused": "متوقف موقت",
    "awaiting_confirmation": "در انتظار تأیید درخواست‌دهنده",
    "final_approval": "در انتظار تأیید نهایی مدیر فنی",
    "closed": "بسته شده", "rejected": "رد شده", "cancelled": "لغو شده",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _wo_out(wo: WorkOrder) -> dict:
    dur = compute_active_minutes(wo)
    return {
        "id": wo.id, "code": wo.code, "title": wo.title, "description": wo.description,
        "request_id": wo.request_id,
        "equipment_id": wo.equipment_id,
        "equipment_name": wo.equipment.name if wo.equipment else None,
        "equipment_code": wo.equipment.code if wo.equipment else None,
        "status": wo.status, "status_fa": STATUSES_FA.get(wo.status, wo.status),
        "work_class": wo.work_class, "execution_mode": wo.execution_mode,
        "permit_required": wo.permit_required,
        "assigned_to": wo.assigned_to,
        "assignee_name": wo.assignee.full_name if wo.assignee else None,
        "priority": wo.priority,
        "completed_at": wo.completed_at.isoformat() if wo.completed_at else None,
        "duration_minutes": dur,
        "version": wo.version,
        "approvals": [
            {"id": a.id, "step": a.step, "approver_id": a.approver_id,
             "approver_name": a.approver.full_name if a.approver else None,
             "status": a.status, "comment": a.comment,
             "decided_at": a.decided_at.isoformat() if a.decided_at else None}
            for a in wo.approvals
        ],
        "time_logs": [
            {"id": t.id, "action": t.action, "note": t.note,
             "user_name": t.user.full_name if t.user else None,
             "at": t.at.isoformat() if t.at else None}
            for t in wo.time_logs
        ],
        "created_at": wo.created_at.isoformat() if wo.created_at else None,
    }


def compute_active_minutes(wo: WorkOrder) -> int:
    """Active (unpaused) duration from the time-log timeline."""
    total = 0.0
    active_start = None
    for t in sorted(wo.time_logs, key=lambda x: x.at or utcnow()):
        at = to_naive(t.at) or naive_utcnow()
        if t.action in ("start", "resume"):
            active_start = at
        elif t.action in ("pause", "finish") and active_start is not None:
            total += max(0.0, (at - active_start).total_seconds())
            active_start = None
    return int(total // 60)


def _get_wo(db: Session, woid: int) -> WorkOrder:
    wo = db.get(WorkOrder, woid)
    if wo is None:
        raise HTTPException(status_code=404, detail="دستور کار یافت نشد")
    return wo


def _next_code(db: Session) -> str:
    n = db.query(WorkOrder).count() + 1
    while db.query(WorkOrder).filter(WorkOrder.code == f"WO-{n:05d}").one_or_none():
        n += 1
    return f"WO-{n:05d}"


def _transition(db: Session, wo: WorkOrder, new_status: str, user: User,
                request: Request, extra_new: dict | None = None) -> None:
    before = wo.status
    wo.status = new_status
    wo.version += 1
    wo.updated_at = utcnow()
    audit.record(db, user_id=user.id, action="workorder.status_changed",
                 entity_type="work_order", entity_id=wo.id,
                 old={"status": before},
                 new={"status": new_status, **(extra_new or {})}, request=request)
    bus.publish("workorder.status_changed",
                {"id": wo.id, "code": wo.code, "from": before, "to": new_status})


def create_from_request(db: Session, req: WorkRequest, user: User) -> WorkOrder:
    """Manager approved a request → generate its Work Order (§18 step 3)."""
    wo = WorkOrder(
        code=_next_code(db), title=req.title, description=req.description,
        request_id=req.id, equipment_id=req.equipment_id,
        status="created", work_class="cm",
        priority=("emergency" if req.priority == "emergency" else req.priority),
        created_by=user.id,
    )
    db.add(wo)
    db.flush()
    managers = users_with_roles(db, ["technical_manager"])
    notify_users(db, managers, kind="workorder",
                 title=f"دستور کار {wo.code} ایجاد شد", body=wo.title,
                 link=f"#/work-orders/{wo.id}")
    bus.publish("workorder.created", {"id": wo.id, "code": wo.code})
    return wo


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------

@router.get("")
def list_work_orders(
    status: str | None = None,
    assigned_to: int | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    user: User = Depends(require("workorders.view")),
    db: Session = Depends(get_db),
):
    query = db.query(WorkOrder)
    if status:
        query = query.filter(WorkOrder.status == status)
    if assigned_to:
        query = query.filter(WorkOrder.assigned_to == assigned_to)
    if q:
        like = f"%{q}%"
        query = query.filter(WorkOrder.code.ilike(like) | WorkOrder.title.ilike(like))
    total = query.count()
    items = query.order_by(WorkOrder.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_wo_out(w) for w in items], "total": total, "page": page}


@router.get("/my-assigned")
def my_assigned(user: User = Depends(require("workorders.execute")),
                db: Session = Depends(get_db)):
    """§20B offline scope: ONLY work orders already assigned to this user."""
    items = (
        db.query(WorkOrder)
        .filter(WorkOrder.assigned_to == user.id,
                WorkOrder.status.in_(["ready", "in_progress", "paused"]))
        .order_by(WorkOrder.id.desc()).all()
    )
    return {"items": [_wo_out(w) for w in items]}


@router.get("/{woid}")
def get_work_order(woid: int, _: User = Depends(require("workorders.view")),
                   db: Session = Depends(get_db)):
    wo = _get_wo(db, woid)
    out = _wo_out(wo)
    out["notes"] = [
        {"id": n.id, "text": n.text, "kind": n.kind,
         "user_name": n.user.full_name if n.user else None,
         "created_at": n.created_at.isoformat() if n.created_at else None}
        for n in db.query(WorkOrderNote)
        .filter(WorkOrderNote.work_order_id == wo.id).order_by(WorkOrderNote.id).all()
    ]
    out["files"] = [
        {"id": f.id, "name": f.original_name, "size": f.size,
         "created_at": f.created_at.isoformat() if f.created_at else None}
        for f in db.query(FileObject)
        .filter(FileObject.entity_type == "workorder", FileObject.entity_id == wo.id).all()
    ]
    out["costs"] = [
        {"id": c.id, "cost_type": c.cost_type, "amount": c.amount,
         "currency": c.currency, "description": c.description}
        for c in db.query(WorkOrderCost).filter(WorkOrderCost.work_order_id == wo.id).all()
    ]
    out["cost_total"] = sum(c["amount"] for c in out["costs"])
    return out


# ---------------------------------------------------------------------------
# create / setup
# ---------------------------------------------------------------------------

class WorkOrderIn(BaseModel):
    title: str = Field(min_length=3, max_length=190)
    description: str | None = None
    equipment_id: int | None = None
    work_class: str | None = "cm"
    priority: str = "normal"
    execution_mode: str = "internal"
    permit_required: bool = False
    assigned_to: int | None = None
    approver_ids: list[int] = []


@router.post("", status_code=201)
def create_work_order(body: WorkOrderIn, request: Request,
                      user: User = Depends(require("workorders.create")),
                      db: Session = Depends(get_db)):
    if body.equipment_id and not db.get(Equipment, body.equipment_id):
        raise HTTPException(status_code=400, detail="تجهیز وجود ندارد")
    wo = WorkOrder(
        code=_next_code(db), title=body.title, description=body.description,
        equipment_id=body.equipment_id, work_class=body.work_class,
        priority=body.priority, execution_mode=body.execution_mode,
        status="created", created_by=user.id,
    )
    db.add(wo)
    db.flush()
    audit.record(db, user_id=user.id, action="workorder.created", entity_type="work_order",
                 entity_id=wo.id, new={"code": wo.code, "title": wo.title}, request=request)
    bus.publish("workorder.created", {"id": wo.id, "code": wo.code})
    _apply_setup(db, wo, body, user, request)
    db.commit()
    return _wo_out(_get_wo(db, wo.id))


def _apply_setup(db: Session, wo: WorkOrder, body: WorkOrderIn, user: User,
                 request: Request) -> None:
    """Assign technician + permit approvers; gate on permits (§19)."""
    wo.permit_required = body.permit_required
    wo.execution_mode = body.execution_mode
    if body.assigned_to:
        tech = db.get(User, body.assigned_to)
        if not tech or not tech.is_active:
            raise HTTPException(status_code=400, detail="تکنسین انتخاب‌شده معتبر نیست")
        wo.assigned_to = body.assigned_to
        notify_users(db, [body.assigned_to], kind="workorder",
                     title=f"دستور کار {wo.code} به شما محول شد", body=wo.title,
                     link=f"#/work-orders/{wo.id}")

    if body.permit_required:
        approver_ids = body.approver_ids or []
        if not approver_ids:
            approver_ids = users_with_roles(db, ["supervisor", "technical_manager",
                                                 "maintenance_manager"])
        if not approver_ids:
            raise HTTPException(status_code=400, detail="تأییدکننده‌ای برای Permit یافت نشد")
        for aid in approver_ids:
            approver = db.get(User, aid)
            if not approver or not approver.is_active:
                continue
            if any(a.approver_id == aid for a in wo.approvals):
                continue
            db.add(WorkOrderApproval(work_order_id=wo.id, approver_id=aid, step="permit"))
        db.flush()
        if wo.status == "created":
            _transition(db, wo, "pending_permit", user, request)
        notify_users(db, approver_ids, kind="workorder",
                     title=f"نیازمند تأیید Permit: {wo.code}", body=wo.title,
                     link=f"#/work-orders/{wo.id}")
    elif wo.status == "created" and wo.assigned_to:
        _transition(db, wo, "ready", user, request)


class SetupIn(WorkOrderIn):
    version: int


@router.put("/{woid}/setup")
def setup_work_order(woid: int, body: SetupIn, request: Request,
                     user: User = Depends(require("workorders.manage")),
                     db: Session = Depends(get_db)):
    wo = _get_wo(db, woid)
    if body.version != wo.version:
        raise HTTPException(status_code=409, detail={"error": "version_conflict",
                            "message": "رکورد تغییر کرده است", "server_version": wo.version})
    if wo.status not in ("created", "pending_permit", "ready"):
        raise HTTPException(status_code=400, detail="این دستور کار دیگر قابل پیکربندی نیست")
    _apply_setup(db, wo, body, user, request)
    db.commit()
    db.refresh(wo)  # reload selectin relationships (approvals/time logs)
    return _wo_out(wo)


# ---------------------------------------------------------------------------
# Permit approvals (§19)
# ---------------------------------------------------------------------------

class ApprovalDecision(BaseModel):
    approve: bool
    comment: str | None = None
    signature: str | None = None  # §19 digital signature meta


@router.post("/approvals/{aid}/decide")
def decide_approval(aid: int, body: ApprovalDecision, request: Request,
                    user: User = Depends(require("workorders.manage")),
                    db: Session = Depends(get_db)):
    a = db.get(WorkOrderApproval, aid)
    if a is None:
        raise HTTPException(status_code=404, detail="تأییدیه یافت نشد")
    if a.approver_id != user.id:
        raise HTTPException(status_code=403, detail="این تأییدیه برای کاربر دیگری است")
    if a.status != "pending":
        raise HTTPException(status_code=400, detail="این تأییدیه قبلاً ثبت شده است")

    wo = _get_wo(db, a.work_order_id)
    a.status = "approved" if body.approve else "rejected"
    a.comment = body.comment
    a.signature = body.signature or f"signed:{user.username}"
    a.decided_at = utcnow()

    audit.record(db, user_id=user.id, action="permit.decided", entity_type="work_order",
                 entity_id=wo.id, new={"approval": a.status, "comment": body.comment},
                 request=request)

    if not body.approve:
        _transition(db, wo, "rejected", user, request, {"reason": "permit_rejected"})
        managers = users_with_roles(db, ["technical_manager"])
        notify_users(db, managers, kind="workorder",
                     title=f"Permit دستور کار {wo.code} رد شد", body=body.comment,
                     link=f"#/work-orders/{wo.id}")
        db.commit()
        return _wo_out(wo)

    pending = [x for x in wo.approvals if x.status == "pending"]
    if not pending and wo.status == "pending_permit":
        if not wo.assigned_to:
            raise HTTPException(status_code=400,
                                detail="تأییدها کامل است اما تکنسین تخصیص نیافته؛ ابتدا تخصیص دهید")
        _transition(db, wo, "ready", user, request, {"permit": "approved"})
        notify_users(db, [wo.assigned_to], kind="workorder",
                     title=f"Permit دستور کار {wo.code} کامل شد — آماده اجرا",
                     link=f"#/work-orders/{wo.id}")
    db.commit()
    return _wo_out(_get_wo(db, wo.id))


# ---------------------------------------------------------------------------
# Technician execution (§20)
# ---------------------------------------------------------------------------

class ExecutionIn(BaseModel):
    action: str  # start | pause | resume | finish
    note: str | None = None
    base_version: int | None = None
    local_id: str | None = None
    device_at: str | None = None  # ISO, from device clock (§20B)


def _parse_device_at(s: str | None):
    if not s:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.post("/{woid}/execution")
def execution_action(woid: int, body: ExecutionIn, request: Request,
                     user: User = Depends(require("workorders.execute")),
                     db: Session = Depends(get_db)):
    wo = _get_wo(db, woid)
    if wo.assigned_to and wo.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="این دستور کار به تکنسین دیگری محول شده است")
    if body.base_version is not None and body.base_version != wo.version:
        raise HTTPException(status_code=409, detail={
            "error": "version_conflict", "server_version": wo.version,
            "message": "قبل از ادامه، نسخه جدید را از سرور دریافت کنید"})

    act = body.action
    if act == "start" and wo.status not in ("ready",):
        raise HTTPException(status_code=400, detail="دستور کار آماده اجرا نیست (Permit/تخصیص را بررسی کنید)")
    if act == "pause" and wo.status != "in_progress":
        raise HTTPException(status_code=400, detail="دستور کار در حال اجرا نیست")
    if act == "resume" and wo.status != "paused":
        raise HTTPException(status_code=400, detail="دستور کار متوقف موقت نیست")
    if act == "finish" and wo.status not in ("in_progress", "paused"):
        raise HTTPException(status_code=400, detail="دستور کار در حال اجرا نیست")
    if act not in ("start", "pause", "resume", "finish"):
        raise HTTPException(status_code=400, detail="کنش نامعتبر است")

    device_at = _parse_device_at(body.device_at)
    # offline dedupe (§20B): same local_id must never apply twice
    if body.local_id:
        dup = db.query(WorkOrderTimeLog).filter(
            WorkOrderTimeLog.work_order_id == wo.id,
            WorkOrderTimeLog.local_id == body.local_id).one_or_none()
        if dup:
            return _wo_out(wo)
    db.add(WorkOrderTimeLog(work_order_id=wo.id, user_id=user.id, action=act,
                            note=body.note, local_id=body.local_id,
                            at=device_at or utcnow()))

    if act == "start":
        _transition(db, wo, "in_progress", user, request)
    elif act == "pause":
        _transition(db, wo, "paused", user, request)
    elif act == "resume":
        _transition(db, wo, "in_progress", user, request)
    elif act == "finish":
        wo.completed_at = utcnow()
        _transition(db, wo, "awaiting_confirmation", user, request,
                    {"duration_minutes": compute_active_minutes(wo)})
        req = db.get(WorkRequest, wo.request_id) if wo.request_id else None
        if req and req.requested_by:
            notify_users(db, [req.requested_by], kind="workorder",
                         title=f"اجرای {wo.code} تمام شد — تأیید کنید", body=wo.title,
                         link=f"#/work-orders/{wo.id}")
        else:
            notify_users(db, users_with_roles(db, ["technical_manager"]), kind="workorder",
                         title=f"اجرای {wo.code} تمام شد", link=f"#/work-orders/{wo.id}")

    audit.record(db, user_id=user.id, action=f"workorder.execution.{act}",
                 entity_type="work_order", entity_id=wo.id, request=request)
    db.commit()
    return _wo_out(_get_wo(db, woid))


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    kind: str = "text"  # text | voice
    base_version: int | None = None
    local_id: str | None = None
    device_at: str | None = None


@router.post("/{woid}/notes", status_code=201)
def add_note(woid: int, body: NoteIn, request: Request,
             user: User = Depends(require("workorders.execute")),
             db: Session = Depends(get_db)):
    wo = _get_wo(db, woid)
    if body.base_version is not None and body.base_version != wo.version:
        raise HTTPException(status_code=409, detail={"error": "version_conflict",
                            "server_version": wo.version})
    if body.local_id:
        dup = db.query(WorkOrderNote).filter(
            WorkOrderNote.work_order_id == wo.id,
            WorkOrderNote.local_id == body.local_id).one_or_none()
        if dup:
            return {"id": dup.id, "duplicate": True}
    n = WorkOrderNote(
        work_order_id=wo.id, user_id=user.id, text=body.text, kind=body.kind,
        local_id=body.local_id, device_at=_parse_device_at(body.device_at),
    )
    db.add(n)
    db.flush()
    audit.record(db, user_id=user.id, action="workorder.note_added",
                 entity_type="work_order", entity_id=wo.id, request=request)
    db.commit()
    return {"id": n.id}


@router.post("/{woid}/files", status_code=201)
async def upload_wo_file(woid: int, request: Request,
                         file: UploadFile = File(...),
                         user: User = Depends(require("files.upload")),
                         db: Session = Depends(get_db)):
    wo = _get_wo(db, woid)
    meta = await storage.save_upload(file, entity_type="workorder", entity_id=wo.id)
    f = FileObject(entity_type="workorder", entity_id=wo.id, created_by=user.id, **meta)
    db.add(f)
    db.flush()
    audit.record(db, user_id=user.id, action="workorder.file_uploaded",
                 entity_type="work_order", entity_id=wo.id,
                 new={"file": f.original_name}, request=request)
    db.commit()
    return {"id": f.id, "name": f.original_name, "size": f.size}


# ---------------------------------------------------------------------------
# Confirmation & final approval (§18 steps 8–10)
# ---------------------------------------------------------------------------

class ConfirmIn(BaseModel):
    approve: bool
    note: str | None = None
    version: int


@router.post("/{woid}/confirm")
def requester_confirm(woid: int, body: ConfirmIn, request: Request,
                      user: User = Depends(require("workorders.confirm")),
                      db: Session = Depends(get_db)):
    wo = _get_wo(db, woid)
    if wo.status != "awaiting_confirmation":
        raise HTTPException(status_code=400, detail="در انتظار تأیید درخواست‌دهنده نیست")
    if body.version != wo.version:
        raise HTTPException(status_code=409, detail={"error": "version_conflict",
                            "server_version": wo.version})
    if body.approve:
        _transition(db, wo, "final_approval", user, request)
        notify_users(db, users_with_roles(db, ["technical_manager"]), kind="workorder",
                     title=f"{wo.code} تأیید درخواست‌دهنده شد — تأیید نهایی",
                     link=f"#/work-orders/{wo.id}")
    else:
        wo.completed_at = None
        _transition(db, wo, "in_progress", user, request,
                    {"requester_rejected": True, "note": body.note})
        if wo.assigned_to:
            notify_users(db, [wo.assigned_to], kind="workorder",
                         title=f"درخواست‌دهنده نتیجه {wo.code} را نپذیرفت",
                         body=body.note, link=f"#/work-orders/{wo.id}")
    db.commit()
    return _wo_out(_get_wo(db, woid))


@router.post("/{woid}/final-approve")
def final_approve(woid: int, body: ConfirmIn, request: Request,
                  user: User = Depends(require("workorders.manage")),
                  db: Session = Depends(get_db)):
    wo = _get_wo(db, woid)
    if wo.status != "final_approval":
        raise HTTPException(status_code=400, detail="در وضعیت تأیید نهایی نیست")
    if body.version != wo.version:
        raise HTTPException(status_code=409, detail={"error": "version_conflict",
                            "server_version": wo.version})
    _transition(db, wo, "closed", user, request)

    # §16 — completed work becomes Maintenance History (real records only).
    first_start = next((t.at for t in sorted(wo.time_logs, key=lambda x: x.at or utcnow())
                        if t.action == "start"), None)
    db.add(MaintenanceHistory(
        equipment_id=wo.equipment_id, work_order_id=wo.id,
        work_type=wo.work_class or "cm", title=wo.title, description=wo.description,
        technician_id=wo.assigned_to, started_at=first_start,
        finished_at=wo.completed_at, duration_minutes=compute_active_minutes(wo),
    ))
    req = db.get(WorkRequest, wo.request_id) if wo.request_id else None
    targets = [wo.assigned_to or user.id]
    if req and req.requested_by:
        targets.append(req.requested_by)
    notify_users(db, targets, kind="workorder",
                 title=f"دستور کار {wo.code} بسته شد و در سوابق نت ثبت شد",
                 link=f"#/work-orders/{wo.id}")
    bus.publish("pm.completed", {"work_order_id": wo.id, "equipment_id": wo.equipment_id})
    db.commit()
    return _wo_out(_get_wo(db, woid))


# ---------------------------------------------------------------------------
# Costs (§25)
# ---------------------------------------------------------------------------

class CostIn(BaseModel):
    cost_type: str
    amount: float = Field(ge=0)
    currency: str = "IRR"
    description: str | None = None


@router.post("/{woid}/costs", status_code=201)
def add_cost(woid: int, body: CostIn, request: Request,
             user: User = Depends(require("workorders.manage")),
             db: Session = Depends(get_db)):
    wo = _get_wo(db, woid)
    c = WorkOrderCost(work_order_id=wo.id, created_by=user.id, **body.model_dump())
    db.add(c)
    db.flush()
    audit.record(db, user_id=user.id, action="workorder.cost_added",
                 entity_type="work_order", entity_id=wo.id,
                 new=body.model_dump(), request=request)
    db.commit()
    return {"id": c.id}


# ---------------------------------------------------------------------------
# Offline sync (§20B) — FIFO-safe batch endpoint + conflict handling (§35)
# ---------------------------------------------------------------------------

class OfflineRecord(BaseModel):
    local_id: str
    type: str  # time_log | note
    action: str | None = None
    text: str | None = None
    kind: str = "text"
    device_at: str | None = None


class OfflineSyncIn(BaseModel):
    base_version: int
    records: list[OfflineRecord] = []


@router.post("/{woid}/offline-sync")
def offline_sync(woid: int, body: OfflineSyncIn, request: Request,
                 user: User = Depends(require("workorders.execute")),
                 db: Session = Depends(get_db)):
    wo = _get_wo(db, woid)
    if wo.assigned_to and wo.assigned_to != user.id:
        raise HTTPException(status_code=403, detail="این دستور کار به شما محول نشده است")

    # Version mismatch → silent overwrite forbidden (§20B/§35): keep both,
    # leave server record untouched, escalate to managers.
    if body.base_version != wo.version:
        conflict = SyncConflict(
            work_order_id=wo.id, user_id=user.id,
            base_version=body.base_version, server_version=wo.version,
            payload={"records": [r.model_dump() for r in body.records]},
        )
        db.add(conflict)
        db.flush()
        notify_users(db, users_with_roles(db, ["technical_manager", "supervisor"]),
                     kind="system", title=f"تعارض همگام‌سازی آفلاین در {wo.code}",
                     body="رکوردهای دستگاه بدون تغییر سرور نگهداری شدند؛ نیازمند حل تعارض",
                     link=f"#/work-orders/{wo.id}")
        audit.record(db, user_id=user.id, action="workorder.sync_conflict",
                     entity_type="work_order", entity_id=wo.id,
                     new={"base_version": body.base_version,
                          "server_version": wo.version}, request=request)
        db.commit()
        raise HTTPException(status_code=409, detail={
            "error": "offline_conflict", "conflict_id": conflict.id,
            "server_version": wo.version,
            "message": "رکورد سرور تغییر کرده است؛ هر دو نسخه نگهداری شد و به مدیر اعلام شد"})

    applied = skipped = 0
    for rec in body.records:
        device_at = _parse_device_at(rec.device_at)
        if rec.type == "time_log" and rec.action:
            dup = db.query(WorkOrderTimeLog).filter(
                WorkOrderTimeLog.work_order_id == wo.id,
                WorkOrderTimeLog.local_id == rec.local_id).one_or_none()
            if dup:
                skipped += 1
                continue
            db.add(WorkOrderTimeLog(work_order_id=wo.id, user_id=user.id,
                                    action=rec.action, local_id=rec.local_id,
                                    at=device_at or utcnow()))
            db.flush()  # make dedupe visible within the same batch (FIFO)
            applied += 1
        elif rec.type == "note" and rec.text:
            dup = db.query(WorkOrderNote).filter(
                WorkOrderNote.work_order_id == wo.id,
                WorkOrderNote.local_id == rec.local_id).one_or_none()
            if dup:
                skipped += 1
                continue
            db.add(WorkOrderNote(work_order_id=wo.id, user_id=user.id, text=rec.text,
                                 kind=rec.kind, local_id=rec.local_id,
                                 device_at=device_at))
            db.flush()
            applied += 1
    if applied:
        wo.version += 1
        wo.offline_sync_status = "synced"
        wo.updated_at = utcnow()
    audit.record(db, user_id=user.id, action="workorder.offline_synced",
                 entity_type="work_order", entity_id=wo.id,
                 new={"applied": applied, "skipped": skipped}, request=request)
    db.commit()
    return {"applied": applied, "skipped": skipped, "server_version": wo.version}


# ---------------------------------------------------------------------------
# Conflicts (manager resolution)
# ---------------------------------------------------------------------------

@router.get("/conflicts/list")
def list_conflicts(status: str = "open",
                   _: User = Depends(require("workorders.manage")),
                   db: Session = Depends(get_db)):
    q = db.query(SyncConflict)
    if status:
        q = q.filter(SyncConflict.status == status)
    items = q.order_by(SyncConflict.id.desc()).all()
    return {"items": [
        {"id": c.id, "work_order_id": c.work_order_id, "user_id": c.user_id,
         "base_version": c.base_version, "server_version": c.server_version,
         "payload": c.payload, "status": c.status, "resolution": c.resolution,
         "created_at": c.created_at.isoformat() if c.created_at else None}
        for c in items]}


class ResolveConflictIn(BaseModel):
    resolution: str = Field(min_length=3, max_length=2000)
    apply_device_records: bool = False


@router.post("/conflicts/{cid}/resolve")
def resolve_conflict(cid: int, body: ResolveConflictIn, request: Request,
                     user: User = Depends(require("workorders.manage")),
                     db: Session = Depends(get_db)):
    c = db.get(SyncConflict, cid)
    if c is None or c.status != "open":
        raise HTTPException(status_code=404, detail="تعارض یافت نشد")
    if body.apply_device_records and c.payload:
        wo = _get_wo(db, c.work_order_id)
        for rec in c.payload.get("records", []):
            device_at = _parse_device_at(rec.get("device_at"))
            if rec.get("type") == "time_log" and rec.get("action"):
                dup = db.query(WorkOrderTimeLog).filter(
                    WorkOrderTimeLog.work_order_id == wo.id,
                    WorkOrderTimeLog.local_id == rec.get("local_id")).one_or_none()
                if not dup:
                    db.add(WorkOrderTimeLog(work_order_id=wo.id, user_id=c.user_id,
                                            action=rec["action"], local_id=rec.get("local_id"),
                                            at=device_at or utcnow()))
            elif rec.get("type") == "note" and rec.get("text"):
                dup = db.query(WorkOrderNote).filter(
                    WorkOrderNote.work_order_id == wo.id,
                    WorkOrderNote.local_id == rec.get("local_id")).one_or_none()
                if not dup:
                    db.add(WorkOrderNote(work_order_id=wo.id, user_id=c.user_id,
                                         text=rec["text"], kind=rec.get("kind", "text"),
                                         local_id=rec.get("local_id"), device_at=device_at))
        wo.version += 1
    c.status = "resolved"
    c.resolution = body.resolution
    c.resolved_by = user.id
    c.resolved_at = utcnow()
    audit.record(db, user_id=user.id, action="workorder.conflict_resolved",
                 entity_type="sync_conflict", entity_id=c.id,
                 new={"apply_device_records": body.apply_device_records}, request=request)
    db.commit()
    return {"ok": True}
