"""Audit log read API (§39) — Admin/Designer only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, User
from ..rbac import require

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
def list_audit_logs(
    user_id: int | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    _: User = Depends(require("audit.view")),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    total = q.count()
    items = (
        q.order_by(AuditLog.id.desc())
        .offset((page - 1) * page_size).limit(page_size).all()
    )
    return {
        "items": [
            {"id": a.id, "user_id": a.user_id,
             "user_name": a.user.username if a.user else None,
             "action": a.action, "entity_type": a.entity_type,
             "entity_id": a.entity_id, "old_values": a.old_values,
             "new_values": a.new_values, "ip": a.ip, "device": a.device,
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in items
        ],
        "total": total, "page": page, "page_size": page_size,
    }
