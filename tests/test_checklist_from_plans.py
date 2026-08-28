"""بند ۶ سند بارگذاری نهایی: چک‌لیست مشتق از برنامه نت + ارتقاء به دستورکار،
و آستانه‌های امتیاز بحرانی (§4.1)."""


def test_criticality_score_thresholds():
    from backend.app.modules.bulk_charge import criticality_from_score, resolve_criticality
    assert criticality_from_score(100) == "critical"
    assert criticality_from_score(75) == "critical"
    assert criticality_from_score(74) == "high"
    assert criticality_from_score(50) == "high"
    assert criticality_from_score(49) == "medium"
    assert criticality_from_score(25) == "medium"
    assert criticality_from_score(24) == "low"
    # ارقام فارسی هم خوانده شوند
    assert resolve_criticality("۱۰۰") == ("critical", 100)
    # متن/حرف بدون امتیاز عددی
    assert resolve_criticality("بحرانی") == ("critical", None)
    assert resolve_criticality("a") == ("critical", None)
    assert resolve_criticality(None) == ("medium", None)


def _mk_equipment_with_plans(client, admin_headers, suffix):
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": f"T-CHK-{suffix}", "name": f"تجهیز تست چک‌لیست {suffix}",
        "level": "equipment", "factory_id": f["id"], "category_id": c["id"]})
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    for title, icode in (("کنترل روزانه الف", "daily"), ("نظافت ماهانه ب", "monthly")):
        rr = client.post("/api/plans", headers=admin_headers, json={
            "equipment_id": eid, "work_title": title, "activity_type": "inspection",
            "interval_code": icode, "work_class": "pm"})
        assert rr.status_code == 201, rr.text
    return eid


def test_checklist_generated_from_plans(client, admin_headers):
    eid = _mk_equipment_with_plans(client, admin_headers, "GEN")
    r = client.post(f"/api/checklists/from-plans/{eid}", headers=admin_headers)
    assert r.status_code == 201, r.text
    tpl = r.json()
    texts = [i["text"] for i in tpl["items"]]
    # آیتم‌ها عیناً از ردیف‌های برنامه نت مشتق شده‌اند — نه متن آزاد
    assert texts == ["کنترل روزانه الف", "نظافت ماهانه ب"]  # روزانه اول
    assert tpl["equipment_id"] == eid
    # ساخت مجدد → تعارض
    assert client.post(f"/api/checklists/from-plans/{eid}", headers=admin_headers).status_code == 409


def test_checklist_no_plans_rejected(client, admin_headers):
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "T-CHK-EMPTY", "name": "تجهیز بدون برنامه", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"]})
    eid = r.json()["id"]
    r2 = client.post(f"/api/checklists/from-plans/{eid}", headers=admin_headers)
    assert r2.status_code == 400


def test_not_ok_escalates_to_workorder(client, admin_headers):
    eid = _mk_equipment_with_plans(client, admin_headers, "ESC")
    tpl = client.post(f"/api/checklists/from-plans/{eid}", headers=admin_headers).json()
    run = client.post("/api/checklists/runs", headers=admin_headers,
                      json={"template_id": tpl["id"], "equipment_id": eid}).json()
    # یک آیتم را نامطلوب کن
    item = run["items"][0]
    client.post(f"/api/checklists/runs/{run['id']}/items/{item['id']}",
                headers=admin_headers, json={"result": "not_ok"})
    client.post(f"/api/checklists/runs/{run['id']}/finish", headers=admin_headers, json={})
    # ارتقاء به دستورکار
    r = client.post(f"/api/checklists/runs/{run['id']}/to-workorder", headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["work_order_id"]
    wo = client.get(f"/api/work-orders/{r.json()['work_order_id']}", headers=admin_headers).json()
    assert "نامطلوب" in wo["title"] or "نامطلوب" in wo["description"]
    assert wo["equipment_id"] == eid


def test_unnamed_equipment_rows_rejected_in_bulk_charge(client, admin_headers):
    """§3.3 سند: رکوردهای بی‌نام (Placeholder) باید Rejected شوند."""
    from backend.app.modules.bulk_charge import REQUIRED
    assert "name" in REQUIRED and "code" in REQUIRED
