"""Backup / Restore (§40, §70).

Backups are self-contained ZIP archives: consistent database snapshot
(SQLite online-backup API) + uploaded files + manifest.  Restoring is an
explicit, audited admin action.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import get_db
from ..models import User
from ..rbac import require

router = APIRouter(prefix="/backup", tags=["backup"])


def create_backup_archive(user_id: int | None) -> Path:
    """Build a backup ZIP; returns its path.  Shared with the CLI script."""
    settings = get_settings()
    settings.ensure_dirs()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive = settings.backup_dir / f"cmms-backup-{stamp}.zip"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db_path = Path(settings.database_url.replace("sqlite:///", ""))
        db_snapshot = tmp_path / "cmms.db"
        if db_path.exists():
            src = sqlite3.connect(str(db_path))
            dst = sqlite3.connect(str(db_snapshot))
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
        else:  # pragma: no cover - non-sqlite deployments use pg_dump tooling
            raise HTTPException(status_code=501,
                                detail="پشتیبان‌گیری خودکار فقط برای SQLite فعال است")

        manifest = {
            "app": settings.app_name,
            "environment": settings.environment,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "created_by": user_id,
            "includes": ["cmms.db", "uploads/"],
        }
        (tmp_path / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_snapshot, "cmms.db")
            zf.write(tmp_path / "manifest.json", "manifest.json")
            uploads = settings.upload_root
            if uploads.exists():
                for p in uploads.rglob("*"):
                    if p.is_file():
                        zf.write(p, Path("uploads") / p.relative_to(uploads))
    return archive


@router.post("")
def make_backup(request: Request,
                user: User = Depends(require("backup.manage")),
                db: Session = Depends(get_db)):
    archive = create_backup_archive(user.id)
    audit.record(db, user_id=user.id, action="backup.created", entity_type="backup",
                 entity_id=archive.name, new={"size": archive.stat().st_size},
                 request=request)
    db.commit()
    return {"ok": True, "filename": archive.name, "size": archive.stat().st_size}


@router.get("")
def list_backups(_: User = Depends(require("backup.manage"))):
    settings = get_settings()
    items = []
    for p in sorted(settings.backup_dir.glob("cmms-backup-*.zip"), reverse=True):
        items.append({"filename": p.name, "size": p.stat().st_size,
                      "created_at": datetime.fromtimestamp(
                          p.stat().st_mtime, tz=timezone.utc).isoformat()})
    return {"items": items, "location": str(settings.backup_dir)}


@router.post("/restore")
def restore_backup(filename: str, request: Request,
                   user: User = Depends(require("backup.manage")),
                   db: Session = Depends(get_db)):
    settings = get_settings()
    archive = (settings.backup_dir / filename).resolve()
    if str(settings.backup_dir.resolve()) not in str(archive) or not archive.exists():
        raise HTTPException(status_code=404, detail="فایل پشتیبان یافت نشد")

    db_path = Path(settings.database_url.replace("sqlite:///", ""))
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            if "cmms.db" not in names:
                raise HTTPException(status_code=400,
                                    detail="فایل پشتیبان معتبر نیست (پایگاه داده موجود نیست)")
            zf.extract("cmms.db", tmp)
            snapshot = Path(tmp) / "cmms.db"
            # sanity: must be a readable sqlite db
            conn = sqlite3.connect(str(snapshot))
            try:
                conn.execute("SELECT count(*) FROM sqlite_master")
            except Exception:
                raise HTTPException(status_code=400, detail="پایگاه داده پشتیبان خراب است")
            finally:
                conn.close()

        # keep a pre-restore safety copy
        if db_path.exists():
            safety = settings.backup_dir / f"pre-restore-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.db"
            shutil.copy2(db_path, safety)
        shutil.copy2(snapshot, db_path)

    audit.record(db, user_id=user.id, action="backup.restored", entity_type="backup",
                 entity_id=filename, request=request)
    db.commit()
    return {"ok": True,
            "note": "بازگردانی انجام شد؛ برای اعمال کامل، سرویس را مجدداً راه‌اندازی کنید"}
