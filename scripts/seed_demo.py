"""سناریوی نمونهٔ کامل و به‌هم‌پیوسته (دمو) — برای دیدن همهٔ ماژول‌ها تا انتها.

این داده صرفاً نمایشی است (§57) و جدا از دادهٔ واقعی کارفرما نگه داشته می‌شود.
Idempotent: با بررسی کد نمونه، از تکرار جلوگیری می‌کند.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal
from backend.app.models import (
    User, Role, Factory, EquipmentCategory, Equipment, MaintenancePlan,
    WorkRequest, WorkOrder, WorkOrderTimeLog, WorkOrderNote, WorkOrderCost,
    WorkOrderApproval, MaintenanceHistory, Part, CalibrationItem, RiskItem,
    ChecklistTemplate, ChecklistItem, ChecklistRun, ChecklistRunItem,
)

NOW = datetime.now(timezone.utc)
D = lambda days: NOW - timedelta(days=days)


def _u(db, name):
    return db.query(User).filter(User.username == name).first()


def _factory(db, name):
    return db.query(Factory).filter(Factory.name == name).first()


def _cat(db, name):
    return db.query(EquipmentCategory).filter(EquipmentCategory.name == name).first()


def main():
    with SessionLocal() as db:
        mgr = _u(db, "manager1") or _u(db, "admin")
        tech = _u(db, "technician1") or _u(db, "admin")
        req_u = _u(db, "requester1") or _u(db, "admin")
        sup = _u(db, "supervisor1") or _u(db, "admin")

        # If the rich demo already exists, skip.
        if db.query(Equipment).filter(Equipment.code == "B1PT-D01").one_or_none():
            print("[demo] rich demo already present — skipping")
            return

        f1 = _factory(db, "بسپار۱") or _factory(db, "کارخانه مرکزی بسپار")
        f2 = _factory(db, "بسپار۲") or f1
        f3 = _factory(db, "بسپار۳") or f1
        ft = _factory(db, "ترابری") or f1
        mac = _cat(db, "ماشین‌آلات تولید") or _cat(db, "تولیدی")
        utl = _cat(db, "تأسیسات")
        ele = _cat(db, "برق")
        anb = _cat(db, "انبارش") or mac

        def eq(code, name, fac, cat, crit="medium", status="active", specs=None,
               hall=None, line=None, parent=None, level="equipment"):
            e = Equipment(code=code, name=name, level=level, parent_id=parent.id if parent else None,
                          factory_id=fac.id if fac else None, category_id=cat.id if cat else None,
                          criticality=crit, status=status, technical_specs=specs or {},
                          hall=hall, line=line, manufacturer="نمونه", created_by=mgr.id)
            db.add(e); db.flush()
            return e

        # ---- Equipment across factories (with structure) ----
        a1 = eq("B1PT-D01", "خط تزریق فوم ۱", f1, mac, "critical", "active",
                {"توان": "75kW", "فشار": "10bar"}, hall="سوله 1", line="خط A")
        eq("B1PT-D01-SS1", "سیستم هیدرولیک", f1, mac, "high", "active", parent=a1, level="subsystem")
        eq("B1PT-D01-CP1", "پمپ هیدرولیک", f1, mac, "high", "active", parent=a1, level="component")
        a2 = eq("B1UT-D02", "کمپرسور هوای فشرده C-101", f1, utl, "critical", "active",
                {"ظرفیت": "12m3/min"}, hall="موتورخانه")
        a3 = eq("B2EL-D03", "تابلو برق اصلی MCC", f2, ele, "high", "active", hall="اتاق برق")
        a4 = eq("B3TR-D04", "لیفتراک ۲.۵ تن تویوتا", ft, anb, "medium", "active")
        a5 = eq("B1UT-D05", "چیلر تراکمی CH-201", f1, utl, "high", "under_maintenance",
                {"ظرفیت": "350kW"}, hall="پشت بام")
        a6 = eq("B4PT-D06", "دستگاه برش CNC", f3, mac, "medium", "active", hall="سوله 4")

        targets = [a1, a2, a3, a4, a5, a6]

        # ---- PM plans ----
        for i, e in enumerate(targets):
            db.add(MaintenancePlan(equipment_id=e.id, work_class="pm", work_title=f"بازرسی دوره‌ای {e.name}",
                                   activity_type="inspection", interval_code="monthly", interval_days=30,
                                   performer="تیم نت", duration_minutes=60, last_execution=D(40 + i),
                                   next_due=D(40 + i) + timedelta(days=30), created_by=mgr.id))
            db.add(MaintenancePlan(equipment_id=e.id, work_class="pm", work_title=f"روانکاری {e.name}",
                                   activity_type="lubrication", interval_code="weekly", interval_days=7,
                                   performer="تکنسین", duration_minutes=30, last_execution=D(10),
                                   next_due=D(10) + timedelta(days=7), created_by=mgr.id))

        # ---- Requests + Work Orders across statuses ----
        def wo(e, title, status, wclass="cm", prio="normal", days=5, cost=None):
            r = WorkRequest(title=title, request_type="repair", equipment_id=e.id,
                            status="converted", requested_by=req_u.id)
            db.add(r); db.flush()
            w = WorkOrder(code=f"WO-D{e.id}-{days}", title=title, request_id=r.id, equipment_id=e.id,
                          status=status, work_class=wclass, priority=prio, assigned_to=tech.id,
                          created_by=mgr.id, completed_at=D(days) if status == "closed" else None)
            db.add(w); db.flush()
            db.add(WorkOrderTimeLog(work_order_id=w.id, user_id=tech.id, action="start", at=D(days) - timedelta(hours=2)))
            db.add(WorkOrderTimeLog(work_order_id=w.id, user_id=tech.id, action="finish", at=D(days)))
            db.add(WorkOrderNote(work_order_id=w.id, user_id=tech.id, text="اقدام انجام شد؛ تست نهایی OK."))
            if status == "pending_permit":
                db.add(WorkOrderApproval(work_order_id=w.id, step="permit", approver_id=sup.id, status="pending"))
            if cost:
                for ct, amt, desc in cost:
                    db.add(WorkOrderCost(work_order_id=w.id, cost_type=ct, amount=amt, description=desc, created_by=mgr.id))
            if status == "closed":
                db.add(MaintenanceHistory(equipment_id=e.id, work_order_id=w.id, work_type=wclass,
                                          title=title, technician_id=tech.id, started_at=D(days) - timedelta(hours=2),
                                          finished_at=D(days), duration_minutes=120))
            return w

        wo(a2, "تعویض روغن کمپرسور C-101", "closed", "pm", "normal", 6,
           [("part", 4500000, "فیلتر روغن"), ("internal_labor", 2800000, "۲ ساعت تکنسین")])
        wo(a5, "رفع نشتی مبرد چیلر CH-201", "in_progress", "cm", "high", 2,
           [("part", 8200000, "مبرد R134a")])
        wo(a1, "تعویض سیل هیدرولیک خط تزریق", "awaiting_confirmation", "cm", "high", 1)
        wo(a3, "بازرسی ترموگرافی تابلو MCC", "pending_permit", "pm", "normal", 0)
        wo(a4, "سرویس دوره‌ای لیفتراک", "ready", "pm", "normal", 0)

        # ---- Parts ----
        for i, e in enumerate(targets[:4]):
            db.add(Part(code=f"P-D{i}a", name=f"قطعه یدکی {e.name}", unit="عدد", stock_qty=1, min_qty=2,
                        criticality="high", lead_time_days=21, supplier="بازرگانی نمونه", equipment_id=e.id, created_by=mgr.id))
            db.add(Part(code=f"P-D{i}b", name=f"بلبرینگ {e.name}", unit="عدد", stock_qty=6, min_qty=2,
                        criticality="critical", lead_time_days=45, supplier="نمونه", equipment_id=e.id, created_by=mgr.id))

        # ---- Calibration ----
        db.add(CalibrationItem(equipment_id=a3.id, standard="ISO 17025", last_calibration=D(400),
                               interval_days=365, next_due=D(400) + timedelta(days=365), result="pass", created_by=mgr.id))
        db.add(CalibrationItem(equipment_id=a6.id, standard="ISO 17025", last_calibration=D(100),
                               interval_days=365, next_due=D(100) + timedelta(days=365), result="pass", created_by=mgr.id))

        # ---- Risks ----
        db.add(RiskItem(scope_type="equipment", kind="risk", equipment_id=a2.id, title="خرابی یاتاقان کمپرسور",
                        probability=3, impact=5, risk_score=15, mitigation="پایش ارتعاش هفتگی",
                        owner_id=mgr.id, status="mitigating", created_by=mgr.id))
        db.add(RiskItem(scope_type="process", kind="opportunity", title="هوشمندسازی قرائت فشار",
                        probability=4, impact=3, risk_score=12, mitigation="بررسی فنی-اقتصادی",
                        owner_id=mgr.id, status="open", created_by=mgr.id))

        # ---- Checklist template + a run ----
        t = ChecklistTemplate(name="بازرسی ماهانه کمپرسور", period_code="monthly", equipment_id=a2.id, created_by=mgr.id)
        db.add(t); db.flush()
        items = []
        for i, text in enumerate(["کنترل سطح روغن", "بازرسی نشتی", "کنترل ارتعاش و صدا"]):
            it = ChecklistItem(template_id=t.id, text=text, sort_order=i); db.add(it); db.flush(); items.append(it)
        run = ChecklistRun(template_id=t.id, equipment_id=a2.id, technician_id=tech.id, run_date=D(3),
                           status="complete", result_summary="fail", completed_at=D(3))
        db.add(run); db.flush()
        for idx, it in enumerate(items):
            db.add(ChecklistRunItem(run_id=run.id, item_id=it.id,
                                    result="not_ok" if idx == 1 else "ok",
                                    comment="نشتی جزئی" if idx == 1 else None))

        db.commit()
        print(f"[demo] rich demo ready: {len(targets)} equipment + structure, PM, WO in 5 statuses, parts, calibration, risks, checklist")


if __name__ == "__main__":
    main()
