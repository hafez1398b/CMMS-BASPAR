"""Auth-gated file download / delete (§45, §46)."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import audit, storage
from ..db import get_db
from ..models import FileObject, User
from ..rbac import require

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{fid}/download")
def download_file(fid: int, user: User = Depends(require("equipment.view")),
                  db: Session = Depends(get_db)):
    f = db.get(FileObject, fid)
    if not f:
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    path = storage.resolve(f.path)
    filename = quote(f.original_name)
    return FileResponse(
        path, media_type=f.mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.delete("/{fid}")
def delete_file(fid: int, request: Request,
                user: User = Depends(require("files.delete")),
                db: Session = Depends(get_db)):
    f = db.get(FileObject, fid)
    if not f:
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    storage.delete(f.path)
    db.delete(f)
    audit.record(db, user_id=user.id, action="file.deleted", entity_type="file",
                 entity_id=f.id, old={"name": f.original_name}, request=request)
    db.commit()
    return {"ok": True}
