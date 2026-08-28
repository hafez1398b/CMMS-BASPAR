"""Health checks (§48, §70).  `/api/health` is dependency-free for
load-balancers; `/api/health/detailed` (admin) inspects every subsystem."""
from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..events import bus
from ..models import User
from ..rbac import require

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}


@router.get("/detailed")
def health_detailed(_: User = Depends(require("backup.manage")),
                    db: Session = Depends(get_db)):
    settings = get_settings()
    checks: dict[str, dict] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"ok": True, "url": settings.database_url.split("@")[-1]}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": str(exc)}

    try:
        probe = settings.storage_root / ".healthcheck"
        probe.write_text("ok")
        probe.unlink()
        checks["storage"] = {"ok": True, "root": str(settings.storage_root)}
    except Exception as exc:
        checks["storage"] = {"ok": False, "error": str(exc)}

    checks["realtime"] = {"ok": True, "subscribers": bus.subscriber_count}
    checks["app"] = {"ok": True, "environment": settings.environment}

    all_ok = all(c["ok"] for c in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}
