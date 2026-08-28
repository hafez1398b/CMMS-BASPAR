"""بارگذاری «برنامه نت با قطعات مصرفی» از استیجینگ.

کد PM با الگوی {کد تجهیز}-PM-{شماره} به برنامه‌های ثبت‌شده نگاشت می‌شود
(شماره = ترتیب ایجاد برنامه برای آن تجهیز).
فقط پس از تأیید مسئول نت اجرا شود.

اجرا:  .venv/bin/python scripts/load_pm_consumables.py
ایدِمپوتنت: رکورد تکراری (برنامه + نام قطعه) اضافه نمی‌شود.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal
from backend.app.models import Equipment, MaintenancePlan, PMConsumable, User

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def main():
    data = json.loads(
        (ROOT / "data/staging/pm_consumables_staging.json").read_text(encoding="utf-8"))
    added = skipped = missing = 0
    with SessionLocal() as db:
        admin = db.query(User).filter(User.username == "admin").one()
        for row in data["rows"]:
            code = row["pm_code"].strip()
            m = re.match(r"^(.+)-PM-(\d+)$", code.translate(FA_DIGITS))
            if not m:
                print(f"  ! کد نامعتبر: {code}")
                missing += 1
                continue
            eq_code, seq = m.group(1), int(m.group(2))
            eq = db.query(Equipment).filter(Equipment.code == eq_code).first()
            if eq is None:
                print(f"  ! تجهیز {eq_code} یافت نشد")
                missing += 1
                continue
            plans = (
                db.query(MaintenancePlan)
                .filter(MaintenancePlan.equipment_id == eq.id,
                        MaintenancePlan.deleted_at.is_(None))
                .order_by(MaintenancePlan.id).all()
            )
            if seq < 1 or seq > len(plans):
                print(f"  ! برنامه شماره {seq} برای {eq_code} وجود ندارد (موجود: {len(plans)})")
                missing += 1
                continue
            plan = plans[seq - 1]
            dup = (
                db.query(PMConsumable)
                .filter(PMConsumable.plan_id == plan.id,
                        PMConsumable.part_name == row["part_name"].strip())
                .first()
            )
            if dup:
                skipped += 1
                continue
            db.add(PMConsumable(
                plan_id=plan.id, equipment_id=eq.id,
                part_name=row["part_name"].strip(),
                quantity=row.get("quantity"), unit=row.get("unit"),
                note=row.get("note"), created_by=admin.id,
            ))
            added += 1
            print(f"  + {code} «{plan.work_title}» ← {row['part_name']}"
                  f" ({row.get('quantity')} {row.get('unit')})")
        db.commit()
    print(f"[load_pm_consumables] added={added} skipped={skipped} missing={missing}")


if __name__ == "__main__":
    main()
