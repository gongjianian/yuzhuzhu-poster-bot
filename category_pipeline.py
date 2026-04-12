"""Category poster pipeline: scheduling + per-slot execution.

New architecture (24-hour even distribution):
  1. initialize_daily_schedule(batch_id) — called once at trigger time.
     Fetches products, runs Gemini matching for all 10 categories, writes
     SCHEDULED rows spread evenly across 24 h starting from today 00:00.

  2. execute_due_slot(row_ids) — called by the background scheduler when a
     slot's scheduled_at has arrived.  Reconstructs CategoryPosterTask objects
     from DB rows and runs them sequentially.

  3. process_category_task(task, db_row_id) — unchanged: generates content,
     image, uploads, and registers one poster.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from asset_processor import process_product_image
from category_content_generator import generate_category_poster_content
from feishu_reader import fetch_all_records
from image_generator import generate_poster_image
from models import CategoryPosterTask, ProductRecord
from symptom_categories import ALL_SYMPTOM_CATEGORIES, get_category_by_id
from symptom_matcher import match_products_to_symptom
from wechat_uploader import (
    build_material_cloud_path,
    register_material,
    upload_image,
)
from dashboard.database import SessionLocal
from dashboard.db_models import CategoryRunRecord
from dashboard.services.category_run_service import (
    create_scheduled_tasks,
    update_task_step,
    mark_slot_running,
    complete_task as db_complete_task,
    fail_task as db_fail_task,
)

# Seconds between categories within the same slot (API rate-limit buffer)
_INTER_TASK_DELAY = 2


# ── Internal helpers ──────────────────────────────────────────────────────────

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
    if db_row_id is None:
        return
    db = SessionLocal()
    try:
        update_task_step(db, db_row_id, step)
    except Exception:
        logger.warning("_update_step: failed to write step={} for row_id={}", step, db_row_id)
    finally:
        db.close()


def _reconstruct_task(row) -> CategoryPosterTask:
    """Rebuild a CategoryPosterTask from a DB row's products_json."""
    products_data = json.loads(row.products_json or "[]")
    products: list[ProductRecord] = []
    for p in products_data:
        if isinstance(p, str):
            # Legacy: only the product name was stored
            products.append(ProductRecord(record_id="", product_name=p))
        else:
            products.append(ProductRecord(
                record_id=p.get("record_id", ""),
                product_name=p.get("product_name", ""),
                ingredients=p.get("ingredients", ""),
                benefits=p.get("benefits", ""),
                xiaohongshu_topics=p.get("xiaohongshu_topics", ""),
                category=p.get("category", "未分类"),
                visual_style=p.get("visual_style", "极简扁平"),
                brand_colors=p.get("brand_colors", "#FFFFFF"),
                asset_filename=p.get("asset_filename", ""),
                product_line=p.get("product_line", ""),
            ))

    cat_info = get_category_by_id(row.category_id) or {}
    return CategoryPosterTask(
        category_id=row.category_id,
        level1_category_id=cat_info.get("level1_id", ""),
        category_name=row.category_name,
        product_line=row.product_line,
        products=products,
    )


# ── Core task executor ────────────────────────────────────────────────────────

