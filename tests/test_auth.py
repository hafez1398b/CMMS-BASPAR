"""Authentication: login, session, password change (§46)."""


def test_login_success(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@12345"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "admin"
    assert "equipment.view" in body["permissions"]


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong-pass-1"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "ghost", "password": "whatever1"})
    assert r.status_code == 401


def test_me_requires_token(client):
    # fresh client without any session cookie
    from fastapi.testclient import TestClient
    from backend.app.main import app
    fresh = TestClient(app)
    assert fresh.get("/api/auth/me").status_code == 401


def test_me_with_token(client, admin_headers):
    r = client.get("/api/auth/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "admin"


def test_change_password_flow(client, admin_headers):
    # create a throwaway user
    r = client.post("/api/users", headers=admin_headers, json={
        "username": "pwuser", "full_name": "PW User",
        "password": "Init@1234", "role_names": ["viewer"],
    })
    assert r.status_code == 201
    uid = r.json()["id"]

    login = client.post("/api/auth/login", json={"username": "pwuser", "password": "Init@1234"})
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # wrong current password rejected
    r = client.post("/api/auth/change-password", headers=h,
                    json={"current_password": "bad", "new_password": "NewPass@123"})
    assert r.status_code == 400

    # weak password rejected
    r = client.post("/api/auth/change-password", headers=h,
                    json={"current_password": "Init@1234", "new_password": "12345678"})
    assert r.status_code == 400

    r = client.post("/api/auth/change-password", headers=h,
                    json={"current_password": "Init@1234", "new_password": "NewPass@123"})
    assert r.status_code == 200

    assert client.post("/api/auth/login", json={"username": "pwuser", "password": "NewPass@123"}).status_code == 200

    # cleanup: deactivate
    client.delete(f"/api/users/{uid}", headers=admin_headers)
