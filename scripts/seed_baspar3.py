"""Seed بسپار۳ / اسفنج equipment from data/baspar3_sponge.json (Staging→DB).

Honors the 7 rules of the EQUIPMENT DATA SEED prompt:
 1. top-level key = Equipment; value = fields.
 2. قطعات → Component children, code = {code}.{nn}.
 3. برنامه نگهداری → MaintenancePlan; تناوب mapped; «کارکرد …» = usage-based trigger.
 4. سوابق تا امروز → MaintenanceHistory (only if non-empty; never fabricated).
 5. «نامشخص» / «نامشخص - نیاز به تکمیل دستی» → flagged needs_manual_completion, not guessed.
 6. «کد در پرونده دیجیتال جداگانه» → key = final code; second code kept in dynamic_fields.
 7. «یادداشت» (B3AD2/B3AD4) → treated as NEW equipment.
Idempotent: skips existing equipment codes.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal
from backend.app.models import (
    Equipment, EquipmentCategory, Factory, MaintenancePlan, MaintenanceHistory,
)

CRIT = {"A": "critical", "B": "high", "C": "medium", "D": "low"}
CAT_MAP = {
    "ایمنی* پشتیبانی": "ایمنی و پشتیبانی", "ایمنی و پشتیبانی": "ایمنی و پشتیبانی",
    "ماشین آلات": "ماشین‌آلات تولید", "ماشین‌آلات تولید": "ماشین‌آلات تولید",
    "ترابری": "ترابری", "اداری": "اداری", "عمرانی": "عمرانی",
}
INTERVAL = {
    "روزانه": ("daily", 1), "هفتگی": ("weekly", 7), "دوهفتگی": ("biweekly", 14),
    "15روزه": ("biweekly", 15), "ماهانه": ("monthly", 30), "3ماهه": ("3monthly", 90),
    "6ماهه": ("6monthly", 180), "سالانه": ("yearly", 365),
}
UNKNOWN = ("نامشخص", "نامشخص - نیاز به تکمیل دستی", "", None)


def parse_date(s):
    if not s or not isinstance(s, str):
        return None
    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", s.strip())
    if not m:
        return None
    from backend.app.jalali import jalali_to_gregorian
    try:
        from datetime import datetime, timezone
        g = jalali_to_gregorian(int(m[1]), int(m[2]), int(m[3]))
        return datetime(g.year, g.month, g.day, tzinfo=timezone.utc)
    except Exception:
        return None


def is_unknown(v):
    return v in UNKNOWN or (isinstance(v, str) and v.strip().startswith("نامشخص"))


def main():
    data = json.load(open(ROOT / "data" / "baspar3_sponge.json", encoding="utf-8"))
    stats = {"equipment": 0, "components": 0, "plans": 0, "history": 0, "skipped": 0, "flagged": 0}
    with SessionLocal() as db:
        factory = db.query(Factory).filter(Factory.name == "بسپار۳").first()
        if factory is None:
            factory = db.query(Factory).first()
        for code, rec in data.items():
            if db.query(Equipment).filter(Equipment.code == code).one_or_none():
                stats["skipped"] += 1
                continue

            cat_name = CAT_MAP.get((rec.get("دسته") or "").strip(), "سایر")
            cat = db.query(EquipmentCategory).filter(EquipmentCategory.name == cat_name).first()

            crit_raw = rec.get("درجه اهمیت (RTF Scale A-D)")
            crit = CRIT.get(str(crit_raw).strip()) if crit_raw else None
            status_raw = (rec.get("وضعیت") or "").strip()
            status = "active" if status_raw == "فعال" else ("active" if not status_raw else "inactive")

            manual = []
            for fld in ("وضعیت", "درجه اهمیت (RTF Scale A-D)", "تاریخ نصب", "زیرقطعات"):
                if is_unknown(rec.get(fld)):
                    manual.append(fld)
            pm = rec.get("برنامه نگهداری")
            if isinstance(pm, str) and is_unknown(pm):
                manual.append("برنامه نگهداری")

            dyn = {}
            if rec.get("تاریخ نصب"): dyn["تاریخ نصب"] = rec["تاریخ نصب"]
            if rec.get("درجه اتوماسیون"): dyn["درجه اتوماسیون"] = rec["درجه اتوماسیون"]
            if rec.get("دسته Access"): dyn["دسته Access"] = rec["دسته Access"]
            if rec.get("مدل (Access)"): dyn["مدل Access"] = rec["مدل (Access)"]
            if rec.get("کد در پرونده دیجیتال جداگانه"):
                dyn["کد قدیمی/جایگزین یافت‌شده"] = rec["کد در پرونده دیجیتال جداگانه"]
            if rec.get("یادداشت"):
                dyn["یادداشت"] = rec["یادداشت"]; dyn["new_equipment"] = True
            if manual:
                dyn["needs_manual_completion"] = manual

            eq = Equipment(
                code=code, name=rec.get("نام تجهیز") or code, level="equipment",
                factory_id=factory.id if factory else None,
                category_id=cat.id if cat else None,
                hall=(rec.get("قسمت") or "").strip() or None,
                line=(rec.get("خط تولید") or "").strip() or None,
                location=(rec.get("محل دقیق (خام)") or "").strip() or None,
                criticality=crit or "medium", status=status,
                dynamic_fields=dyn or None, created_by=None,
            )
            db.add(eq); db.flush()
            stats["equipment"] += 1
            if manual or rec.get("یادداشت"):
                stats["flagged"] += 1

            # 2) components
            for i, comp in enumerate(rec.get("قطعات") or [], start=1):
                db.add(Equipment(
                    code=f"{code}.{i:02d}", name=comp, level="component",
                    parent_id=eq.id, factory_id=eq.factory_id, category_id=eq.category_id,
                    criticality=eq.criticality, status="active", created_by=None))
                stats["components"] += 1

            # 3) PM plans
            if isinstance(pm, list):
                for act in pm:
                    freq = (act.get("تناوب") or "").strip()
                    icode, idays = INTERVAL.get(freq, ("custom", 0))
                    usage = freq if freq.startswith("کارکرد") else None
                    db.add(MaintenancePlan(
                        equipment_id=eq.id, work_class="pm", work_title=act.get("فعالیت") or "",
                        activity_type="inspection", interval_code=icode if not usage else "custom",
                        interval_days=idays if not usage else 0,
                        activity_description=(act.get("ملاحظات") or "") + (f" | Trigger: {usage}" if usage else ""),
                        created_by=None))
                    stats["plans"] += 1

            # 4) history (only if present)
            for hrec in rec.get("سوابق تا امروز") or []:
                desc = (hrec.get("شرح") or "")
                if hrec.get("اقدام تعمیر"): desc += " | اقدام: " + hrec["اقدام تعمیر"]
                if hrec.get("وضعیت"): desc += " | وضعیت: " + hrec["وضعیت"]
                if hrec.get("مدت توقف"): desc += " | توقف: " + hrec["مدت توقف"]
                db.add(MaintenanceHistory(
                    equipment_id=eq.id, work_type="cm",
                    title=(hrec.get("شرح") or "")[:190] or "سابقه", description=desc,
                    finished_at=parse_date(hrec.get("تاریخ"))))
                stats["history"] += 1

        db.commit()
    print("[seed_baspar3]", stats)


if __name__ == "__main__":
    main()
