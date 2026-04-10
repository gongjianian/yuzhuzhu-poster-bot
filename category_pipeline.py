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


async def process_category_task(task: CategoryPosterTask) -> dict:
    """Generate and upload one poster for a symptom × product-line group."""
    result = _build_result(task)
    asset_dir = Path(os.getenv("ASSETS_DIR", "./assets/products"))

    # Use the first product's asset image as the representative visual
    primary_product = task.products[0]
    asset_path = asset_dir / primary_product.asset_filename

    try:
        # Step 1: generate content (scheme + image_prompt)
        scheme = await asyncio.to_thread(generate_category_poster_content, task)
        result["headline"] = scheme.headline
        logger.info(
            "[{}×{}] content OK → {}",
            task.category_name, task.product_line, scheme.headline,
        )

        # Step 2: load product image
        product_b64 = await asyncio.to_thread(
            process_product_image, str(asset_path)
        )

        # Step 3: generate poster image
        poster_bytes = await asyncio.to_thread(
            generate_poster_image, scheme.image_prompt, product_b64
        )
        logger.info("[{}×{}] image generated", task.category_name, task.product_line)

        # Step 4: upload to cloud storage
        cloud_path = build_material_cloud_path(
            level1_category_id=task.level1_category_id,
            category_id=task.category_id,
            product_type=task.product_line,
        )
        file_id = await asyncio.to_thread(upload_image, poster_bytes, cloud_path)
        result["cloud_file_id"] = file_id

        # Step 5: register in mini-program materials collection
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
        return result

    except FileNotFoundError as exc:
        msg = f"product asset not found: {exc}"
        logger.error("[{}×{}] {}", task.category_name, task.product_line, msg)
        return _finalize(result, "FAILED", msg)
    except Exception as exc:
        logger.exception(
            "[{}×{}] unexpected error", task.category_name, task.product_line
        )
        return _finalize(result, "FAILED", str(exc))


async def run_daily_category_pipeline() -> list[dict]:
    """Run the full daily pipeline: all 10 symptom categories.

    Fetches all products from Feishu once, then sequentially processes
    each category to avoid overwhelming the API.
    """
    async with _PIPELINE_LOCK:
        logger.info("=== Daily category pipeline START ===")
        all_products = await asyncio.to_thread(fetch_all_records)
        logger.info("Loaded {} products from Feishu", len(all_products))

        all_results: list[dict] = []

        for category in ALL_SYMPTOM_CATEGORIES:
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

            for task in tasks:
                result = await process_category_task(task)
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
