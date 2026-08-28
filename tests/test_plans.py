"""Maintenance plan: intervals, next-due computation, concurrency (§14, §35)."""
import pytest


@pytest.fixture(scope="module")
def eq_id(client, admin_headers):
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "T-PLAN-EQ", "name": "تجهیز برنامه تست", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"],
    })
    assert r.status_code == 201
    return r.json()["id"]


def test_create_plan_computes_next_due(client, admin_headers, eq_id):
    r = client.post("/api/plans", headers=admin_headers, json={
        "equipment_id": eq_id, "work_title": "روانکاری یاتاقان‌ها",
        "activity_type": "lubrication", "interval_code": "monthly",
        "last_execution_jalali": "1404/04/01", "performer": "تیم نت",
    })
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["interval_days"] == 30
    assert p["next_due"] is not None and p["last_execution"] is not None
    # 1404/04/01 + 30 days ≈ 1404/04/31
    from datetime import datetime, timedelta
    le = datetime.fromisoformat(p["last_execution"])
    nd = datetime.fromisoformat(p["next_due"])
    assert (nd - le).days == 30


def test_invalid_interval_rejected(client, admin_headers, eq_id):
    r = client.post("/api/plans", headers=admin_headers, json={
        "equipment_id": eq_id, "work_title": "عنوان تست", "interval_code": "every-moon",
    })
    assert r.status_code == 400


def test_invalid_activity_type_rejected(client, admin_headers, eq_id):
    r = client.post("/api/plans", headers=admin_headers, json={
        "equipment_id": eq_id, "work_title": "عنوان تست", "activity_type": "teleport",
    })
    assert r.status_code == 400


def test_plan_version_conflict(client, admin_headers, eq_id):
    r = client.post("/api/plans", headers=admin_headers, json={
        "equipment_id": eq_id, "work_title": "بازرسی ماهانه", "interval_code": "monthly",
    })
    p = r.json()
    body = {
        "equipment_id": eq_id, "work_title": "بازرسی ماهانه (ویرایش)",
        "interval_code": "weekly", "version": p["version"],
    }
    assert client.put(f"/api/plans/{p['id']}", headers=admin_headers, json=body).status_code == 200
    assert client.put(f"/api/plans/{p['id']}", headers=admin_headers, json=body).status_code == 409


def test_due_plans_endpoint(client, admin_headers):
    r = client.get("/api/plans/due?days=3650", headers=admin_headers)
    assert r.status_code == 200
    assert "items" in r.json()
