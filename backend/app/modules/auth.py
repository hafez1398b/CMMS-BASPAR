"""Authentication API: login, me, logout, change password (Phase 0)."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import get_db
from ..events import bus
from ..models import User
from ..rbac import get_current_user, user_permissions
from ..security import (
    create_access_token,
    hash_password,
    validate_password_strength,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory login throttle (per IP) — swap for Redis in multi-server mode.
_attempts: dict[str, deque] = defaultdict(deque)


def _rate_limit(key: str) -> None:
    s = get_settings()
    now = time.monotonic()
    q = _attempts[key]
    while q and now - q[0] > s.login_rate_window_seconds:
        q.popleft()
    if len(q) >= s.login_rate_limit:
        raise HTTPException(status_code=429, detail="تعداد تلاش‌های ورود بیش از حد مجاز است؛ کمی بعد دوباره تلاش کنید")
    q.append(now)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "roles": [{"name": r.name, "title_fa": r.title_fa} for r in user.roles],
    }


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    """Accepts JSON *or* form-encoded bodies — some reverse proxies
    rewrite POST payloads; auth must not break because of that."""
    ctype = (request.headers.get("content-type") or "").lower()
    data: dict = {}
    if "application/json" in ctype:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if not data:
        try:
            form = await request.form()
            data = {k: v for k, v in form.items()}
        except Exception:
            data = {}
    try:
        body = LoginIn(username=str(data.get("username") or "").strip(),
                       password=str(data.get("password") or ""))
    except Exception:
        raise HTTPException(status_code=422, detail="بدنه درخواست ورود نامعتبر است")

    ip = request.client.host if request.client else "unknown"
    _rate_limit(ip)

    user = (
        db.query(User)
        .filter(User.username == body.username.strip().lower())
        .one_or_none()
    )
    if (
        user is None
        or user.deleted_at is not None
        or not user.is_active
        or not verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است")

    roles = [r.name for r in user.roles]
    token, jti = create_access_token(user.id, user.username, roles)
    audit.record(
        db, user_id=user.id, action="auth.login", entity_type="user",
        entity_id=user.id, new={"jti": jti}, request=request,
    )
    db.commit()

    from fastapi.responses import JSONResponse
    resp = JSONResponse({
        "access_token": token,
        "token_type": "bearer",
        "user": _user_out(user),
        "permissions": sorted(user_permissions(user)),
    })
    # Cookie fallback for proxies that drop Authorization.  SameSite=None
    # so cross-site iframe previews can keep it; the query-token fallback in
    # the SPA is the extra safety net where third-party cookies are blocked.
    resp.set_cookie(
        "cmms_token", token,
        max_age=get_settings().access_token_ttl_minutes * 60,
        httponly=True, samesite="none", secure=True, path="/",
    )
    return resp


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": _user_out(user), "permissions": sorted(user_permissions(user))}


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db),
           request: Request = None):
    # JWT is stateless; the client discards it.  We audit the action.
    audit.record(db, user_id=user.id, action="auth.logout", entity_type="user",
                 entity_id=user.id, request=request)
    db.commit()
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("cmms_token", path="/")
    return resp


@router.post("/change-password")
def change_password(
    body: ChangePasswordIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="رمز عبور فعلی اشتباه است")
    errors = validate_password_strength(body.new_password)
    if errors:
        raise HTTPException(status_code=400, detail="؛ ".join(errors))
    user.password_hash = hash_password(body.new_password)
    user.updated_by = user.id
    audit.record(db, user_id=user.id, action="auth.password_changed",
                 entity_type="user", entity_id=user.id, request=request)
    db.commit()
    return {"ok": True}
