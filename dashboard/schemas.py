from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    product_name: str
    record_id: str
    trigger_type: str
    status: str
    stage: str
    headline: str
    qc_passed: Optional[bool]
    qc_confidence: Optional[float]
    qc_issues: list[str]
    cloud_file_id: str
    error_msg: str
    duration_seconds: Optional[float]
    started_at: datetime
    finished_at: Optional[datetime]

    @field_validator("qc_issues", mode="before")
    @classmethod
    def parse_qc_issues(cls, value):
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return [value] if value else []
            return parsed if isinstance(parsed, list) else []
        return value or []


class RunListResponse(BaseModel):
    items: list[RunResponse]
    total: int
    page: int
    page_size: int


class TaskResponse(BaseModel):
    record_id: str
    product_name: str
    category: str
    status: str
    asset_filename: str
    cloud_file_id: str = ""


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


class StatsResponse(BaseModel):
    date: str
    total: int
    success: int
    failed: int
    success_rate: float
    avg_duration: float


class TrendResponse(BaseModel):
    items: list[StatsResponse]


class TriggerResponse(BaseModel):
    run_id: str
    status: str
    message: str


class HealthItem(BaseModel):
    name: str
    status: str
    latency_ms: Optional[float] = None
    detail: str = ""


class HealthResponse(BaseModel):
    items: list[HealthItem]


class LogEntry(BaseModel):
    line_number: int
    timestamp: str
    level: str
    message: str


class LogResponse(BaseModel):
    date: str
    total_lines: int
    lines: list[LogEntry]
