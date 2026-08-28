"""ثبت تجهیزات بسپار۱ از استیجینگ تأییدشده.

فقط پس از تأیید صریح مسئول نت اجرا شود.
- ردیف‌های «جدید»: ایجاد تجهیز با همه فیلدها + مشخصات پویا
- ردیف‌های «به‌روزرسانی» (پرونده‌های غنی قبلی): فقط تکمیل فیلدهای خالی؛
  داده‌های تأییدشده قبلی هرگز بازنویسی نمی‌شوند (ظرفیت رسمی هم محفوظ)
ایدِمپوتنت: کد موجود ← رد می‌شود.

اجرا:  .venv/bin/python scripts/load_baspar1_equipment.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal
from backend.app.models import Equipment, EquipmentCategory, Factory, User

STAGE = ROOT / "data" / "staging" / "baspar1_equipment_staging.json"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    data = json.loads(STAGE.read_text(encoding="utf-8"))
    if data["meta"]["status"].startswith("AWAITING"):
        print("⚠ استیجینگ هنوز تأیید نشده است — ابتدا تأیید مسئول نت لازم است.")
        sys.exit(1)

    created = updated = skipped = conflicts = 0
    with SessionLocal() as db:
        admin = db.query(User).filter(User.username == "admin").one()
        factories = {f.name: f for f in db.query(Factory).all()}
        cats = {c.name: c for c in db.query(EquipmentCategory).all()}

        for row in data["rows"]:
            code = row["code"]
            if row["status"] == "cancelled":
                print(f"  ✗ {code} کنسل شده — ثبت نمی‌شود")
                continue
            if row["status"] == "conflict" and not row.get("approved"):
                conflicts += 1
                continue
            factory = factories.get(row["factory"])
            cat = cats.get(row["category"]) if row["category"] else None
            if factory is None:
                print(f"  ! کارخانه «{row['factory']}» یافت نشد — {code} رد شد")
                skipped += 1
                continue
            if cat is None and row["category"]:
                print(f"  ! دسته «{row['category']}» یافت نشد — {code} رد شد")
                skipped += 1
                continue

            specs = {}
            if row.get("capacity") and not row.get("capacity_guard"):
                specs["ظرفیت"] = f"{row['capacity']} {row.get('capacity_unit','')}".strip()
            if row.get("country"):
                specs["کشور سازنده"] = row["country"]
            dyn = {
                "نوع تجهیز (مبدأ)": row.get("equipment_type") or None,
                "خط محصول": row.get("product_line") or None,
                "درجه اتوماسیون (مبدأ)": row.get("automation_level") or None,
            }
            if row.get("install_date"):
                dyn["تاریخ نصب (شمسی)"] = row["install_date"]
            if row.get("daily_hours") not in ("", "0", None):
                dyn["ساعت کار روزانه"] = row["daily_hours"]
            dims = []
            for k, lbl in (("length", "طول"), ("width", "عرض"), ("height", "ارتفاع")):
                v = row.get(k)
                if v not in ("", "0", None):
                    dims.append(f"{lbl} {v}m")
            if dims:
                dyn["ابعاد"] = " × ".join(dims)
            if row.get("weight") not in ("", "0", None):
                dyn["وزن (تن)"] = row["weight"]
            dyn = {k: v for k, v in dyn.items() if v}

            existing = db.query(Equipment).filter(Equipment.code == code).first()
            if existing and row.get("in_existing_rich"):
                # پرونده غنی قبلی — فقط تکمیل خالی‌ها
                changed = False
                if not existing.model and row.get("model") and row["model"] != "-":
                    existing.model = row["model"]; changed = True
                if not existing.line and row.get("product_line"):
                    existing.line = row["product_line"]; changed = True
                if not existing.dept and row.get("dept"):
                    existing.dept = row["dept"]; changed = True
                ts = dict(existing.technical_specs or {})
                for k, v in specs.items():
                    if k not in ts:
                        ts[k] = v; changed = True
                if ts:
                    existing.technical_specs = ts
                df = dict(existing.dynamic_fields or {})
                for k, v in dyn.items():
                    if k not in df:
                        df[k] = v; changed = True
                if df:
                    existing.dynamic_fields = df
                if changed:
                    updated += 1
                    print(f"  ~ {code} تکمیل شد")
                else:
                    skipped += 1
                continue
            if existing:
                print(f"  ! {code} از قبل وجود دارد — رد شد")
                skipped += 1
                continue

            e = Equipment(
                code=code, name=row["name"], level="equipment",
                factory_id=factory.id,
                category_id=cat.id if cat else None,
                dept=row.get("dept") or None,
                line=row.get("product_line") or None,
                model=(row.get("model") if row.get("model") not in ("-", "*", "0", "") else None),
                manufacturer=None,
                criticality="medium",
                status=row.get("status_active", "active"),
                technical_specs=specs or None,
                dynamic_fields=dyn or None,
                created_by=admin.id,
            )
            db.add(e)
            created += 1
            print(f"  + {code} — {row['name']}")
        db.commit()
    print(f"[load_baspar1] جدید {created} | تکمیل {updated} | رد {skipped} | "
          f"تعارض بدون تأیید {conflicts}")


if __name__ == "__main__":
    main()
