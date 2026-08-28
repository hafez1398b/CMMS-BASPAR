#!/usr/bin/env bash
# بازسازی کامل محیط پس از ریست سندباکس + اجرای سرور (یک دستور).
# ویرایش دستی لازم نیست — همه لودرها ایدمپوتنت هستند.
set -uo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  echo "[restore] ساخت محیط مجازی…"
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

if [ ! -f storage/db/cmms.db ]; then
  echo "[restore] بازسازی دیتابیس و داده‌های تأییدشده…"
  .venv/bin/python scripts/migrate.py
  .venv/bin/python scripts/seed.py
  .venv/bin/python scripts/seed_baspar3.py
  .venv/bin/python scripts/seed_personnel.py
  # ترتیب مهم: اول پرونده‌های غنی، بعد جدول تجهیزات، بعد ساختار و امتیاز و سوابق
  .venv/bin/python scripts/load_b1p01.py
  .venv/bin/python scripts/load_b1p02.py
  .venv/bin/python scripts/load_b1p04.py
  .venv/bin/python scripts/load_pm_consumables.py
  .venv/bin/python scripts/load_baspar1_equipment.py
  .venv/bin/python scripts/load_b1p03_structure.py
  .venv/bin/python scripts/load_baspar1_criticality.py --apply
  .venv/bin/python scripts/load_failure_history.py
fi

echo "[restore] اجرای سرور…"
exec bash scripts/start.sh
