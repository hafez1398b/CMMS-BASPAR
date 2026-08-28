"""استیجینگ سوابق خرابی بسپار (گام ۶ بارگذاری نهایی).

قواعد:
- تاریخ فشرده 14001208 ← ۱۴۰۰-۱۲-۰۸
- «بسته شده» ← دستورکار بسته + سابقه نت · «باز» ← دستورکار باز (بدون سابقه)
- تخصیص تکنسین طبق قانون نیروی انسانی سند نهایی
- تجهیزات ثبت‌نشده ← در انتظار (ثبت نمی‌شوند تا تجهیز بیاید)
- تکراری‌های کامل حذف و پرچم می‌شوند

خروجی: data/staging/failure_history_staging.json
اجرا:  .venv/bin/python scripts/stage_failure_history.py
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SRC = ROOT / "data" / "baspar_failure_failure.csv"
SRC = ROOT / "data" / "baspar_failure_history.csv"
OUT = ROOT / "data" / "staging" / "failure_history_staging.json"

ELECTRICAL_KW = ("تابلو برق", "کنتاکتور", "پرشر سویچ", "سیستم برقی", "باتری",
                 "سنسور", "انکودر", "سیم پیچی", "سیم‌پیچی", "درایو", "پمپ بنزین")
GEARBOX_KW = ("روغن گیربکس", "کاسه نمد", "کاسه‌نمد")


def fmt_date(s):
    s = (s or "").strip()
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else s


def assign_technician(equipment, row_text, action_text):
    """قانون نیروی انسانی سند نهایی."""
    txt = f"{row_text} {action_text}"
    cat = equipment.category.name if equipment.category else ""
    fac = equipment.factory.name if equipment.factory else ""
    if any(k in txt for k in ELECTRICAL_KW):
        return "a.kavousi", "برق صنعتی (قاعده سراسری کاووسی)"
    if "جوشکاری" in txt or "جوش" in action_text:
        if cat == "ماشین‌آلات تولید" and fac == "بسپار۱":
            return "e.shahkarami", "جوشکاری ماشین‌آلات فوم"
        return "a.rezaei", "جوشکاری تیم مرکزی"
    if cat == "ماشین‌آلات تولید" and fac == "بسپار۱":
        if any(k in txt for k in GEARBOX_KW):
            return "m.pirayesh", "روغن گیربکس/کاسه‌نمد"
        return "n.babaei", "مکانیک محلی فوم (قبل از برج ۱۰)"
    if cat in ("ترابری", "تأسیسات"):
        return "m.pirayesh", "مکانیک تیم مرکزی"
    return None, "نیازمند تعیین مجری"


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    from backend.app.db import SessionLocal
    from backend.app.models import Equipment
    with SessionLocal() as db:
        existing = {e.code: e for e in
                    db.query(Equipment).filter(Equipment.deleted_at.is_(None)).all()}

        out, seen, flags = [], set(), []
        skipped_dup = pending_eq = near_dup = 0
        for i, r in enumerate(rows, start=2):
            code = r["EquipmentCode"].strip()
            date = fmt_date(r["FailureDate"])
            desc = r["Description"].strip()
            action = r["RepairAction"].strip()
            comp = r["ComponentName"].strip()
            status = r["Status"].strip()
            entry = {"row": i, "equipment_code": code, "component": comp,
                     "date": date, "description": desc, "action": action,
                     "status": "بسته" if status == "بسته شده" else "باز"}

            key = (code, date, desc)
            if key in seen:
                skipped_dup += 1
                flags.append(f"ردیف {i}: تکراری کامل — حذف شد")
                continue
            seen.add(key)

            eq = existing.get(code)
            if eq is None:
                entry["decision"] = "pending_equipment"
                pending_eq += 1
                out.append(entry)
                continue

            # تشخیص نزدیکی: شرح‌های مشابه همان تجهیز و تاریخ
            near = [o for o in out if o.get("equipment_code") == code
                    and o.get("date") == date and o.get("decision") != "pending_equipment"
                    and _similar(o["description"], desc)]
            if near:
                near_dup += 1
                flags.append(f"ردیف {i}: شبیه ردیف {near[0]['row']} ({code} {date}) — فقط اولی ثبت می‌شود")
                entry["decision"] = "skip_near_duplicate"
                out.append(entry)
                continue

            tech, basis = assign_technician(eq, f"{comp} {desc}", action)
            entry.update({
                "decision": "register",
                "equipment_name": eq.name,
                "category": eq.category.name if eq.category else None,
                "technician": tech, "technician_basis": basis,
                "wo_status": "closed" if status == "بسته شده" else "in_progress",
            })
            out.append(entry)

        summary = {
            "total": len(rows),
            "register": sum(1 for o in out if o.get("decision") == "register"),
            "register_closed": sum(1 for o in out if o.get("wo_status") == "closed"),
            "register_open": sum(1 for o in out if o.get("wo_status") == "in_progress"),
            "pending_equipment": pending_eq,
            "skipped_exact_duplicate": skipped_dup,
            "skipped_near_duplicate": near_dup,
        }
    payload = {"meta": {"status": "AWAITING_APPROVAL", "source": "data/baspar_failure_history.csv",
                        "summary": summary, "flags": flags},
               "rows": out}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("\nپرچم‌ها:")
    for f in flags:
        print(" -", f)
    pend = sorted({o["equipment_code"] for o in out if o.get("decision") == "pending_equipment"})
    print("\tتجهیزات در انتظار ثبت:", ", ".join(pend))
    techs = {}
    for o in out:
        if o.get("decision") == "register":
            techs[o["technician"]] = techs.get(o["technician"], 0) + 1
    print("توزیع تکنسین:", techs)


def _similar(a, b):
    a, b = a.replace(" ", ""), b.replace(" ", "")
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) > 4 and short in long


if __name__ == "__main__":
    main()
