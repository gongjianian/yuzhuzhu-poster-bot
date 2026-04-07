import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"

from fastapi.testclient import TestClient

from dashboard.app import create_app

app = create_app()
client = TestClient(app)


def _get_token():
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test123"},
    )
    return resp.json()["access_token"]


def test_pipeline_trigger_requires_auth():
    resp = client.post("/api/pipeline/run")
    assert resp.status_code == 401


def test_pipeline_trigger_with_auth():
    token = _get_token()
    with patch(
        "dashboard.routers.pipeline_router.execute_full_pipeline",
        new=AsyncMock(return_value=[]),
    ):
        resp = client.post(
            "/api/pipeline/run",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
