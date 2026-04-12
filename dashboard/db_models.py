from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from dashboard.database import Base


class RunRecord(Base):
    __tablename__ = "run_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    product_name: Mapped[str] = mapped_column(String(200))
    record_id: Mapped[str] = mapped_column(String(100), index=True)
    trigger_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), index=True)
    stage: Mapped[str] = mapped_column(String(30), default="")
    headline: Mapped[str] = mapped_column(String(500), default="")
    image_prompt: Mapped[str] = mapped_column(Text, default="")
    qc_passed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    qc_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    qc_issues: Mapped[str] = mapped_column(Text, default="")
    cloud_file_id: Mapped[str] = mapped_column(String(500), default="")
    error_msg: Mapped[str] = mapped_column(Text, default="")
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class DailyStats(Base):
    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    avg_duration: Mapped[float] = mapped_column(Float, default=0.0)


class CategoryRunRecord(Base):
    __tablename__ = "category_run_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    category_id: Mapped[str] = mapped_column(String(64))
    category_name: Mapped[str] = mapped_column(String(100))
    level1_name: Mapped[str] = mapped_column(String(100), default="")
    product_line: Mapped[str] = mapped_column(String(50), default="")
    products_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), index=True, default="PENDING")
    step: Mapped[str] = mapped_column(String(20), default="matching")
    headline: Mapped[str] = mapped_column(String(500), default="")
    cloud_file_id: Mapped[str] = mapped_column(String(500), default="")
    material_id: Mapped[str] = mapped_column(String(200), default="")
    error_msg: Mapped[str] = mapped_column(Text, default="")
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
