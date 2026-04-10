# Category Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "分类海报" dashboard page showing real-time pipeline progress and historical results per symptom category.

**Architecture:** New SQLite table `category_run_records` stores per-task results. The pipeline writes progress to DB at each step via a thin service layer. A new FastAPI router exposes batch/task data. The Vue frontend polls `/api/category-runs/current` every 3s for live updates and supports date-based history browsing.

**Tech Stack:** SQLAlchemy (existing), FastAPI, Vue 3 + Element Plus + TypeScript, SQLite

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `dashboard/db_models.py` | Add `CategoryRunRecord` ORM model |
| Create | `dashboard/services/category_run_service.py` | DB CRUD for category runs |
| Modify | `dashboard/schemas.py` | Add response schemas |
| Create | `dashboard/routers/category_runs_router.py` | REST API endpoints |
| Modify | `dashboard/app.py` | Register new router |
| Modify | `category_pipeline.py` | Write progress to DB at each step |
| Create | `frontend/src/api/categoryRuns.ts` | API client |
| Create | `frontend/src/views/CategoryRunsView.vue` | Main view |
| Modify | `frontend/src/router/index.ts` | Add route |
| Modify | `frontend/src/layouts/DashboardLayout.vue` | Add sidebar item |
| Create | `tests/test_category_run_service.py` | Service tests |
| Create | `tests/test_category_runs_router.py` | API endpoint tests |

---

### Task 1: CategoryRunRecord DB Model

**Files:**
- Modify: `dashboard/db_models.py`
- Test: `tests/test_category_run_service.py`

- [ ] **Step 1: Write failing test for model existence**

```python
# tests/test_category_run_service.py
import pytest
from dashboard.database import Base, engine
from dashboard.db_models import CategoryRunRecord


def test_category_run_record_table_exists():
    """CategoryRunRecord model should have correct table name and columns."""
    assert CategoryRunRecord.__tablename__ == "category_run_records"
    col_names = {c.name for c in CategoryRunRecord.__table__.columns}
    assert "batch_id" in col_names
    assert "category_id" in col_names
    assert "step" in col_names
    assert "status" in col_names
    assert "material_id" in col_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_category_run_service.py::test_category_run_record_table_exists -v`
Expected: FAIL with `ImportError: cannot import name 'CategoryRunRecord'`

- [ ] **Step 3: Add CategoryRunRecord to db_models.py**

Add this class after the existing `DailyStats` class in `dashboard/db_models.py`:

```python
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
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_category_run_service.py::test_category_run_record_table_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/db_models.py tests/test_category_run_service.py
git commit -m "feat: add CategoryRunRecord DB model"
```

---

### Task 2: Category Run Service

**Files:**
- Create: `dashboard/services/category_run_service.py`
- Modify: `tests/test_category_run_service.py`

- [ ] **Step 1: Write failing tests for service functions**

Append to `tests/test_category_run_service.py`:

