"""REST API for category pipeline runs: trigger, stop, progress, history."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from loguru import logger
from sqlalchemy.orm import Session

from dashboard.auth import get_current_user
from dashboard.database import SessionLocal
from dashboard.schemas import (
    CategoryBatchDetail,
    CategoryBatchListResponse,
    CategoryBatchSummary,
    TriggerResponse,
)
from dashboard.services.category_run_service import (
    get_batch_detail,
    get_current_batch,
    list_batches,
)

router = APIRouter(prefix="/api/category-runs", tags=["category-runs"])

# Cancel flag — set to signal the pipeline to stop after current task
_cancel_event: asyncio.Event | None = None


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
) -> Optional[CategoryBatchDetail]:
    result = get_batch_detail(db, batch_id)
    if result is None:
        return None
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


@router.post("/trigger", response_model=TriggerResponse)
async def trigger(
    current_user: str = Depends(get_current_user),
):
    global _cancel_event
    from category_pipeline import run_daily_category_pipeline

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    _cancel_event = asyncio.Event()

    async def run():
        try:
            await run_daily_category_pipeline(
                batch_id=batch_id,
                cancel_event=_cancel_event,
            )
        except Exception:
            logger.exception("Category pipeline background run failed")

    asyncio.create_task(run())
    return TriggerResponse(
        run_id=batch_id, status="queued", message="Category pipeline started"
    )


@router.post("/stop", response_model=TriggerResponse)
async def stop(
    current_user: str = Depends(get_current_user),
):
    global _cancel_event
    if _cancel_event is not None:
        _cancel_event.set()
        return TriggerResponse(
            run_id="", status="stopping", message="Stop signal sent"
        )
    return TriggerResponse(
        run_id="", status="idle", message="No pipeline running"
    )
