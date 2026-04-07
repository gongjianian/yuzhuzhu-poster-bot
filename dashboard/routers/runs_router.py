from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from dashboard.auth import get_current_user
from dashboard.database import get_db
from dashboard.schemas import RunListResponse, RunResponse
from dashboard.services.run_service import get_run_by_id, get_runs

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _to_response(run) -> RunResponse:
    return RunResponse.model_validate(run)


@router.get("", response_model=RunListResponse)
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    product_name: Optional[str] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    items, total = get_runs(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        product_name=product_name,
        date=date,
    )
    return RunListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run_detail(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user),
):
    run = get_run_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run record not found")
    return _to_response(run)
