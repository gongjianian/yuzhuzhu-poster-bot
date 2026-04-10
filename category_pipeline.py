"""Daily category-based poster generation pipeline.

For each of the 10 symptom subcategories:
  1. Fetch all products from Feishu
  2. AI matches products → per-product-line groups (CategoryPosterTask)
  3. For each group: generate content → generate image → upload → register material

Entry point: run_daily_category_pipeline()
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path

from loguru import logger

from asset_processor import process_product_image
from category_content_generator import generate_category_poster_content
from feishu_reader import fetch_all_records
from image_generator import generate_poster_image
from models import CategoryPosterTask
from symptom_categories import ALL_SYMPTOM_CATEGORIES
from symptom_matcher import match_products_to_symptom
from wechat_uploader import (
    build_material_cloud_path,
    register_material,
    upload_image,
)
from dashboard.database import SessionLocal
from dashboard.services.category_run_service import (
    create_batch_tasks,
    update_task_step,
    complete_task as db_complete_task,
    fail_task as db_fail_task,
)

_PIPELINE_LOCK = asyncio.Lock()


def _build_result(task: CategoryPosterTask) -> dict:
    return {
        "run_id": f"cat-{uuid.uuid4().hex[:12]}",
        "category_id": task.category_id,
        "category_name": task.category_name,
        "product_line": task.product_line,
        "products": [p.product_name for p in task.products],
        "status": "RUNNING",
        "headline": "",
        "cloud_file_id": "",
        "material_id": "",
        "error_msg": "",
        "started_at": datetime.now(),
        "finished_at": None,
        "duration_seconds": None,
    }


def _finalize(result: dict, status: str, error_msg: str = "") -> dict:
    result["status"] = status
    result["error_msg"] = error_msg
    result["finished_at"] = datetime.now()
    result["duration_seconds"] = (
        result["finished_at"] - result["started_at"]
    ).total_seconds()
    return result


def _update_step(db_row_id: int | None, step: str) -> None:
    """Write step progress to DB. Silently ignores errors."""
    if db_row_id is None:
        return
    try:
        db = SessionLocal()
        update_task_step(db, db_row_id, step)
        db.close()
    except Exception:
        pass


async def process_category_task(task: CategoryPosterTask, db_row_id: int | None = None) -> dict:
    """Generate and upload one poster for a symptom × product-line group."""
    result = _build_result(task)
    asset_dir = Path(os.getenv("ASSETS_DIR", "./assets/products"))

    # Use the first product's asset image as the representative visual
    primary_product = task.products[0]
    asset_path = asset_dir / primary_product.asset_filename

    try:
        # Step 1: generate content (scheme + image_prompt)
        await asyncio.to_thread(_update_step, db_row_id, "content")
        scheme = await asyncio.to_thread(generate_category_poster_content, task)
        result["headline"] = scheme.headline
        logger.info(
            "[{}×{}] content OK → {}",
            task.category_name, task.product_line, scheme.headline,
        )

        # Step 2: load product image
        await asyncio.to_thread(_update_step, db_row_id, "image")
        product_b64 = await asyncio.to_thread(
            process_product_image, str(asset_path)
        )

        # Step 3: generate poster image
        poster_bytes = await asyncio.to_thread(
            generate_poster_image, scheme.image_prompt, product_b64
        )
        logger.info("[{}×{}] image generated", task.category_name, task.product_line)

        # Step 4: upload to cloud storage
        await asyncio.to_thread(_update_step, db_row_id, "uploading")
        cloud_path = build_material_cloud_path(
            level1_category_id=task.level1_category_id,
            category_id=task.category_id,
            product_type=task.product_line,
        )
        file_id = await asyncio.to_thread(upload_image, poster_bytes, cloud_path)
        result["cloud_file_id"] = file_id

        # Step 5: register in mini-program materials collection
        await asyncio.to_thread(_update_step, db_row_id, "registering")
        products_label = "×".join(p.product_name for p in task.products)
        title = f"{task.category_name} · {products_label}"
        material_id = await asyncio.to_thread(
            register_material,
            file_id,
            title,
            task.category_id,
            task.level1_category_id,
            task.product_line,
        )
        result["material_id"] = material_id

        _finalize(result, "DONE")
        logger.success(
            "[{}×{}] DONE in {:.1f}s → material_id={}",
            task.category_name, task.product_line,
            result["duration_seconds"], material_id,
        )
        if db_row_id:
            try:
                db = SessionLocal()
                db_complete_task(
                    db, db_row_id,
                    result.get("headline", ""),
                    result.get("cloud_file_id", ""),
                    result.get("material_id", ""),
                    result.get("duration_seconds") or 0.0,
                )
                db.close()
            except Exception:
                pass
        return result

    except FileNotFoundError as exc:
        msg = f"product asset not found: {exc}"
        logger.error("[{}×{}] {}", task.category_name, task.product_line, msg)
        _finalize(result, "FAILED", msg)
        if db_row_id:
            try:
                db = SessionLocal()
                db_fail_task(db, db_row_id, msg)
                db.close()
            except Exception:
                pass
        return result
    except Exception as exc:
        logger.exception(
            "[{}×{}] unexpected error", task.category_name, task.product_line
        )
        msg = str(exc)
        _finalize(result, "FAILED", msg)
        if db_row_id:
            try:
                db = SessionLocal()
                db_fail_task(db, db_row_id, msg)
                db.close()
            except Exception:
                pass
        return result


async def run_daily_category_pipeline(
    batch_id: str | None = None,
    cancel_event: asyncio.Event | None = None,
) -> list[dict]:
    """Run the full daily pipeline: all 10 symptom categories.

    Fetches all products from Feishu once, then sequentially processes
    each category to avoid overwhelming the API.
    """
    async with _PIPELINE_LOCK:
        if batch_id is None:
            batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        logger.info("=== Daily category pipeline START ===")
        all_products = await asyncio.to_thread(fetch_all_records)
        logger.info("Loaded {} products from Feishu", len(all_products))

        all_results: list[dict] = []

        for category in ALL_SYMPTOM_CATEGORIES:
            # Check cancel flag before each category
            if cancel_event and cancel_event.is_set():
                logger.info("Pipeline cancelled by user")
                break

            logger.info("Processing category: {}", category["name"])
            try:
                tasks = await asyncio.to_thread(
                    match_products_to_symptom, category, all_products
                )
            except Exception:
                logger.exception("match_products_to_symptom failed for {}", category["name"])
                continue

            if not tasks:
                logger.info("No matching products for {}, skipping", category["name"])
                continue

            # Register tasks in DB
            task_defs = [
                {
                    "category_id": t.category_id,
                    "category_name": t.category_name,
                    "level1_name": category.get("level1_name", ""),
                    "product_line": t.product_line,
                    "products": [p.product_name for p in t.products],
                }
                for t in tasks
            ]
            try:
                db = SessionLocal()
                db_rows = create_batch_tasks(db, batch_id, task_defs)
                db_row_ids = [r.id for r in db_rows]
                db.close()
            except Exception:
                logger.exception("DB create_batch_tasks failed, continuing without progress tracking")
                db_row_ids = [None] * len(tasks)

            for task, db_row_id in zip(tasks, db_row_ids):
                if cancel_event and cancel_event.is_set():
                    logger.info("Pipeline cancelled by user")
                    break
                result = await process_category_task(task, db_row_id=db_row_id)
                all_results.append(result)
                # Brief pause between tasks to be gentle on API rate limits
                await asyncio.sleep(2)

        done = sum(1 for r in all_results if r["status"] == "DONE")
        failed = sum(1 for r in all_results if r["status"] == "FAILED")
        logger.info(
            "=== Daily category pipeline END: {} done, {} failed ===",
            done, failed,
        )
        return all_results
