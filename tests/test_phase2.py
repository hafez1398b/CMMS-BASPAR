"""Phase 2 — SELEN AI (§21/§22/§61/§62), Inspection Checklists (§15),
Risk & Opportunity (§28), Calibration (§29), Inventory Gateway (§23),
Critical parts (§24), Internal consultation (§32), Reports (§26/§27)."""
import io

import pytest
from openpyxl import Workbook

PW = "Phase2@123"


@pytest.fixture(scope="module")
def mgr(client, admin_headers):
    r = client.post("/api/users", headers=admin_headers, json={
        "username": "p2mgr", "full_name": "p2mgr", "password": PW,
        "role_names": ["technical_manager"],
    })
    assert r.status_code == 201
    t = client.post("/api/auth/login", json={"username": "p2mgr", "password": PW})
    return {"Authorization": f"Bearer {t.json()['access_token']}"}


@pytest.fixture(scope="module")
def eq_id(client, admin_headers):
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "P2-EQ-1", "name": "تجهیز فاز دو", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"], "criticality": "critical",
        "technical_specs": {"توان": "30kW"},
    })
    assert r.status_code == 201
    return r.json()["id"]


# ---------------- SELEN -----------------------------------------------------

def test_selen_diagnose_rule_based(client, mgr, eq_id):
    r = client.post("/api/selen/diagnose", headers=mgr, json={
        "equipment_id": eq_id, "description": "صدای غیرعادی از یاتاقان و لرزش",
    })
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["probable_failures"] and out["suggested_actions"]
    assert out["safety_notes"] and out["disclaimer"]
    assert "بحرانی" in out["safety_notes"][0]  # criticality-aware advice
    assert "rule" in out["provider"]


def test_selen_needs_equipment(client, mgr):
    assert client.post("/api/selen/diagnose", headers=mgr, json={
        "equipment_id": 99999, "description": "خرابی"}).status_code == 404


def test_selen_permission_gated(client, admin_headers, eq_id):
    r = client.post("/api/users", headers=admin_headers, json={
        "username": "p2viewer", "full_name": "P2 Viewer", "password": PW,
        "role_names": ["viewer"],
    })
    t = client.post("/api/auth/login", json={"username": "p2viewer", "password": PW})
    h = {"Authorization": f"Bearer {t.json()['access_token']}"}
    # viewer role has no selen.use grant
    assert client.post("/api/selen/diagnose", headers=h, json={
        "equipment_id": eq_id, "description": "تست"}).status_code == 403


def test_selen_spare_suggestions(client, admin_headers, mgr, eq_id):
    # seed parts via gateway below first is not required; create directly
    r = client.post("/api/parts", headers=admin_headers, json={
        "code": "P2-PT-1", "name": "یاتاقان ۶۲۰۵", "stock_qty": 0, "min_qty": 2,
        "criticality": "critical", "lead_time_days": 60, "equipment_id": eq_id,
    })
    assert r.status_code == 201, r.text
    rows = client.get("/api/selen/spare-suggestions", headers=mgr).json()["items"]
    row = next(x for x in rows if x["code"] == "P2-PT-1")
    assert row["selen_score"] >= 40 and row["suggested"] == "بله"
    assert row["selen_reasons"]


# ---------------- Checklists ------------------------------------------------

