"""ثبت سوابق خرابی بسپار از استیجینگ تأییدشده.

- «بسته» ← سابقه نت + دستورکار بسته‌شده (work_class=cm)
- «باز»  ← دستورکار در جریان (بدون سابقه، چون هنوز کامل نشده)
- ردیف‌های pending_equipment رد می‌شوند (تجهیزشان هنوز ثبت نشده)
کد دستورکار: {کد تجهیز}-WO-{شماره} با ادامه شماره‌های موجود.

اجرا:  .venv/bin/python scripts/load_failure_history.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import SessionLocal
from backend.app.models import Equipment, MaintenanceHistory, User, WorkOrder

STAGE = ROOT / "data" / "staging" / "failure_history_staging.json"


def parse_date(s):
    if not s or len(s) != 10:
        return None
    try:
        y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
        from backend.app.jalali import jalali_to_gregorian
        g = jalali_to_gregorian(y, m, d)
        return datetime(g.year, g.month, g.day, 12, 0, tzinfo=timezone.utc)
    except Exception:
        return None


def main():
    data = json.loads(STAGE.read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r.get("decision") == "register"]
    if not rows:
        print("! ردیف قابل ثبتی نیست"); return

    created_wo = created_hist = skipped = 0
    with SessionLocal() as db:
        users = {u.username: u for u in db.query(User).all()}
        eq_by_code = {e.code: e for e in
                      db.query(Equipment).filter(Equipment.deleted_at.is_(None)).all()}
        wo_seq = {}
        for r in rows:
            eq = eq_by_code.get(r["equipment_code"])
            if eq is None:
                skipped += 1
                continue
            at = parse_date(r["date"])
            tech = users.get(r.get("technician")) if r.get("technician") else None
            title = f"{r['component']} — {r['description']}"[:190]
            desc = r.get("action") or None

            if eq.id not in wo_seq:
                wo_seq[eq.id] = db.query(WorkOrder).filter(
                    WorkOrder.code.like(f"{eq.code}-WO-%")).count()
            wo_seq[eq.id] += 1
            wo = WorkOrder(
                code=f"{eq.code}-WO-{wo_seq[eq.id]:02d}",
                title=title, description=desc,
                equipment_id=eq.id, status=r.get("wo_status", "closed"),
                work_class="cm", priority="normal",
                assigned_to=tech.id if tech else None,
                completed_at=at if r.get("wo_status") == "closed" else None,
                created_by=users["admin"].id,
            )
            db.add(wo); db.flush()
            created_wo += 1

            if r.get("wo_status") == "closed":
                db.add(MaintenanceHistory(
                    equipment_id=eq.id, work_order_id=wo.id,
                    work_type="cm", title=title, description=desc,
                    technician_id=tech.id if tech else None,
                    started_at=at, finished_at=at,
                ))
                created_hist += 1
        db.commit()
    print(f"[load_failure_history] دستورکار {created_wo} | سابقه {created_hist} | رد {skipped}")


if __name__ == "__main__":
    main()
