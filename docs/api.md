# API (§43 — API-First)

مستندات زنده و تعاملی: **`/api/docs`** (Swagger UI) و اسپک کامل `/api/openapi.json`.
Frontend هرگز مستقیم به دیتابیس وصل نیست؛ همه چیز از این API عبور می‌کند.

## الگوها
- احراز هویت: `Authorization: Bearer <JWT>`؛ پاسخ خطاها JSON فارسی با کد HTTP صحیح.
- به‌روزرسانی رکوردها نیازمند `version` جاری است؛ تعارض → `409` با `server_version`.
- تاریخ‌ها در Backend به ISO-8601 میلادی ذخیره می‌شوند؛ ورودی شمسی فقط در فیلدهای `*_jalali` پذیرفته می‌شود.

## فهرست مسیرها (فاز ۰)

| متد | مسیر | توضیح |
|---|---|---|
| POST | /api/auth/login | ورود + Rate Limit |
| GET | /api/auth/me | کاربر جاری + دسترسی‌ها |
| POST | /api/auth/logout / change-password | خروج / تغییر رمز |
| GET/POST/PUT/DELETE | /api/users | مدیریت کاربران (Admin) |
| GET | /api/roles · PUT /api/roles/{id}/permissions | نقش‌ها و ماتریس دسترسی |
| GET/POST/PUT/DELETE | /api/factories /api/categories /api/lookups | داده پایه |
| GET | /api/equipment | فهرست با فیلتر و صفحه‌بندی |
| GET | /api/equipment/tree | درخت کارخانه→دسته→تجهیز |
| GET/POST/PUT/DELETE | /api/equipment[/{id}] | CRUD با کنترل نسخه و Soft Delete |
| GET | /api/equipment/{id}/passport | سند تجمیعی پاسپورت |
| POST | /api/equipment/{id}/files · GET/DELETE /api/files/{id} | فایل‌ها (آپلود امن/دانلود با احراز هویت) |
| GET | /api/equipment/bulk-import/template | قالب Excel |
| POST | /api/equipment/bulk-import | آپلود → اعتبارسنجی/پیش‌نمایش |
| POST | /api/equipment/bulk-import/{id}/confirm · /rollback | تأیید تراکنشی / بازگردانی |
| GET | /api/equipment/bulk-import/batches | فهرست بسته‌ها |
| GET/POST/PUT/DELETE | /api/equipment/{id}/plans · /api/plans/{id} | برنامه نت |
| GET | /api/plans/due | سررسیدهای نزدیک/عقب‌افتاده |
| GET | /api/dashboard/kpis · /critical-equipment | KPI داشبورد |
| GET | /api/search?q= | جستجوی سراسری |
| GET | /api/audit-logs | گزارش ممیزی |
| GET/POST | /api/backup · POST /api/backup/restore | پشتیبان/بازیابی |
| GET | /api/health · /api/health/detailed | Health Check |
| GET | /api/events/stream | SSE رویدادهای لحظه‌ای |

## مسیرهای فاز ۱ (اضافه شدند)

| متد | مسیر | توضیح |
|---|---|---|
| GET/POST | /api/requests | فهرست/ایجاد درخواست (§17 با ۷ نوع) |
| POST | /api/requests/{id}/supervisor-decision · /manager-decision | تأیید سرپرست / مدیر فنی؛ تأیید مدیر = صدور خودکار دستور کار |
| GET/POST | /api/work-orders | فهرست/ایجاد دستور کار |
| GET | /api/work-orders/my-assigned | اسکوپ آفلاین تکنسین (§20B) |
| GET | /api/work-orders/{id} | جزئیات کامل (تأییدیه‌ها، تایم‌لاین، یادداشت، فایل، هزینه) |
| PUT | /api/work-orders/{id}/setup | تخصیص تکنسین + Permit (ایجاد تأییدکنندگان) |
| POST | /api/work-orders/approvals/{id}/decide | تصمیم هر تأییدکننده Permit/HSE (§19 با امضا) |
| POST | /api/work-orders/{id}/execution | start/pause/resume/finish با local_id و base_version |
| POST | /api/work-orders/{id}/notes · /files | گزارش اجرا / پیوست |
| POST | /api/work-orders/{id}/confirm · /final-approve | تأیید درخواست‌دهنده / تأیید نهایی → ثبت سوابق نت |
| POST | /api/work-orders/{id}/costs | ثبت هزینه (§25) |
| POST | /api/work-orders/{id}/offline-sync | همگام‌سازی FIFO رکوردهای آفلاین + تشخیص تعارض |
| GET | /api/work-orders/conflicts/list · POST /conflicts/{id}/resolve | حل تعارض توسط مدیر (§20B/§35) |
| GET | /api/equipment/{id}/history | سوابق اصلی نت (§16) |
| GET/POST | /api/notifications + /unread-count + /read-all | مرکز اعلان‌ها (§31) |

