import os
import tempfile
from datetime import datetime
from pathlib import Path

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")

from dashboard.database import SessionLocal, init_db
from dashboard.db_models import DailyStats, RunRecord
from dashboard.services.run_service import get_runs, save_run_result, update_daily_stats

init_db()


def _make_result(run_id: str, status: str = "DONE", product_name: str = "test-product"):
    return {
        "run_id": run_id,
        "product_name": product_name,
        "record_id": "rec_abc",
        "trigger_type": "manual",
        "status": status,
        "stage": "UPLOAD_OK",
        "headline": "test headline",
        "image_prompt": "test prompt",
        "qc_passed": True,
        "qc_confidence": 0.95,
        "qc_issues": "[]",
        "cloud_file_id": "file_123",
        "error_msg": "",
        "duration_seconds": 42.5,
        "started_at": datetime(2026, 4, 7, 8, 0, 0),
        "finished_at": datetime(2026, 4, 7, 8, 0, 42),
    }


def _reset_tables(db):
    db.query(DailyStats).delete()
    db.query(RunRecord).delete()
    db.commit()


def test_save_and_query_run():
    db = SessionLocal()
    _reset_tables(db)
    save_run_result(db, _make_result("run-001"))
    items, total = get_runs(db, page=1, page_size=10)
    assert total == 1
    assert items[0].run_id == "run-001"
    db.close()


def test_filter_by_status():
    db = SessionLocal()
    _reset_tables(db)
    save_run_result(db, _make_result("run-002", status="FAILED"))
    items, total = get_runs(db, status="FAILED")
    assert total == 1
    assert all(item.status == "FAILED" for item in items)
    db.close()


def test_update_daily_stats():
    db = SessionLocal()
    _reset_tables(db)
    save_run_result(db, _make_result("run-003", status="DONE"))
    save_run_result(db, _make_result("run-004", status="FAILED"))
    stat = update_daily_stats(db, "2026-04-07")
    assert stat.total == 2
    assert stat.success == 1
    assert stat.failed == 1
    db.close()
