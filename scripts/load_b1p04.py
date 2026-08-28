"""بارگذاری تجهیز ۴ از ۲۰ — ربات تزریق دو (B1P04) — بسپار۱.

فقط پس از تأیید صریح مسئول نت اجرا شود (پیش‌نمایش → تأیید → ثبت).
داده منبع: data/staging/b1p04_staging.json (ساختاریافته از data/injection_robot2_b1p04.md)

اجرا:  .venv/bin/python scripts/load_b1p04.py
ایدِمپوتنت: اگر کد تجهیز وجود داشته باشد، بدون تغییر خارج می‌شود.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal
from backend.app.jalali import jalali_to_gregorian
from backend.app.models import (
    ChecklistItem, ChecklistTemplate, Equipment, EquipmentCategory, Factory,
    MaintenanceHistory, MaintenancePlan, User, WorkOrder, WorkOrderApproval,
)

INTERVAL_DAYS = {"daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30,
                 "2monthly": 60, "3monthly": 90, "6monthly": 180,
                 "yearly": 365, "2yearly": 730, "custom": 0}


def jdt(jalali: str | None) -> datetime | None:
    if not jalali:
        return None
    y, m, d = (int(x) for x in jalali.split("-"))
    g = jalali_to_gregorian(y, m, d)
    return datetime(g.year, g.month, g.day, 8, 30, tzinfo=timezone.utc)


def main():
    data = json.loads((ROOT / "data/staging/b1p04_staging.json").read_text(encoding="utf-8"))
    with SessionLocal() as db:
        if db.query(Equipment).filter(Equipment.code == "B1P04").first():
            print("[load_b1p04] تجهیز B1P04 از قبل وجود دارد — هیچ تغییری داده نشد.")
            return

        factory = db.query(Factory).filter(Factory.name == data["meta"]["factory"]).one()
        cat = db.query(EquipmentCategory).filter(
            EquipmentCategory.name == data["meta"]["category"]).one()
        users = {u.username: u for u in db.query(User).all()}
        admin = users["admin"]
        approver_user = users.get("a.jahanmoradi", admin)

        # -------------------------------------------------- equipment
        e = data["equipment"]
        eq = Equipment(
            code=e["code"], name=e["name"], level="equipment",
            factory_id=factory.id, category_id=cat.id,
            model=e["model"], manufacturer=e.get("manufacturer"),
            year=e.get("year_gregorian"), dept=e["dept"],
            criticality="medium", status="active",
            component_type=e.get("component_type"),
            technical_specs=e["technical_specs"],
            dynamic_fields=e["dynamic_fields"],
            created_by=admin.id,
        )
        db.add(eq); db.flush()
        print(f"  + تجهیز: {eq.code} — {eq.name} (مدل {eq.model})")

        # -------------------------------------------------- structure
        comp_seq = 0
        for si, sub in enumerate(data["structure"], start=1):
            s = Equipment(
                code=f"B1P04-S{si}", name=sub["name"], level="subsystem",
                parent_id=eq.id, factory_id=factory.id, category_id=cat.id,
                criticality="medium", status="active", created_by=admin.id,
            )
            db.add(s); db.flush()
            for comp in sub["components"]:
                comp_seq += 1
                c = Equipment(
                    code=f"B1P04.{comp_seq}", name=comp["name"], level="component",
                    parent_id=s.id, factory_id=factory.id, category_id=cat.id,
                    criticality="medium", status="active", created_by=admin.id,
                )
                db.add(c); db.flush()
        print(f"  + ساختار: {len(data['structure'])} زیرسیستم، {comp_seq} قطعه"
              " (کنترل دما و ایمنی بدون قطعه — نیازمند تکمیل)")

        # -------------------------------------------------- PM plans
        origin = jdt(data["meta"]["pm_origin_jalali"])
        req_appr = data["meta"]["requester_approver"]
        for p in data["pm_plans"]:
            days = INTERVAL_DAYS[p["interval"]]
            desc = f"زیرسیستم: {p['subsystem']} · تیم: {p['team']} · درخواست/تأیید: {req_appr}"
            if p.get("flag"):
                desc += f" · ⚠ {p['flag']}"
            db.add(MaintenancePlan(
                equipment_id=eq.id, work_class="pm", work_title=p["title"],
                activity_type=p["type"], interval_code=p["interval"],
                interval_days=days, performer=p["performer"],
                activity_description=desc,
                last_execution=origin, next_due=None,
                is_active=True, created_by=admin.id,
            ))
        print(f"  + برنامه نگهداری: {len(data['pm_plans'])} فعالیت"
              " (آچارکشی پایه‌ها: تناوب سفارشی — در مبدأ ثبت نشده)")

        # -------------------------------------------------- work orders + history
        closed = 0
        for w in data["work_orders"]:
            tech = users.get(w["tech"])
            if w["tech"] and tech is None:
                print(f"  ! کاربر {w['tech']} یافت نشد")
            finished = jdt(w.get("date"))
            title = f"{w['part']} — {w['action']}"
            notes = []
            if w.get("note"):
                notes.append(w["note"])
            notes.append("منبع: فایل تجهیز ۴ از ۲۰ — دستورکار بسته‌شده")
            wo = WorkOrder(
                code=w["wo"], title=title[:190],
                description=(" | ".join(notes)),
                equipment_id=eq.id, status="closed",
                work_class=w["class"], execution_mode="internal",
                assigned_to=tech.id if tech else None,
                priority="normal",
                completed_at=finished, created_by=admin.id,
            )
            db.add(wo); db.flush()
            db.add(WorkOrderApproval(
                work_order_id=wo.id, step="final",
                approver_id=approver_user.id, status="approved",
                comment=f"درخواست‌دهنده/تأییدکننده: {req_appr}",
                decided_at=finished,
            ))
            db.add(MaintenanceHistory(
                equipment_id=eq.id, work_order_id=wo.id,
                work_type=w["class"], title=title[:190],
                description=f"دستورکار {w['wo']}" + (f" — {w['note']}" if w.get("note") else ""),
                technician_id=tech.id if tech else None,
                started_at=finished, finished_at=finished,
            ))
            closed += 1
        print(f"  + دستورکارهای بسته‌شده: {closed} (با سابقه نت متصل و تأیید نهایی)")

        # -------------------------------------------------- checklists
        prop = data.get("checklists_proposal", {})
        for name, period, days in (("چک‌لیست روزانه ربات تزریق (B1P04)", "custom", 1),):
            key = name.replace(" (B1P04)", "")
            items = prop.get(key, [])
            if not items:
                continue
            t = ChecklistTemplate(name=name, period_code=period, custom_days=days,
                                  equipment_id=eq.id, created_by=admin.id)
            db.add(t); db.flush()
            for i, text in enumerate(items, start=1):
                db.add(ChecklistItem(template_id=t.id, text=text, sort_order=i))
        print("  + چک‌لیست روزانه ربات تزریق متصل به تجهیز")

        db.commit()
        print(f"[load_b1p04] ثبت کامل شد — تجهیز آیدی {eq.id}")


if __name__ == "__main__":
    main()
