"""CRUD operations for category pipeline run records."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from dashboard.db_models import CategoryRunRecord


# ── Write helpers ─────────────────────────────────────────────────────────────

def create_scheduled_tasks(
    db: Session,
    batch_id: str,
    task_defs: list[dict],
    scheduled_at: datetime,
) -> list[CategoryRunRecord]:
    """Insert SCHEDULED rows for one category slot.

    task_defs[*]["products"] should be a list of dicts with full ProductRecord
    fields (not just names) so they can be reconstructed at execution time.
    """
    records = []
    for td in task_defs:
        row = CategoryRunRecord(
            batch_id=batch_id,
            category_id=td["category_id"],
            category_name=td["category_name"],
            level1_name=td.get("level1_name", ""),
            product_line=td.get("product_line", ""),
            products_json=json.dumps(td.get("products", []), ensure_ascii=False),
            status="SCHEDULED",
            step="matching",
            scheduled_at=scheduled_at,
        )
        db.add(row)
        records.append(row)
    db.commit()
    for r in records:
        db.refresh(r)
    return records


def create_batch_tasks(
    db: Session,
    batch_id: str,
    task_defs: list[dict],
) -> list[CategoryRunRecord]:
    """Legacy: insert PENDING rows (kept for compatibility)."""
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
    """Update step and mark task RUNNING (handles SCHEDULED→RUNNING too)."""
    row = db.get(CategoryRunRecord, record_id)
    if row:
        row.step = step
        row.status = "RUNNING"
        if row.started_at is None:
            row.started_at = datetime.now()
        db.commit()


def mark_slot_running(db: Session, record_ids: list[int]) -> None:
    """Atomically mark a group of SCHEDULED tasks as RUNNING.

    Called at the start of execute_due_slot to prevent the scheduler from
    picking up the same slot again on the next tick.
    """
    now = datetime.now()
    for rid in record_ids:
        row = db.get(CategoryRunRecord, rid)
        if row and row.status == "SCHEDULED":
            row.status = "RUNNING"
            row.step = "matching"
            row.started_at = now
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


def cancel_pending_tasks(db: Session, batch_id: str) -> int:
    """Mark all PENDING tasks in a batch as FAILED (legacy stop support)."""
    rows = (
        db.query(CategoryRunRecord)
        .filter(
            CategoryRunRecord.batch_id == batch_id,
            CategoryRunRecord.status == "PENDING",
        )
        .all()
    )
    for row in rows:
        row.status = "FAILED"
        row.error_msg = "Cancelled by user"
        row.finished_at = datetime.now()
    db.commit()
    return len(rows)


def cancel_scheduled_tasks(db: Session, batch_id: str) -> int:
    """Mark all still-SCHEDULED tasks as FAILED. Used by the stop endpoint."""
    rows = (
        db.query(CategoryRunRecord)
        .filter(
            CategoryRunRecord.batch_id == batch_id,
            CategoryRunRecord.status == "SCHEDULED",
        )
        .all()
    )
    for row in rows:
        row.status = "FAILED"
        row.error_msg = "Cancelled by user"
        row.finished_at = datetime.now()
    db.commit()
    return len(rows)


# ── Query helpers ──────────────────────────────────────────────────────────────

def recover_stale_running_tasks(db: Session) -> int:
    """On process restart, reset any RUNNING tasks to FAILED.

    A task that is still RUNNING in the DB after a restart was interrupted
    mid-flight and will never self-resolve. Left untouched, has_running_tasks()
    would permanently block the scheduler from executing new slots.
    """
    rows = (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.status == "RUNNING")
        .all()
    )
    for row in rows:
        row.status = "FAILED"
        row.error_msg = "Process restarted: task interrupted"
        row.finished_at = datetime.now()
    db.commit()
    return len(rows)


def recover_timed_out_tasks(db: Session, timeout_minutes: int = 45) -> int:
    """Reset RUNNING tasks that have exceeded the timeout to FAILED.

    Called on every scheduler tick so that a DB-write failure inside
    process_category_task() (which leaves the row stuck in RUNNING) cannot
    permanently block the scheduler — it will self-heal after timeout_minutes.
    """
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(minutes=timeout_minutes)
    rows = (
        db.query(CategoryRunRecord)
        .filter(
            CategoryRunRecord.status == "RUNNING",
            CategoryRunRecord.started_at <= cutoff,
        )
        .all()
    )
    for row in rows:
        row.status = "FAILED"
        row.error_msg = f"Task timed out after {timeout_minutes} minutes"
        row.finished_at = datetime.now()
    if rows:
        db.commit()
    return len(rows)


def has_today_batch(db: Session) -> bool:
    """Return True if any records exist for today's batch_id (including DONE/FAILED)."""
    today = datetime.now().strftime("%Y%m%d")
    return (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.batch_id == today)
        .first()
        is not None
    )


def has_active_today_batch(db: Session) -> bool:
    """Return True if today's batch has tasks that are SCHEDULED or RUNNING.

    Unlike has_today_batch(), this returns False when all rows are DONE/FAILED,
    so a batch whose initialisation crashed mid-way can be retried via /trigger.
    """
    today = datetime.now().strftime("%Y%m%d")
    return (
        db.query(CategoryRunRecord)
        .filter(
            CategoryRunRecord.batch_id == today,
            CategoryRunRecord.status.in_(["SCHEDULED", "RUNNING"]),
        )
        .first()
        is not None
    )


