"""بارگذاری تجهیز ۲ از ۲۰ — دستگاه تزریق دو (B1P02) — بسپار۱.

فقط پس از تأیید صریح مسئول نت اجرا شود (پیش‌نمایش → تأیید → ثبت).
داده منبع: data/staging/b1p02_staging.json (ساختاریافته از data/injection2_b1p02.md)

اجرا:  .venv/bin/python scripts/load_b1p02.py
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
    MaintenanceHistory, MaintenancePlan, RiskItem, User,
)

INTERVAL_DAYS = {"daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30,
                 "2monthly": 60, "3monthly": 90, "6monthly": 180,
                 "yearly": 365, "2yearly": 730, "custom": 0}


def jdt(jalali: str) -> datetime:
    y, m, d = (int(x) for x in jalali.split("-"))
    g = jalali_to_gregorian(y, m, d)
    return datetime(g.year, g.month, g.day, 8, 30, tzinfo=timezone.utc)


def main():
    data = json.loads((ROOT / "data/staging/b1p02_staging.json").read_text(encoding="utf-8"))
    with SessionLocal() as db:
        if db.query(Equipment).filter(Equipment.code == "B1P02").first():
            print("[load_b1p02] تجهیز B1P02 از قبل وجود دارد — هیچ تغییری داده نشد.")
            return

        factory = db.query(Factory).filter(Factory.name == data["meta"]["factory"]).one()
        cat = db.query(EquipmentCategory).filter(
            EquipmentCategory.name == data["meta"]["category"]).one()
        users = {u.username: u for u in db.query(User).all()}
        admin = users["admin"]

        # -------------------------------------------------- equipment
        e = data["equipment"]
        eq = Equipment(
            code=e["code"], name=e["name"], level="equipment",
            factory_id=factory.id, category_id=cat.id,
            model=e["model"], manufacturer=e.get("manufacturer"),
            year=e["year_gregorian"], dept=e["dept"],
            criticality="medium", status="active",
            component_type=e.get("component_type"),
            technical_specs=e["technical_specs"],
            dynamic_fields=e["dynamic_fields"],
            created_by=admin.id,
        )
        db.add(eq); db.flush()
        print(f"  + تجهیز: {eq.code} — {eq.name}")

        # -------------------------------------------------- structure
        comp_seq = 0
        for si, sub in enumerate(data["structure"], start=1):
            s = Equipment(
                code=f"B1P02-S{si}", name=sub["name"], level="subsystem",
                parent_id=eq.id, factory_id=factory.id, category_id=cat.id,
                criticality="medium", status="active", created_by=admin.id,
            )
            db.add(s); db.flush()
            for comp in sub["components"]:
                comp_seq += 1
                c = Equipment(
                    code=f"B1P02.{comp_seq}", name=comp["name"], level="component",
                    parent_id=s.id, factory_id=factory.id, category_id=cat.id,
                    criticality="medium", status="active", created_by=admin.id,
                )
                db.add(c); db.flush()
        print(f"  + ساختار: {len(data['structure'])} زیرسیستم، {comp_seq} قطعه"
              " (سیستم ایمنی بدون قطعه — نیازمند بازدید میدانی)")

        # -------------------------------------------------- PM plans
        origin = jdt(data["meta"]["pm_origin_jalali"])
        approver = data["meta"]["requester_approver"]
        for p in data["pm_plans"]:
            days = INTERVAL_DAYS[p["interval"]]
            db.add(MaintenancePlan(
                equipment_id=eq.id, work_class="pm", work_title=p["title"],
                activity_type=p["type"], interval_code=p["interval"],
                interval_days=days, performer=p["performer"],
                activity_description=(f"زیرسیستم: {p['subsystem']} · تیم: {p['team']} · "
                                      f"درخواست/تأیید: {approver}"),
                last_execution=origin, next_due=None,
                is_active=True, created_by=admin.id,
            ))
        print(f"  + برنامه نگهداری: {len(data['pm_plans'])} فعالیت"
              f" (مبدأ سررسید {data['meta']['pm_origin_jalali']})")

        # -------------------------------------------------- history
        for rec in data["history"]:
            tech = users.get(rec["tech"])
            if rec["tech"] and tech is None:
                print(f"  ! کاربر {rec['tech']} یافت نشد — سابقه بدون تکنسین ثبت می‌شود")
            finished = jdt(rec["date"])
            action = rec.get("action")
            title = (f"{rec['part']} — {action}" if action
                     else f"{rec['part']} — (اقدام در منبع ثبت نشده)")
            db.add(MaintenanceHistory(
                equipment_id=eq.id, work_type="cm", title=title[:190],
                description=f"منبع: فایل تجهیز ۲ از ۲۰. قاعده انتساب: {rec['basis']}",
                technician_id=tech.id if tech else None,
                started_at=finished, finished_at=finished,
            ))
        print(f"  + سوابق: {len(data['history'])} رکورد"
              " (۱۵ رکوردِ ۱۴۰۲ بدون شرح اقدام — خلأ سند مبدأ)")

        # -------------------------------------------------- risk (سطح خط تولید)
        r = data["risk"]
        db.add(RiskItem(
            scope_type=r.get("scope", "process"), kind="risk", equipment_id=None,
            title=r["title"][:190], description=r["source"] + " — " + r["mitigation"],
            probability=r["probability"], impact=r["impact"],
            risk_score=r["probability"] * r["impact"],
            mitigation=r["mitigation"], status="open",
            owner_id=users.get("h.bayramian", admin).id, created_by=admin.id,
        ))
        print("  + ریسک سطح خط تولید: پک هیدرولیک دستگاه‌های تزریق (B1P01+B1P02)")

        # -------------------------------------------------- checklists
        prop = data.get("checklists_proposal", {})
        for name, period, days in (
            ("چک‌لیست روزانه تزریق (B1P02)", "custom", 1),
            ("چک‌لیست ماهانه تزریق (B1P02)", "monthly", None),
        ):
            key = name.replace(" (B1P02)", "")
            items = prop.get(key, [])
            if not items:
                continue
            t = ChecklistTemplate(name=name, period_code=period, custom_days=days,
                                  equipment_id=eq.id, created_by=admin.id)
            db.add(t); db.flush()
            for i, text in enumerate(items, start=1):
                db.add(ChecklistItem(template_id=t.id, text=text, sort_order=i))
        print("  + چک‌لیست‌ها: روزانه و ماهانه متصل به تجهیز")

        db.commit()
        print(f"[load_b1p02] ثبت کامل شد — تجهیز آیدی {eq.id}")


if __name__ == "__main__":
    main()
