"""Test fixtures — isolated temp database/storage per test session (§49)."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Environment MUST be set before the app package is imported.
_TMP = Path(os.environ.get("CMMS_TEST_TMP", ROOT / "storage" / "tmp" / "tests"))
_TMP.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["STORAGE_ROOT"] = str(_TMP / "storage")
os.environ["BACKUP_DIR"] = str(_TMP / "backups")
os.environ["LOGIN_RATE_LIMIT"] = "10000"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789-0123456789"


@pytest.fixture(scope="session")
def client():
    # fresh database each session
    db_file = _TMP / "test.db"
    for f in (db_file, *_TMP.glob("test.db*")):
        try:
            f.unlink()
        except FileNotFoundError:
            pass

    from fastapi.testclient import TestClient
    from backend.app.db import SessionLocal
    from backend.app.main import app
    from backend.app.migrate import run_migrations
    from backend.app.seeds import seed

    run_migrations(verbose=False)
    with SessionLocal() as db:
        seed(db, verbose=False)

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@12345"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def make_user(client, admin_headers, username, password, role):
    r = client.post("/api/users", headers=admin_headers, json={
        "username": username, "full_name": username, "password": password,
        "role_names": [role],
    })
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def viewer_headers(client, admin_headers):
    t = make_user(client, admin_headers, "viewer1", "Viewer@123", "viewer")
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="session")
def tech_headers(client, admin_headers):
    t = make_user(client, admin_headers, "tech1", "Tech@1234", "technician")
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="session")
def manager_headers(client, admin_headers):
    t = make_user(client, admin_headers, "manager1", "Manager@123", "technical_manager")
    return {"Authorization": f"Bearer {t}"}
