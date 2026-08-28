# استقرار و عملیات (§50, §60)

## Docker Compose (پیش‌فرض)
- سرویس `app`: API + Frontend + Real-Time در یک پروسس (Modular Monolith).
- Volume `cmms-storage`: دیتابیس + فایل‌ها + پشتیبان‌ها → **قابل Backup و انتقال به سرور دیگر**.
- Healthcheck داخلی هر ۳۰ ثانیه `/api/health` را می‌سنجد.

## انتقال به سرور دیگر (§42)
1. `docker compose down`
2. کپی Volume (یا `scripts/backup.py`) به سرور جدید
3. `docker compose up -d --build` با همان `.env`
هیچ وابستگی به محیط ساخت وجود ندارد؛ همه چیز از Source + Migration + Seed بازتولید می‌شود.

## مقیاس‌پذیری (§60)
| مرحله | تغییر |
|---|---|
| ۱ | چند Replica از `app` پشت Load Balancer (JWT Stateless) |
| ۲ | افزودن Redis و تعویض Event Bus با Pub/Sub (رابط ثابت است) |
| ۳ | PostgreSQL مرکزی (`DATABASE_URL`) |
| ۴ | تفکیک Routerها به میکروسرویس در صورت نیاز |

## سه محیط (§51)
با Tag/پروفایل جدا در Compose یا کلاستر جدا؛ `ENVIRONMENT=staging|production` فقط رفتار لاگ/خطا را تغییر می‌دهد.

## خطرات و قواعد ایمنی (§68)
هیچ‌گاه بدون تأیید صریح: DROP DATABASE / TRUNCATE / حذف پروژه / RESET. بازیابی پشتیبان فقط از مسیر Admin و با لاگ ممیزی انجام می‌شود.
