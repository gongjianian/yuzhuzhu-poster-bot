import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from models import ProductRecord


@pytest.mark.asyncio
async def test_run_full_pipeline_rejects_concurrent_execution():
    from pipeline import run_full_pipeline

    record = ProductRecord(
        record_id="rec_001",
        product_name="Product A",
        asset_filename="asset.png",
    )

    async def slow_process(record, trigger_type):
        await asyncio.sleep(0.05)
        return {"record_id": record.record_id, "status": "DONE", "trigger_type": trigger_type}

    with patch("pipeline.fetch_pending_records", return_value=[record]), patch(
        "pipeline.process_single_product",
        new=AsyncMock(side_effect=slow_process),
    ):
        first, second = await asyncio.gather(
            run_full_pipeline("cron"),
            run_full_pipeline("cron"),
        )

    assert sorted([len(first), len(second)]) == [0, 1]


def test_process_single_product_missing_asset_survives_status_update_failure():
    from pipeline import process_single_product

    record = ProductRecord(
        record_id="rec_test",
        product_name="test-product",
        asset_filename="",
    )
    with patch("pipeline.update_record_status", side_effect=RuntimeError("boom")):
        result = asyncio.run(process_single_product(record))

    assert result["status"] == "FAILED"
    assert "Missing product asset" in result["error_msg"]
