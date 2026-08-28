"""Central audit trail (Master-prompt §39).

Every sensitive mutation records: user, action, entity, old/new values,
timestamp, client IP and device (user-agent).  Audit rows are append-only.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog


def record(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    ip = None
    device = None
    if request is not None:
        ip = request.client.host if request.client else None
        device = (request.headers.get("user-agent") or "")[:255]
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            old_values=old or {},
            new_values=new or {},
            ip=ip,
            device=device,
        )
    )
    db.flush()
