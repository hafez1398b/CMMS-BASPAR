"""اعمال امتیازهای بحرانی (DegresOFEquipment) روی تجهیزات بسپار۱.

هر تجهیز چهار شاخص Safety/Product/Cost/Repair و یک TotalScore رسمی دارد.
- criticality_score ← TotalScore (مقدار رسمی منبع)
- criticality ← سطح مشتق‌شده از TotalScore (آستانه‌ها در bulk_charge)
- چهار شاخص در dynamic_fields برای ممیزی ذخیره می‌شود
- اگر TotalScore با مجموع چهار شاخص نخواند، پرچم می‌خورد (ولی TotalScore رسمی مبناست)

پیش‌نمایش:  .venv/bin/python scripts/load_baspar1_criticality.py
اعمال:     .venv/bin/python scripts/load_baspar1_criticality.py --apply
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal
from backend.app.models import Equipment
from backend.app.modules.bulk_charge import criticality_from_score

SRC = ROOT / "data" / "baspar1_criticality.csv"
APPLY = "--apply" in sys.argv

LEVEL_FA = {"low": "کم", "medium": "متوسط", "high": "زیاد", "critical": "بحرانی"}


def main():
    with open(SRC, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    with SessionLocal() as db:
        existing = {e.code: e for e in
                    db.query(Equipment).filter(Equipment.deleted_at.is_(None)).all()}
        updated = missing = mismatch = 0
        for r in rows:
            code = r["EquipmentCode"].strip()
            eq = existing.get(code)
            if eq is None:
                print(f"  ! {code} یافت نشد (احتمالاً کنسل/حذف شده)")
                missing += 1
                continue
            total = int(r["TotalScore"])
            s, p, c, rep = int(r["Safety"]), int(r["Product"]), int(r["Cost"]), int(r["Repair"])
            calc = s + p + c + rep
            level = criticality_from_score(total)
            flag = ""
            if calc != total:
                mismatch += 1
                flag = f"  ⚠ مجموع={calc} ≠ رسمی={total}"
            if APPLY:
                eq.criticality_score = total
                eq.criticality = level
                dyn = dict(eq.dynamic_fields or {})
                dyn["امتیاز بحرانی"] = (
                    f"ایمنی {s} · محصول {p} · هزینه {c} · تعمیر {rep} = {total} (رسمی)")
                eq.dynamic_fields = dyn
                updated += 1
            print(f"  {code:14} رسمی={total:3} → {LEVEL_FA[level]:6}{flag}")
        if APPLY:
            db.commit()
        verb = "اعمال شد" if APPLY else "پیش‌نمایش (بدون اعمال)"
        print(f"\n[{verb}] به‌روز {updated} | یافت‌نشد {missing} | مغایرت مجموع {mismatch}")


if __name__ == "__main__":
    main()