```python
import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dashboard.database import Base
from dashboard.db_models import CategoryRunRecord
from dashboard.services.category_run_service import (
    create_batch_tasks,
    update_task_step,
    complete_task,
    fail_task,
    get_current_batch,
    get_batch_detail,
    list_batches,
)


@pytest.fixture()
def db_session():
    """In-memory SQLite session for testing."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    session = Session()
    yield session
    session.close()


def test_create_batch_tasks(db_session):
    records = create_batch_tasks(
        db_session,
        batch_id="20260410_120000",
        task_defs=[
            {
                "category_id": "cat_pw_jstl",
                "category_name": "积食停滞类",
                "level1_name": "脾胃系列",
                "product_line": "五行泡浴",
                "products": ["鸡内金泡浴", "金银花泡浴"],
            },
        ],
    )
    assert len(records) == 1
    assert records[0].batch_id == "20260410_120000"
    assert records[0].status == "PENDING"
    assert json.loads(records[0].products_json) == ["鸡内金泡浴", "金银花泡浴"]


def test_update_task_step(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    update_task_step(db_session, row.id, "content")
    db_session.refresh(row)
    assert row.step == "content"
    assert row.status == "RUNNING"


def test_complete_task(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    complete_task(db_session, row.id, headline="Test", cloud_file_id="cid", material_id="mid", duration=12.5)
    db_session.refresh(row)
    assert row.status == "DONE"
    assert row.step == "done"
    assert row.headline == "Test"
    assert row.material_id == "mid"
    assert row.duration_seconds == 12.5
    assert row.finished_at is not None


def test_fail_task(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    fail_task(db_session, row.id, error_msg="boom")
    db_session.refresh(row)
    assert row.status == "FAILED"
    assert row.error_msg == "boom"


def test_get_current_batch(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    update_task_step(db_session, row.id, "image")
    result = get_current_batch(db_session)
    assert result is not None
    assert result["batch_id"] == "b1"
    assert len(result["tasks"]) == 1


def test_get_current_batch_none_when_all_done(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    complete_task(db_session, row.id, "H", "c", "m", 1.0)
    result = get_current_batch(db_session)
    assert result is None


def test_list_batches(db_session):
    create_batch_tasks(db_session, "20260410_120000", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": []},
        {"category_id": "c2", "category_name": "B", "level1_name": "X",
         "product_line": "PL2", "products": []},
    ])
    row = db_session.query(CategoryRunRecord).first()
    complete_task(db_session, row.id, "H", "c", "m", 1.0)
    batches = list_batches(db_session, date="2026-04-10")
    assert len(batches) == 1
    assert batches[0]["batch_id"] == "20260410_120000"
    assert batches[0]["total"] == 2
    assert batches[0]["done"] == 1


def test_get_batch_detail(db_session):
    create_batch_tasks(db_session, "b1", [
        {"category_id": "c1", "category_name": "A", "level1_name": "X",
         "product_line": "PL", "products": ["P1"]},
    ])
    detail = get_batch_detail(db_session, "b1")
    assert detail is not None
    assert len(detail["tasks"]) == 1
    assert detail["tasks"][0]["category_name"] == "A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_category_run_service.py -v -k "not table_exists"`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement category_run_service.py**

Create `dashboard/services/category_run_service.py`:

```python
"""CRUD operations for category pipeline run records."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from dashboard.db_models import CategoryRunRecord


def create_batch_tasks(
    db: Session,
    batch_id: str,
    task_defs: list[dict],
) -> list[CategoryRunRecord]:
    """Insert one row per task definition. Returns created records."""
    records = []
    for td in task_defs:
        row = CategoryRunRecord(
            batch_id=batch_id,
            category_id=td["category_id"],
            category_name=td["category_name"],
            level1_name=td.get("level1_name", ""),
            product_line=td.get("product_line", ""),
            products_json=json.dumps(td.get("products", []), ensure_ascii=False),
            status="PENDING",
            step="matching",
        )
        db.add(row)
        records.append(row)
    db.commit()
    for r in records:
        db.refresh(r)
    return records


def update_task_step(db: Session, record_id: int, step: str) -> None:
    """Update current step and set status to RUNNING."""
    row = db.get(CategoryRunRecord, record_id)
    if row:
        row.step = step
        row.status = "RUNNING"
        db.commit()


def complete_task(
    db: Session,
    record_id: int,
    headline: str,
    cloud_file_id: str,
    material_id: str,
    duration: float,
) -> None:
    row = db.get(CategoryRunRecord, record_id)
    if row:
        row.status = "DONE"
        row.step = "done"
        row.headline = headline
        row.cloud_file_id = cloud_file_id
        row.material_id = material_id
        row.duration_seconds = duration
        row.finished_at = datetime.now()
        db.commit()


def fail_task(db: Session, record_id: int, error_msg: str) -> None:
    row = db.get(CategoryRunRecord, record_id)
    if row:
        row.status = "FAILED"
        row.error_msg = error_msg
        row.finished_at = datetime.now()
        db.commit()


def _serialize_task(row: CategoryRunRecord) -> dict:
    return {
        "id": row.id,
        "category_id": row.category_id,
        "category_name": row.category_name,
        "level1_name": row.level1_name,
        "product_line": row.product_line,
        "products": json.loads(row.products_json) if row.products_json else [],
        "status": row.status,
        "step": row.step,
        "headline": row.headline,
        "cloud_file_id": row.cloud_file_id,
        "material_id": row.material_id,
        "error_msg": row.error_msg,
        "duration_seconds": row.duration_seconds,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def get_current_batch(db: Session) -> dict | None:
    """Return the batch that has RUNNING or PENDING tasks, or None."""
    running_row = (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.status.in_(["RUNNING", "PENDING"]))
        .order_by(CategoryRunRecord.started_at.desc())
        .first()
    )
    if not running_row:
        return None

    batch_id = running_row.batch_id
    tasks = (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.batch_id == batch_id)
        .order_by(CategoryRunRecord.id)
        .all()
    )
    return {
        "batch_id": batch_id,
        "status": "running",
        "tasks": [_serialize_task(t) for t in tasks],
    }


def get_batch_detail(db: Session, batch_id: str) -> dict | None:
    tasks = (
        db.query(CategoryRunRecord)
        .filter(CategoryRunRecord.batch_id == batch_id)
        .order_by(CategoryRunRecord.id)
        .all()
    )
    if not tasks:
        return None
    return {
        "batch_id": batch_id,
        "tasks": [_serialize_task(t) for t in tasks],
    }


def list_batches(db: Session, date: str | None = None) -> list[dict]:
    """List batch summaries, optionally filtered by date (YYYY-MM-DD)."""
    query = db.query(
        CategoryRunRecord.batch_id,
        func.min(CategoryRunRecord.started_at).label("started_at"),
        func.count().label("total"),
        func.sum(func.cast(CategoryRunRecord.status == "DONE", Integer)).label("done"),
        func.sum(func.cast(CategoryRunRecord.status == "FAILED", Integer)).label("failed"),
        func.sum(func.cast(CategoryRunRecord.status == "RUNNING", Integer)).label("running"),
    ).group_by(CategoryRunRecord.batch_id)

    if date:
        query = query.filter(CategoryRunRecord.batch_id.startswith(date.replace("-", "")))

    rows = query.order_by(func.min(CategoryRunRecord.started_at).desc()).all()
    return [
        {
            "batch_id": r.batch_id,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "total": r.total,
            "done": r.done or 0,
            "failed": r.failed or 0,
            "running": r.running or 0,
        }
        for r in rows
    ]
```

