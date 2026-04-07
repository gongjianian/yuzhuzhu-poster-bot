from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from dashboard.auth import get_current_user
from dashboard.database import get_db
from dashboard.schemas import StatsResponse, TrendResponse
from dashboard.services.stats_service import get_stats_summary, get_stats_trend

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary", response_model=StatsResponse)
def stats_summary(
    date: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    return get_stats_summary(db, date)


@router.get("/trend", response_model=TrendResponse)
def stats_trend(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    return TrendResponse(items=get_stats_trend(db, days))
