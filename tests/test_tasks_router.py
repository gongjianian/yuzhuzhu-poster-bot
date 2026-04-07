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
from dashboard.routers.tasks_router import MAX_BATCH_SIZE
from models import ProductRecord

app = create_app()
client = TestClient(app)


def _get_token():
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test123"},
    )
    return resp.json()["access_token"]


def _mock_records():
    return [
        ProductRecord(
            record_id="rec_001",
            product_name="Product A",
            category="skin",
            status="PENDING",
            asset_filename="a.png",
        ),
        ProductRecord(
            record_id="rec_002",
            product_name="Product B",
            category="bath",
            status="DONE",
            asset_filename="b.png",
        ),
    ]


@patch("dashboard.routers.tasks_router.fetch_all_records")
def test_list_tasks(mock_fetch):
    mock_fetch.return_value = _mock_records()
    token = _get_token()
    resp = client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@patch("dashboard.routers.tasks_router.fetch_all_records")
def test_list_tasks_filter_by_status(mock_fetch):
    mock_fetch.return_value = _mock_records()
    token = _get_token()
    resp = client.get(
        "/api/tasks?status=PENDING",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["record_id"] == "rec_001"


def test_list_tasks_requires_auth():
    resp = client.get("/api/tasks")
    assert resp.status_code == 401


@patch("dashboard.routers.tasks_router.fetch_all_records")
@patch(
    "dashboard.routers.tasks_router.execute_single_trigger",
    new=AsyncMock(return_value={"status": "DONE"}),
)
def test_trigger_single(mock_fetch):
    mock_fetch.return_value = _mock_records()
    token = _get_token()
    resp = client.post(
        "/api/tasks/rec_001/trigger",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


@patch("dashboard.routers.tasks_router.fetch_all_records")
def test_trigger_single_returns_404_for_missing_record(mock_fetch):
    mock_fetch.return_value = _mock_records()
    token = _get_token()
    resp = client.post(
        "/api/tasks/rec_missing/trigger",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@patch(
    "dashboard.routers.tasks_router.execute_single_trigger",
    new=AsyncMock(return_value={"status": "DONE"}),
)
def test_batch_trigger():
    token = _get_token()
    resp = client.post(
        "/api/tasks/batch-trigger",
        json=["rec_001", "rec_002"],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_batch_trigger_rejects_empty_list():
    token = _get_token()
    resp = client.post(
        "/api/tasks/batch-trigger",
        json=[],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


def test_batch_trigger_rejects_oversized_batch():
    token = _get_token()
    resp = client.post(
        "/api/tasks/batch-trigger",
        json=[f"rec_{index:03d}" for index in range(MAX_BATCH_SIZE + 1)],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
