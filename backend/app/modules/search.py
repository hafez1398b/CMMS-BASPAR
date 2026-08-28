"""Global search (§8) across equipment, categories, factories, plans, users."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Equipment, EquipmentCategory, Factory, MaintenancePlan, User
from ..rbac import get_current_user

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def global_search(q: str = Query(min_length=2, max_length=64),
                  user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    like = f"%{q}%"
    equipment = (
        db.query(Equipment)
        .filter(Equipment.deleted_at.is_(None),
                or_(Equipment.code.ilike(like), Equipment.name.ilike(like),
                    Equipment.serial_number.ilike(like)))
        .order_by(Equipment.code).limit(10).all()
    )
    categories = (
        db.query(EquipmentCategory)
        .filter(EquipmentCategory.name.ilike(like)).limit(5).all()
    )
    factories = db.query(Factory).filter(Factory.name.ilike(like)).limit(5).all()
    plans = (
        db.query(MaintenancePlan)
        .filter(MaintenancePlan.deleted_at.is_(None),
                MaintenancePlan.work_title.ilike(like))
        .limit(5).all()
    )
    users = []
    perms = {p.code for r in user.roles for p in r.permissions}
    if user.roles and any(r.name == "admin" for r in user.roles) or "users.view" in perms:
        users = (
            db.query(User)
            .filter(User.deleted_at.is_(None),
                    or_(User.username.ilike(like), User.full_name.ilike(like)))
            .limit(5).all()
        )

    return {
        "equipment": [{"id": e.id, "code": e.code, "name": e.name, "level": e.level}
                      for e in equipment],
        "categories": [{"id": c.id, "name": c.name} for c in categories],
        "factories": [{"id": f.id, "name": f.name} for f in factories],
        "plans": [{"id": p.id, "title": p.work_title, "equipment_id": p.equipment_id}
                  for p in plans],
        "users": [{"id": u.id, "username": u.username, "full_name": u.full_name}
                  for u in users],
    }
