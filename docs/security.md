# امنیت (§46)

| کنترل | پیاده‌سازی |
|---|---|
| Password Hashing | PBKDF2-HMAC-SHA256 با ۳۹۰٬۰۰۰ تکرار + salt تصادفی ۱۶ بایتی برای هر کاربر |
| سیاست رمز عبور | حداقل ۸ نویسه، شامل حرف و عدد؛ تغییر رمز با تأیید رمز فعلی |
| Authentication | JWT (HS256، issuer-check، TTL پیش‌فرض ۱۲ ساعت)؛ SECRET از محیط |
| Authorization | RBAC نقش/دسترسی با Dependency Guard در تک‌تک مسیرها؛ نقش Admin ذاتاً کامل (§38) |
| Rate Limiting | تلاش ورود: ۱۰ بار در ۵ دقیقه per-IP (قابل‌تنظیم) |
| SQL Injection | فقط SQLAlchemy ORM/پارامتریزه؛ هیچ SQL رشته‌ای از ورودی کاربر |
| XSS | ساخت DOM با textContent (کتابخانه داخلی)؛ هیچ innerHTML از داده کاربر |
| CSRF | ناپذیر by-design: احراز کوکی‌محور نیست (Bearer Token در هدر) |
| Secure Upload | Whitelist پسوند، سقف حجم، نام UUID روی دیسک، دانلود فقط با احراز هویت، جلوگیری از Path Traversal |
| Secret Management | فقط `.env` (در `.gitignore`)؛ `.env.example` برای الگو |
| Concurrency | کنترل خوش‌بینانه version → بدون Silent Overwrite (§35) |
| Audit | ثبت user/action/entity/old/new/IP/device برای همه تغییرات حساس (§39) |
| Soft Delete | کاربران و تجهیزات حذف فیزیکی نمی‌شوند (§58) |

آزمون‌های امنیتی خودکار: `tests/test_rbac.py`, `tests/test_auth.py`, تست‌های آپلود/مسیر در `tests/test_misc.py`.
