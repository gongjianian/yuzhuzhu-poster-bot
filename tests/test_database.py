import os
import tempfile
from pathlib import Path

os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test-password"
os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")

from dashboard.database import SessionLocal, init_db
from dashboard.db_models import DailyStats, RunRecord


def test_init_db_creates_tables():
    init_db()
    db = SessionLocal()
    db.query(RunRecord).count()
    db.query(DailyStats).count()
    db.close()


def test_run_record_insert():
    init_db()
    db = SessionLocal()
    record = RunRecord(
        run_id="test-001",
        product_name="test-product",
        record_id="rec_abc",
        trigger_type="manual",
        status="RUNNING",
    )
    db.add(record)
    db.commit()
    result = db.query(RunRecord).filter_by(run_id="test-001").first()
    assert result is not None
    assert result.product_name == "test-product"
    db.close()


def test_daily_stats_insert():
    init_db()
    db = SessionLocal()
    stat = DailyStats(
        date="2026-04-07",
        total=10,
        success=8,
        failed=2,
        avg_duration=45.5,
    )
    db.add(stat)
    db.commit()
    result = db.query(DailyStats).filter_by(date="2026-04-07").first()
    assert result.success == 8
    db.close()
