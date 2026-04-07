import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"

from dashboard.app import create_app
from dashboard.database import SessionLocal, init_db
from dashboard.db_models import RunRecord
from dashboard.services.run_service import save_run_result

app = create_app()
client = TestClient(app)
init_db()


def _get_token():
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test123"},
    )
    return resp.json()["access_token"]


@pytest.fixture(autouse=True)
def seed_run_data():
    db = SessionLocal()
    db.query(RunRecord).delete()
    db.commit()
    save_run_result(
        db,
        {
            "run_id": "run-test-001",
            "product_name": "Test Product A",
            "record_id": "rec_001",
            "trigger_type": "cron",
            "status": "DONE",
            "stage": "UPLOAD_OK",
            "headline": "Test headline",
            "image_prompt": "test",
            "qc_passed": True,
            "qc_confidence": 0.95,
            "qc_issues": "[]",
            "cloud_file_id": "file_001",
            "error_msg": "",
            "duration_seconds": 30.0,
            "started_at": datetime(2026, 4, 7, 8, 0, 0),
            "finished_at": datetime(2026, 4, 7, 8, 0, 30),
        },
    )
    db.close()
    yield


def test_list_runs():
    token = _get_token()
    resp = client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_get_run_detail():
    token = _get_token()
    resp = client.get(
        "/api/runs/run-test-001",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["product_name"] == "Test Product A"


def test_get_run_not_found():
    token = _get_token()
    resp = client.get(
        "/api/runs/nonexistent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
