"""CRUD operations for category pipeline run records."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from dashboard.db_models import CategoryRunRecord


def create_batch_tasks(
    db: Session,
    batch_id: str,
    task_defs: list[dict],
) -> list[CategoryRunRecord]:
    """Insert one row per task definition. Returns created records."""
    records = []
    for td in task_defs:
        row = CategoryRunRecord(
            batch_id=batch_id,
            category_id=td["category_id"],
            category_name=td["category_name"],
            level1_name=td.get("level1_name", ""),
            product_line=td.get("product_line", ""),
            products_json=json.dumps(td.get("products", []), ensure_ascii=False),
            status="PENDING",
            step="matching",
        )
        db.add(row)
        records.append(row)
    db.commit()
    for r in records:
        db.refresh(r)
    return records


def update_task_step(db: Session, record_id: int, step: str) -> None:
    """Update current step and set status to RUNNING."""
    row = db.get(CategoryRunRecord, record_id)
    if row:
        row.step = step
        row.status = "RUNNING"
        db.commit()


def complete_task(
    db: Session,
    record_id: int,
    headline: str,
    cloud_file_id: str,
    material_id: str,
    duration: float,
) -> None:
    row = db.get(CategoryRunRecord, record_id)
    if row:
        row.status = "DONE"
        row.step = "done"
        row.headline = headline
        row.cloud_file_id = cloud_file_id
        row.material_id = material_id
        row.duration_seconds = duration
        row.finished_at = datetime.now()
        db.commit()


def fail_task(db: Session, record_id: int, error_msg: str) -> None:
    row = db.get(CategoryRunRecord, record_id)
    if row:
        row.status = "FAILED"
        row.error_msg = error_msg
        row.finished_at = datetime.now()
        db.commit()


def _serialize_task(row: CategoryRunRecord) -> dict:
    return {
        "id": row.id,
        "category_id": row.category_id,
        "category_name": row.category_name,
        "level1_name": row.level1_name,
        "product_line": row.product_line,
        "products": json.loads(row.products_json) if row.products_json else [],
        "status": row.status,
        "step": row.step,
        "headline": row.headline,
        "cloud_file_id": row.cloud_file_id,
        "material_id": row.material_id,
        "error_msg": row.error_msg,
        "duration_seconds": row.duration_seconds,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def get_current_batch(db: Session) -> dict | None:
    """Return the batch that has RUNNING or PENDING tasks, or None."""
    running_row = (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.status.in_(["RUNNING", "PENDING"]))
        .order_by(CategoryRunRecord.started_at.desc())
        .first()
    )
    if not running_row:
        return None

    batch_id = running_row.batch_id
    tasks = (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.batch_id == batch_id)
        .order_by(CategoryRunRecord.id)
        .all()
    )
    return {
        "batch_id": batch_id,
        "status": "running",
        "tasks": [_serialize_task(t) for t in tasks],
    }


def get_batch_detail(db: Session, batch_id: str) -> dict | None:
    tasks = (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.batch_id == batch_id)
        .order_by(CategoryRunRecord.id)
        .all()
    )
    if not tasks:
        return None
    return {
        "batch_id": batch_id,
        "tasks": [_serialize_task(t) for t in tasks],
    }


def list_batches(db: Session, date: str | None = None) -> list[dict]:
    """List batch summaries, optionally filtered by date (YYYY-MM-DD).

    Uses a Python-side aggregation approach for SQLite compatibility —
    func.cast(bool_expr, Integer) is not reliably supported in SQLite.
    """
    query = db.query(CategoryRunRecord)

    if date:
        prefix = date.replace("-", "")
        query = query.filter(CategoryRunRecord.batch_id.startswith(prefix))

    rows = query.order_by(CategoryRunRecord.batch_id, CategoryRunRecord.id).all()

    # Aggregate per batch in Python for SQLite compatibility
    batches: dict[str, dict] = {}
    for row in rows:
        bid = row.batch_id
        if bid not in batches:
            batches[bid] = {
                "batch_id": bid,
                "started_at": row.started_at,
                "total": 0,
                "done": 0,
                "failed": 0,
                "running": 0,
            }
        entry = batches[bid]
        entry["total"] += 1
        if row.status == "DONE":
            entry["done"] += 1
        elif row.status == "FAILED":
            entry["failed"] += 1
        elif row.status == "RUNNING":
            entry["running"] += 1
        # Track earliest started_at per batch
        if row.started_at and (entry["started_at"] is None or row.started_at < entry["started_at"]):
            entry["started_at"] = row.started_at

    # Sort by batch_id descending (newest first) and format
    result = []
    for bid in sorted(batches.keys(), reverse=True):
        entry = batches[bid]
        result.append({
            "batch_id": bid,
            "started_at": entry["started_at"].isoformat() if entry["started_at"] else None,
            "total": entry["total"],
            "done": entry["done"],
            "failed": entry["failed"],
            "running": entry["running"],
        })
    return result
