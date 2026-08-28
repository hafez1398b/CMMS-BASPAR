# سامانه مدیریت نت هوشمند بسپار — BASPAR Intelligent CMMS/EAM

سامانه Enterprise مدیریت نگهداری و تعمیرات: چندکاربره، Real-Time، امن، مقیاس‌پذیر، با تقویم شمسی، پرونده دیجیتال تجهیز، شناسنامه چاپی (Passport)، ورود گروهی داده‌های قدیمی (Bulk Data Charge)، گزارش ممیزی کامل و پشتیبان‌گیری/بازیابی.

> فازبندی: فاز ۰ (آماده ممیزی)، فاز ۱ (چرخه درخواست→دستورکار، Permit/HSE، اجرا + زیرساخت آفلاین، مرکز اعلان‌ها) و فاز ۲ (SELEN AI با معماری Provider-محور، چک‌لیست بازرسی، ریسک/فرصت، کالیبراسیون، انبار/Critical Parts، مشاوره داخلی، گزارش‌ساز/KPI) پیاده‌سازی شده‌اند — Schema از ابتدا برای همه فازها طراحی شده است.

## شروع سریع

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # SECRET_KEY را عوض کنید
bash scripts/start.sh           # migrate + seed + اجرا روی http://localhost:8000
```

**ورود اولیه:** `admin` / `Admin@12345`

### Docker
```bash
cp .env.example .env
docker compose up -d --build
```

### تست‌ها
```bash
python -m pytest tests/ -q      # 58 تست خودکار
```

## ساختار
```
backend/     FastAPI + SQLAlchemy (ماژول‌های مستقل: auth, equipment, plans, …)
frontend/    SPA فارسی RTL بدون وابستگی (Design System صنعتی)
database/    migrations نسخه‌بندی‌شده
scripts/     migrate / seed / backup / healthcheck / start
tests/       pytest (auth, RBAC, concurrency, bulk import, تقویم, …)
docs/        معماری، دیتابیس، API، نصب، استقرار، امنیت، نقش‌ها، SELEN
storage/     دیتابیس + فایل‌ها + پشتیبان‌ها (خارج از Git)
```

## مستندات
- معماری و انتخاب Stack: [docs/architecture.md](docs/architecture.md)
- API (زنده در `/api/docs`): [docs/api.md](docs/api.md)
- امنیت: [docs/security.md](docs/security.md) · نقش‌ها: [docs/user-roles.md](docs/user-roles.md)
- نصب/استقرار/پشتیبان: [docs/installation.md](docs/installation.md), [docs/deployment.md](docs/deployment.md), [docs/backup-restore.md](docs/backup-restore.md)

سامانه هیچ وابستگی به هیچ ابزار ساخت خاصی ندارد: Source + Migration + Seed + `.env` برای اجرای مستقل کافی است.
