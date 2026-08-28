"""Equipment module: hierarchy, validation, concurrency (§11, §35)."""
import pytest


@pytest.fixture(scope="module")
def eq_id(client, admin_headers):
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "T-EQ-100", "name": "پمپ سانتریفیوژ P-100", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"],
        "manufacturer": "KSB", "criticality": "high",
        "technical_specs": {"توان": "75kW"},
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_duplicate_code_rejected(client, admin_headers, eq_id):
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "T-EQ-100", "name": "dup", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"],
    })
    assert r.status_code == 409


def test_hierarchy_levels_enforced(client, admin_headers, eq_id):
    # component cannot hang directly under equipment
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "T-EQ-100-C1", "name": "component", "level": "component", "parent_id": eq_id,
    })
    assert r.status_code == 400

    # subsystem OK
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "T-EQ-100-S1", "name": "سیستم محرک", "level": "subsystem", "parent_id": eq_id,
    })
    assert r.status_code == 201
    sid = r.json()["id"]

    # component under subsystem OK
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "T-EQ-100-S1-C1", "name": "یاتاقان", "level": "component", "parent_id": sid,
    })
    assert r.status_code == 201

    # equipment cannot have a parent
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "T-EQ-BAD", "name": "bad", "level": "equipment", "parent_id": eq_id,
    })
    assert r.status_code == 400

    # subsystem without factory/category inherits from parent implicitly
    r = client.get(f"/api/equipment/{sid}", headers=admin_headers)
    assert r.status_code == 200


def test_version_conflict_detected(client, admin_headers, eq_id):
    cur = client.get(f"/api/equipment/{eq_id}", headers=admin_headers).json()
    body = {
        "code": cur["code"], "name": cur["name"] + " (ویرایش A)", "level": cur["level"],
        "factory_id": cur["factory"]["id"], "category_id": cur["category"]["id"],
        "parent_id": None, "criticality": cur["criticality"], "status": cur["status"],
        "version": cur["version"],
    }
    # first writer wins
    r1 = client.put(f"/api/equipment/{eq_id}", headers=admin_headers, json=body)
    assert r1.status_code == 200

    # second writer with stale version → 409 (§35: silent overwrite forbidden)
    r2 = client.put(f"/api/equipment/{eq_id}", headers=admin_headers, json=body)
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert detail["error"] == "version_conflict"
    assert detail["server_version"] == cur["version"] + 1

    # missing version also rejected
    stale = dict(body)
    stale.pop("version")
    assert client.put(f"/api/equipment/{eq_id}", headers=admin_headers, json=stale).status_code == 409


def test_tree_shape(client, admin_headers):
    tree = client.get("/api/equipment/tree", headers=admin_headers).json()["tree"]
    assert tree and "categories" in tree[0]


def test_passport_aggregates(client, admin_headers, eq_id):
    p = client.get(f"/api/equipment/{eq_id}/passport", headers=admin_headers).json()
    assert p["equipment"]["id"] == eq_id
    assert len(p["structure"]) >= 2  # subsystem + component
    assert "maintenance_plans" in p and "documents" in p


def test_soft_delete_requires_children_removed_first(client, admin_headers, eq_id):
    r = client.delete(f"/api/equipment/{eq_id}", headers=admin_headers)
    assert r.status_code == 400  # has live children

    # children of children… find and delete bottom-up
    eq = client.get(f"/api/equipment/{eq_id}", headers=admin_headers).json()
    def del_children(e):
        for c in e["children"]:
            del_children(client.get(f"/api/equipment/{c['id']}", headers=admin_headers).json())
            client.delete(f"/api/equipment/{c['id']}", headers=admin_headers)
    del_children(eq)

    r = client.delete(f"/api/equipment/{eq_id}", headers=admin_headers)
    assert r.status_code == 200
    assert client.get(f"/api/equipment/{eq_id}", headers=admin_headers).status_code == 404


def test_validation_error_is_readable_persian(client, admin_headers):
    """422 responses must carry human-readable Persian messages (regression:
    the UI used to show a misleading «خطا در اتصال به سرور» toast)."""
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "T-422-1", "name": "تجهیز تست خطای اعتبارسنجی", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"]})
    assert r.status_code == 201, r.text
    eq = r.json()
    body = {"code": eq["code"], "name": eq["name"], "level": "equipment",
            "factory_id": eq["factory"]["id"], "category_id": eq["category"]["id"],
            "year": 1398, "version": eq["version"],
            "criticality": "medium", "status": "active"}
    r = client.put(f"/api/equipment/{eq['id']}", headers=admin_headers, json=body)
    assert r.status_code == 422
    data = r.json()
    assert "سال ساخت" in data["message"]
    assert "۱۸۰۰" in data["message"]
    assert isinstance(data["detail"], list) and data["detail"][0]["field"] == "year"

    # Persian digits must also fail with a readable message
    body["year"] = "۱۳۹۸"
    r = client.put(f"/api/equipment/{eq['id']}", headers=admin_headers, json=body)
    assert r.status_code == 422
    assert "عدد" in r.json()["message"]
