from __future__ import annotations

import asyncio
import os
from datetime import datetime

import requests
from loguru import logger

from dashboard.database import SessionLocal
from dashboard.services.run_service import save_run_result, update_daily_stats
from pipeline import _pipeline_lock, process_single_product, run_full_pipeline


def _send_alert(message: str) -> None:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        return
    try:
        requests.post(
            webhook_url,
            json={"msg_type": "text", "content": {"text": message}},
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.error("Failed to send Feishu alert: {}", exc)


async def execute_full_pipeline(trigger_type: str = "cron") -> list[dict]:
    results = await run_full_pipeline(trigger_type)

    db = SessionLocal()
    try:
        for result in results:
            save_run_result(db, result)
            if result["status"] == "FAILED":
                await asyncio.to_thread(
                    _send_alert,
                    f"Poster generation failed: {result['product_name']} -> {result['error_msg']}"
                )

        today = datetime.now().strftime("%Y-%m-%d")
        update_daily_stats(db, today)
    finally:
        db.close()

    success = sum(1 for result in results if result["status"] == "DONE")
    failed = sum(1 for result in results if result["status"] == "FAILED")
    logger.info("Pipeline complete: {} success, {} failed", success, failed)
    return results


async def execute_single_trigger(record_id: str) -> dict:
    from feishu_reader import fetch_all_records

    if _pipeline_lock.locked():
        return {
            "run_id": "",
            "status": "BUSY",
            "error_msg": "Pipeline is already running, try again later",
        }

    try:
        await asyncio.wait_for(_pipeline_lock.acquire(), timeout=0.001)
    except asyncio.TimeoutError:
        return {
            "run_id": "",
            "status": "BUSY",
            "error_msg": "Pipeline is already running, try again later",
        }

    try:
        all_records = await asyncio.to_thread(fetch_all_records)
        record = next((item for item in all_records if item.record_id == record_id), None)

        if record is None:
            return {
                "run_id": "",
                "status": "FAILED",
                "error_msg": f"Record not found: {record_id}",
            }

        result = await process_single_product(record, trigger_type="manual")
    finally:
        _pipeline_lock.release()

    db = SessionLocal()
    try:
        save_run_result(db, result)
        today = datetime.now().strftime("%Y-%m-%d")
        update_daily_stats(db, today)
    finally:
        db.close()

    if result["status"] == "FAILED":
        await asyncio.to_thread(
            _send_alert,
            f"Poster generation failed: {result['product_name']} -> {result['error_msg']}"
        )

    return result
