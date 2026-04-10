import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"

from dashboard.database import Base
from dashboard.db_models import CategoryRunRecord
from dashboard.services.category_run_service import (
    create_batch_tasks,
    update_task_step,
    complete_task,
    fail_task,
    get_current_batch,
    get_batch_detail,
    list_batches,
)


def test_category_run_record_table_exists():
    """CategoryRunRecord model should have correct table name and columns."""
    assert CategoryRunRecord.__tablename__ == "category_run_records"
    col_names = {c.name for c in CategoryRunRecord.__table__.columns}
    assert "batch_id" in col_names
    assert "category_id" in col_names
    assert "step" in col_names
    assert "status" in col_names
    assert "material_id" in col_names


@pytest.fixture()
def db_session():
    """In-memory SQLite session for testing."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    session = Session()
    yield session
    session.close()


def test_create_batch_tasks(db_session):
    records = create_batch_tasks(
        db_session,
        batch_id="20260410_120000",
        task_defs=[
            {
                "category_id": "cat_pw_jstl",
                "category_name": "积食停滞类",
                "level1_name": "脾胃系列",
                "product_line": "五行泡浴",
                "products": ["鸡内金泡浴", "金银花泡浴"],
            },
        ],
    )
    assert len(records) == 1
    assert records[0].batch_id == "20260410_120000"
    assert records[0].status == "PENDING"
    assert json.loads(records[0].products_json) == ["鸡内金泡浴", "金银花泡浴"]


def test_update_task_step(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    update_task_step(db_session, row.id, "content")
    db_session.refresh(row)
    assert row.step == "content"
    assert row.status == "RUNNING"


def test_complete_task(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    complete_task(db_session, row.id, headline="Test", cloud_file_id="cid", material_id="mid", duration=12.5)
    db_session.refresh(row)
    assert row.status == "DONE"
    assert row.step == "done"
    assert row.headline == "Test"
    assert row.material_id == "mid"
    assert row.duration_seconds == 12.5
    assert row.finished_at is not None


def test_fail_task(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    fail_task(db_session, row.id, error_msg="boom")
    db_session.refresh(row)
    assert row.status == "FAILED"
    assert row.error_msg == "boom"


def test_get_current_batch(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    update_task_step(db_session, row.id, "image")
    result = get_current_batch(db_session)
    assert result is not None
    assert result["batch_id"] == "b1"
    assert len(result["tasks"]) == 1


def test_get_current_batch_none_when_all_done(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    complete_task(db_session, row.id, "H", "c", "m", 1.0)
    result = get_current_batch(db_session)
    assert result is None


def test_list_batches(db_session):
    create_batch_tasks(db_session, "20260410_120000", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
        {"category_id": "c2", "category_name": "B", "level1_name": "X",
         "product_line": "PL2", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    complete_task(db_session, row.id, "H", "c", "m", 1.0)
    batches = list_batches(db_session, date="2026-04-10")
    assert len(batches) == 1
    assert batches[0]["batch_id"] == "20260410_120000"
    assert batches[0]["total"] == 2
    assert batches[0]["done"] == 1


def test_get_batch_detail(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": ["P1"]},
    ])
    detail = get_batch_detail(db_session, "b1")
    assert detail is not None
    assert len(detail["tasks"]) == 1
    assert detail["tasks"][0]["category_name"] == "A"
