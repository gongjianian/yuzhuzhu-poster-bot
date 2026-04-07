from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from loguru import logger

from dashboard.auth import get_current_user
from dashboard.schemas import TaskListResponse, TaskResponse, TriggerResponse
from dashboard.services.task_service import execute_single_trigger
from feishu_reader import fetch_all_records

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
MAX_BATCH_SIZE = 50


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = Query(None),
    current_user: str = Depends(get_current_user),
):
    records = await asyncio.to_thread(fetch_all_records)
    items = [
        TaskResponse(
            record_id=record.record_id,
            product_name=record.product_name,
            category=record.category,
            status=record.status,
            asset_filename=record.asset_filename,
        )
        for record in records
        if status is None or record.status == status
    ]
    return TaskListResponse(items=items, total=len(items))


@router.post("/{record_id}/trigger", response_model=TriggerResponse)
async def trigger_single(
    record_id: str,
    current_user: str = Depends(get_current_user),
):
    records = await asyncio.to_thread(fetch_all_records)
    if not any(record.record_id == record_id for record in records):
        raise HTTPException(status_code=404, detail=f"Record not found: {record_id}")

    async def run_single():
        try:
            await execute_single_trigger(record_id)
        except Exception:
            logger.exception("Background single trigger failed for {}", record_id)

    asyncio.create_task(run_single())
    return TriggerResponse(
        run_id=record_id,
        status="queued",
        message=f"Triggered record {record_id}",
    )


@router.post("/batch-trigger", response_model=TriggerResponse)
async def batch_trigger(
    record_ids: list[str] = Body(...),
    current_user: str = Depends(get_current_user),
):
    if not record_ids:
        raise HTTPException(status_code=400, detail="record_ids must not be empty")
    if len(record_ids) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"record_ids exceeds max batch size of {MAX_BATCH_SIZE}",
        )

    async def run_batch():
        try:
            for record_id in record_ids:
                await execute_single_trigger(record_id)
        except Exception:
            logger.exception("Background batch trigger failed")

    asyncio.create_task(run_batch())
    return TriggerResponse(
        run_id="batch",
        status="queued",
        message=f"Triggered {len(record_ids)} records",
    )
