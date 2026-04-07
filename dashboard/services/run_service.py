from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from dashboard.db_models import DailyStats, RunRecord


def save_run_result(db: Session, result: dict) -> RunRecord:
    record = RunRecord(
        run_id=result["run_id"],
        product_name=result["product_name"],
        record_id=result["record_id"],
        trigger_type=result["trigger_type"],
        status=result["status"],
        stage=result.get("stage", ""),
        headline=result.get("headline", ""),
        image_prompt=result.get("image_prompt", ""),
        qc_passed=result.get("qc_passed"),
        qc_confidence=result.get("qc_confidence"),
        qc_issues=result.get("qc_issues", "[]"),
        cloud_file_id=result.get("cloud_file_id", ""),
        error_msg=result.get("error_msg", ""),
        duration_seconds=result.get("duration_seconds"),
        started_at=result.get("started_at", datetime.now()),
        finished_at=result.get("finished_at"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_runs(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    product_name: Optional[str] = None,
    date: Optional[str] = None,
) -> tuple[list[RunRecord], int]:
    query = db.query(RunRecord)

    if status:
        query = query.filter(RunRecord.status == status)
    if product_name:
        query = query.filter(RunRecord.product_name.contains(product_name))
    if date:
        query = query.filter(RunRecord.started_at >= f"{date} 00:00:00")
        query = query.filter(RunRecord.started_at <= f"{date} 23:59:59")

    total = query.count()
    items = (
        query.order_by(RunRecord.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_run_by_id(db: Session, run_id: str) -> Optional[RunRecord]:
    return db.query(RunRecord).filter_by(run_id=run_id).first()


def update_daily_stats(db: Session, date_str: str) -> DailyStats:
    runs = (
        db.query(RunRecord)
        .filter(RunRecord.started_at >= f"{date_str} 00:00:00")
        .filter(RunRecord.started_at <= f"{date_str} 23:59:59")
        .all()
    )

    total = len(runs)
    success = sum(1 for run in runs if run.status == "DONE")
    failed = sum(1 for run in runs if run.status == "FAILED")
    durations = [run.duration_seconds for run in runs if run.duration_seconds is not None]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    stat = db.query(DailyStats).filter_by(date=date_str).first()
    if stat:
        stat.total = total
        stat.success = success
        stat.failed = failed
        stat.avg_duration = avg_duration
    else:
        stat = DailyStats(
            date=date_str,
            total=total,
            success=success,
            failed=failed,
            avg_duration=avg_duration,
        )
        db.add(stat)

    db.commit()
    db.refresh(stat)
    return stat
