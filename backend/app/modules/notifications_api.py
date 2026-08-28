"""Notification Center API (§31) — personal, real-time."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db, utcnow
from ..models import Notification, User
from ..rbac import require

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(unread_only: bool = False,
                       page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=100),
                       user: User = Depends(require("notifications.view")),
                       db: Session = Depends(get_db)):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))
    total = q.count()
    items = q.order_by(Notification.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
             "link": n.link, "is_read": n.is_read,
             "created_at": n.created_at.isoformat() if n.created_at else None}
            for n in items
        ],
        "total": total,
        "unread": db.query(Notification).filter(
            Notification.user_id == user.id, Notification.is_read.is_(False)).count(),
    }


@router.get("/unread-count")
def unread_count(user: User = Depends(require("notifications.view")),
                 db: Session = Depends(get_db)):
    n = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read.is_(False)).count()
    return {"unread": n}


@router.post("/{nid}/read")
def mark_read(nid: int, user: User = Depends(require("notifications.view")),
              db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if n is None or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="اعلان یافت نشد")
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(user: User = Depends(require("notifications.view")),
                  db: Session = Depends(get_db)):
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.is_read.is_(False))
        .update({"is_read": True})
    )
    db.commit()
    return {"ok": True, "updated": updated}
