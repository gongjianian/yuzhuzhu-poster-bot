import os
import tempfile
from datetime import datetime
from pathlib import Path

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"

from fastapi.testclient import TestClient

from dashboard.app import create_app

app = create_app()
client = TestClient(app)

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
today = datetime.now().strftime("%Y-%m-%d")
log_file = log_dir / f"poster_bot_{today}.log"
log_file.write_text(
    "2026-04-07 08:00:01.123 | INFO | first log line\n"
    "2026-04-07 08:00:02.456 | ERROR | second error line\n"
    "2026-04-07 08:00:03.789 | INFO | line with keyword\n",
    encoding="utf-8",
)


def _get_token():
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test123"},
    )
    return resp.json()["access_token"]


def test_get_logs_today():
    token = _get_token()
    resp = client.get(
        f"/api/logs?date={today}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_lines"] == 3


def test_get_logs_filter_by_level():
    token = _get_token()
    resp = client.get(
        f"/api/logs?date={today}&level=ERROR",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_lines"] == 1


def test_get_logs_filter_by_keyword():
    token = _get_token()
    resp = client.get(
        f"/api/logs?date={today}&keyword=keyword",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_lines"] == 1


def test_get_logs_invalid_date():
    token = _get_token()
    resp = client.get(
        "/api/logs?date=../../etc/passwd",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
