"""Notification engine (§31) — in-app + real-time push.

Never loses a message (§32B fallback): delivery is a DB row first, the
SSE push is best-effort on top.  External messenger adapters (Phase 2)
will hook into the same function.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .events import bus
from .models import Notification, Role, User


def notify_users(
    db: Session,
    user_ids: list[int],
    *,
    kind: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> int:
    created = 0
    for uid in sorted(set(user_ids)):
        db.add(Notification(user_id=uid, kind=kind, title=title, body=body, link=link))
        created += 1
    db.flush()
    for uid in sorted(set(user_ids)):
        bus.publish("notification.created", {
            "user_id": uid, "kind": kind, "title": title, "link": link,
        })
    return created


def users_with_roles(db: Session, role_names: list[str]) -> list[int]:
    roles = db.query(Role).filter(Role.name.in_(role_names)).all()
    ids: list[int] = []
    for r in roles:
        ids.extend(u.id for u in r.users if u.is_active and u.deleted_at is None)
    return sorted(set(ids))
