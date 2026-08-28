"""Security primitives: password hashing, JWT tokens, password policy.

No third-party crypto binaries: PBKDF2-HMAC-SHA256 from the standard library
with per-user random salt (OWASP-recommended iteration count) and HS256 JWT.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from .config import get_settings

PBKDF2_ITERATIONS = 390_000


class AuthError(Exception):
    """Raised for any authentication failure (kept opaque on purpose)."""


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, digest = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def validate_password_strength(password: str) -> list[str]:
    """Enterprise password policy; returns list of violations (empty = OK)."""
    errors: list[str] = []
    if len(password) < 8:
        errors.append("رمز عبور باید حداقل ۸ نویسه باشد")
    if not re.search(r"[A-Za-z]", password or ""):
        errors.append("رمز عبور باید شامل حروف باشد")
    if not re.search(r"\d", password or ""):
        errors.append("رمز عبور باید شامل عدد باشد")
    return errors


# --------------------------------------------------------------------------
# JWT
# --------------------------------------------------------------------------

def create_access_token(user_id: int, username: str, roles: list[str]) -> tuple[str, str]:
    """Return (token, jti)."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    jti = secrets.token_hex(8)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "jti": jti,
        "iss": "baspar-cmms",
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer="baspar-cmms",
        )
    except jwt.PyJWTError as exc:  # includes expiredSignatureError
        raise AuthError("نشست معتبر نیست یا منقضی شده است") from exc


def new_api_key() -> str:
    return secrets.token_urlsafe(32)