@pytest.fixture(scope="module")
def tpl_id(client, mgr, eq_id):
    r = client.post("/api/checklists/templates", headers=mgr, json={
        "name": "بازرسی ماهانه P2", "period_code": "monthly",
        "equipment_id": eq_id,
        "items": ["کنترل سطح روغن", "بازرسی نشتی", "کنترل صدا"],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_checklist_full_cycle_and_escalation(client, mgr, eq_id, tpl_id):
    r = client.post("/api/checklists/runs", headers=mgr, json={
        "template_id": tpl_id, "equipment_id": eq_id,
        "run_date_jalali": "1405/05/26",
    })
    assert r.status_code == 201
    run = r.json()
    assert len(run["items"]) == 3

    # cannot finish with pending items
    assert client.post(f"/api/checklists/runs/{run['id']}/finish",
                       headers=mgr, json={}).status_code == 400

    results = ["ok", "not_ok", "requires_action"]
    for item, res in zip(run["items"], results):
        r = client.post(f"/api/checklists/runs/{run['id']}/items/{item['id']}",
                        headers=mgr, json={"result": res})
        assert r.status_code == 200
    # invalid result rejected
    assert client.post(f"/api/checklists/runs/{run['id']}/items/{run['items'][0]['id']}",
                       headers=mgr, json={"result": "maybe"}).status_code == 400

    r = client.post(f"/api/checklists/runs/{run['id']}/finish",
                    headers=mgr, json={"general_comment": "نشتی در ناحیه سیل"})
    assert r.status_code == 200 and r.json()["result_summary"] == "fail"

    # §15 escalation: not-OK → work request
    r = client.post(f"/api/checklists/runs/{run['id']}/to-request", headers=mgr)
    assert r.status_code == 201 and r.json()["request_id"]

    # closed runs are immutable
    assert client.post(f"/api/checklists/runs/{run['id']}/items/{run['items'][0]['id']}",
                       headers=mgr, json={"result": "ok"}).status_code == 400


def test_checklist_template_validation(client, mgr):
    r = client.post("/api/checklists/templates", headers=mgr, json={
        "name": "بدون آیتم", "items": [],
    })
    assert r.status_code == 400
    r = client.post("/api/checklists/templates", headers=mgr, json={
        "name": "سفارشی بدون روز", "period_code": "custom", "items": ["a"],
    })
    assert r.status_code == 400


# ---------------- Risk & Opportunity ----------------------------------------

def test_risk_scoring_and_lifecycle(client, mgr, eq_id):
    r = client.post("/api/risks", headers=mgr, json={
        "title": "ریسک توقف خط به دلیل خرابی پمپ", "scope_type": "equipment",
        "equipment_id": eq_id, "probability": 4, "impact": 5,
        "mitigation": "نگهداری پیشگیرانه + قطعه یدکی", "due_date_jalali": "1405/07/01",
    })
    assert r.status_code == 201
    risk = r.json()
    assert risk["risk_score"] == 20  # p*i

    r = client.post("/api/risks", headers=mgr, json={
        "title": "فرصت کاهش مصرف انرژی", "kind": "opportunity",
        "scope_type": "process", "probability": 2, "impact": 3,
    })
    assert r.status_code == 201 and r.json()["risk_score"] == 6

    r = client.delete(f"/api/risks/{risk['id']}", headers=mgr)
    assert r.status_code == 200
    items = client.get("/api/risks", headers=mgr).json()["items"]
    assert next(i for i in items if i["id"] == risk["id"])["status"] == "closed"


# ---------------- Calibration -------------------------------------------------

def test_calibration_dates_and_overdue(client, mgr, eq_id):
    r = client.post("/api/calibration", headers=mgr, json={
        "equipment_id": eq_id, "standard": "ISO 17025",
        "last_calibration_jalali": "1403/01/01", "interval_days": 365,
        "result": "pass",
    })
    assert r.status_code == 201
    c1 = r.json()
    assert c1["next_due"] is not None and c1["overdue"] is True  # 1403 + 1y < today

    r = client.post("/api/calibration", headers=mgr, json={
        "equipment_id": eq_id, "standard": "ISO 17025",
        "last_calibration_jalali": "1405/05/01", "interval_days": 365,
    })
    assert r.json()["overdue"] is False

    # invalid result rejected
    assert client.post("/api/calibration", headers=mgr, json={
        "equipment_id": eq_id, "result": "maybe"}).status_code == 400


# ---------------- Inventory gateway (§23) + parts ----------------------------

def _parts_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def test_parts_import_gateway_full_cycle(client, admin_headers):
    header = ["کد قطعه", "نام قطعه", "واحد", "موجودی", "حد سفارش", "درجه اهمیت",
              "زمان تأمین", "تأمین‌کننده", "قطعه جایگزین", "کد تجهیز مرتبط"]
    data = _parts_xlsx([
        header,
        ["GW-1", "فیلتر گیج", "عدد", 5, 2, "متوسط", 15, "تأمین‌کننده الف", "", ""],
        ["GW-1", "تکراری", "عدد", 1, 1, "کم", "", "", "", ""],
        ["GW-2", "", "عدد", "abc", 1, "کم", "", "", "", ""],
    ])
    r = client.post("/api/parts/import", headers=admin_headers,
                    files={"file": ("parts.xlsx", data, "application/octet-stream")})
    assert r.status_code == 200
    p = r.json()
    assert p["valid_rows"] == 1 and p["error_rows"] == 2

    r = client.post(f"/api/parts/import/{p['batch_id']}/confirm", headers=admin_headers)
    assert r.json()["created"] == 1
    items = client.get("/api/parts?q=GW-1", headers=admin_headers).json()["items"]
    assert items and items[0]["name"] == "فیلتر گیج"

    # rollback removes imported parts
    r = client.post(f"/api/parts/import/{p['batch_id']}/rollback", headers=admin_headers)
    assert r.json()["removed"] == 1
    assert client.get("/api/parts?q=GW-1", headers=admin_headers).json()["items"] == []


def test_part_duplicate_code_rejected(client, admin_headers):
    r = client.post("/api/parts", headers=admin_headers, json={
        "code": "P2-DUP", "name": "قطعه"})
    assert r.status_code == 201
    r = client.post("/api/parts", headers=admin_headers, json={
        "code": "P2-DUP", "name": "قطعه دیگر"})
    assert r.status_code == 409


# ---------------- Consultation (§32) ------------------------------------------

def test_consultation_flow(client, admin_headers, mgr):
    # start consultation with the technical-manager role
    mgr_id = client.get("/api/auth/me", headers=mgr).json()["user"]["id"]
    r = client.post("/api/messages/conversations", headers=admin_headers,
                    json={"with_user_id": mgr_id, "subject": "مشاوره فنی"})
    assert r.status_code == 201
    cid = r.json()["id"]

    r = client.post(f"/api/messages/conversations/{cid}/messages",
                    headers=admin_headers, json={"text": "سلام، سؤال فنی دارم"})
    assert r.status_code == 201

    d = client.get(f"/api/messages/conversations/{cid}", headers=mgr).json()
    assert d["messages"][-1]["text"] == "سلام، سؤال فنی دارم"

    r = client.post(f"/api/messages/conversations/{cid}/messages",
                    headers=mgr, json={"text": "بفرمایید"})
    assert r.status_code == 201

    convs = client.get("/api/messages/conversations", headers=admin_headers).json()["items"]
    conv = next(x for x in convs if x["id"] == cid)
    assert conv["unread"] == 1

    # strangers cannot enter the thread
    r = client.post("/api/users", headers=admin_headers, json={
        "username": "p2outsider", "full_name": "P2 Outsider", "password": PW,
        "role_names": ["technician"],
    })
    t = client.post("/api/auth/login", json={"username": "p2outsider", "password": PW})
    oh = {"Authorization": f"Bearer {t.json()['access_token']}"}
    assert client.get(f"/api/messages/conversations/{cid}", headers=oh).status_code == 404


# ---------------- Reports --------------------------------------------------------

def test_reports_endpoints(client, mgr):
    r = client.get("/api/reports/work-orders", headers=mgr)
    assert r.status_code == 200
    assert "rows" in r.json() and "by_status" in r.json()

    r = client.get("/api/reports/work-orders/export.csv", headers=mgr)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")

    r = client.get("/api/reports/kpis-advanced", headers=mgr)
    assert r.status_code == 200
    body = r.json()
    for key in ("mttr_minutes", "pm_compliance_pct", "backlog",
                "emergency_pct", "maintenance_cost_total", "critical_parts_low_stock"):
        assert key in body
