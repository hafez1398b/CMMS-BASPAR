"""User administration (Admin module §37)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db, utcnow
from ..models import Role, User
from ..rbac import get_current_user, require, user_permissions
from ..security import hash_password, validate_password_strength

router = APIRouter(prefix="/users", tags=["users"])


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9._-]+$")
    full_name: str = Field(min_length=2, max_length=128)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    email: str | None = None
    phone: str | None = None
    is_active: bool = True
    role_names: list[str] = []


def _out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
        "roles": [{"name": r.name, "title_fa": r.title_fa} for r in user.roles],
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _resolve_roles(db: Session, names: list[str]) -> list[Role]:
    roles = db.query(Role).filter(Role.name.in_(names)).all() if names else []
    found = {r.name for r in roles}
    missing = set(names) - found
    if missing:
        raise HTTPException(status_code=400, detail=f"نقش‌های نامعتبر: {', '.join(sorted(missing))}")
    return roles


@router.get("")
def list_users(admin: User = Depends(require("users.view")), db: Session = Depends(get_db)):
    users = (
        db.query(User).filter(User.deleted_at.is_(None)).order_by(User.username).all()
    )
    return {"items": [_out(u) for u in users], "total": len(users)}


@router.post("", status_code=201)
def create_user(
    body: UserIn,
    request: Request,
    admin: User = Depends(require("users.create")),
    db: Session = Depends(get_db),
):
    if not body.password:
        raise HTTPException(status_code=400, detail="رمز عبور اولیه الزامی است")
    errors = validate_password_strength(body.password)
    if errors:
        raise HTTPException(status_code=400, detail="؛ ".join(errors))
    exists = db.query(User).filter(User.username == body.username).one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="این نام کاربری قبلاً ثبت شده است")

    user = User(
        username=body.username,
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        is_active=body.is_active,
        password_hash=hash_password(body.password),
        created_by=admin.id,
    )
    user.roles = _resolve_roles(db, body.role_names)
    db.add(user)
    db.flush()
    audit.record(db, user_id=admin.id, action="user.created", entity_type="user",
                 entity_id=user.id, new=_out(user), request=request)
    db.commit()
    return _out(user)


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UserIn,
    request: Request,
    admin: User = Depends(require("users.edit")),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    before = _out(user)

    user.full_name = body.full_name
    user.email = body.email
    user.phone = body.phone
    user.is_active = body.is_active
    if body.role_names:
        user.roles = _resolve_roles(db, body.role_names)
    if body.password:
        errors = validate_password_strength(body.password)
        if errors:
            raise HTTPException(status_code=400, detail="؛ ".join(errors))
        user.password_hash = hash_password(body.password)
    user.updated_by = admin.id
    user.updated_at = utcnow()

    audit.record(db, user_id=admin.id, action="user.updated", entity_type="user",
                 entity_id=user.id, old=before, new=_out(user), request=request)
    db.commit()
    return _out(user)


@router.delete("/{user_id}")
def deactivate_user(
    user_id: int,
    request: Request,
    admin: User = Depends(require("users.delete")),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="نمی‌توانید حساب خود را حذف کنید")
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    user.is_active = False
    user.deleted_at = utcnow()  # soft delete §58
    user.updated_by = admin.id
    audit.record(db, user_id=admin.id, action="user.deleted", entity_type="user",
                 entity_id=user.id, old={"is_active": True}, new={"is_active": False},
                 request=request)
    db.commit()
    return {"ok": True}