## مسیرهای ماژول تجهیزات (MODULE EQUIPMENT — سند مرجع BASPAR)
فهرست کامل در [docs/module-equipment.md](module-equipment.md): CRUD با PATCH و Archive، درخت، خروجی CSV، عملیات گروهی، Endpointهای پرونده دیجیتال (history/plans/checklists/documents/costs/kpi/parts/risks) و مرکز شارژ داده §6B (upload → mapping → preview → resolve → commit → rollback).

## مسیرهای فاز ۲ (اضافه شدند)

| متد | مسیر | توضیح |
|---|---|---|
| POST | /api/selen/diagnose | تحلیل SELEN (§22) — Provider-محور (§62) با Fallback خودکار |
| GET | /api/selen/spare-suggestions | امتیازدهی قطعات حیاتی (§24) |
| POST | /api/selen/structure-suggestions | پیشنهاد زیرسیستم/قطعه برای ویزارد (§3B) — فقط پیشنهاددهنده (§14) |
| POST | /api/selen/checklist-suggestions | پیشنهاد آیتم‌های فرم چک‌لیست (§5B) — فقط پیشنهاددهنده (§14) |
| GET/POST/PUT | /api/checklists/templates | قالب‌های بازرسی (ماهانه/سالانه/سفارشی §15) |
| GET/POST | /api/checklists/runs | اجراهای بازرسی |
| POST | /api/checklists/runs/{id}/items/{iid} | نتیجه آیتم (ok/not_ok/na/requires_action) |
| POST | /api/checklists/runs/{id}/finish · /to-request | بستن اجرا / ارتقاء به درخواست کار (§15) |
| GET/POST/PUT/DELETE | /api/risks | ریسک و فرصت با Risk Score = احتمال × اثر (§28) |
| GET/POST/PUT/DELETE | /api/calibration | برنامه کالیبراسیون با next_due محاسباتی (§29) |
| GET/POST/PUT/DELETE | /api/parts | قطعات/انبار (Add/Edit/Delete/Override §24) |
| GET | /api/parts/import/template | قالب Excel انبار خارجی |
| POST | /api/parts/import · /import/{id}/confirm · /rollback | درگاه ورود انبار خارجی (§23) |
| GET/POST | /api/messages/conversations[/{id}/messages] | مشاوره/پیام‌رسانی درون‌برنامه‌ای (§32) |
| GET | /api/reports/work-orders | گزارش‌ساز با فیلتر تاریخ شمسی/وضعیت (§26) |
| GET | /api/reports/work-orders/export.csv | خروجی CSV/Excel |
| GET | /api/reports/kpis-advanced | KPIهای استاندارد CMMS از داده واقعی (§27) |

## رویدادهای Real-Time (§59)
فعال: `equipment.*`, `pm.created|updated|completed`, `request.created|approved|rejected`, `workorder.created|updated|status_changed`, `notification.created`, `inventory.updated`, `message.created`, `selen.diagnosed`. رویداد `part.consumed` با اتصال مصرف قطعه به دستورکار در نسخه‌های بعدی فعال می‌شود.