async def process_category_task(
    task: CategoryPosterTask,
    db_row_id: int | None = None,
) -> dict:
    """Generate and upload one poster for a symptom × product-line group."""
    result = _build_result(task)
    asset_dir = Path(os.getenv("ASSETS_DIR", "./assets/products"))

    try:
        # Step 1: generate content (scheme + image_prompt)
        await asyncio.to_thread(_update_step, db_row_id, "content")
        scheme = await asyncio.to_thread(generate_category_poster_content, task)
        result["headline"] = scheme.headline
        logger.info(
            "[{}×{}] content OK → {}",
            task.category_name, task.product_line, scheme.headline,
        )

        # Step 2: load matched product images
        await asyncio.to_thread(_update_step, db_row_id, "image")
        product_images_b64: list[str] = []
        for product in task.products:
            asset_path = asset_dir / product.asset_filename
            try:
                b64 = await asyncio.to_thread(process_product_image, str(asset_path))
                product_images_b64.append(b64)
            except FileNotFoundError:
                logger.warning(
                    "[{}×{}] asset not found, skipping: {}",
                    task.category_name, task.product_line, asset_path,
                )

        if not product_images_b64:
            raise FileNotFoundError(
                f"No product assets found for {task.product_line}: "
                + ", ".join(p.asset_filename for p in task.products)
            )

        logger.info(
            "[{}×{}] loaded {} product image(s)",
            task.category_name, task.product_line, len(product_images_b64),
        )

        # Step 3: generate poster image
        poster_bytes = await asyncio.to_thread(
            generate_poster_image, scheme.image_prompt, product_images_b64
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
            db = SessionLocal()
            try:
                db_complete_task(
                    db, db_row_id,
                    result.get("headline", ""),
                    result.get("cloud_file_id", ""),
                    result.get("material_id", ""),
                    result.get("duration_seconds") or 0.0,
                )
            except Exception:
                logger.exception(
                    "[{}×{}] failed to write DONE status to DB (row_id={})",
                    task.category_name, task.product_line, db_row_id,
                )
            finally:
                db.close()
        return result

    except FileNotFoundError as exc:
        msg = f"product asset not found: {exc}"
        logger.error("[{}×{}] {}", task.category_name, task.product_line, msg)
        _finalize(result, "FAILED", msg)
        if db_row_id:
            db = SessionLocal()
            try:
                db_fail_task(db, db_row_id, msg)
            except Exception:
                logger.exception(
                    "[{}×{}] failed to write FAILED status to DB (row_id={})",
                    task.category_name, task.product_line, db_row_id,
                )
            finally:
                db.close()
        return result

    except Exception as exc:
        logger.exception(
            "[{}×{}] unexpected error", task.category_name, task.product_line
        )
        msg = str(exc)
        _finalize(result, "FAILED", msg)
        if db_row_id:
            db = SessionLocal()
            try:
                db_fail_task(db, db_row_id, msg)
            except Exception:
                logger.exception(
                    "[{}×{}] failed to write FAILED status to DB (row_id={})",
                    task.category_name, task.product_line, db_row_id,
                )
            finally:
                db.close()
        return result


# ── Schedule initialisation ───────────────────────────────────────────────────

async def initialize_daily_schedule(batch_id: str) -> None:
    """Fetch products, match all categories, write SCHEDULED DB rows.

    Slots are spread evenly across 24 h starting from today's midnight.
    Matching runs sequentially (Gemini calls) — typical duration ~1-2 min.
    """
    logger.info("=== Initializing daily schedule: batch={} ===", batch_id)

    all_products = await asyncio.to_thread(fetch_all_records)
    logger.info("Feishu: loaded {} products", len(all_products))

    n = len(ALL_SYMPTOM_CATEGORIES)
    interval_seconds = 24 * 3600 / n  # e.g. 8640s = 2h24m for n=10
    today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    scheduled_count = 0
    for i, category in enumerate(ALL_SYMPTOM_CATEGORIES):
        slot_time = today_midnight + timedelta(seconds=i * interval_seconds)

        try:
            tasks = await asyncio.to_thread(
                match_products_to_symptom, category, all_products
            )
        except Exception:
            logger.exception("Matching failed for category '{}'", category["name"])
            continue

        if not tasks:
            logger.info("No products matched for '{}', skipping", category["name"])
            continue

        task_defs = [
            {
                "category_id": t.category_id,
                "category_name": t.category_name,
                "level1_name": category.get("level1_name", ""),
                "product_line": t.product_line,
                # Store full product info so it can be reconstructed at execution time
                "products": [
                    {
                        "record_id": p.record_id,
                        "product_name": p.product_name,
                        "asset_filename": p.asset_filename,
                        "product_line": p.product_line,
                        "ingredients": p.ingredients,
                        "benefits": p.benefits,
                        "xiaohongshu_topics": p.xiaohongshu_topics,
                        "category": p.category,
                        "visual_style": p.visual_style,
                        "brand_colors": p.brand_colors,
                    }
                    for p in t.products
                ],
            }
            for t in tasks
        ]

        db = SessionLocal()
        try:
            rows = create_scheduled_tasks(db, batch_id, task_defs, slot_time)
            scheduled_count += len(rows)
            logger.info(
                "Slot {}/{} '{}' @ {} → {} task(s) scheduled",
                i + 1, n, category["name"],
                slot_time.strftime("%H:%M"), len(rows),
            )
        except Exception:
            logger.exception(
                "DB write failed for category '{}'", category["name"]
            )
        finally:
            db.close()

    logger.info(
        "=== Schedule ready: {} tasks across {} slots ===",
        scheduled_count, n,
    )


# ── Slot executor (called by scheduler) ──────────────────────────────────────

async def execute_due_slot(row_ids: list[int]) -> None:
    """Run all tasks for one scheduled time slot.

    Tasks are marked RUNNING atomically before execution begins so the
    scheduler will not pick them up again on the next tick.
    """
    if not row_ids:
        return

    # Mark SCHEDULED → RUNNING atomically, then only execute rows that
    # actually made the transition.  If /stop cancelled some rows between
    # the scheduler's get_due_slot() call and here, those rows will still
    # be FAILED and are skipped — preventing execution of cancelled tasks.
    db = SessionLocal()
    try:
        mark_slot_running(db, row_ids)
        rows = (
            db.query(CategoryRunRecord)
            .filter(
                CategoryRunRecord.id.in_(row_ids),
                CategoryRunRecord.status == "RUNNING",  # claimed rows only
            )
            .order_by(CategoryRunRecord.id)
            .all()
        )
        task_data = [(row.id, _reconstruct_task(row)) for row in rows]
    finally:
        db.close()

    if not task_data:
        logger.info("execute_due_slot: all {} row(s) were cancelled before execution", len(row_ids))
        return

    cat_name = task_data[0][1].category_name if task_data else "?"
    logger.info(
        "Executing slot '{}': {} task(s)", cat_name, len(task_data)
    )

    for row_id, task in task_data:
        await process_category_task(task, db_row_id=row_id)
        if _INTER_TASK_DELAY > 0:
            await asyncio.sleep(_INTER_TASK_DELAY)

    logger.info("Slot '{}' finished", cat_name)
