"""RBAC permission matrix (§36): what each role can and cannot do."""


def test_viewer_can_view_equipment(client, viewer_headers):
    assert client.get("/api/equipment", headers=viewer_headers).status_code == 200


def test_viewer_cannot_create_equipment(client, viewer_headers):
    r = client.post("/api/equipment", headers=viewer_headers, json={
        "code": "NOPE-1", "name": "x", "level": "equipment",
    })
    assert r.status_code == 403


def test_viewer_cannot_see_users(client, viewer_headers):
    assert client.get("/api/users", headers=viewer_headers).status_code == 403


def test_viewer_cannot_see_audit(client, viewer_headers):
    assert client.get("/api/audit-logs", headers=viewer_headers).status_code == 403


def test_technician_can_view_but_not_edit(client, tech_headers):
    assert client.get("/api/equipment", headers=tech_headers).status_code == 200
    r = client.post("/api/equipment", headers=tech_headers, json={
        "code": "NOPE-2", "name": "x", "level": "equipment",
    })
    assert r.status_code == 403


def test_technician_cannot_manage_users(client, tech_headers):
    assert client.get("/api/users", headers=tech_headers).status_code == 403


def test_manager_can_create_equipment(client, manager_headers):
    r = client.get("/api/factories", headers=manager_headers)
    fid = r.json()["items"][0]["id"]
    r = client.get("/api/categories", headers=manager_headers)
    cid = r.json()["items"][0]["id"]
    r = client.post("/api/equipment", headers=manager_headers, json={
        "code": "MGR-EQ-1", "name": "Manager Equipment", "level": "equipment",
        "factory_id": fid, "category_id": cid,
    })
    assert r.status_code == 201, r.text


def test_manager_user_scope(client, manager_headers):
    # Technical manager may view users but not create/delete them,
    # and never touches backup/restore.
    assert client.get("/api/users", headers=manager_headers).status_code == 200
    r = client.post("/api/users", headers=manager_headers, json={
        "username": "nope1", "full_name": "Nope", "password": "Nope@1234",
    })
    assert r.status_code == 403
    assert client.get("/api/backup", headers=manager_headers).status_code == 403


def test_admin_can_manage_users(client, admin_headers):
    assert client.get("/api/users", headers=admin_headers).status_code == 200
    assert client.get("/api/audit-logs", headers=admin_headers).status_code == 200
    assert client.get("/api/backup", headers=admin_headers).status_code == 200


def test_invalid_token_rejected(client):
    r = client.get("/api/equipment", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
