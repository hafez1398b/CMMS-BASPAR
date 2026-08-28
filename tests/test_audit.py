"""Audit trail: every sensitive mutation is recorded (§39)."""


def test_login_is_audited(client, admin_headers):
    r = client.get("/api/audit-logs?action=auth.login&page_size=5", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_equipment_create_update_delete_audited(client, admin_headers):
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "AUD-EQ-1", "name": "audit target", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"],
    })
    eid = r.json()["id"]

    body = r.json()
    client.put(f"/api/equipment/{eid}", headers=admin_headers, json={
        "code": "AUD-EQ-1", "name": "audit target v2", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"], "parent_id": None,
        "criticality": body["criticality"], "status": body["status"],
        "version": body["version"],
    })
    client.delete(f"/api/equipment/{eid}", headers=admin_headers)

    logs = client.get(f"/api/audit-logs?entity_type=equipment&page_size=200", headers=admin_headers).json()
    actions = [l["action"] for l in logs["items"] if l["entity_id"] == str(eid)]
    assert "equipment.created" in actions
    assert "equipment.updated" in actions
    # §34 MODULE EQUIPMENT: deletion is archiving (soft, reversible)
    assert "equipment.archived" in actions

    upd = next(l for l in logs["items"]
               if l["entity_id"] == str(eid) and l["action"] == "equipment.updated")
    assert upd["old_values"]["name"] == "audit target"
    assert upd["new_values"]["name"] == "audit target v2"
    assert upd["ip"] is not None
    assert upd["device"] is not None
