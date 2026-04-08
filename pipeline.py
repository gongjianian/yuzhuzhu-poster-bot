from __future__ import annotations

import asyncio
import base64
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from asset_processor import process_product_image
from content_generator import generate_poster_content
from feishu_reader import fetch_pending_records, update_record_status
from image_generator import generate_poster_image
from qc_checker import check_poster_quality
from wechat_uploader import build_cloud_path, upload_image

load_dotenv()

MAX_QC_RETRIES = 2

_pipeline_lock = asyncio.Lock()


def _build_result(record, trigger_type: str) -> dict:
    start_time = datetime.now()
    return {
        "run_id": f"run-{uuid.uuid4().hex[:12]}",
        "product_name": record.product_name,
        "record_id": record.record_id,
        "trigger_type": trigger_type,
        "status": "RUNNING",
        "stage": "",
        "headline": "",
        "image_prompt": "",
        "qc_passed": None,
        "qc_confidence": None,
        "qc_issues": "[]",
        "cloud_file_id": "",
        "error_msg": "",
        "started_at": start_time,
        "finished_at": None,
        "duration_seconds": None,
    }


def _finalize_result(result: dict, status: str, error_msg: str = "") -> dict:
    result["status"] = status
    result["error_msg"] = error_msg
    result["finished_at"] = datetime.now()
    result["duration_seconds"] = (
        result["finished_at"] - result["started_at"]
    ).total_seconds()
    return result


async def _safe_update_status(
    record_id: str,
    status: str,
    *,
    file_id: str = "",
    error_msg: str = "",
) -> None:
    try:
        await asyncio.to_thread(
            update_record_status,
            record_id,
            status,
            file_id=file_id,
            error_msg=error_msg,
        )
    except Exception:
        logger.exception(
            "Failed to update Feishu record {} to status {}",
            record_id,
            status,
        )


async def process_single_product(record, trigger_type: str = "cron") -> dict:
    result = _build_result(record, trigger_type)
    asset_dir = Path(os.getenv("ASSETS_DIR", "./assets/products"))

    if not record.asset_filename:
        _finalize_result(result, "FAILED", "Missing product asset filename")
        await _safe_update_status(
            record.record_id,
            "FAILED_MANUAL",
            error_msg=result["error_msg"],
        )
        return result

    asset_path = asset_dir / record.asset_filename

    try:
        poster_scheme = await asyncio.to_thread(generate_poster_content, record)
        result["stage"] = "COPY_OK"
        result["headline"] = poster_scheme.headline
        result["image_prompt"] = poster_scheme.image_prompt
        await _safe_update_status(record.record_id, "COPY_OK")
        logger.info("{}: content generated -> {}", record.product_name, poster_scheme.headline)

        product_b64 = await asyncio.to_thread(process_product_image, str(asset_path))

        poster_bytes = None
        qc_prompt_suffix = ""
        for attempt in range(MAX_QC_RETRIES + 1):
            poster_bytes = await asyncio.to_thread(
                generate_poster_image,
                poster_scheme.image_prompt + qc_prompt_suffix,
                product_b64,
            )
            result["stage"] = "IMAGE_OK"
            await _safe_update_status(record.record_id, "IMAGE_OK")

            poster_b64 = base64.b64encode(poster_bytes).decode("utf-8")
            qc_result = await asyncio.to_thread(
                check_poster_quality,
                poster_b64,
                product_b64,
            )
            result["qc_passed"] = qc_result.passed
            result["qc_confidence"] = qc_result.confidence
            result["qc_issues"] = json.dumps(qc_result.issues, ensure_ascii=False)

            if qc_result.passed:
                logger.info(
                    "{}: QC passed (confidence={})",
                    record.product_name,
                    qc_result.confidence,
                )
                break

            logger.warning(
                "{}: QC failed attempt {}: {}",
                record.product_name,
                attempt + 1,
                qc_result.issues,
            )
            if attempt < MAX_QC_RETRIES:
                issues_str = "; ".join(qc_result.issues)
                qc_prompt_suffix = (
                    "\n\nPREVIOUS ATTEMPT FAILED QC. "
                    f"Fix: {issues_str}. Strictly preserve the product."
                )
            else:
                _finalize_result(
                    result,
                    "FAILED",
                    f"QC failed after {MAX_QC_RETRIES + 1} attempts: {qc_result.issues}",
                )
                await _safe_update_status(
                    record.record_id,
                    "FAILED_MANUAL",
                    error_msg=result["error_msg"],
                )
                return result

        cloud_path = build_cloud_path(record.category, record.product_name)
        file_id = await asyncio.to_thread(upload_image, poster_bytes, cloud_path)
        result["stage"] = "UPLOAD_OK"
        result["cloud_file_id"] = file_id
        await _safe_update_status(
            record.record_id,
            "DONE",
            file_id=file_id,
        )

        _finalize_result(result, "DONE")
        logger.success(
            "{}: DONE in {:.1f}s",
            record.product_name,
            result["duration_seconds"],
        )
        return result
    except Exception as exc:
        # Log full stack trace so failures are debuggable in systemd.log
        logger.exception(
            "Pipeline failed for {} (stage={}): {}",
            record.product_name,
            result.get("stage", ""),
            exc,
        )
        _finalize_result(result, "FAILED", f"{type(exc).__name__}: {exc}")
        await _safe_update_status(
            record.record_id,
            "FAILED_RETRYABLE",
            error_msg=result["error_msg"],
        )
        return result


async def run_full_pipeline(trigger_type: str = "cron") -> list[dict]:
    if _pipeline_lock.locked():
        logger.warning("Pipeline is already running, skipping")
        return []

    try:
        await asyncio.wait_for(_pipeline_lock.acquire(), timeout=0.001)
    except asyncio.TimeoutError:
        logger.warning("Pipeline is already running, skipping")
        return []

    try:
        records = await asyncio.to_thread(fetch_pending_records)
        if not records:
            logger.info("No pending records found")
            return []

        results = []
        for record in records:
            results.append(await process_single_product(record, trigger_type))
        return results
    finally:
        _pipeline_lock.release()


async def trigger_single_product(record_id: str) -> dict:
    if _pipeline_lock.locked():
        return {
            "run_id": "",
            "product_name": "",
            "record_id": record_id,
            "trigger_type": "manual",
            "status": "BUSY",
            "stage": "",
            "headline": "",
            "image_prompt": "",
            "qc_passed": None,
            "qc_confidence": None,
            "qc_issues": "[]",
            "cloud_file_id": "",
            "error_msg": "Pipeline is already running",
            "started_at": datetime.now(),
            "finished_at": datetime.now(),
            "duration_seconds": 0.0,
        }

    async with _pipeline_lock:
        all_records = await asyncio.to_thread(fetch_pending_records)
        record = next((r for r in all_records if r.record_id == record_id), None)
        if record is None:
            return {
                "run_id": "",
                "product_name": "",
                "record_id": record_id,
                "trigger_type": "manual",
                "status": "FAILED",
                "stage": "",
                "headline": "",
                "image_prompt": "",
                "qc_passed": None,
                "qc_confidence": None,
                "qc_issues": "[]",
                "cloud_file_id": "",
                "error_msg": f"Record {record_id} not found or not in PENDING/FAILED_RETRYABLE status",
                "started_at": datetime.now(),
                "finished_at": datetime.now(),
                "duration_seconds": 0.0,
            }
        return await process_single_product(record, trigger_type="manual")
