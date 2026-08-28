"""ثبت پرسنل واقعی بسپار (ایدِمپوتنت) — برای انتساب سوابق و دستورکارها.

تیم فنی بسپار۱ (فوم): ثبت سوابق با نام این نفرات انجام می‌شود.
تیم فنی/مهندسی کارخانه فوم: مسئول نگهداری تجهیزات به‌جز موارد برون‌سپاری.
اجرا:  .venv/bin/python scripts/seed_personnel.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal
from backend.app.models import Role, User
from backend.app.security import hash_password

PASSWORD = "Baspar@1404"

# (username, full_name, [roles], note)
PERSONNEL = [
    # --- تیم فنی بسپار۱ (ثبت سوابق با این نفرات) ---
    ("a.jahanmoradi", "مهندس علی جهان مرادی", ["supervisor", "requester"],
     "مدیر تولید — درخواست‌دهنده و تأییدکننده فعالیت‌ها"),
    ("n.babaei", "نجات بابایی", ["technician"], "مکانیک صنعتی"),
    ("p.moafipour", "پوریا معافی پور", ["technician"], "مکانیک صنعتی / تأسیسات"),
    ("e.shahkarami", "عزت شاه کرمی", ["technician", "warehouse"],
     "جوشکار / مسئول انبار مواد اولیه فوم"),
    # --- تیم فنی و مهندسی کارخانه فوم ---
    ("m.mahmoudabadi", "محمود محمود آبادی", ["technician"], "تأسیسات"),
    ("a.rezaei", "اصغر رضایی", ["technician"], "جوشکاری / تأسیسات"),
    ("m.pirayesh", "محسن پیرایش", ["technician"], "مکانیک خودرو و صنعتی"),
    ("a.kavousi", "احمد کاووسی", ["technician"],
     "برق صنعتی — کلیه کارخانجات از جمله بسپار۱"),
    ("s.shokri", "سجاد شکری", ["technician"], "کارگر فنی"),
    ("h.bayramian", "حافظ بایرامیان", ["technical_manager", "maintenance_manager"],
     "مسئول PM، مدیر فنی و طراح سامانه"),
]


def main():
    created = skipped = 0
    with SessionLocal() as db:
        for username, full_name, roles, note in PERSONNEL:
            if db.query(User).filter(User.username == username).first():
                skipped += 1
                continue
            role_objs = db.query(Role).filter(Role.name.in_(roles)).all()
            u = User(username=username, full_name=full_name,
                     password_hash=hash_password(PASSWORD), roles=role_objs)
            db.add(u)
            created += 1
            print(f"  + {username} — {full_name} ({', '.join(roles)}) — {note}")
        db.commit()
    print(f"[seed_personnel] created={created} skipped(existing)={skipped}")


if __name__ == "__main__":
    main()
