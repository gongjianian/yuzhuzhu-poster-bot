import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DASHBOARD_DB_PATH", str(Path(tempfile.mkdtemp()) / "test_cat_runs.db"))
os.environ.setdefault("DASHBOARD_ADMIN_USER", "admin")
os.environ.setdefault("DASHBOARD_ADMIN_PASSWORD", "change-this")
os.environ.setdefault("DASHBOARD_SECRET_KEY", "test-secret-key-with-32-bytes-min")

import dashboard.db_models  # ensure all ORM models are registered in Base.metadata  # noqa: F401
from dashboard.app import create_app
from dashboard.database import Base, engine


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def auth_header(client):
    import os
    user = os.getenv("DASHBOARD_ADMIN_USER", "admin")
    pwd = os.getenv("DASHBOARD_ADMIN_PASSWORD", "change-this")
    resp = client.post("/api/auth/login", json={"username": user, "password": pwd})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_current_no_running(client, auth_header):
    resp = client.get("/api/category-runs/current", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json() is None


def test_list_batches_empty(client, auth_header):
    resp = client.get("/api/category-runs", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []


def test_stop_when_idle(client, auth_header):
    resp = client.post("/api/category-runs/stop", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"
