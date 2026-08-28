"""File storage service (Master-prompt §45, §46 secure upload).

Uploads live under a configurable root (default `storage/uploads`), named
by UUID so original filenames never reach the filesystem.  Extension
whitelist + size limit + auth-gated download keep the surface small.
"""
from __future__ import annotations

import os
import re
import secrets
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .config import get_settings

_SAFE_NAME = re.compile(r"[\w\u0600-\u06FF .()\-]+")


class StorageError(Exception):
    pass


def _allowed_extensions() -> set[str]:
    s = get_settings()
    return {e.strip().lower() for e in s.allowed_upload_extensions.split(",") if e.strip()}


async def save_upload(
    file: UploadFile, *, entity_type: str, entity_id: int | str
) -> dict:
    """Persist an upload; returns metadata dict ready for the DB."""
    settings = get_settings()
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else ""
    if ext not in _allowed_extensions():
        raise HTTPException(status_code=400, detail=f"نوع فایل مجاز نیست: .{ext}")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    target_dir = settings.upload_root / entity_type / str(entity_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}.{ext}"
    target = target_dir / stored_name
    size = 0
    with open(target, "wb") as out:
        while chunk := await file.read(1024 * 256):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                target.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"حجم فایل بیش از حد مجاز است ({settings.max_upload_mb}MB)",
                )
            out.write(chunk)

    original = file.filename or "file"
    if len(original) > 180:
        original = original[-180:]
    return {
        "original_name": original,
        "stored_name": stored_name,
        "path": str(target.relative_to(settings.storage_root)),
        "mime_type": file.content_type or "application/octet-stream",
        "size": size,
    }


def resolve(path_relative: str) -> Path:
    """Resolve a stored relative path, refusing path traversal."""
    settings = get_settings()
    candidate = (settings.storage_root / path_relative).resolve()
    root = settings.storage_root.resolve()
    if root not in candidate.parents and candidate != root:
        raise HTTPException(status_code=400, detail="مسیر فایل نامعتبر است")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    return candidate


def delete(path_relative: str) -> None:
    try:
        resolve(path_relative).unlink(missing_ok=True)
    except HTTPException:
        pass