def has_running_tasks(db: Session) -> bool:
    """Return True if any task is currently executing."""
    return (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.status == "RUNNING")
        .first()
        is not None
    )


def get_due_slot(db: Session) -> list[CategoryRunRecord]:
    """Return all SCHEDULED tasks for the earliest due slot (scheduled_at ≤ now).

    All tasks returned share the same category_name and batch_id so they can
    be run as one atomic group.
    """
    now = datetime.now()
    first = (
        db.query(CategoryRunRecord)
        .filter(
            CategoryRunRecord.status == "SCHEDULED",
            CategoryRunRecord.scheduled_at <= now,
        )
        .order_by(CategoryRunRecord.scheduled_at, CategoryRunRecord.id)
        .first()
    )
    if first is None:
        return []
    # Group by category_id (stable FK) rather than category_name (mutable string)
    return (
        db.query(CategoryRunRecord)
        .filter(
            CategoryRunRecord.batch_id == first.batch_id,
            CategoryRunRecord.category_id == first.category_id,
            CategoryRunRecord.status == "SCHEDULED",
        )
        .order_by(CategoryRunRecord.id)
        .all()
    )


# ── Serialisation ──────────────────────────────────────────────────────────────

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
        "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def get_today_schedule(db: Session) -> dict | None:
    """Return today's full schedule grouped by category slot."""
    today = datetime.now().strftime("%Y%m%d")
    rows = (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.batch_id == today)
        .order_by(CategoryRunRecord.scheduled_at, CategoryRunRecord.id)
        .all()
    )
    if not rows:
        return None

    groups: dict[str, list[CategoryRunRecord]] = defaultdict(list)
    for row in rows:
        groups[row.category_name].append(row)

    slots = []
    for category_name, task_rows in groups.items():
        statuses = {r.status for r in task_rows}

        if "RUNNING" in statuses:
            slot_status = "RUNNING"
        elif statuses == {"DONE"}:
            slot_status = "DONE"
        elif statuses == {"SCHEDULED"}:
            slot_status = "SCHEDULED"
        elif statuses == {"FAILED"}:
            slot_status = "FAILED"
        else:
            # Mix of DONE + FAILED
            slot_status = "PARTIAL"

        done_count = sum(1 for r in task_rows if r.status == "DONE")
        failed_count = sum(1 for r in task_rows if r.status == "FAILED")
        first_row = task_rows[0]

        slots.append({
            "category_id": first_row.category_id,
            "category_name": category_name,
            "level1_name": first_row.level1_name,
            "scheduled_at": (
                first_row.scheduled_at.isoformat() if first_row.scheduled_at else None
            ),
            "slot_status": slot_status,
            "tasks": [_serialize_task(r) for r in task_rows],
            "done_count": done_count,
            "failed_count": failed_count,
            "total_count": len(task_rows),
        })

    slots.sort(key=lambda s: s["scheduled_at"] or "")
    done_slots = sum(1 for s in slots if s["slot_status"] in ("DONE", "PARTIAL"))

    return {
        "batch_id": today,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_slots": len(slots),
        "done_slots": done_slots,
        "slots": slots,
    }


def get_current_batch(db: Session) -> dict | None:
    """Return the batch that has active (RUNNING/PENDING/SCHEDULED) tasks."""
    active_row = (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.status.in_(["RUNNING", "PENDING", "SCHEDULED"]))
        .order_by(CategoryRunRecord.id.desc())
        .first()
    )
    if not active_row:
        return None

    batch_id = active_row.batch_id
    tasks = (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.batch_id == batch_id)
        .order_by(CategoryRunRecord.scheduled_at, CategoryRunRecord.id)
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
        .order_by(CategoryRunRecord.scheduled_at, CategoryRunRecord.id)
        .all()
    )
    if not tasks:
        return None
    return {
        "batch_id": batch_id,
        "tasks": [_serialize_task(t) for t in tasks],
    }


def list_batches(db: Session, date: str | None = None) -> list[dict]:
    """List batch summaries, optionally filtered by date (YYYY-MM-DD)."""
    query = db.query(CategoryRunRecord)
    if date:
        prefix = date.replace("-", "")
        query = query.filter(CategoryRunRecord.batch_id.startswith(prefix))

    rows = query.order_by(CategoryRunRecord.batch_id, CategoryRunRecord.id).all()

    batches: dict[str, dict] = {}
    for row in rows:
        bid = row.batch_id
        if bid not in batches:
            batches[bid] = {
                "batch_id": bid,
                "started_at": row.scheduled_at or row.started_at,
                "total": 0,
                "done": 0,
                "failed": 0,
                "running": 0,
                "scheduled": 0,
            }
        entry = batches[bid]
        entry["total"] += 1
        if row.status == "DONE":
            entry["done"] += 1
        elif row.status == "FAILED":
            entry["failed"] += 1
        elif row.status == "RUNNING":
            entry["running"] += 1
        elif row.status == "SCHEDULED":
            entry["scheduled"] += 1

    result = []
    for bid in sorted(batches.keys(), reverse=True):
        entry = batches[bid]
        ts = entry["started_at"]
        result.append({
            "batch_id": bid,
            "started_at": ts.isoformat() if ts else None,
            "total": entry["total"],
            "done": entry["done"],
            "failed": entry["failed"],
            "running": entry["running"],
            "scheduled": entry["scheduled"],
        })
    return result