Note: The `func.cast(condition, Integer)` pattern for SQLite boolean aggregation — SQLite has no native bool, so casting the comparison to integer and summing gives the count.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_category_run_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/services/category_run_service.py tests/test_category_run_service.py
git commit -m "feat: add category_run_service CRUD layer"
```

---

### Task 3: Pydantic Response Schemas

**Files:**
- Modify: `dashboard/schemas.py`

- [ ] **Step 1: Add schemas at the end of dashboard/schemas.py**

```python
class CategoryTaskItem(BaseModel):
    id: int
    category_id: str
    category_name: str
    level1_name: str
    product_line: str
    products: list[str]
    status: str
    step: str
    headline: str
    cloud_file_id: str
    material_id: str
    error_msg: str
    duration_seconds: Optional[float]
    started_at: Optional[str]
    finished_at: Optional[str]


class CategoryBatchDetail(BaseModel):
    batch_id: str
    status: str = ""
    tasks: list[CategoryTaskItem]


class CategoryBatchSummary(BaseModel):
    batch_id: str
    started_at: Optional[str]
    total: int
    done: int
    failed: int
    running: int


class CategoryBatchListResponse(BaseModel):
    items: list[CategoryBatchSummary]
```

- [ ] **Step 2: Run existing tests to confirm nothing broke**

Run: `pytest tests/ -v -q`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add dashboard/schemas.py
git commit -m "feat: add Pydantic schemas for category run responses"
```

---

### Task 4: Category Runs Router

**Files:**
- Create: `dashboard/routers/category_runs_router.py`
- Modify: `dashboard/app.py`
- Create: `tests/test_category_runs_router.py`

- [ ] **Step 1: Write failing test for GET /api/category-runs/current**

Create `tests/test_category_runs_router.py`:

```python
import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.database import Base, engine, SessionLocal


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def auth_header(client):
    import os
    user = os.getenv("DASHBOARD_ADMIN_USER", "admin")
    pwd = os.getenv("DASHBOARD_ADMIN_PASSWORD", "change-this")
    resp = client.post("/api/auth/login", json={"username": user, "password": pwd})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_current_no_running(client, auth_header):
    resp = client.get("/api/category-runs/current", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json() is None or resp.json().get("tasks") is not None


def test_list_batches_empty(client, auth_header):
    resp = client.get("/api/category-runs", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []


def test_trigger_and_stop(client, auth_header):
    resp = client.post("/api/category-runs/trigger", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"

    # Stop immediately
    resp2 = client.post("/api/category-runs/stop", headers=auth_header)
    assert resp2.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_category_runs_router.py -v`
