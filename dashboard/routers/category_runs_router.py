"""REST API for the 24-hour category poster schedule."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.orm import Session

from dashboard.auth import get_current_user
from dashboard.database import SessionLocal
from dashboard.schemas import (
    CategoryBatchDetail,
    CategoryBatchListResponse,
    CategoryBatchSummary,
    TodayScheduleResponse,
    TriggerResponse,
)
from dashboard.services.category_run_service import (
    cancel_scheduled_tasks,
    get_batch_detail,
    get_current_batch,
    get_today_schedule,
    has_active_today_batch,
    list_batches,
)

router = APIRouter(prefix="/api/category-runs", tags=["category-runs"])


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Today's schedule ──────────────────────────────────────────────────────────

@router.get("/today")
async def today_schedule(
    db: Session = Depends(_get_db),
    current_user: str = Depends(get_current_user),
) -> Optional[TodayScheduleResponse]:
    result = get_today_schedule(db)
    if result is None:
        return None
    return TodayScheduleResponse(**result)


# ── Trigger / Stop ────────────────────────────────────────────────────────────

@router.post("/trigger", response_model=TriggerResponse)
async def trigger(
    current_user: str = Depends(get_current_user),
):
    """Create today's schedule and let the background scheduler execute it.

    Returns immediately; the background task calls initialize_daily_schedule().

    Duplicate-trigger protection works via _init_in_progress:
    - The flag is set synchronously (no await) before create_task().
    - Because asyncio is single-threaded and cooperative, no other coroutine
      can run between "set flag" and "return response".
    - A second concurrent request therefore always sees the flag as True.

    has_active_today_batch() (not has_today_batch) is used so that a batch
    whose init crashed mid-way (all rows FAILED, none SCHEDULED) can be
    retried instead of being permanently stuck.
    """
    from dashboard import scheduler

    if scheduler._init_in_progress:
        raise HTTPException(status_code=409, detail="Initialisation already in progress.")

    db = SessionLocal()
    try:
        if has_active_today_batch(db):
            raise HTTPException(
                status_code=409,
                detail="Today's schedule already has active tasks. Stop them first.",
            )
    finally:
        db.close()

    batch_id = datetime.now().strftime("%Y%m%d")

    scheduler._init_in_progress = True

    async def _init():
        try:
            from category_pipeline import initialize_daily_schedule
            await initialize_daily_schedule(batch_id)
        except Exception:
            logger.exception("Failed to initialize daily schedule (batch={})", batch_id)
        finally:
            scheduler._init_in_progress = False

    asyncio.create_task(_init())
    return TriggerResponse(
        run_id=batch_id,
        status="scheduling",
        message="Initialising today's schedule — slots will execute automatically.",
    )


@router.post("/stop", response_model=TriggerResponse)
async def stop(
    current_user: str = Depends(get_current_user),
):
    """Cancel all remaining SCHEDULED slots for today.

    Any slot currently RUNNING finishes naturally; only future slots are cancelled.
    """
    batch_id = datetime.now().strftime("%Y%m%d")
    db = SessionLocal()
    try:
        n = cancel_scheduled_tasks(db, batch_id)
    finally:
        db.close()

    if n:
        logger.info("Stop: cancelled {} scheduled task(s) in batch {}", n, batch_id)
        return TriggerResponse(
            run_id=batch_id, status="stopped",
            message=f"Cancelled {n} scheduled task(s). Running task (if any) finishes naturally.",
        )
    return TriggerResponse(
        run_id=batch_id, status="idle",
        message="No scheduled tasks to cancel.",
    )


# ── History / Detail ──────────────────────────────────────────────────────────

@router.get("/current")
async def current_batch(
    db: Session = Depends(_get_db),
    current_user: str = Depends(get_current_user),
) -> Optional[CategoryBatchDetail]:
    result = get_current_batch(db)
    if result is None:
        return None
    return CategoryBatchDetail(**result)


@router.get("/{batch_id}")
async def batch_detail(
    batch_id: str,
    db: Session = Depends(_get_db),
    current_user: str = Depends(get_current_user),
) -> CategoryBatchDetail:
    result = get_batch_detail(db, batch_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return CategoryBatchDetail(**result)


@router.get("", response_model=CategoryBatchListResponse)
async def batches(
    date: Optional[str] = Query(None),
    db: Session = Depends(_get_db),
    current_user: str = Depends(get_current_user),
):
    items = list_batches(db, date=date)
    return CategoryBatchListResponse(
        items=[CategoryBatchSummary(**b) for b in items]
    )
