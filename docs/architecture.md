# معماری سامانه — BASPAR Intelligent CMMS/EAM

## 1. ارزیابی و انتخاب Technology Stack (§4 Master Prompt)

| معیار | انتخاب | دلیل |
|---|---|---|
| Backend | **Python 3.11 + FastAPI** | ASGI ناهمگام، پشتیبانی بومی WebSocket/SSE، OpenAPI خودکار (مستندات API)، اکوسیستم Enterprise با پشتیبانی بلندمدت |
| ORM | **SQLAlchemy 2.x** | مستقل از پایگاه داده (§44)، Migration نسخه‌بندی‌شده |
| Database | **SQLite** (پیش‌فرض) / **PostgreSQL** (تولید) | رابطه‌ای، تراکنشی، ایندکس‌دار؛ تغییر فقط با `DATABASE_URL` |
| Auth | **JWT (HS256) + PBKDF2-SHA256** (۳۹۰هزار تکرار، salt مستقل) | بدون وابستگی باینری خارجی؛ سیاست رمز عبور قوی |
| Real-Time | **SSE روی Event Bus** | در فاز ۰ In-Process؛ در Multi-Server به Redis Pub/Sub تعویض می‌شود بدون تغییر کد کسب‌وکار |
| File Storage | دیسک محلی با ریشه قابل‌تنظیم | انتزاع StorageService؛ قابل تعویض به S3/MinIO |
| Frontend | **ES-Module SPA بدون وابستگی** (RTL Native) | حداکثر قابلیت انتقال (§42/§63)، بدون Build Step شکننده؛ API-First بودن یعنی تعویض Frontend بدون تغییر Backend |
| Testing | **pytest + TestClient** | ۵۸ تست خودکار در فاز ۰ |
| Logging/Audit | جدول `audit_logs` + لاگ استاندارد | §39 |
| Deployment | Docker / docker-compose / اسکریپت start | §50 |

> چرا Frontend فریم‌ورک‌دار (React/Vue) نه؟ اولویت سند کارفرما **Source-Code Independence و انتقال به سرور دیگر** است؛ SPA بدون وابستگی با همان کیفیت عملکردی، ریسک build را به صفر می‌رساند و چون معماری API-First است، در آینده می‌توان کلاینت دیگری جایگزین کرد بدون هیچ تغییری در Backend.

## 2. ساختار Modular Monolith (§2)

```
backend/app/
  main.py          ← App factory؛ مرز ماژول‌ها = Routerها
  config.py        ← تنظیمات محیطی (12-factor)
  db.py, models.py ← ORM و Schema واحد برای همه فازها
  rbac.py          ← رجیستری دسترسی‌ها + نگهبان‌ها
  security.py      ← Hash/JWT
  events.py        ← Event Bus (قابل تعویض با Redis Pub/Sub)
  audit.py         ← ثبت ممیزی
  storage.py       ← سرویس فایل
  jalali.py        ← تقویم شمسی (ذخیره میلادی ISO-8601)
  modules/         ← auth, users, base_data, equipment, bulk_import,
                     plans, dashboard, search, audit_api, files,
                     backup_api, health, events_api
```

هر ماژول مستقل و قابل‌تست است (§56)؛ Business Logic در UI نیست؛ Database Logic در Frontend نیست.

## 3. فازبندی (§1B)

- **فاز ۰ (آماده ممیزی):** Equipment + Bulk Import + Digital File + Passport، Auth + RBAC چهار نقش، Audit Log، Maintenance Plan پایه، Dashboard KPI پایه، Global Search، تقویم شمسی، Backup/Restore، Health Check.
- **فاز ۱:** Request→Work Order workflow، اجرای تکنسین + Offline Mode (§20B با Sync Queue و کنترل تعارض نسخه)، Notification Center، Permit/HSE. جداول `work_requests`، `work_orders`، `work_order_status_log`، `notifications` از ابتدا در Schema وجود دارند تا فاز ۱ بدون تغییر ساختار اجرا شود.
- **فاز ۲:** SELEN AI، مشاوره داخلی + Messenger (رابط Provider-محور)، Inspection Checklist، ریسک و فرصت، کالیبراسیون، Report Builder پیشرفته.

## 4. Real-Time & Concurrency (§33–§35)

- Eventها با نام‌گذاری §59 منتشر می‌شوند (`equipment.created`, `pm.created`, …) و کلاینت‌ها از طریق `/api/events/stream` (SSE) بدون Refresh به‌روز می‌شوند.
- هر رکورد مهم ستون `version` دارد؛ PUT بدون نسخه معتبر → **409 Conflict**؛ Silent Overwrite ممنوع.
- در حالت چندکاربره آفلاین (فاز ۱)، تعارض نسخه طبق §20B با نگهداری هر دو نسخه و ارجاع به مدیر فنی حل می‌شود.

## 5. مقیاس‌پذیری (§60)

فاز ۰: یک App Server + دیتابیس مرکزی. مسیر ارتقا:
1. چند Replica پشت Load Balancer (به‌دلیل Stateless بودن JWT).
2. تعویض Event Bus با Redis Pub/Sub (رابط `publish/subscribe` ثابت).
3. انتقال به PostgreSQL با تغییر یک متغیر محیطی.
4. جداسازی سرویس‌ها از مرز Routerها (Microservice در صورت نیاز).
