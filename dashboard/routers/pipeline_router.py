from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from dashboard.auth import get_current_user
from dashboard.schemas import TriggerResponse
from dashboard.services.task_service import execute_full_pipeline, execute_single_trigger

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run", response_model=TriggerResponse)
async def trigger_full_pipeline(
    current_user: str = Depends(get_current_user),
):
    asyncio.create_task(execute_full_pipeline("manual"))
    return TriggerResponse(
        run_id="batch",
        status="queued",
        message="Pipeline has been queued in the background",
    )
