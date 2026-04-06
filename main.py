from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from loguru import logger
import requests

from asset_processor import process_product_image
from content_generator import generate_poster_content
from feishu_reader import fetch_pending_records, update_record_status
from image_generator import generate_poster_image
from wechat_uploader import build_cloud_path, upload_image

from qc_checker import check_poster_quality


load_dotenv()


LOCK_PATH = Path("/tmp/poster_bot.lock")
MAX_QC_RETRIES = 2


def setup_logging() -> None:
    import sys
    Path("logs").mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        "logs/poster_bot_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        level="DEBUG",
    )


def acquire_lock() -> Optional[int]:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        logger.warning("Lock file already exists: {}", LOCK_PATH)
        return None

    os.write(fd, str(os.getpid()).encode("utf-8"))
    return fd


def release_lock(lock_fd: Optional[int]) -> None:
    if lock_fd is not None:
        os.close(lock_fd)
    if LOCK_PATH.exists():
        LOCK_PATH.unlink()


def send_feishu_alert(message: str) -> None:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        logger.warning("FEISHU_WEBHOOK_URL is not configured")
        return

    try:
        response = requests.post(
            webhook_url,
            json={"msg_type": "text", "content": {"text": message}},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Failed to send Feishu alert: {}", exc)


async def process_product(record) -> Optional[str]:
    asset_dir = Path(os.getenv("ASSETS_DIR", "./assets/products"))
    if not record.asset_filename:
        error_message = "Missing product asset filename"
        await asyncio.to_thread(
            update_record_status,
            record.record_id,
            "FAILED_MANUAL",
            error_msg=error_message,
        )
        await asyncio.to_thread(
            send_feishu_alert,
            f"Poster generation failed for {record.product_name}: {error_message}",
        )
        return None

    asset_path = asset_dir / record.asset_filename

    try:
        # Step A: Generate copy & image prompt
        poster_scheme = await asyncio.to_thread(generate_poster_content, record)
        await asyncio.to_thread(update_record_status, record.record_id, "COPY_OK")
        logger.info("{}: content generated — {}", record.product_name, poster_scheme.headline)

        # Step B: Preprocess product image
        product_b64 = await asyncio.to_thread(process_product_image, str(asset_path))

        # Step C+D: Generate poster with QC retry loop
        poster_bytes = None
        qc_prompt_suffix = ""
        for attempt in range(MAX_QC_RETRIES + 1):
            poster_bytes = await asyncio.to_thread(
                generate_poster_image,
                poster_scheme.image_prompt + qc_prompt_suffix,
                product_b64,
            )
            await asyncio.to_thread(update_record_status, record.record_id, "IMAGE_OK")

            poster_b64 = base64.b64encode(poster_bytes).decode("utf-8")
            qc_result = await asyncio.to_thread(check_poster_quality, poster_b64, product_b64)

            if qc_result.passed:
                logger.info("{}: QC passed (confidence={})", record.product_name, qc_result.confidence)
                break

            logger.warning("{}: QC failed attempt {}: {}", record.product_name, attempt + 1, qc_result.issues)
            if attempt < MAX_QC_RETRIES:
                issues_str = "; ".join(qc_result.issues)
                qc_prompt_suffix = f"\n\nPREVIOUS ATTEMPT FAILED QC. Fix: {issues_str}. Strictly preserve the product."
            else:
                await asyncio.to_thread(
                    update_record_status, record.record_id, "FAILED_MANUAL",
                    error_msg=f"QC failed after {MAX_QC_RETRIES + 1} attempts: {qc_result.issues}",
                )
                await asyncio.to_thread(
                    send_feishu_alert,
                    f"{record.product_name}: QC 失败 {MAX_QC_RETRIES + 1} 次: {qc_result.issues}",
                )
                return None

        # Step E: Upload to WeChat cloud storage
        cloud_path = build_cloud_path(record.category, record.product_name)
        file_id = await asyncio.to_thread(upload_image, poster_bytes, cloud_path)
        logger.info("{}: uploaded → {}", record.product_name, file_id)
        await asyncio.to_thread(update_record_status, record.record_id, "UPLOAD_OK", file_id=file_id)
        await asyncio.to_thread(update_record_status, record.record_id, "DONE", file_id=file_id)
        logger.success("{}: DONE", record.product_name)
        return file_id
    except Exception as exc:
        error_message = str(exc)
        await asyncio.to_thread(
            update_record_status,
            record.record_id,
            "FAILED_RETRYABLE",
            error_msg=error_message,
        )
        await asyncio.to_thread(
            send_feishu_alert,
            f"Poster generation failed for {record.product_name}: {error_message}",
        )
        return None


async def run_pipeline() -> list[Optional[str]]:
    records = await asyncio.to_thread(fetch_pending_records)
    if not records:
        logger.info("No pending records found")
        return []

    return await asyncio.gather(*(process_product(record) for record in records))


def main() -> None:
    setup_logging()
    lock_fd = acquire_lock()
    if lock_fd is None:
        return

    try:
        asyncio.run(run_pipeline())
    finally:
        release_lock(lock_fd)


if __name__ == "__main__":
    main()
