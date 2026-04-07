import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "integration-test"
os.environ["DASHBOARD_SECRET_KEY"] = "integration-secret-key-with-32-bytes"

from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.database import SessionLocal, init_db
from dashboard.db_models import DailyStats, RunRecord
from dashboard.services.run_service import get_run_by_id, save_run_result, update_daily_stats

app = create_app()
client = TestClient(app)


def _configure_auth_env():
    os.environ["DASHBOARD_ADMIN_USER"] = "admin"
    os.environ["DASHBOARD_ADMIN_PASSWORD"] = "integration-test"
    os.environ["DASHBOARD_SECRET_KEY"] = "integration-secret-key-with-32-bytes"


def _get_token():
    _configure_auth_env()
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "integration-test"},
    )
    return resp.json()["access_token"]


class TestAuthFlow:
    def test_login_and_access(self):
        _configure_auth_env()
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "integration-test"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        resp = client.get(
            "/api/stats/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_unauthorized_access(self):
        resp = client.get("/api/stats/summary")
        assert resp.status_code == 401


class TestFullWorkflow:
    def setup_method(self):
        _configure_auth_env()
        init_db()
        self.db = SessionLocal()
        self.db.query(DailyStats).delete()
        self.db.query(RunRecord).delete()
        self.db.commit()
        self.token = _get_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def teardown_method(self):
        self.db.close()

    def test_runs_empty_then_populated(self):
        resp = client.get("/api/runs", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

        save_run_result(
            self.db,
            {
                "run_id": "integ-001",
                "product_name": "Integration Product",
                "record_id": "rec_integ",
                "trigger_type": "manual",
                "status": "DONE",
                "stage": "UPLOAD_OK",
                "headline": "Integration headline",
                "image_prompt": "integration prompt",
                "qc_passed": True,
                "qc_confidence": 0.9,
                "qc_issues": "[]",
                "cloud_file_id": "file_integ",
                "error_msg": "",
                "duration_seconds": 20.0,
                "started_at": datetime(2026, 4, 7, 8, 0, 0),
                "finished_at": datetime(2026, 4, 7, 8, 0, 20),
            },
        )
        update_daily_stats(self.db, "2026-04-07")

        resp = client.get("/api/runs", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

        detail = client.get("/api/runs/integ-001", headers=self.headers)
        assert detail.status_code == 200
        assert detail.json()["product_name"] == "Integration Product"
        assert get_run_by_id(self.db, "integ-001") is not None

    def test_health_logs_and_stats(self):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_date = "2026-04-07"
        log_file = log_dir / f"poster_bot_{log_date}.log"
        log_file.write_text(
            "2026-04-07 08:00:01.123 | INFO | integration log line\n",
            encoding="utf-8",
        )

        save_run_result(
            self.db,
            {
                "run_id": "integ-002",
                "product_name": "Stats Product",
                "record_id": "rec_stats",
                "trigger_type": "manual",
                "status": "DONE",
                "stage": "UPLOAD_OK",
                "headline": "Stats headline",
                "image_prompt": "stats prompt",
                "qc_passed": True,
                "qc_confidence": 0.95,
                "qc_issues": "[]",
                "cloud_file_id": "file_stats",
                "error_msg": "",
                "duration_seconds": 10.0,
                "started_at": datetime(2026, 4, 7, 9, 0, 0),
                "finished_at": datetime(2026, 4, 7, 9, 0, 10),
            },
        )
        update_daily_stats(self.db, "2026-04-07")

        with patch(
            "dashboard.routers.health_router.run_all_checks",
            return_value=[
                {
                    "name": "Feishu API",
                    "status": "ok",
                    "latency_ms": 12.0,
                    "detail": "Connection ok",
                }
            ],
        ):
            health = client.get("/api/health", headers=self.headers)
        assert health.status_code == 200
        assert len(health.json()["items"]) == 1

        logs = client.get(
            f"/api/logs?date={log_date}",
            headers=self.headers,
        )
        assert logs.status_code == 200
        assert logs.json()["total_lines"] == 1

        stats = client.get(
            "/api/stats/summary?date=2026-04-07",
            headers=self.headers,
        )
        assert stats.status_code == 200
        data = stats.json()
        assert data["total"] >= 1
        assert "success_rate" in data
