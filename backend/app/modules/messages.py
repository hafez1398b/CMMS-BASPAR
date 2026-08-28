"""Internal consultation / in-app messenger (§32, §32B core).

Fully independent of any external service.  External messengers (Phase 2
optional) may ONLY add one-way notification channels through the provider
interface — never replace this core (§32B).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db, utcnow
from ..events import bus
from ..models import Conversation, Message, Role, User
from ..notify import notify_users
from ..rbac import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])


def _require(user: User) -> User:
    perms = {p.code for r in user.roles for p in r.permissions}
    if not (any(r.name == "admin" for r in user.roles) or "messages.view" in perms):
        raise HTTPException(status_code=403, detail="دسترسی پیام‌رسانی ندارید")
    return user


class StartIn(BaseModel):
    with_user_id: int | None = None
    with_role: str | None = None  # e.g. "technical_manager" for consultation
    subject: str | None = None


@router.get("/contacts")
def contacts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require(user)
    users = (
        db.query(User)
        .filter(User.is_active.is_(True), User.deleted_at.is_(None), User.id != user.id)
        .order_by(User.full_name).all()
    )
    return {"items": [{"id": u.id, "full_name": u.full_name, "username": u.username,
                       "roles": [r.title_fa for r in u.roles]} for u in users]}


@router.get("/conversations")
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require(user)
    convs = (
        db.query(Conversation)
        .filter(or_(Conversation.user_a == user.id, Conversation.user_b == user.id))
        .order_by(Conversation.updated_at.desc()).all()
    )
    items = []
    for c in convs:
        other = c.a if c.user_b == user.id else c.b
        last = (
            db.query(Message).filter(Message.conversation_id == c.id)
            .order_by(Message.id.desc()).first()
        )
        unread = (
            db.query(Message)
            .filter(Message.conversation_id == c.id, Message.is_read.is_(False),
                    Message.sender_id != user.id)
            .count()
        )
        items.append({
            "id": c.id, "subject": c.subject,
            "other_id": other.id if other else None,
            "other_name": other.full_name if other else "—",
            "last_text": last.text[:80] if last else None,
            "last_at": last.created_at.isoformat() if last else None,
            "unread": unread,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        })
    return {"items": items}


@router.post("/conversations", status_code=201)
def start_conversation(body: StartIn, request: Request,
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _require(user)
    target_id = body.with_user_id
    if not target_id and body.with_role:
        role = db.query(Role).filter(Role.name == body.with_role).one_or_none()
        if role is None:
            raise HTTPException(status_code=400, detail="نقش نامعتبر است")
        candidates = [u for u in role.users if u.is_active and u.deleted_at is None and u.id != user.id]
        if not candidates:
            raise HTTPException(status_code=404, detail="کاربری با این نقش یافت نشد")
        target_id = candidates[0].id
    if not target_id or target_id == user.id:
        raise HTTPException(status_code=400, detail="مخاطب معتبر نیست")
    target = db.get(User, target_id)
    if target is None or not target.is_active:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")

    pair = sorted((user.id, target_id))
    conv = (
        db.query(Conversation)
        .filter(Conversation.user_a == pair[0], Conversation.user_b == pair[1])
        .one_or_none()
    )
    if conv is None:
        conv = Conversation(user_a=pair[0], user_b=pair[1], subject=body.subject)
        db.add(conv)
        db.flush()
        audit.record(db, user_id=user.id, action="consultation.started",
                     entity_type="conversation", entity_id=conv.id,
                     new={"with": target.username, "subject": body.subject}, request=request)
        notify_users(db, [target_id], kind="system",
                     title=f"درخواست مشاوره/گفتگو از {user.full_name}",
                     body=body.subject, link="#/consultation")
    db.commit()
    return {"id": conv.id}


@router.get("/conversations/{cid}")
def conversation_detail(cid: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    _require(user)
    c = db.get(Conversation, cid)
    if c is None or user.id not in (c.user_a, c.user_b):
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد")
    # reading marks the other party's messages as read
    db.query(Message).filter(Message.conversation_id == cid,
                             Message.sender_id != user.id,
                             Message.is_read.is_(False)).update({"is_read": True})
    db.commit()
    msgs = db.query(Message).filter(Message.conversation_id == cid).order_by(Message.id).all()
    other = c.a if c.user_b == user.id else c.b
    return {
        "id": c.id, "subject": c.subject,
        "other_name": other.full_name if other else "—",
        "messages": [{"id": m.id, "sender_id": m.sender_id, "text": m.text,
                      "mine": m.sender_id == user.id,
                      "created_at": m.created_at.isoformat() if m.created_at else None}
                     for m in msgs],
    }


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/conversations/{cid}/messages", status_code=201)
def send_message(cid: int, body: MessageIn, request: Request,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _require(user)
    c = db.get(Conversation, cid)
    if c is None or user.id not in (c.user_a, c.user_b):
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد")
    m = Message(conversation_id=cid, sender_id=user.id, text=body.text)
    db.add(m)
    c.updated_at = utcnow()
    db.flush()
    other_id = c.user_b if c.user_a == user.id else c.user_a
    notify_users(db, [other_id], kind="system",
                 title=f"پیام جدید از {user.full_name}", body=body.text[:60],
                 link="#/consultation")
    db.commit()
    bus.publish("message.created", {"conversation_id": cid, "to": other_id})
    return {"id": m.id, "created_at": m.created_at.isoformat()}
