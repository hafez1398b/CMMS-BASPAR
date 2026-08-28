"""Base data: factories, equipment categories, dropdown lists, roles.

All dropdown lists are data-driven (`lookup_items`) so Admin/Designer can
extend them without code changes (§37, §38).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import EquipmentCategory, Factory, LookupItem, Role, User
from ..rbac import PERMISSIONS, get_current_user, require

router = APIRouter(tags=["base-data"])


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


class FactoryIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=2, max_length=128)
    address: str | None = None
    is_active: bool = True


@router.get("/factories")
def list_factories(_: User = Depends(require("base_data.view")), db: Session = Depends(get_db)):
    items = db.query(Factory).order_by(Factory.name).all()
    return {
        "items": [
            {"id": f.id, "code": f.code, "name": f.name, "address": f.address,
             "is_active": f.is_active}
            for f in items
        ]
    }


@router.post("/factories", status_code=201)
def create_factory(body: FactoryIn, request: Request,
                   admin: User = Depends(require("base_data.manage")),
                   db: Session = Depends(get_db)):
    if db.query(Factory).filter(Factory.code == body.code).one_or_none():
        raise HTTPException(status_code=409, detail="کد کارخانه تکراری است")
    f = Factory(**body.model_dump(), created_by=admin.id)
    db.add(f)
    db.flush()
    audit.record(db, user_id=admin.id, action="factory.created", entity_type="factory",
                 entity_id=f.id, new=body.model_dump(), request=request)
    db.commit()
    return {"id": f.id, **body.model_dump()}


@router.put("/factories/{fid}")
def update_factory(fid: int, body: FactoryIn, request: Request,
                   admin: User = Depends(require("base_data.manage")),
                   db: Session = Depends(get_db)):
    f = db.get(Factory, fid)
    if not f:
        raise HTTPException(status_code=404, detail="کارخانه یافت نشد")
    old = {"code": f.code, "name": f.name, "address": f.address, "is_active": f.is_active}
    for k, v in body.model_dump().items():
        setattr(f, k, v)
    f.updated_by = admin.id
    audit.record(db, user_id=admin.id, action="factory.updated", entity_type="factory",
                 entity_id=f.id, old=old, new=body.model_dump(), request=request)
    db.commit()
    return {"id": f.id, **body.model_dump()}


@router.delete("/factories/{fid}")
def delete_factory(fid: int, request: Request,
                   admin: User = Depends(require("base_data.manage")),
                   db: Session = Depends(get_db)):
    f = db.get(Factory, fid)
    if not f:
        raise HTTPException(status_code=404, detail="کارخانه یافت نشد")
    f.is_active = False
    audit.record(db, user_id=admin.id, action="factory.deactivated", entity_type="factory",
                 entity_id=f.id, request=request)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Equipment categories
# ---------------------------------------------------------------------------


class CategoryIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=2, max_length=128)
    parent_id: int | None = None
    is_active: bool = True


@router.get("/categories")
def list_categories(_: User = Depends(require("base_data.view")), db: Session = Depends(get_db)):
    items = db.query(EquipmentCategory).order_by(EquipmentCategory.name).all()
    return {
        "items": [
            {"id": c.id, "code": c.code, "name": c.name, "parent_id": c.parent_id,
             "is_active": c.is_active}
            for c in items
        ]
    }


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, request: Request,
                    admin: User = Depends(require("base_data.manage")),
                    db: Session = Depends(get_db)):
    if db.query(EquipmentCategory).filter(EquipmentCategory.code == body.code).one_or_none():
        raise HTTPException(status_code=409, detail="کد دسته‌بندی تکراری است")
    c = EquipmentCategory(**body.model_dump(), created_by=admin.id)
    db.add(c)
    db.flush()
    audit.record(db, user_id=admin.id, action="category.created",
                 entity_type="equipment_category", entity_id=c.id,
                 new=body.model_dump(), request=request)
    db.commit()
    return {"id": c.id, **body.model_dump()}


@router.put("/categories/{cid}")
def update_category(cid: int, body: CategoryIn, request: Request,
                    admin: User = Depends(require("base_data.manage")),
                    db: Session = Depends(get_db)):
    c = db.get(EquipmentCategory, cid)
    if not c:
        raise HTTPException(status_code=404, detail="دسته‌بندی یافت نشد")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    c.updated_by = admin.id
    audit.record(db, user_id=admin.id, action="category.updated",
                 entity_type="equipment_category", entity_id=c.id, request=request)
    db.commit()
    return {"id": c.id, **body.model_dump()}


@router.delete("/categories/{cid}")
def delete_category(cid: int, request: Request,
                    admin: User = Depends(require("base_data.manage")),
                    db: Session = Depends(get_db)):
    c = db.get(EquipmentCategory, cid)
    if not c:
        raise HTTPException(status_code=404, detail="دسته‌بندی یافت نشد")
    c.is_active = False
    audit.record(db, user_id=admin.id, action="category.deactivated",
                 entity_type="equipment_category", entity_id=c.id, request=request)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Lookup lists (dropdowns)
# ---------------------------------------------------------------------------


class LookupIn(BaseModel):
    list_code: str = Field(min_length=1, max_length=48)
    code: str = Field(min_length=1, max_length=48)
    title_fa: str = Field(min_length=1, max_length=128)
    extra: dict | None = None
    sort_order: int = 0
    is_active: bool = True


@router.get("/lookups")
def list_lookups(list_code: str | None = None,
                 _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(LookupItem)
    if list_code:
        q = q.filter(LookupItem.list_code == list_code)
    items = q.order_by(LookupItem.list_code, LookupItem.sort_order).all()
    return {
        "items": [
            {"id": i.id, "list_code": i.list_code, "code": i.code,
             "title_fa": i.title_fa, "extra": i.extra, "sort_order": i.sort_order,
             "is_active": i.is_active}
            for i in items
        ]
    }


@router.post("/lookups", status_code=201)
def create_lookup(body: LookupIn, request: Request,
                  admin: User = Depends(require("base_data.manage")),
                  db: Session = Depends(get_db)):
    dup = (
        db.query(LookupItem)
        .filter(LookupItem.list_code == body.list_code, LookupItem.code == body.code)
        .one_or_none()
    )
    if dup:
        raise HTTPException(status_code=409, detail="این آیتم در فهرست وجود دارد")
    item = LookupItem(**body.model_dump())
    db.add(item)
    db.flush()
    audit.record(db, user_id=admin.id, action="lookup.created", entity_type="lookup",
                 entity_id=item.id, new=body.model_dump(), request=request)
    db.commit()
    return {"id": item.id, **body.model_dump()}


@router.put("/lookups/{iid}")
def update_lookup(iid: int, body: LookupIn, request: Request,
                  admin: User = Depends(require("base_data.manage")),
                  db: Session = Depends(get_db)):
    item = db.get(LookupItem, iid)
    if not item:
        raise HTTPException(status_code=404, detail="آیتم یافت نشد")
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    audit.record(db, user_id=admin.id, action="lookup.updated", entity_type="lookup",
                 entity_id=item.id, request=request)
    db.commit()
    return {"id": item.id, **body.model_dump()}


@router.delete("/lookups/{iid}")
def delete_lookup(iid: int, request: Request,
                  admin: User = Depends(require("base_data.manage")),
                  db: Session = Depends(get_db)):
    item = db.get(LookupItem, iid)
    if not item:
        raise HTTPException(status_code=404, detail="آیتم یافت نشد")
    item.is_active = False
    audit.record(db, user_id=admin.id, action="lookup.deactivated", entity_type="lookup",
                 entity_id=item.id, request=request)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Roles & permission matrix (§36)
# ---------------------------------------------------------------------------


@router.get("/roles")
def list_roles(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    roles = db.query(Role).order_by(Role.id).all()
    return {
        "items": [
            {"id": r.id, "name": r.name, "title_fa": r.title_fa,
             "description": r.description, "is_system": r.is_system,
             "permissions": sorted(p.code for p in r.permissions)}
            for r in roles
        ],
        "all_permissions": [
            {"code": f"{m}.{a}", "module": m, "title_fa": t} for m, a, t in PERMISSIONS
        ],
    }


class RolePermissionsIn(BaseModel):
    permissions: list[str]


@router.put("/roles/{role_id}/permissions")
def set_role_permissions(role_id: int, body: RolePermissionsIn, request: Request,
                         admin: User = Depends(require("roles.manage")),
                         db: Session = Depends(get_db)):
    from ..models import Permission

    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="نقش یافت نشد")
    if role.name == "admin":
        raise HTTPException(status_code=400, detail="نقش مدیر سیستم به‌صورت ذاتی همه دسترسی‌ها را دارد")

    valid = {p.code for p in PERMISSIONS}
    unknown = set(body.permissions) - valid
    if unknown:
        raise HTTPException(status_code=400, detail=f"دسترسی‌های نامعتبر: {', '.join(sorted(unknown))}")

    perms = (
        db.query(Permission)
        .filter(Permission.code.in_(list(body.permissions)))
        .all()
    )
    role.permissions = perms
    audit.record(db, user_id=admin.id, action="role.permissions_updated",
                 entity_type="role", entity_id=role.id,
                 new={"permissions": sorted(body.permissions)}, request=request)
    db.commit()
    return {"ok": True, "permissions": sorted(body.permissions)}
