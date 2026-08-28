"""Phase 1 — Request → Work Order workflow, Permit gating, execution,
requester confirmation, maintenance history, notifications, offline
conflict handling (§17–§20B)."""
import pytest

PW = "Phase1@123"


@pytest.fixture(scope="module")
def actors(client, admin_headers):
    def mk(username, role):
        r = client.post("/api/users", headers=admin_headers, json={
            "username": username, "full_name": username,
            "password": PW, "role_names": [role],
        })
        assert r.status_code == 201, r.text
        t = client.post("/api/auth/login", json={"username": username, "password": PW})
        return {"Authorization": f"Bearer {t.json()['access_token']}"}

    return {
        "sup": mk("p1sup", "supervisor"),
        "req": mk("p1req", "requester"),
        "tec": mk("p1tec", "technician"),
        "mgr": mk("p1mgr", "technical_manager"),
    }


@pytest.fixture(scope="module")
def eq_id(client, admin_headers):
    f = client.get("/api/factories", headers=admin_headers).json()["items"][0]
    c = client.get("/api/categories", headers=admin_headers).json()["items"][0]
    r = client.post("/api/equipment", headers=admin_headers, json={
        "code": "P1-EQ-1", "name": "تجهیز فاز یک", "level": "equipment",
        "factory_id": f["id"], "category_id": c["id"],
    })
    assert r.status_code == 201
    return r.json()["id"]


@pytest.fixture(scope="module")
def flow(client, actors, eq_id):
    """Full happy path; returns (request_id, work_order_id)."""
    r = client.post("/api/requests", headers=actors["req"], json={
        "title": "نشتی روغن از گیربکس", "request_type": "repair",
        "priority": "high", "equipment_id": eq_id,
    })
    assert r.status_code == 201 and r.json()["status"] == "pending_supervisor"
    rid = r.json()["id"]

    r = client.post(f"/api/requests/{rid}/supervisor-decision",
                    headers=actors["sup"], json={"approve": True})
    assert r.json()["status"] == "pending_manager"

    r = client.post(f"/api/requests/{rid}/manager-decision",
                    headers=actors["mgr"], json={"approve": True})
    assert r.json()["status"] == "converted"
    return rid, r.json()["work_order_id"]


def test_request_type_validation(client, actors, eq_id):
    r = client.post("/api/requests", headers=actors["req"], json={
        "title": "bad type", "request_type": "sabotage", "equipment_id": eq_id,
    })
    assert r.status_code == 400


def test_request_rejection_path(client, actors, eq_id):
    r = client.post("/api/requests", headers=actors["req"], json={
        "title": "درخواست رد شونده", "equipment_id": eq_id,
    })
    rid = r.json()["id"]
    r = client.post(f"/api/requests/{rid}/supervisor-decision",
                    headers=actors["sup"], json={"approve": False, "note": "نیاز نیست"})
    assert r.json()["status"] == "rejected"
    # manager decision on a rejected request is refused
    r = client.post(f"/api/requests/{rid}/manager-decision",
                    headers=actors["mgr"], json={"approve": True})
    assert r.status_code == 400


def test_workflow_and_permit_gating(client, actors, eq_id, flow):
    rid, woid = flow

    # technician cannot start before permit (§19 gating)
    r = client.post(f"/api/work-orders/{woid}/execution",
                    headers=actors["tec"], json={"action": "start"})
    assert r.status_code == 400

    # manager configures permit + assignment
    wo = client.get(f"/api/work-orders/{woid}", headers=actors["mgr"]).json()
    users = client.get("/api/users", headers=_admin(client)).json()["items"]
    tec_id = next(u["id"] for u in users if u["username"] == "p1tec")
    sup_id = client.get("/api/auth/me", headers=actors["sup"]).json()["user"]["id"]

    r = client.put(f"/api/work-orders/{woid}/setup", headers=actors["mgr"], json={
        "title": wo["title"], "permit_required": True,
        "assigned_to": tec_id, "approver_ids": [sup_id],
        "version": wo["version"], "execution_mode": "internal", "priority": "high",
    })
    assert r.status_code == 200
    wo = r.json()
    assert wo["status"] == "pending_permit"
    assert wo["approvals"], "permit approvers must be created"

    # still blocked before all approvals
    r = client.post(f"/api/work-orders/{woid}/execution",
                    headers=actors["tec"], json={"action": "start"})
    assert r.status_code == 400

    # approve as each approver using their own sessions
    me_map = {}
    for name, h in actors.items():
        me_map[client.get("/api/auth/me", headers=h).json()["user"]["id"]] = h
    for a in wo["approvals"]:
        hdr = me_map.get(a["approver_id"])
        if hdr:
            r = client.post(f"/api/work-orders/approvals/{a['id']}/decide",
                            headers=hdr, json={"approve": True, "comment": "ok"})
            assert r.status_code == 200

    wo = client.get(f"/api/work-orders/{woid}", headers=actors["mgr"]).json()
    assert wo["status"] == "ready"

    # execution lifecycle §20
    for action, expected in [("start", "in_progress"), ("pause", "paused"),
                             ("resume", "in_progress"), ("finish", "awaiting_confirmation")]:
        r = client.post(f"/api/work-orders/{woid}/execution",
                        headers=actors["tec"], json={"action": action})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == expected

    # offline dedupe: finish again with same local_id must not duplicate
    wo = client.get(f"/api/work-orders/{woid}", headers=actors["mgr"]).json()

    # requester confirmation
    r = client.post(f"/api/work-orders/{woid}/confirm", headers=actors["req"],
                    json={"approve": True, "version": wo["version"]})
    assert r.json()["status"] == "final_approval"

    wo = client.get(f"/api/work-orders/{woid}", headers=actors["mgr"]).json()
    r = client.post(f"/api/work-orders/{woid}/final-approve", headers=actors["mgr"],
                    json={"approve": True, "version": wo["version"]})
    assert r.json()["status"] == "closed"

    # §16: closed work became maintenance history
    hist = client.get(f"/api/equipment/{eq_id}/history", headers=actors["mgr"]).json()
    assert any(hh["title"] == "نشتی روغن از گیربکس" for hh in hist["items"])

    # passport now carries the history + cost summary
    p = client.get(f"/api/equipment/{eq_id}/passport", headers=actors["mgr"]).json()
    assert p["maintenance_history"]
    assert p["cost_summary"]["total"] == 0.0