Expected: FAIL (router not registered)

- [ ] **Step 3: Create the router**

Create `dashboard/routers/category_runs_router.py`:

```python
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
```

- [ ] **Step 4: Register router in dashboard/app.py**

Add these two lines following the existing router imports and `app.include_router` calls in `dashboard/app.py`:

Import (after the `tasks_router` import):
```python
from dashboard.routers.category_runs_router import router as category_runs_router
```

Register (after `app.include_router(tasks_router)`):
```python
app.include_router(category_runs_router)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_category_runs_router.py -v`
Expected: PASS (except `test_trigger_and_stop` may fail because `run_daily_category_pipeline` signature hasn't been updated yet — that's expected and will be fixed in Task 5)

- [ ] **Step 6: Commit**

```bash
git add dashboard/routers/category_runs_router.py dashboard/app.py tests/test_category_runs_router.py
git commit -m "feat: add category-runs REST API router"
```

---

### Task 5: Pipeline Progress Integration

**Files:**
- Modify: `category_pipeline.py`

This is the core change: make `run_daily_category_pipeline` and `process_category_task` write progress to the DB.

- [ ] **Step 1: Update `run_daily_category_pipeline` signature and body**

Change the function signature to accept `batch_id` and `cancel_event`:

```python
async def run_daily_category_pipeline(
    batch_id: str | None = None,
    cancel_event: asyncio.Event | None = None,
) -> list[dict]:
```

Add these imports at the top of `category_pipeline.py`:

```python
from dashboard.database import SessionLocal
from dashboard.services.category_run_service import (
    create_batch_tasks,
    update_task_step,
    complete_task as db_complete_task,
    fail_task as db_fail_task,
)
```

- [ ] **Step 2: Rewrite the function body with DB hooks**

Replace the body of `run_daily_category_pipeline` (keep the `async with _PIPELINE_LOCK:` wrapper):

```python
async def run_daily_category_pipeline(
    batch_id: str | None = None,
    cancel_event: asyncio.Event | None = None,
) -> list[dict]:
    """Run the full daily pipeline: all 10 symptom categories."""
    if batch_id is None:
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    async with _PIPELINE_LOCK:
        logger.info("=== Daily category pipeline START (batch={}) ===", batch_id)
        all_products = await asyncio.to_thread(fetch_all_records)
        logger.info("Loaded {} products from Feishu", len(all_products))

        all_results: list[dict] = []

        for category in ALL_SYMPTOM_CATEGORIES:
            # Check cancel flag before each category
            if cancel_event and cancel_event.is_set():
                logger.info("Pipeline cancelled by user")
                break

            logger.info("Processing category: {}", category["name"])
            try:
                tasks = await asyncio.to_thread(
                    match_products_to_symptom, category, all_products
                )
            except Exception:
                logger.exception("match_products_to_symptom failed for {}", category["name"])
                continue

            if not tasks:
                logger.info("No matching products for {}, skipping", category["name"])
                continue

            # Register tasks in DB
            task_defs = [
                {
                    "category_id": t.category_id,
                    "category_name": t.category_name,
                    "level1_name": category.get("level1_name", ""),
                    "product_line": t.product_line,
                    "products": [p.product_name for p in t.products],
                }
                for t in tasks
            ]
            try:
                db = SessionLocal()
                db_rows = create_batch_tasks(db, batch_id, task_defs)
                db_row_ids = [r.id for r in db_rows]
                db.close()
            except Exception:
                logger.exception("DB create_batch_tasks failed, continuing without progress tracking")
                db_row_ids = [None] * len(tasks)

            for task, db_row_id in zip(tasks, db_row_ids):
                if cancel_event and cancel_event.is_set():
                    logger.info("Pipeline cancelled by user")
                    break

                result = await process_category_task(task, db_row_id=db_row_id)
                all_results.append(result)
                await asyncio.sleep(2)

        done = sum(1 for r in all_results if r["status"] == "DONE")
        failed = sum(1 for r in all_results if r["status"] == "FAILED")
        logger.info(
            "=== Daily category pipeline END: {} done, {} failed ===",
            done, failed,
        )
        return all_results
```

- [ ] **Step 3: Update process_category_task to accept db_row_id and write step progress**

