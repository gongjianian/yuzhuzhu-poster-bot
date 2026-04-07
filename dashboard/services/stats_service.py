from __future__ import annotations

from sqlalchemy.orm import Session

from dashboard.db_models import DailyStats


def get_stats_summary(db: Session, date_str: str) -> dict:
    stat = db.query(DailyStats).filter_by(date=date_str).first()
    if not stat:
        return {
            "date": date_str,
            "total": 0,
            "success": 0,
            "failed": 0,
            "success_rate": 0.0,
            "avg_duration": 0.0,
        }

    success_rate = (stat.success / stat.total * 100) if stat.total > 0 else 0.0
    return {
        "date": stat.date,
        "total": stat.total,
        "success": stat.success,
        "failed": stat.failed,
        "success_rate": round(success_rate, 1),
        "avg_duration": round(stat.avg_duration, 1),
    }


def get_stats_trend(db: Session, days: int = 7) -> list[dict]:
    stats = db.query(DailyStats).order_by(DailyStats.date.desc()).limit(days).all()
    items = []
    for stat in reversed(stats):
        success_rate = (stat.success / stat.total * 100) if stat.total > 0 else 0.0
        items.append(
            {
                "date": stat.date,
                "total": stat.total,
                "success": stat.success,
                "failed": stat.failed,
                "success_rate": round(success_rate, 1),
                "avg_duration": round(stat.avg_duration, 1),
            }
        )
    return items
