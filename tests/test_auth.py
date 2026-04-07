import os
import tempfile
from pathlib import Path

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"

from fastapi.testclient import TestClient

from dashboard.app import create_app

app = create_app()
client = TestClient(app)


def test_login_success():
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_login_wrong_user():
    resp = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "test123"},
    )
    assert resp.status_code == 401


def test_protected_endpoint_without_token():
    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401


def test_refresh_with_valid_token():
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test123"},
    )
    token = login_resp.json()["access_token"]
    resp = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
