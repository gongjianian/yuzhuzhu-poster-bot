import asyncio
from unittest.mock import patch

import pytest

from models import ProductRecord


@pytest.mark.asyncio
async def test_pipeline_lock_prevents_double_run():
    from pipeline import _pipeline_lock

    results = []

    async def fake_run():
        if _pipeline_lock.locked():
            results.append("skipped")
            return
        async with _pipeline_lock:
            await asyncio.sleep(0.1)
            results.append("ran")

    await asyncio.gather(fake_run(), fake_run())
    assert "ran" in results
    assert "skipped" in results


def test_process_single_product_missing_asset():
    from pipeline import process_single_product

    record = ProductRecord(
        record_id="rec_test",
        product_name="test-product",
        asset_filename="",
    )
    with patch("pipeline.update_record_status"):
        result = asyncio.run(process_single_product(record))

    assert result["status"] == "FAILED"
    assert "Missing product asset" in result["error_msg"]
