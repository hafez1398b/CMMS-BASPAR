# نصب و راه‌اندازی (§51, §70)

## پیش‌نیازها
- Python 3.11+ (و `python3-venv`)
- برای Docker: docker + docker-compose

## حالت توسعه (Local)
```bash
git clone <repo> && cd CMMS-BASPAR
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # SECRET_KEY را عوض کنید
bash scripts/start.sh          # migrate + seed + uvicorn روی 0.0.0.0:8000
```
سپس `http://localhost:8000` — ورود اولیه: `admin` / `Admin@12345` (در `.env` قابل تغییر).

## استقرار با Docker (توصیه‌شده برای Production)
```bash
cp .env.example .env    # SECRET_KEY الزامی است
docker compose up -d --build
```

## اجرای تست‌ها (§49)
```bash
python -m pytest tests/ -q      # ۵۸ تست: auth، RBAC، concurrency، import، تقویم، …
```

## Health Check (§70)
```bash
python scripts/healthcheck.py http://127.0.0.1:8000
```

## محیط‌ها (§51)
Development / Staging / Production فقط با `ENVIRONMENT` و `DATABASE_URL` متفاوت‌اند؛ دیتابیس هر محیط جداست (§41).

## Seed اولیه (§70)
`scripts/seed.py` (اید‌امپوتنت): نقش‌ها و دسترسی‌ها، کاربر Admin، فهرست‌های کشویی (انواع فعالیت §14، دوره‌های تکرار، کلاس کار، وضعیت‌ها، اهمیت، انواع درخواست §17، انواع هزینه §25) و کارخانه/دسته‌بندی‌های اولیه. **فهرست واقعی کارخانه‌ها/دسته‌ها را کارفرما از مسیر «داده‌های پایه» در UI تکمیل می‌کند.**
