"""SELEN equipment-code intelligence (§7, §6B).

Decodes legacy equipment codes using the two admin-managed lookup tables:
  factory_prefix  (B1, B2, B3, B4, BT, FA)
  equipment_area_code (A, P, F, PF, AF)

SELEN only SUGGESTS (§14): an unknown prefix is flagged for Admin
definition — never guessed.  Code is a *helper signal*, not a substitute
for the location/factory/type columns.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import LookupItem


def _lookups(db: Session, list_code: str) -> list[LookupItem]:
    return (
        db.query(LookupItem)
        .filter(LookupItem.list_code == list_code, LookupItem.is_active.is_(True))
        .order_by(LookupItem.sort_order).all()
    )


def decode_code(db: Session, code: str) -> dict[str, Any]:
    """Parse `code` into factory-prefix + area-code signals.

    Returns {factory_code, factory_name, area_code, area_name, remainder,
    unknown_prefix}.  Longest-match wins so multi-letter codes (PF, BT, FA)
    are preferred over single letters.
    """
    code = (code or "").strip()
    if not code:
        return {"unknown_prefix": False, "remainder": code}

    prefixes = sorted(_lookups(db, "factory_prefix"), key=lambda x: -len(x.code))
    areas = sorted(_lookups(db, "equipment_area_code"), key=lambda x: -len(x.code))

    up = code.upper()
    factory = None
    for p in prefixes:
        if up.startswith(p.code.upper()):
            factory = p
            break
    if factory is None:
        # No known factory prefix — flag the leading token as unknown.
        head = "".join(ch for ch in code if ch.isalpha())[:2]
        return {"unknown_prefix": True, "prefix_guess": head, "remainder": code}

    rest = code[len(factory.code):]
    area = None
    for a in areas:
        if rest.upper().startswith(a.code.upper()):
            area = a
            break

    remainder = rest[len(area.code):] if area else rest
    return {
        "unknown_prefix": False,
        "factory_code": factory.code,
        "factory_name": factory.title_fa,
        "area_code": area.code if area else None,
        "area_name": area.title_fa if area else None,
        "remainder": remainder,
    }


def factory_of_code(db: Session, code: str) -> str | None:
    """Factory title inferred from code prefix, or None."""
    d = decode_code(db, code)
    return d.get("factory_name")


# ---------------------------------------------------------------------------
# Assisted column mapping (§6B SELEN ASSISTED MAPPING)
# ---------------------------------------------------------------------------

# Standard equipment fields the template maps onto.
EQUIPMENT_FIELDS = [
    ("code", "کد تجهیز"), ("name", "نام تجهیز"), ("factory", "کارخانه"),
    ("category", "دسته"), ("equipment_type", "نوع تجهیز"),
    ("manufacturer", "سازنده"), ("model", "مدل"),
    ("serial_number", "شماره سریال"), ("year", "سال ساخت"),
    ("country", "کشور سازنده"), ("status", "وضعیت"),
    ("criticality", "Criticality"), ("hall", "سالن"), ("dept", "بخش"),
    ("line", "خط"), ("location", "موقعیت"), ("capacity", "ظرفیت"),
    ("power", "توان"), ("capacity_unit", "واحد ظرفیت"),
    ("install_date", "تاریخ نصب"), ("automation", "درجه اتوماسیون"),
    ("description", "شرح"), ("repair_action", "اقدام تعمیراتی"),
    ("min_stock", "حد موجودی"), ("order_qty", "مقدار سفارش"),
    ("equipment_type", "نوع تجهیز"), ("product_line", "خط محصول"),
    ("daily_hours", "ساعت کار روزانه"), ("length", "طول"), ("width", "عرض"),
    ("height", "ارتفاع"), ("weight", "وزن"),
]

# Header aliases → canonical field (Persian + English, case-insensitive).
HEADER_ALIASES: dict[str, str] = {
    "کد تجهیز": "code", "کد": "code", "code": "code", "شناسه": "code",
    "نام تجهیز": "name", "نام": "name", "name": "name", "شرح تجهیز": "name",
    "دسته تجهیز": "name",  # legacy BASPAR sheet: column holds the equipment name
    "کارخانه": "factory", "factory": "factory", "واحد": "factory",
    "دسته": "category", "دسته‌بندی": "category", "کلاس": "category",
    "category": "category", "گروه": "category",
    "نوع تجهیز": "component_type", "نوع قطعه": "component_type",
    "نوع": "component_type", "type": "component_type", "component_type": "component_type",
    "سازنده": "manufacturer", "manufacturer": "manufacturer", "برند": "manufacturer",
    "مدل": "model", "model": "model",
    "شماره سریال": "serial_number", "سریال": "serial_number",
    "serial": "serial_number", "serial_number": "serial_number",
    "سال ساخت": "year", "سال": "year", "year": "year",
    "کشور سازنده": "country", "کشور": "country", "country": "country",
    "وضعیت": "status", "وضعیت تجهیز": "status", "status": "status",
    "criticality": "criticality", "درجه اهمیت": "criticality",
    "بحرانیت": "criticality", "بحرانی بودن": "criticality",
    "سالن": "hall", "hall": "hall", "محل تجهیز": "hall",
    "بخش": "dept", "قسمت": "dept", "dept": "dept", "department": "dept",
    "خط": "line", "line": "line",
    "خط تولید": "category",  # legacy BASPAR sheet: production line == domain/category
    "موقعیت": "location", "محل استقرار": "location", "محل نصب": "location",
    "location": "location",
    "تاریخ نصب": "install_date", "install_date": "install_date",
    "درجه اتوماسیون": "automation", "automation": "automation",
    "ظرفیت": "capacity", "capacity": "capacity",
    "توان": "power", "power": "power",
    # --- نام فیلدهای واقعی پایگاه‌داده Access (منبع بارگذاری نهایی) ---
    # عیناً با همان املا (شامل غلط‌های تایپی منبع) نگه داشته شده‌اند.
    "equipmentcode": "code",
    "equipmentname": "name",
    "equipment name": "name",
    "equipment location": "location",
    "typeofequipment": "equipment_type",
    "productline": "product_line",
    "dailyworkinghours": "daily_hours",
    "length": "length", "width": "width", "height": "height", "weight": "weight",
    "installationdate": "install_date",
    "capacityunit": "capacity_unit",
    "automationlevel": "automation",
    "equipmentcategory": "category",
    "eqyuipmentmodel": "model",   # غلط تایپی در Access — عمداً حفظ شده
    "equipmentmodel": "model",
    "equipmentstatus": "status",
    "installation date": "install_date",
    "unit of capacity": "capacity_unit",
    "level of automation": "automation",
    "capacity_unit": "capacity_unit",
    # --- جدول سوابق خرابی (Failure) ---
    "day failuer": "failure_date",  # غلط تایپی در Access
    "day failure": "failure_date",
    "dateadd": "failure_date",
    "discription": "description",   # غلط تایپی در Access
    "description": "description",
    "شرح": "description",
    "repair": "repair_action",
    "اقدام تعمیراتی": "repair_action",
    "idmainequipment": "parent_code",
    # --- جدول زمان‌بندی PM (Scheduling/Frequency) ---
    "frequencyid": "interval",
    "frequency": "interval",
    "تناوب": "interval",
    # --- جدول قطعات یدکی (Spare Parts) ---
    "equipment spar parts": "part_code",  # غلط تایپی در Access
    "spare parts": "part_name",
    "کد قطعه": "part_code",
    "نام قطعه": "part_name",
    "inventoryminimum": "min_stock",
    "حد موجودی": "min_stock",
    "spareorder": "order_qty",
    "سفارش": "order_qty",
    "supplier": "supplier",
    "تأمین‌کننده": "supplier",
}

# Value-based field detection (§6B ROW-LEVEL FIELD DETECTION)
VALUE_SETS = {
    "status": {"فعال", "غیرفعال", "در دست تعمیر", "اسقاط"},
    "automation": {"دستی", "نیمه اتوماتیک", "اتوماتیک"},
    "criticality_grade": {"A", "B", "C", "D"},
    "equipment_type": {"تأسیساتی", "تاسیساتی", "تولیدی", "انبارش", "حمل و نقل"},
    "location_hint": {"انبار", "کارخانه", "محوطه", "سالن"},
}

DATE_TOKENS = ("/", "-", ".")


def guess_field_from_value(value: str) -> str | None:
    """Return a field guess for a cell value, or None if unrecognised."""
    v = (value or "").strip()
    if not v:
        return None
    for field, members in VALUE_SETS.items():
        if v in members:
            return field
    # single-letter A-D => criticality grade
    if len(v) == 1 and v.upper() in VALUE_SETS["criticality_grade"]:
        return "criticality"
    # date-ish YYYY/MM/DD
    if len(v) >= 8 and any(t in v for t in DATE_TOKENS) and v.replace("/", "").replace("-", "").replace(".", "").isdigit():
        return "install_date"
    return None


def is_date_like(value: str) -> bool:
    v = (value or "").strip()
    return len(v) >= 8 and any(t in v for t in DATE_TOKENS) and \
        v.replace("/", "").replace("-", "").replace(".", "").isdigit()


def suggest_mapping(headers: list[str]) -> list[dict[str, Any]]:
    """Suggest a column→field mapping for a raw header row.

    Each result: {index, header, field, confidence, reason}.  Unmapped
    columns get field=None so the Admin can assign or ignore them (§6B).
    """
    suggestions = []
    for i, raw in enumerate(headers):
        header = (raw or "").strip()
        key = header.lower().replace("‌", "")
        field = HEADER_ALIASES.get(header) or HEADER_ALIASES.get(key)
        if field:
            suggestions.append({"index": i, "header": header, "field": field,
                                "confidence": "high", "reason": "تطابق سربرگ"})
        else:
            suggestions.append({"index": i, "header": header, "field": None,
                                "confidence": "none",
                                "reason": "نیازمند تعیین توسط کاربر"})
    return suggestions
