# پایگاه داده (§44, §52, §58)

- **نوع:** رابطه‌ای، تراکنشی، ایندکس‌گذاری‌شده؛ پیش‌فرض SQLite (WAL + foreign_keys)، تولید PostgreSQL.
- **Migrations:** `database/migrations/mNNNN_*.py` با جدول `schema_migrations`؛ اجرا: `python scripts/migrate.py` (اید‌امپوتنت).
- **یکپارچگی داده (§58):** همه رکوردهای مهم `created_by/created_at/updated_by/updated_at` دارند؛ حذف‌های حساس Soft Delete (`deleted_at`) هستند.
- **هم‌زمانی (§35):** ستون `version` روی `equipment` و `maintenance_plans` (و WorkOrderها در فاز ۱).

## جداول اصلی

| جدول | نقش |
|---|---|
| users / roles / permissions / user_roles / role_permissions | احراز هویت و RBAC |
| factories / equipment_categories / lookup_items | داده پایه و فهرست‌های کشویی قابل‌مدیریت |
| equipment | سلسله‌مراتب تجهیز/زیرسیستم/جزء/زیرقطعه + مشخصات + فیلدهای پویا (JSON) |
| files | پیوست‌های چندریختی (entity_type/entity_id) برای تجهیز/دستورکار/… |
| maintenance_plans | برنامه نت با interval قابل‌تنظیم و next_due محاسباتی |
| import_batches / import_batch_rows | موتور Bulk Data Charge با Rollback |
| audit_logs | ردپای تغییرات (کاربر، عملیات، مقدار قدیم/جدید، IP، دستگاه) |
| notifications / work_requests / work_orders / work_order_status_log | Schema فاز ۱ (آماده، بدون UI) |

## ایندکس‌ها
`equipment(code)`, `equipment(criticality|status|factory|category)`, `maintenance_plans(next_due|equipment_id)`, `files(entity)`, `audit_logs(created_at|action|entity_type)` و سایر کلیدهای خارجی.

## جدا بودن محیط‌ها (§41)
Development با `storage/db/cmms.db` و Production با Volume/DATABASE_URL جدا — هرگز مشترک نیستند؛ تست‌ها نیز دیتابیس مستقل در `storage/tmp/tests` می‌سازند.
