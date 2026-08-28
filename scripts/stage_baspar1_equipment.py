"""استیجینگ تجهیزات بسپار۱ از خروجی اکسس (پیش‌نمایش قبل از ثبت).

قواعد اعمال‌شده (مطابق اسناد تأییدشده پروژه):
- شکافت محل (§11): «بسپار1 تولید فوم» ← کارخانه بسپار۱ + قسمت تولید فوم
- نگاشت نوع تجهیز به دسته: تولیدی←ماشین‌آلات تولید، تأسیساتی←تأسیسات، انبارش←انبارش
- ظرفیت B1P02: عدد اکسس (500) نادیده گرفته می‌شود — شناسنامه رسمی ۹۰۰ مرجع است
- ردیف معیوب B1P08-4 (کاما داخل مدل): اصلاح و پرچم‌گذاری
- پیشوند ناشناخته/ناهماهنگ (FA-CE 9): پرچم تعارض، بدون اصلاح خودکار (§7)
- تاریخ نصب 0 ← خالی؛ تاریخ‌های فشرده 13940726 ← ۱۳۹۴-۰۷-۲۶

خروجی: data/staging/baspar1_equipment_staging.json
اجرا:  .venv/bin/python scripts/stage_baspar1_equipment.py
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SRC = ROOT / "data" / "baspar1_equipment.csv"
OUT = ROOT / "data" / "staging" / "baspar1_equipment_staging.json"

CATEGORY_BY_TYPE = {
    "تولیدی": "ماشین‌آلات تولید",
    "تأسیساتی": "تأسیسات",
    "انبارش": "انبارش",
}
STATUS_MAP = {"فعال": "active", "غیرفعال": "inactive"}
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# تجهیزاتی که قبلاً با پرونده کامل ثبت شده‌اند — فقط به‌روزرسانی فیلدهای پایه
EXISTING_RICH = {"B1P01", "B1P02", "B1P04"}
# ظرفیت رسمی (شناسنامه چاپی) که نباید با عدد اکسس بازنویسی شود
OFFICIAL_CAPACITY = {"B1P02": "900 گرم بر ثانیه"}


def split_location(loc: str):
    """«بسپار1 تولید فوم» ← (بسپار۱، تولید فوم) — نرمال‌سازی رقم لاتین."""
    loc = (loc or "").strip()
    m = re.match(r"^(بسپار)\s*([0-9۰-۹])\s*(.*)$", loc)
    if m:
        return f"{m.group(1)}{m.group(2).translate(FA_DIGITS)}", (m.group(3) or "").strip()
    return loc, ""


def fmt_date(compact: str) -> str | None:
    s = (compact or "").strip()
    if not s or s == "0":
        return None
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def main():
    rows_out = []
    counts = {"new": 0, "update": 0, "conflict": 0}
    with open(SRC, encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        raw_rows = [r for r in reader if any(c.strip() for c in r)]

    from backend.app.db import SessionLocal
    from backend.app.models import Equipment
    with SessionLocal() as db:
        existing = {e.code: e for e in
                    db.query(Equipment).filter(Equipment.deleted_at.is_(None)).all()}

    for idx, cells in enumerate(raw_rows, start=2):
        notes = []
        # ردیف معیوب: کاما داخل فیلد مدل (18 ستون به‌جای 17)
        if len(cells) == len(headers) + 1:
            merged_model = f"{cells[5]}، {cells[6]}"
            cells = cells[:5] + [merged_model] + cells[7:]
            notes.append("خطای ساختاری مبدأ (کاما داخل مدل) به‌صورت خودکار اصلاح شد")

        rec = dict(zip(headers, cells))
        code = rec.get("EquipmentCode", "").strip()
        name = rec.get("EquipmentName", "").strip()
        factory, dept = split_location(rec.get("Location", ""))
        eq_type = rec.get("TypeOfEquipment", "").strip()
        category = CATEGORY_BY_TYPE.get(eq_type)

        status = "conflict" if code.startswith("FA") else (
            "update" if code in existing else "new")

        cap_guard = None
        if code in OFFICIAL_CAPACITY:
            cap_guard = OFFICIAL_CAPACITY[code]
            file_cap = f"{rec.get('Capacity', '')} {rec.get('CapacityUnit', '')}".strip()
            notes.append(f"ظرفیت فایل ({file_cap}) با مرجع رسمی ({cap_guard}) مغایر است — "
                         "مقدار رسمی حفظ می‌شود")

        if code.startswith("FA"):
            notes.append("پیشوند کد (FA) با محل ثبت‌شده (بسپار۱) ناهماهنگ است — "
                         "طبق §7 اصلاح خودکار نمی‌شود؛ پیشنهاد: ثبت زیر بسپار۱ "
                         "(کد قدیمی استثنا). تصمیم با شما")

        if not category:
            notes.append(f"نوع تجهیز «{eq_type}» نگاشت دسته ندارد")

        counts[status] = counts.get(status, 0) + 1
        rows_out.append({
            "row": idx,
            "code": code,
            "name": name,
            "status": status,
            "factory": factory,
            "dept": dept,
            "category": category,
            "equipment_type": eq_type,
            "product_line": rec.get("ProductLine", "").strip(),
            "model": rec.get("Model", "").strip(),
            "country": rec.get("Manufacturer", "").strip(),
            "install_date": fmt_date(rec.get("InstallationDate", "")),
            "capacity": rec.get("Capacity", "").strip(),
            "capacity_unit": rec.get("CapacityUnit", "").strip(),
            "capacity_guard": cap_guard,
            "status_active": STATUS_MAP.get(rec.get("Status", "").strip(), "active"),
            "daily_hours": rec.get("DailyWorkingHours", "").strip(),
            "length": rec.get("Length", "").strip(),
            "width": rec.get("Width", "").strip(),
            "height": rec.get("Height", "").strip(),
            "weight": rec.get("Weight", "").strip(),
            "automation_level": rec.get("AutomationLevel", "").strip(),
            "in_existing_rich": code in EXISTING_RICH,
            "notes": notes,
        })

    payload = {
        "meta": {
            "status": "AWAITING_APPROVAL — پیش‌نمایش؛ بدون تأیید ثبت نشود",
            "source": "data/baspar1_equipment.csv",
            "counts": counts,
            "total": len(rows_out),
        },
        "rows": rows_out,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"استیجینگ: {len(rows_out)} ردیف → جدید {counts.get('new', 0)} | "
          f"به‌روزرسانی {counts.get('update', 0)} | تعارض {counts.get('conflict', 0)}")
    flagged = [r for r in rows_out if r["notes"]]
    print(f"پرچم‌دار: {len(flagged)} ردیف")
    for r in flagged:
        print(f"  - {r['code']}: {'؛ '.join(r['notes'])}")


if __name__ == "__main__":
    main()
