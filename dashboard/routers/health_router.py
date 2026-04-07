from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from dashboard.auth import get_current_user
from dashboard.schemas import HealthResponse
from dashboard.services.health_service import run_all_checks

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check(current_user: str = Depends(get_current_user)):
    items = await asyncio.to_thread(run_all_checks)
    return HealthResponse(items=items)
