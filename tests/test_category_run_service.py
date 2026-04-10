import os
import tempfile
from pathlib import Path

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"

from dashboard.db_models import CategoryRunRecord


def test_category_run_record_table_exists():
    """CategoryRunRecord model should have correct table name and columns."""
    assert CategoryRunRecord.__tablename__ == "category_run_records"
    col_names = {c.name for c in CategoryRunRecord.__table__.columns}
    assert "batch_id" in col_names
    assert "category_id" in col_names
    assert "step" in col_names
    assert "status" in col_names
    assert "material_id" in col_names
