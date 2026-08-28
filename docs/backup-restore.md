# پشتیبان‌گیری و بازیابی (§40, §70)

## ساخت پشتیبان
- **UI:** ادمین → پشتیبان‌گیری → «پشتیبان کامل جدید».
- **CLI:** `python scripts/backup.py`
- **API:** `POST /api/backup` (نیازمند دسترسی `backup.manage`)

هر پشتیبان یک ZIP خودکفاست: **اسنپ‌شات سازگار دیتابیس** (SQLite Online Backup API — بدون قفل شدن سرویس) + تمام فایل‌های بارگذاری‌شده + `manifest.json`. محل ذخیره: `storage/backups` (قابل‌تنظیم با `BACKUP_DIR`).

## بازیابی
- مسیر Admin → «بازیابی» روی یک فایل پشتیبان؛ قبل از جایگزینی، یک کاپی `pre-restore-*.db` نگهداری می‌شود.
- بازیابی در `audit_logs` ثبت می‌شود؛ پس از بازیابی سرویس را restart کنید.

## پشتیبان افزایشی / زمان‌بندی‌شده
برای زمان‌بندی از cron استفاده کنید:
```cron
0 2 * * *  cd /opt/cmms && .venv/bin/python scripts/backup.py >> /var/log/cmms-backup.log 2>&1
```
(پشتیبان Full هر شب؛ نگهداری N نسخه آخر به‌عهده سیاست Retention سازمان است.)

## تست بازیابی
در محیط Staging: بازیابی آخرین پشتیبان + اجرای `scripts/healthcheck.py` + بررسی چند رکورد — طبق §40 «Restore قابل تست» است.
