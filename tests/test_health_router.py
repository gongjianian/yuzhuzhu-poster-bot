import os
import tempfile
from pathlib import Path
from unittest.mock import patch

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


@patch(
    "dashboard.routers.health_router.run_all_checks",
    return_value=[
        {
            "name": "Feishu API",
            "status": "ok",
            "latency_ms": 50.0,
            "detail": "Connection ok",
        },
        {
            "name": "Disk Space",
            "status": "ok",
            "latency_ms": None,
            "detail": "50GB available",
        },
    ],
)
def test_health_check(mock_checks):
    token = _get_token()
    resp = client.get("/api/health", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[0]["status"] == "ok"
