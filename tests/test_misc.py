"""Cross-cutting: health, search, files, backup, lookups, events stream."""
import io
import zipfile

from fastapi.testclient import TestClient


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    # detailed requires authentication (fresh client = no session cookie)
    from fastapi.testclient import TestClient
    from backend.app.main import app
    fresh = TestClient(app)
    assert fresh.get("/api/health/detailed").status_code == 401


def test_health_detailed_admin(client, admin_headers):
    r = client.get("/api/health/detailed", headers=admin_headers)
    assert r.status_code == 200
    checks = r.json()["checks"]
    assert checks["database"]["ok"] and checks["storage"]["ok"] and checks["realtime"]["ok"]


def test_global_search(client, admin_headers):
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    client.post("/api/equipment", headers=admin_headers, json={
        "code": "SRCH-77", "name": "موتور جستجو", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"],
    })
    r = client.get("/api/search?q=SRCH-77", headers=admin_headers)
    assert r.status_code == 200
    assert any(e["code"] == "SRCH-77" for e in r.json()["equipment"])

    # too-short query rejected
    assert client.get("/api/search?q=a", headers=admin_headers).status_code == 422


def test_file_upload_download_delete(client, admin_headers):
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    eq = client.post("/api/equipment", headers=admin_headers, json={
        "code": "FILE-EQ-1", "name": "file host", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"],
    }).json()

    content = b"hello baspar"
    r = client.post(f"/api/equipment/{eq['id']}/files", headers=admin_headers,
                    files={"file": ("note.txt", io.BytesIO(content), "text/plain")})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]

    r = client.get(f"/api/files/{fid}/download", headers=admin_headers)
    assert r.status_code == 200 and r.content == content

    # extension whitelist enforced
    r = client.post(f"/api/equipment/{eq['id']}/files", headers=admin_headers,
                    files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")})
    assert r.status_code == 400

    # unauthorized download rejected (fresh client = no session cookie)
    from fastapi.testclient import TestClient
    from backend.app.main import app
    fresh = TestClient(app)
    assert fresh.get(f"/api/files/{fid}/download").status_code == 401

    r = client.delete(f"/api/files/{fid}", headers=admin_headers)
    assert r.status_code == 200
    assert client.get(f"/api/files/{fid}/download", headers=admin_headers).status_code == 404


def test_backup_and_listing(client, admin_headers):
    r = client.post("/api/backup", headers=admin_headers)
    assert r.status_code == 200, r.text
    filename = r.json()["filename"]

    listing = client.get("/api/backup", headers=admin_headers).json()
    assert any(b["filename"] == filename for b in listing["items"])

    # archive really contains db + manifest
    from backend.app.config import get_settings
    archive = get_settings().backup_dir / filename
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        assert "cmms.db" in names and "manifest.json" in names

    # restore works (on the same live db — safe in tests)
    r = client.post(f"/api/backup/restore?filename={filename}", headers=admin_headers)
    assert r.status_code == 200

    # path traversal blocked
    r = client.post("/api/backup/restore?filename=../../etc/passwd", headers=admin_headers)
    assert r.status_code == 404


def test_lookups_seeded(client, admin_headers):
    items = client.get("/api/lookups", headers=admin_headers).json()["items"]
    lists = {i["list_code"] for i in items}
    for needed in ("activity_type", "interval", "work_class", "equipment_status",
                   "criticality", "request_type", "cost_type"):
        assert needed in lists
    # activity types per §14
    acts = [i for i in items if i["list_code"] == "activity_type" and i["is_active"]]
    assert len(acts) >= 10


def test_roles_endpoint(client, admin_headers):
    r = client.get("/api/roles", headers=admin_headers)
    names = {x["name"] for x in r.json()["items"]}
    assert {"admin", "technical_manager", "technician", "viewer"} <= names

    viewer = next(x for x in r.json()["items"] if x["name"] == "viewer")
    assert "equipment.view" in viewer["permissions"]
    assert "equipment.delete" not in viewer["permissions"]


def test_static_frontend_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "سامانه مدیریت نت بسپار" in r.text
    r = client.get("/assets/css/design-system.css")
    assert r.status_code == 200
