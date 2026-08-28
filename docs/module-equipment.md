# ماژول تجهیزات — MODULE EQUIPMENT (BASPAR)

پیاده‌سازی کامل سند «MODULE EQUIPMENT PROMPT — BASPAR» روی هسته فاز ۰–۲.

## ساختار (§1–§3)
- سلسله‌مراتب: شرکت → **کارخانه** → **دسته** → تجهیز → زیرسیستم → قطعه/Component → زیرقطعه
- دسته‌ها Hard-Code نیستند: CRUD کامل در «داده‌های پایه» (Add/Edit/Deactivate) + دسته‌های §3 در Seed اولیه
- فیلتر «یک دسته در همه کارخانه‌ها»: فهرست تجهیزات با فیلتر category بدون factory

## کد تجهیز (§7)
- Unique با کنترل تکرار (409)؛ الگوی `[پیشوند کارخانه][کد حوزه][شناسه اختیاری][شماره]`
- دو جدول Lookup قابل مدیریت توسط Admin: `factory_prefix` (B1,B2,B3,B4,BT,FA) و `equipment_area_code` (A,P,F,PF,AF)
- SELEN در شارژ داده این کدها را رمزگشایی می‌کند؛ پیشوند ناشناخته = Flag برای Admin، هرگز حدس زده نمی‌شود

## صفحه اصلی (§4–§5)
جستجو (کد/نام/سریال/محل)، فیلترهای ترکیبی (کارخانه/دسته/وضعیت/اهمیت/…)، سه نما: **جدول / کارت / درخت**، خروجی CSV با فیلترهای جاری (§31)، انتخاب گروهی + تغییر وضعیت گروهی (حذف گروهی فقط آرشیو §34).

## Wizard افزودن تجهیز (§6) — ۹ مرحله
۱ شناسایی · ۲ اطلاعات فنی (Dynamic §10) · ۳ ساختار · ۴ برنامه نگهداری · ۵ چک‌لیست · ۶ اسناد · ۷ کالیبراسیون · ۸ بحرانی‌بودن/ریسک · ۹ تأیید → «ایجاد پرونده تجهیز». مراحل ۳–۷ قابل رد شدن و تکمیل بعدی از پرونده دیجیتال.

## مرکز شارژ داده (§6B)
مسیر Admin → «مرکز شارژ داده» (قالب استاندارد: **۶ شیت** — تجهیزات، مشخصات فنی، ساختار، قطعات، **برنامه نگهداری**، **سوابق تعمیرات**):
1. **آپلود** فایل خام چندشیت — فایل خام برای Audit نگهداری می‌شود؛ خطا در یک شیت مانع سایر شیت‌ها نیست
2. **Staging** — هیچ داده‌ای مستقیم وارد DB اصلی نمی‌شود
3. **SELEN Assisted Mapping** — پیشنهاد نگاشت ستون‌ها (سربرگ + مقدار-محور) + ردیف‌های سرگروه به‌عنوان Context + رمزگشایی کد §7 + پرکردن کارخانه از پیشوند کد و Flag ناهماهنگی (بدون اصلاح خودکار)
4. **Preview/Diff** — شمارنده New/Update/Conflict/Rejected + Fuzzy Duplicate با تصمیم کاربر؛ اعتبارسنجی شیت‌های PM/سوابق (تجهیز مرجع، تناوب، تاریخ شمسی/میلادی)
5. **ویرایش دستی** ردیف‌های مشکل‌دار · حل تعارض (جدید/ادغام/رد)
6. **Commit** — فقط رکوردهای بدون Conflict؛ برنامه‌های نت با محاسبه سررسید از تاریخ شمسی و سوابق تعمیرات واقعی نیز ثبت می‌شوند؛ کارخانه/دسته جدید با تأیید ضمنی Commit ساخته می‌شود
7. **Rollback** بر اساس Batch ID با گارد نسخه — شامل برنامه‌ها/سوابق/قطعات ایجادشده

## پرونده دیجیتال (§8) — ۱۲ تب
شناسنامه · اطلاعات فنی (Dynamic §10) · ساختار · برنامه نگهداری · چک‌لیست‌های بازرسی · سوابق نت (اصلی §16 + بازرسی §19 جدا) · قطعات و مصرفی‌ها (§21) · هزینه‌ها (§22) · اسناد (§23) · کالیبراسیون (§24) · KPI (§25) · ریسک و فرصت (§26)

## شناسنامه چاپی (§9)
لوگو + نام شرکت + همه فیلدهای شناسایی/فنی/ساختار/PM/سوابق/کالیبراسیون/هزینه — Print/PDF از مرورگر.

## سایر الزامات
- **محل استقرار (§11):** سالن/بخش/خط/موقعیت/توضیحات فقط Property تجهیز
- **SELEN پیشنهاددهنده (§14):** تشخیص‌ها Flag هستند؛ تأیید نهایی با Admin
- **حذف (§34):** حذف مستقیم ممنوع — فقط Archive؛ سوابق حفظ می‌شوند
- **Multi-User (§35):** کنترل نسخه در PUT/PATCH — Silent Overwrite ممنوع (409)
- **Real-Time (§36):** رویدادهای equipment.* روی SSE
- **تقویم شمسی (§37)** در همه Date Pickerها · **Voice→Text (§38)** روی فیلدهای توضیحات
- **Performance (§40):** Pagination + فیلتر/جستجوی سمت سرور + ایندکس‌ها
- **دسترسی‌ها (§33):** equipment.view/create/edit/delete/export/print/manage_structure/manage_pm/manage_checklist + bulk_charge.charge/approve/rollback

## API (§42)
| متد | مسیر |
|---|---|
| GET/POST | /api/equipment · GET/PUT/PATCH/DELETE /api/equipment/{id} |
| POST | /api/equipment/{id}/archive |
| GET | /api/equipment/{id}/history · /plans · /checklists · /documents(files) · /costs · /kpi · /parts |
| GET | /api/equipment/tree · /export/csv · POST /bulk/status |
| POST | /api/equipment/bulk-charge/upload |
| POST | /api/equipment/bulk-charge/{id}/mapping |
| GET | /api/equipment/bulk-charge/{id}/preview |
| POST | /api/equipment/bulk-charge/{id}/rows/{rowId} · /rows/{rowId}/resolve |
| POST | /api/equipment/bulk-charge/{id}/commit · /rollback |

## Schema (§41)
جداول موجود منطبق بر فهرست §41: factories, equipment_categories, equipment (سطح‌ها + location properties + archived_at), maintenance_plans, checklist_templates/items/runs/run_items, maintenance_history, files (EquipmentDocument), parts (EquipmentPart + Inventory), work_order_costs (EquipmentCost), calibration_items, risk_items, audit_logs, import_batches + import_batch_rows (EquipmentBulkChargeBatch + EquipmentStaging). KPIها محاسباتی (Endpoint) هستند نه جدول ذخیره‌ای.

## تست‌ها
`tests/test_bulk_charge.py` (چرخه کامل: staging/mapping/§7/fuzzy/commit/rollback/دسترسی‌ها) + `tests/test_equipment.py` (سلسله‌مراتب/تعارض نسخه/آرشیو) — بخشی از ۸۲ تست خودکار.
