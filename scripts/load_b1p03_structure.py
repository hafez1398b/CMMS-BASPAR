"""ساخت ساختار ربات تزریق یک (B1P03) از جدول قطعات اکسس — گزینه الف.

۷ زیرسیستم + ۱۲ قطعه. فقط اگر تجهیز فرزند نداشته باشد اجرا می‌شود
(ایدِمپوتنت). به ساختار تأییدشده B1P01/2/4 دست نمی‌زند.

اجرا:  .venv/bin/python scripts/load_b1p03_structure.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal
from backend.app.models import Equipment, User

# (زیرسیستم، [قطعات]) — به ترتیب ثبت
STRUCTURE = [
    ("سیستم حرکتی", ["سروموتورها", "سرودرایوها"]),
    ("سیستم تزریق", ["هد تزریق"]),
    ("سیستم هیدرولیک", ["سیستم هیدرولیک"]),
    ("سیستم پنوماتیک", ["سیستم پنوماتیک"]),
    ("سیستم برق و کنترل", ["تابلوهای برق", "کنترل پنل", "نرم‌افزار", "وایرینگ", "سنسورها"]),
    ("سیستم خنک‌کاری", ["سیستم خنک‌کننده"]),
    ("فریم و بدنه", ["فریم و بدنه"]),
]


def main():
    with SessionLocal() as db:
        eq = db.query(Equipment).filter(Equipment.code == "B1P03",
                                        Equipment.deleted_at.is_(None)).first()
        if eq is None:
            print("! تجهیز B1P03 یافت نشد")
            sys.exit(1)
        children = db.query(Equipment).filter(Equipment.parent_id == eq.id,
                                              Equipment.deleted_at.is_(None)).count()
        if children:
            print(f"B1P03 از قبل {children} فرزند دارد — تغییری داده نشد")
            sys.exit(0)
        admin = db.query(User).filter(User.username == "admin").one()
        comp_seq = 0
        for si, (sub_name, comps) in enumerate(STRUCTURE, start=1):
            sub = Equipment(
                code=f"B1P03-S{si}", name=sub_name, level="subsystem",
                parent_id=eq.id, factory_id=eq.factory_id, category_id=eq.category_id,
                criticality=eq.criticality, status="active", created_by=admin.id,
            )
            db.add(sub); db.flush()
            print(f"  + زیرسیستم: {sub_name}")
            for cname in comps:
                comp_seq += 1
                c = Equipment(
                    code=f"B1P03.{comp_seq}", name=cname, level="component",
                    parent_id=sub.id, factory_id=eq.factory_id, category_id=eq.category_id,
                    criticality=eq.criticality, status="active", created_by=admin.id,
                )
                db.add(c); db.flush()
                print(f"      └ قطعه: {cname} ({c.code})")
        db.commit()
        print(f"[load_b1p03_structure] {len(STRUCTURE)} زیرسیستم و {comp_seq} قطعه برای B1P03 ثبت شد")


if __name__ == "__main__":
    main()
