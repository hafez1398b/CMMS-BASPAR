"""Idempotent seed data (§70): roles, permissions, admin user, lookup
lists, and starter factories/categories.  Re-running never duplicates."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    EquipmentCategory, Factory, LookupItem, Permission, Role, User,
)
from .rbac import PERMISSIONS
from .security import hash_password

ROLE_GRANTS: dict[str, list[str]] = {
    "admin": ["*"],
    "technical_manager": [
        "dashboard.view",
        "equipment.view", "equipment.create", "equipment.edit", "equipment.delete",
        "equipment.export",
        "import.manage",
        "plans.view", "plans.create", "plans.edit", "plans.delete",
        "files.upload", "files.delete",
        "users.view",
        "base_data.view",
        "audit.view",
        "reports.view",
        # Phase 1
        "requests.view", "requests.approve",
        "workorders.view", "workorders.create", "workorders.manage",
        "notifications.view", "requests.create",
        # Phase 2
        "checklist.view", "checklist.manage", "checklist.execute",
        "risks.view", "risks.manage", "calibration.view", "calibration.manage",
        "parts.view", "messages.view", "selen.use",
        # MODULE EQUIPMENT spec (S33)
        "equipment.print", "equipment.manage_structure", "equipment.manage_pm",
        "equipment.manage_checklist",
        "bulk_charge.charge", "bulk_charge.approve", "bulk_charge.rollback",
    ],
    "technician": [
        "dashboard.view", "equipment.view", "plans.view", "reports.view",
        # Phase 1
        "requests.view",
        "workorders.view", "workorders.execute",
        "files.upload",
        "notifications.view", "requests.create",
        # Phase 2
        "checklist.view", "checklist.execute", "risks.view",
        "parts.view", "messages.view", "selen.use",
        "equipment.print", "bulk_charge.charge",
    ],
    "viewer": [
        "dashboard.view", "equipment.view", "plans.view", "base_data.view",
        "reports.view", "notifications.view",
        # Phase 2
        "checklist.view", "risks.view", "calibration.view", "parts.view",
        # MODULE EQUIPMENT spec (S33)
        "equipment.print",
    ],
    # Phase 1+ roles — created now so RBAC never needs a schema change.
    "maintenance_manager": [
        "dashboard.view",
        "equipment.view", "equipment.create", "equipment.edit",
        "plans.view", "plans.create", "plans.edit", "plans.delete",
        "files.upload", "files.delete", "users.view", "base_data.view",
        "reports.view",
        "requests.view", "requests.approve",
        "workorders.view", "workorders.create", "workorders.manage",
        "notifications.view", "requests.create",
        # Phase 2
        "checklist.view", "checklist.manage", "checklist.execute",
        "risks.view", "risks.manage", "calibration.view", "calibration.manage",
        "parts.view", "messages.view", "selen.use",
        # MODULE EQUIPMENT spec (S33)
        "equipment.print", "equipment.manage_structure", "equipment.manage_pm",
        "equipment.manage_checklist",
        "bulk_charge.charge", "bulk_charge.approve", "bulk_charge.rollback",
    ],
    "supervisor": [
        "dashboard.view", "equipment.view", "plans.view", "users.view",
        "reports.view",
        # Phase 1: supervisor approval step (§18) + permit approver (§19)
        "requests.view", "requests.approve",
        "workorders.view", "workorders.manage",
        "notifications.view",
        # Phase 2
        "checklist.view", "risks.view", "calibration.view", "parts.view",
        "messages.view", "selen.use",
        "equipment.print",
    ],
    "warehouse": ["dashboard.view", "equipment.view", "reports.view",
                  "notifications.view",
                  # Phase 2
                  "parts.view", "parts.manage", "messages.view"],
    "requester": ["dashboard.view", "equipment.view",
                  "requests.view", "requests.create",
                  "workorders.view", "workorders.confirm",
                  "notifications.view",
                  # Phase 2
                  "messages.view"],
}

ROLE_TITLES = {
    "admin": "مدیر سیستم / Designer",
    "technical_manager": "مدیر فنی",
    "technician": "تکنسین",
    "viewer": "بازدیدکننده",
    "maintenance_manager": "مدیر نت",
    "supervisor": "سرپرست",
    "warehouse": "انباردار",
    "requester": "درخواست‌دهنده",
}

ACTIVITY_TYPES = [
    ("inspection", "بازرسی"),
    ("part_replacement", "تعویض قطعه"),
    ("oil_change", "تعویض روغن"),
    ("lubrication", "روانکاری"),
    ("cleaning", "تمیزکاری"),
    ("tightening", "آچارکشی"),
    ("adjustment", "تنظیم"),
    ("control", "کنترل"),
    ("service", "سرویس"),
    ("other", "سایر"),
]

INTERVALS = [
    ("daily", "روزانه", 1),
    ("weekly", "هفتگی", 7),
    ("biweekly", "دو هفته", 14),
    ("3weekly", "سه هفته", 21),
    ("monthly", "ماهانه", 30),
    ("2monthly", "دو ماهه", 60),
    ("3monthly", "سه ماهه", 90),
    ("6monthly", "شش ماهه", 180),
    ("yearly", "سالانه", 365),
    ("2yearly", "دو ساله", 730),
    ("custom", "سفارشی", None),
]

WORK_CLASSES = [("pm", "پیشگیرانه"), ("cm", "اصلاحی"), ("em", "اضطراری"),
                ("ovh", "اورهال"), ("ins", "بازرسی"), ("cal", "کالیبراسیون")]

EQUIPMENT_STATUSES = [("active", "فعال"), ("inactive", "غیرفعال"),
                      ("under_maintenance", "در دست تعمیر"), ("scrapped", "اسقاط")]

CRITICALITIES = [("low", "کم"), ("medium", "متوسط"), ("high", "زیاد"),
                 ("critical", "بحرانی")]

REQUEST_TYPES = [("repair", "تعمیر"), ("service", "سرویس"), ("modification", "اصلاح"),
                 ("inspection", "بازرسی"), ("improvement", "بهبود"),
                 ("emergency", "اضطراری"), ("other", "سایر")]

COST_TYPES = [("preventive", "پیشگیرانه"), ("corrective", "اصلاحی"),
              ("emergency", "اضطراری"), ("external_contractor", "پیمانکار خارجی"),
              ("internal_labor", "نیروی داخلی"), ("part", "قطعه"),
              ("material", "مواد"), ("service", "سرویس"), ("other", "سایر")]

STARTER_FACTORIES = [("FAC-01", "کارخانه مرکزی بسپار")]
STARTER_CATEGORIES = [
    ("CAT-HVAC", "تأسیسات"),
    ("CAT-PROD", "خط تولید"),
    ("CAT-UTIL", "یوتیلیتی"),
    ("CAT-ELEC", "برق"),
    ("CAT-INST", "ابزار دقیق"),
]

# MODULE EQUIPMENT — BASPAR §7: real factories (prefix table) + §3 categories
REAL_FACTORIES = [
    ("FAC-B1", "بسپار۱"), ("FAC-B2", "بسپار۲"), ("FAC-B3", "بسپار۳"),
    ("FAC-B4", "بسپار۴"), ("FAC-B5", "بسپار۵"), ("FAC-B6", "بسپار۶"),
]
REAL_CATEGORIES = [
    ("CAT-TRB", "ترابری"), ("CAT-CIV", "عمرانی"), ("CAT-ELE", "برق"),
    ("CAT-SAF", "ایمنی و پشتیبانی"), ("CAT-TLS", "ابزارها"),
    ("CAT-MEA", "تجهیزات اندازه‌گیری"), ("CAT-ADM", "اداری"), ("CAT-OTH", "سایر"),
    ("CAT-PRD", "تولیدی"), ("CAT-UTL", "تأسیسات"),
    ("CAT-MAC", "ماشین‌آلات تولید"), ("CAT-FOM", "فوم"),
    ("CAT-ANB", "انبارش"), ("CAT-BOR", "برش"), ("CAT-ESF", "اسفنج"),
]

# §7: Equipment code pattern tables — managed as lookups (not hard-coded).
FACTORY_PREFIXES = [
    ("B1", "بسپار۱"), ("B2", "بسپار۲"), ("B3", "بسپار۳"), ("B4", "بسپار۴"),
    ("B5", "بسپار۵"), ("B6", "بسپار۶"),
]
AREA_CODES = [
    ("A", "تجهیزات محوطه‌ای"),
    ("P", "تجهیزات یا ماشین‌آلات تولیدی"),
    ("F", "تجهیزات تاسیساتی (Facility)"),
    ("PF", "تاسیسات تولید"),
    ("AF", "تاسیسات محوطه"),
]


def seed(db: Session, verbose: bool = True) -> dict:
    settings = get_settings()
    report: dict[str, int] = {}

    # --- Permissions ------------------------------------------------------
    existing = {p.code for p in db.query(Permission).all()}
    for module, action, title_fa in PERMISSIONS:
        code = f"{module}.{action}"
        if code not in existing:
            db.add(Permission(code=code, module=module, title_fa=title_fa))
    db.flush()

    # --- Roles --------------------------------------------------------------
    perm_by_code = {p.code: p for p in db.query(Permission).all()}
    for name, grants in ROLE_GRANTS.items():
        role = db.query(Role).filter(Role.name == name).one_or_none()
        if role is None:
            role = Role(name=name, title_fa=ROLE_TITLES[name],
                        is_system=name in ("admin", "technical_manager", "technician", "viewer"))
            db.add(role)
            db.flush()
        wanted = (set(perm_by_code) if grants == ["*"] else set(grants))
        have = {p.code for p in role.permissions}
        if name == "admin":
            role.permissions = list(perm_by_code.values())  # all, always
        else:
            role.permissions = [perm_by_code[c] for c in wanted if c in perm_by_code]
        report.setdefault("roles", 0)
    db.flush()

    # --- Admin user -----------------------------------------------------------
    admin_role = db.query(Role).filter(Role.name == "admin").one()
    admin = db.query(User).filter(User.username == settings.admin_username).one_or_none()
    if admin is None:
        admin = User(
            username=settings.admin_username,
            full_name="مدیر سیستم",
            password_hash=hash_password(settings.admin_password),
            is_active=True,
        )
        admin.roles = [admin_role]
        db.add(admin)
        db.flush()
        report["admin_created"] = admin.id
        if verbose:
            print(f"[seed] admin user created: {settings.admin_username}")

    # --- Lookups -----------------------------------------------------------------
    def seed_list(list_code: str, items, extra_fn=None):
        have = {
            i.code for i in
            db.query(LookupItem).filter(LookupItem.list_code == list_code).all()
        }
        for idx, item in enumerate(items):
            code, title = item[0], item[1]
            if code in have:
                continue
            extra = extra_fn(item) if extra_fn else None
            db.add(LookupItem(list_code=list_code, code=code, title_fa=title,
                              extra=extra, sort_order=idx))

    seed_list("activity_type", ACTIVITY_TYPES)
    seed_list("interval", INTERVALS,
              extra_fn=lambda i: {"days": i[2]} if i[2] else {})
    seed_list("work_class", WORK_CLASSES)
    seed_list("equipment_status", EQUIPMENT_STATUSES)
    seed_list("criticality", CRITICALITIES)
    seed_list("request_type", REQUEST_TYPES)
    seed_list("cost_type", COST_TYPES)
    db.flush()

    # --- Real base data (§7 factories, §3 categories) -------------------------------
    for code, name in REAL_FACTORIES:
        existing_f = db.query(Factory).filter(Factory.code == code).one_or_none()
        if existing_f is None:
            db.add(Factory(code=code, name=name, created_by=admin.id))
        elif existing_f.name != name:  # keep brand naming current (بسپار)
            existing_f.name = name
    for code, name in STARTER_CATEGORIES + REAL_CATEGORIES:
        if not db.query(EquipmentCategory).filter(EquipmentCategory.code == code).one_or_none():
            db.add(EquipmentCategory(code=code, name=name, created_by=admin.id))

    # §7 code tables + equipment status/type lists (admin-editable lookups)
    seed_list("factory_prefix", [(c, t) for c, t in FACTORY_PREFIXES])
    seed_list("equipment_area_code", [(c, t) for c, t in AREA_CODES])
    seed_list("equipment_type", [
        ("facility", "تأسیساتی"), ("production", "تولیدی"),
        ("storage", "انبارش"), ("transport", "حمل و نقل"),
    ])
    # «نوع قطعه» — component types for rich reporting filters (پمپ/تابلو برق/دینام…)
    seed_list("component_type", [
        ("pump", "پمپ"), ("panel", "تابلو برق"), ("dynamo", "دینام"),
        ("generator", "ژنراتور"), ("compressor", "کمپرسور"), ("motor", "الکتروموتور"),
        ("forklift", "لیفتراک"), ("tank", "مخزن"), ("boiler", "دیگ بخار"),
        ("chiller", "چیلر"), ("conveyor", "نوار نقاله"), ("crane", "جرثقیل"),
    ])

    db.commit()
    if verbose:
        print("[seed] done: permissions, roles, admin, lookups, base data")
    return report
