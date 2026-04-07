import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"

from dashboard.app import create_app
from dashboard.database import SessionLocal, init_db
from dashboard.db_models import DailyStats

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
def seed_stats_data():
    db = SessionLocal()
    db.query(DailyStats).delete()
    db.commit()
    db.add(
        DailyStats(
            date="2026-04-07",
            total=10,
            success=8,
            failed=2,
            avg_duration=35.0,
        )
    )
    db.add(
        DailyStats(
            date="2026-04-06",
            total=5,
            success=5,
            failed=0,
            avg_duration=28.0,
        )
    )
    db.commit()
    db.close()
    yield


def test_stats_summary():
    token = _get_token()
    resp = client.get(
        "/api/stats/summary?date=2026-04-07",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert data["success_rate"] == 80.0


def test_stats_trend():
    token = _get_token()
    resp = client.get(
        "/api/stats/trend?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 2