Change the signature:
```python
async def process_category_task(
    task: CategoryPosterTask,
    db_row_id: int | None = None,
) -> dict:
```

Add a helper inside or before the function:
```python
def _update_step(db_row_id: int | None, step: str) -> None:
    """Write step progress to DB. Silently ignore errors."""
    if db_row_id is None:
        return
    try:
        db = SessionLocal()
        update_task_step(db, db_row_id, step)
        db.close()
    except Exception:
        pass
```

Insert `_update_step` calls before each step in the try block:
- Before content generation: `await asyncio.to_thread(_update_step, db_row_id, "content")`
- Before asset loading: `await asyncio.to_thread(_update_step, db_row_id, "image")`
- Before image generation: (same step "image", already set)
- Before upload: `await asyncio.to_thread(_update_step, db_row_id, "uploading")`
- Before register_material: `await asyncio.to_thread(_update_step, db_row_id, "registering")`

After `_finalize(result, "DONE")`:
```python
if db_row_id:
    try:
        db = SessionLocal()
        db_complete_task(db, db_row_id, result["headline"], result.get("cloud_file_id", ""), result.get("material_id", ""), result.get("duration_seconds", 0))
        db.close()
    except Exception:
        pass
```

In each except block, after `_finalize(result, "FAILED", msg)`:
```python
if db_row_id:
    try:
        db = SessionLocal()
        db_fail_task(db, db_row_id, msg)
        db.close()
    except Exception:
        pass
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v -q`
Expected: ALL PASS (existing tests don't pass batch_id/cancel_event, so defaults of None keep them working)

- [ ] **Step 5: Commit**

```bash
git add category_pipeline.py
git commit -m "feat: pipeline writes step progress to DB for dashboard"
```

---

### Task 6: Frontend API Client + View

**Files:**
- Create: `frontend/src/api/categoryRuns.ts`
- Create: `frontend/src/views/CategoryRunsView.vue`

- [ ] **Step 1: Create API client**

Create `frontend/src/api/categoryRuns.ts`:

```typescript
import request from './request'

export function getCurrent() {
  return request.get('/category-runs/current')
}

export function getBatchDetail(batchId: string) {
  return request.get(`/category-runs/${batchId}`)
}

export function listBatches(params?: { date?: string }) {
  return request.get('/category-runs', { params })
}

export function triggerPipeline() {
  return request.post('/category-runs/trigger')
}

export function stopPipeline() {
  return request.post('/category-runs/stop')
}
```

- [ ] **Step 2: Create CategoryRunsView.vue**

Create `frontend/src/views/CategoryRunsView.vue`:

```vue
<template>
  <div class="category-runs-view">
    <!-- Action Bar -->
    <el-card shadow="never" class="action-card">
      <div class="action-bar">
        <div class="left">
          <el-tag :type="isRunning ? 'warning' : 'info'" size="large" effect="dark">
            {{ isRunning ? '运行中' : '空闲' }}
          </el-tag>
          <span v-if="isRunning && currentBatch" class="progress-text">
            {{ doneCount }}/{{ currentBatch.tasks.length }} 完成
          </span>
        </div>
        <div class="right">
          <el-button
            type="primary"
            icon="VideoPlay"
            :disabled="isRunning"
            :loading="triggering"
            @click="handleTrigger"
          >
            立即触发
          </el-button>
          <el-button
            type="danger"
            icon="SwitchButton"
            :disabled="!isRunning"
            @click="handleStop"
          >
            终止
          </el-button>
          <el-switch
            v-model="autoRefresh"
            active-text="自动刷新"
            style="margin-left: 16px"
          />
        </div>
      </div>
    </el-card>

    <!-- Live Progress -->
    <el-card v-if="isRunning && currentBatch" shadow="never" class="progress-card">
      <template #header>
        <span>当前进度 · 批次 {{ currentBatch.batch_id }}</span>
      </template>
      <el-progress
        :percentage="progressPct"
        :stroke-width="20"
        :text-inside="true"
        striped
        striped-flow
        style="margin-bottom: 16px"
      />
      <el-table :data="currentBatch.tasks" stripe border size="small">
        <el-table-column prop="category_name" label="分类" width="130" />
        <el-table-column prop="product_line" label="产品线" width="120" />
        <el-table-column label="步骤" width="320">
          <template #default="{ row }">
            <el-steps :active="stepIndex(row.step)" finish-status="success" simple style="margin: 0">
              <el-step title="匹配" />
              <el-step title="文案" />
              <el-step title="生图" />
              <el-step title="上传" />
              <el-step title="注册" />
            </el-steps>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag
              :type="statusType(row.status)"
              size="small"
            >{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="headline" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column label="耗时" width="80" align="right">
          <template #default="{ row }">
            {{ row.duration_seconds ? row.duration_seconds.toFixed(1) + 's' : '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- History -->
    <el-card shadow="never" class="history-card">
      <template #header>
        <div class="history-header">
          <span>历史记录</span>
          <el-date-picker
            v-model="historyDate"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            @change="loadBatches"
            style="width: 160px"
          />
        </div>
      </template>

      <el-empty v-if="batches.length === 0" description="暂无记录" />

      <div v-for="batch in batches" :key="batch.batch_id" class="batch-section">
        <div class="batch-header" @click="toggleBatch(batch.batch_id)">
          <span class="batch-title">
            批次 {{ batch.batch_id }}
            <el-tag size="small" type="success">{{ batch.done }} 成功</el-tag>
            <el-tag v-if="batch.failed > 0" size="small" type="danger">{{ batch.failed }} 失败</el-tag>
            <el-tag size="small" type="info">共 {{ batch.total }}</el-tag>
          </span>
          <el-icon>
            <ArrowDown v-if="!expandedBatches.has(batch.batch_id)" />
            <ArrowUp v-else />
          </el-icon>
        </div>
        <el-table
          v-if="expandedBatches.has(batch.batch_id)"
          :data="batchDetails[batch.batch_id] || []"
          v-loading="loadingDetail === batch.batch_id"
          stripe
          border
          size="small"
          style="margin-top: 8px"
        >
          <el-table-column prop="category_name" label="分类" width="130" />
          <el-table-column prop="product_line" label="产品线" width="120" />
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="headline" label="标题" min-width="180" show-overflow-tooltip />
          <el-table-column label="产品" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.products?.join('、') || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="80" align="right">
            <template #default="{ row }">
              {{ row.duration_seconds ? row.duration_seconds.toFixed(1) + 's' : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="error_msg" label="错误信息" min-width="150" show-overflow-tooltip />
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getCurrent,
  listBatches,
  getBatchDetail,
  triggerPipeline,
  stopPipeline,
} from '@/api/categoryRuns'

// --- State ---
const currentBatch = ref<any>(null)
const isRunning = ref(false)
const triggering = ref(false)
const autoRefresh = ref(true)
const historyDate = ref(new Date().toISOString().slice(0, 10))
const batches = ref<any[]>([])
const expandedBatches = ref(new Set<string>())
const batchDetails = ref<Record<string, any[]>>({})
const loadingDetail = ref('')

let timer: ReturnType<typeof setInterval> | null = null

// --- Computed ---
const doneCount = computed(() =>
  currentBatch.value?.tasks?.filter((t: any) => t.status === 'DONE').length ?? 0
)
const progressPct = computed(() => {
  if (!currentBatch.value?.tasks?.length) return 0
  return Math.round((doneCount.value / currentBatch.value.tasks.length) * 100)
})

// --- Helpers ---
function stepIndex(step: string): number {
  const steps: Record<string, number> = {
    matching: 0, content: 1, image: 2, uploading: 3, registering: 4, done: 5,
  }
  return steps[step] ?? 0
}

function statusType(status: string) {
  const map: Record<string, string> = {
    DONE: 'success', FAILED: 'danger', RUNNING: 'warning', PENDING: 'info',
  }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    DONE: '完成', FAILED: '失败', RUNNING: '进行中', PENDING: '等待中',
  }
  return map[status] || status
}

// --- Data loading ---
async function loadCurrent() {
  try {
    const { data } = await getCurrent()
    currentBatch.value = data
    isRunning.value = data !== null && data !== ''
  } catch {
    isRunning.value = false
  }
}

async function loadBatches() {
  try {
    const { data } = await listBatches({ date: historyDate.value || undefined })
    batches.value = data.items || []
  } catch {
    batches.value = []
  }
}

async function toggleBatch(batchId: string) {
  if (expandedBatches.value.has(batchId)) {
    expandedBatches.value.delete(batchId)
    return
  }
  expandedBatches.value.add(batchId)
  if (!batchDetails.value[batchId]) {
    loadingDetail.value = batchId
    try {
      const { data } = await getBatchDetail(batchId)
      batchDetails.value[batchId] = data?.tasks || []
    } catch {
      batchDetails.value[batchId] = []
    }
    loadingDetail.value = ''
  }
}

// --- Actions ---
async function handleTrigger() {
  triggering.value = true
  try {
    await triggerPipeline()
    ElMessage.success('流水线已触发')
    autoRefresh.value = true
    await loadCurrent()
  } catch {
    ElMessage.error('触发失败')
  }
  triggering.value = false
}

async function handleStop() {
  try {
    await stopPipeline()
    ElMessage.info('已发送终止信号')
  } catch {
    ElMessage.error('终止失败')
  }
}

// --- Polling ---
function startPolling() {
  stopPolling()
  timer = setInterval(async () => {
    if (document.hidden || !autoRefresh.value) return
    await loadCurrent()
    // Also refresh history if pipeline just finished
    if (!isRunning.value) {
      await loadBatches()
    }
  }, 3000)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(async () => {
  await Promise.all([loadCurrent(), loadBatches()])
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.category-runs-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.action-bar .left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.action-bar .right {
  display: flex;
  align-items: center;
}
.progress-text {
  font-size: 14px;
  color: #606266;
}
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.batch-section {
  margin-bottom: 16px;
}
.batch-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  cursor: pointer;
  user-select: none;
}
.batch-header:hover {
  background: #ebeef5;
}
.batch-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/categoryRuns.ts frontend/src/views/CategoryRunsView.vue
git commit -m "feat: add CategoryRunsView frontend with live polling"
```

---

### Task 7: Wire Route, Sidebar, Build & Deploy

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/DashboardLayout.vue`

- [ ] **Step 1: Add route**

In `frontend/src/router/index.ts`, add this entry inside the `children` array, after the `runs` route:

```typescript
{
  path: 'category-runs',
  name: 'category-runs',
  component: () => import('../views/CategoryRunsView.vue'),
  meta: { title: '分类海报' }
},
```

- [ ] **Step 2: Add sidebar item**

In `frontend/src/layouts/DashboardLayout.vue`, add this menu item after the `<el-menu-item index="/tasks">` block:

```vue
<el-menu-item index="/category-runs">
  <el-icon><Picture /></el-icon>
  <span>分类海报</span>
</el-menu-item>
```

Note: `Picture` is an Element Plus icon. No extra import needed — Element Plus auto-registers icons when using `@element-plus/icons-vue`.

- [ ] **Step 3: Build frontend**

```bash
cd frontend && npm run build
```

This outputs to `static/` directory.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/layouts/DashboardLayout.vue static/
git commit -m "feat: wire category-runs route and sidebar, build frontend"
```

- [ ] **Step 5: Deploy to server**

Upload new/changed files and restart:

```python
# Use paramiko SFTP to upload:
# - dashboard/db_models.py
# - dashboard/services/category_run_service.py
# - dashboard/schemas.py
# - dashboard/routers/category_runs_router.py
# - dashboard/app.py
# - category_pipeline.py
# - static/index.html
# - static/assets/*  (rebuilt frontend bundle)

# Then: sudo systemctl restart poster-dashboard
```

- [ ] **Step 6: Verify**

Open http://49.235.145.49/ → 侧边栏应出现「分类海报」→ 点击进入 → 页面加载无报错 → 点击「立即触发」→ 进度面板出现并实时更新。

---

## Self-Review Checklist

**Spec coverage:**
- [x] DB table for storing results → Task 1
- [x] Service layer CRUD → Task 2
- [x] Pydantic schemas → Task 3
- [x] REST API (list, current, detail, trigger, stop) → Task 4
- [x] Pipeline writes progress at each step → Task 5
- [x] Frontend view with live progress + history → Task 6
- [x] Route + sidebar + build + deploy → Task 7

**Placeholder scan:** None found. All code blocks are complete.

**Type consistency:**
- `batch_id` is `str` everywhere (service, router, frontend)
- `CategoryRunRecord.id` is `int`, used as `db_row_id: int | None` in pipeline
- `step` values: matching → content → image → uploading → registering → done — consistent between service, pipeline, and frontend `stepIndex()`
- `status` values: PENDING / RUNNING / DONE / FAILED — consistent across all layers
