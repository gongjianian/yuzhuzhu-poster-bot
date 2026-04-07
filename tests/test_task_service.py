import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret-key-with-32-bytes-min"

from dashboard.services import task_service
from models import ProductRecord


@pytest.mark.asyncio
async def test_execute_single_trigger_returns_busy_when_lock_is_held():
    await task_service._pipeline_lock.acquire()
    try:
        result = await task_service.execute_single_trigger("rec_busy")
    finally:
        if task_service._pipeline_lock.locked():
            task_service._pipeline_lock.release()

    assert result["status"] == "BUSY"


@pytest.mark.asyncio
async def test_execute_single_trigger_uses_all_records():
    record = ProductRecord(
        record_id="rec_001",
        product_name="Product A",
        asset_filename="asset.png",
    )
    result_payload = {
        "run_id": "run-001",
        "product_name": "Product A",
        "record_id": "rec_001",
        "trigger_type": "manual",
        "status": "DONE",
        "error_msg": "",
    }
    mock_db = MagicMock()

    with patch("feishu_reader.fetch_all_records", return_value=[record]), patch(
        "dashboard.services.task_service.process_single_product",
        new=AsyncMock(return_value=result_payload),
    ), patch("dashboard.services.task_service.SessionLocal", return_value=mock_db), patch(
        "dashboard.services.task_service.save_run_result"
    ) as mock_save, patch(
        "dashboard.services.task_service.update_daily_stats"
    ) as mock_update_stats:
        result = await task_service.execute_single_trigger("rec_001")

    assert result == result_payload
    mock_save.assert_called_once_with(mock_db, result_payload)
    mock_update_stats.assert_called_once()
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_execute_full_pipeline_sends_alert_for_failed_results():
    failed_result = {
        "run_id": "run-failed",
        "product_name": "Product B",
        "record_id": "rec_002",
        "trigger_type": "manual",
        "status": "FAILED",
        "error_msg": "generation failed",
    }
    mock_db = MagicMock()

    with patch(
        "dashboard.services.task_service.run_full_pipeline",
        new=AsyncMock(return_value=[failed_result]),
    ), patch("dashboard.services.task_service.SessionLocal", return_value=mock_db), patch(
        "dashboard.services.task_service.save_run_result"
    ) as mock_save, patch(
        "dashboard.services.task_service.update_daily_stats"
    ) as mock_update_stats, patch(
        "dashboard.services.task_service._send_alert"
    ) as mock_send_alert:
        results = await task_service.execute_full_pipeline("manual")

    assert results == [failed_result]
    mock_save.assert_called_once_with(mock_db, failed_result)
    mock_update_stats.assert_called_once()
    mock_send_alert.assert_called_once()
    mock_db.close.assert_called_once()