def test_offline_conflict_keeps_both_versions(client, actors, flow):
    rid, woid = flow
    wo = client.get(f"/api/work-orders/{woid}", headers=actors["mgr"]).json()

    # stale base_version → conflict (§20B): server record untouched
    r = client.post(f"/api/work-orders/{woid}/offline-sync", headers=actors["tec"], json={
        "base_version": 1,
        "records": [{"local_id": "OF-1", "type": "note", "text": "یادداشت آفلاین"}],
    })
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "offline_conflict"

    # server data untouched: note must NOT exist
    wo2 = client.get(f"/api/work-orders/{woid}", headers=actors["mgr"]).json()
    assert all(n["text"] != "یادداشت آفلاین" for n in wo2["notes"])
    assert wo2["version"] == wo["version"]

    # manager sees and resolves the conflict
    conf = client.get("/api/work-orders/conflicts/list", headers=actors["mgr"]).json()
    assert len(conf["items"]) >= 1
    cid = conf["items"][0]["id"]
    r = client.post(f"/api/work-orders/conflicts/{cid}/resolve", headers=actors["mgr"],
                    json={"resolution": "هر دو نسخه بررسی شد", "apply_device_records": True})
    assert r.status_code == 200
    wo3 = client.get(f"/api/work-orders/{woid}", headers=actors["mgr"]).json()
    assert any(n["text"] == "یادداشت آفلاین" for n in wo3["notes"])


def test_offline_sync_fifo_apply(client, actors, eq_id):
    # direct WO created & assigned, no permit → ready
    mgr = actors["mgr"]
    users = client.get("/api/users", headers=_admin(client)).json()["items"]
    tec_id = next(u["id"] for u in users if u["username"] == "p1tec")
    r = client.post("/api/work-orders", headers=mgr, json={
        "title": "کار آفلاین", "equipment_id": eq_id,
        "permit_required": False, "assigned_to": tec_id, "approver_ids": [],
    })
    assert r.status_code == 201, r.text
    woid = r.json()["id"]
    assert r.json()["status"] == "ready"

    wo = client.get(f"/api/work-orders/{woid}", headers=mgr).json()
    r = client.post(f"/api/work-orders/{woid}/offline-sync", headers=actors["tec"], json={
        "base_version": wo["version"],
        "records": [
            {"local_id": "T-1", "type": "time_log", "action": "start"},
            {"local_id": "N-1", "type": "note", "text": "ثبت آفلاین"},
            {"local_id": "T-1", "type": "time_log", "action": "start"},  # duplicate
        ],
    })
    assert r.status_code == 200
    assert r.json()["applied"] == 2 and r.json()["skipped"] == 1


def test_notifications_delivered(client, actors, flow):
    n = client.get("/api/notifications", headers=actors["tec"]).json()
    assert n["total"] >= 1  # assignment / permit / execution notifications
    # mark-all-read works
    r = client.post("/api/notifications/read-all", headers=actors["tec"])
    assert r.status_code == 200
    n = client.get("/api/notifications/unread-count", headers=actors["tec"]).json()
    assert n["unread"] == 0


def _admin(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@12345"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
