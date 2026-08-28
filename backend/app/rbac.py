"""RBAC — permissions registry, JWT principal resolution, guards.

Permission codes are `module.action` (Master-prompt §36):
actions ⊆ {view, create, edit, delete, approve, export, manage}.
The Admin/Designer role implicitly holds every permission (§38).
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import AuthError, decode_access_token

# (module, action, Persian title)
PERMISSIONS: list[tuple[str, str, str]] = [
    ("dashboard", "view", "مشاهده داشبورد"),
    ("equipment", "view", "مشاهده تجهیزات"),
    ("equipment", "create", "ایجاد تجهیز"),
    ("equipment", "edit", "ویرایش تجهیز"),
    ("equipment", "delete", "حذف تجهیز"),
    ("equipment", "export", "خروجی گرفتن تجهیزات"),
    ("import", "manage", "بارگذاری گروهی داده (Bulk Import)"),
    ("plans", "view", "مشاهده برنامه نت"),
    ("plans", "create", "ایجاد برنامه نت"),
    ("plans", "edit", "ویرایش برنامه نت"),
    ("plans", "delete", "حذف برنامه نت"),
    ("files", "upload", "بارگذاری فایل"),
    ("files", "delete", "حذف فایل"),
    ("users", "view", "مشاهده کاربران"),
    ("users", "create", "ایجاد کاربر"),
    ("users", "edit", "ویرایش کاربر"),
    ("users", "delete", "حذف کاربر"),
    ("roles", "manage", "مدیریت نقش‌ها و دسترسی‌ها"),
    ("base_data", "view", "مشاهده داده‌های پایه"),
    ("base_data", "manage", "مدیریت داده‌های پایه"),
    ("audit", "view", "مشاهده گزارش ممیزی"),
    ("backup", "manage", "مدیریت پشتیبان‌گیری"),
    ("reports", "view", "مشاهده گزارش‌ها"),
    # Phase 1 (§1B) -------------------------------------------------------
    ("requests", "view", "مشاهده درخواست‌ها"),
    ("requests", "create", "ایجاد درخواست کار"),
    ("requests", "approve", "بررسی و تأیید درخواست"),
    ("workorders", "view", "مشاهده دستور کارها"),
    ("workorders", "create", "ایجاد دستور کار"),
    ("workorders", "manage", "مدیریت دستور کار (تخصیص/Permit/تأیید نهایی)"),
    ("workorders", "execute", "اجرای دستور کار (تکنسین)"),
    ("workorders", "confirm", "تأیید انجام کار توسط درخواست‌دهنده"),
    ("notifications", "view", "مشاهده اعلان‌ها"),
    # Phase 2 (§1B) -------------------------------------------------------
    ("checklist", "view", "مشاهده چک‌لیست‌های بازرسی"),
    ("checklist", "manage", "مدیریت قالب‌های چک‌لیست"),
    ("checklist", "execute", "اجرای چک‌لیست بازرسی"),
    ("risks", "view", "مشاهده ریسک و فرصت"),
    ("risks", "manage", "مدیریت ریسک و فرصت"),
    ("calibration", "view", "مشاهده کالیبراسیون"),
    ("calibration", "manage", "مدیریت کالیبراسیون"),
    ("parts", "view", "مشاهده قطعات و انبار"),
    ("parts", "manage", "مدیریت قطعات و انبار"),
    ("messages", "view", "مشاوره و پیام‌رسانی داخلی"),
    ("selen", "use", "استفاده از دستیار هوشمند SELEN"),
    # MODULE EQUIPMENT — BASPAR (§33) --------------------------------------
    ("equipment", "print", "چاپ شناسنامه/پاسپورت تجهیز"),
    ("equipment", "manage_structure", "مدیریت ساختار تجهیز"),
    ("equipment", "manage_pm", "مدیریت برنامه نت تجهیز"),
    ("equipment", "manage_checklist", "مدیریت چک‌لیست تجهیز"),
    ("bulk_charge", "charge", "شارژ داده انبوه تجهیزات"),
    ("bulk_charge", "approve", "تأیید/Commit شارژ داده"),
    ("bulk_charge", "rollback", "بازگردانی شارژ داده"),
]

ADMIN_ROLE = "admin"


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    # SSE/EventSource cannot set headers → allow token as query param there.
    q = request.query_params.get("token")
    if q:
        return q
    # Some reverse proxies strip the Authorization header — the HttpOnly
    # session cookie (set at login) is the resilient fallback.
    return request.cookies.get("cmms_token")


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    token = _bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="احراز هویت لازم است")
    try:
        payload = decode_access_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="حساب کاربری غیرفعال است")
    return user


def user_permissions(user: User) -> set[str]:
    perms: set[str] = set()
    for role in user.roles:
        if role.name == ADMIN_ROLE:
            return {f"{m}.{a}" for m, a, _ in PERMISSIONS}
        perms.update(p.code for p in role.permissions)
    return perms


def require(*codes: str) -> Callable:
    """Dependency factory: require ALL given permission codes."""

    def checker(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        have = user_permissions(user)
        missing = [c for c in codes if c not in have]
        if missing:
            raise HTTPException(
                status_code=403, detail="دسترسی لازم برای این عملیات را ندارید"
            )
        request.state.user = user
        return user

    return checker
