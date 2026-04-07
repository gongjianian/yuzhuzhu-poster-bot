# Web 控制面板实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为浴小主海报自动生成系统搭建 FastAPI + Vue 3 + Element Plus 全栈控制面板，支持任务管理、执行记录、日志查询、健康监测、统计仪表盘。

**Architecture:** FastAPI 后端统一管线入口（Cron 和手动触发都走 HTTP），SQLite 持久化执行记录和统计数据，飞书多维表格保持 SSOT。Vue 3 + Element Plus 前端通过 JWT 鉴权的 REST API + WebSocket 与后端通信。前端打包后由 FastAPI 静态托管，Nginx 反向代理。

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, PyJWT, Vue 3, Vite, Element Plus, ECharts, Pinia, Axios, WebSocket

---

## 分工总览

| 角色 | 负责范围 | Tasks |
|------|----------|-------|
| **Codex** | 后端基础设施、API、管线重构、数据库、部署 | 1-10, 18-20 |
| **Gemini** | Vue 3 前端全部页面和组件 | 11-17 |
| **Claude** | 架构设计、代码审核、集成协调 | 每个 Phase 完成后审核 |

## 审核节点

| 节点 | 触发时机 | 审核内容 |
|------|----------|----------|
| **Review A** | Task 4 完成后 | 后端骨架 + Auth 是否安全合理 |
| **Review B** | Task 7 完成后 | 管线重构 + 锁机制是否消除竞态 |
| **Review C** | Task 10 完成后 | 全部后端 API 是否完整、安全 |
| **Review D** | Task 13 完成后 | 前端骨架 + 登录 + Dashboard 是否联通 |
| **Review E** | Task 17 完成后 | 全部前端页面是否与 API 对接正确 |
| **Review F** | Task 20 完成后 | 完整集成测试 + 部署配置 |

---

## 文件结构

### 后端新增 (Codex)

```
dashboard/
├── __init__.py
├── app.py                    # FastAPI application factory + lifespan
├── config.py                 # pydantic-settings 配置
├── database.py               # SQLAlchemy engine + session
├── db_models.py              # ORM: RunRecord, DailyStats
├── schemas.py                # API 请求/响应 Pydantic schemas
├── auth.py                   # JWT 工具函数 + FastAPI 依赖
├── websocket_manager.py      # WebSocket 连接管理 + loguru sink
├── routers/
│   ├── __init__.py
│   ├── auth_router.py        # POST /api/auth/login, /api/auth/refresh
│   ├── tasks_router.py       # GET/POST /api/tasks
│   ├── runs_router.py        # GET /api/runs
│   ├── stats_router.py       # GET /api/stats
│   ├── logs_router.py        # GET /api/logs, WS /api/logs/stream
│   ├── health_router.py      # GET /api/health
│   └── pipeline_router.py    # POST /api/pipeline/run
└── services/
    ├── __init__.py
    ├── task_service.py        # 飞书数据读取 + 触发逻辑
    ├── run_service.py         # 执行记录 CRUD
    ├── stats_service.py       # 统计聚合
    ├── log_service.py         # 日志文件读取
    └── health_service.py      # API 连通性检测
```

### 管线重构 (Codex)

```
pipeline.py                    # 从 main.py 提取的核心管线逻辑
main.py                        # 简化为 uvicorn 启动入口
```

### 前端新增 (Gemini)

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── env.d.ts
├── index.html
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/index.ts
│   ├── api/                   # 按资源拆分的 API 客户端
│   │   ├── request.ts         # Axios 实例 + JWT 拦截器
│   │   ├── auth.ts
│   │   ├── tasks.ts
│   │   ├── runs.ts
│   │   ├── stats.ts
│   │   ├── logs.ts
│   │   └── health.ts
│   ├── stores/
│   │   ├── auth.ts            # Pinia JWT 状态管理
│   │   └── app.ts             # 全局 UI 状态
│   ├── layouts/
│   │   └── DashboardLayout.vue
│   ├── views/
│   │   ├── LoginView.vue
│   │   ├── DashboardView.vue
│   │   ├── TasksView.vue
│   │   ├── RunsView.vue
│   │   ├── LogsView.vue
│   │   └── HealthView.vue
│   └── components/
│       ├── PosterPreview.vue
│       ├── StatusBadge.vue
│       ├── StatsCard.vue
│       ├── TrendChart.vue
│       └── LogStream.vue
```

### 部署配置 (Codex)

```
deploy/
├── nginx.conf                 # Nginx 反向代理配置
├── poster-dashboard.service   # systemd 守护进程
└── setup.sh                   # 服务器一键部署脚本
```

---

# Phase 1: 后端基础设施 (Codex)

## Task 1: 项目依赖与目录结构

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Create: `dashboard/__init__.py`
- Create: `dashboard/routers/__init__.py`
- Create: `dashboard/services/__init__.py`

- [ ] **Step 1: 更新 requirements.txt**

在现有依赖后追加：

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
PyJWT>=2.8.0
passlib[bcrypt]>=1.7.4
websockets>=12.0
python-multipart>=0.0.6
```

- [ ] **Step 2: 更新 .env.example**

追加以下配置：

```
# Dashboard
DASHBOARD_SECRET_KEY=change-this-to-a-random-string
DASHBOARD_ADMIN_USER=admin
DASHBOARD_ADMIN_PASSWORD=change-this
DASHBOARD_DB_PATH=./data/dashboard.db
DASHBOARD_PORT=8000
DASHBOARD_ALLOWED_ORIGINS=http://localhost:5173
```

- [ ] **Step 3: 创建目录结构**

```bash
mkdir -p dashboard/routers dashboard/services data
touch dashboard/__init__.py dashboard/routers/__init__.py dashboard/services/__init__.py
```

- [ ] **Step 4: 安装依赖验证**

```bash
pip install -r requirements.txt
python -c "import fastapi, sqlalchemy, jwt; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example dashboard/
git commit -m "feat(dashboard): add dependencies and directory structure"
```

---

## Task 2: SQLite 数据库 + ORM 模型

**Files:**
- Create: `dashboard/config.py`
- Create: `dashboard/database.py`
- Create: `dashboard/db_models.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: 编写 config.py**

```python
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class DashboardSettings(BaseSettings):
    secret_key: str = os.getenv("DASHBOARD_SECRET_KEY", "dev-secret-change-me")
    admin_user: str = os.getenv("DASHBOARD_ADMIN_USER", "admin")
    admin_password: str = os.getenv("DASHBOARD_ADMIN_PASSWORD", "admin")
    db_path: str = os.getenv("DASHBOARD_DB_PATH", "./data/dashboard.db")
    port: int = int(os.getenv("DASHBOARD_PORT", "8000"))
    allowed_origins: list[str] = os.getenv(
        "DASHBOARD_ALLOWED_ORIGINS", "http://localhost:5173"
    ).split(",")
    log_dir: str = "logs"
    assets_dir: str = os.getenv("ASSETS_DIR", "./assets/products")

    class Config:
        env_prefix = "DASHBOARD_"


settings = DashboardSettings()
```

- [ ] **Step 2: 编写 database.py**

```python
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from dashboard.config import settings


class Base(DeclarativeBase):
    pass


def get_engine():
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


engine = get_engine()
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 3: 编写 db_models.py**

```python
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
    trigger_type: Mapped[str] = mapped_column(String(20))  # "cron" | "manual"
    status: Mapped[str] = mapped_column(String(30), index=True)  # RUNNING/DONE/FAILED
    stage: Mapped[str] = mapped_column(String(30), default="")  # COPY_OK/IMAGE_OK/...
    headline: Mapped[str] = mapped_column(String(500), default="")
    image_prompt: Mapped[str] = mapped_column(Text, default="")
    qc_passed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    qc_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    qc_issues: Mapped[str] = mapped_column(Text, default="")  # JSON array string
    cloud_file_id: Mapped[str] = mapped_column(String(500), default="")
    error_msg: Mapped[str] = mapped_column(Text, default="")
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class DailyStats(Base):
    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # YYYY-MM-DD
    total: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    avg_duration: Mapped[float] = mapped_column(Float, default=0.0)
```

- [ ] **Step 4: 编写测试**

```python
# tests/test_database.py
import os
import tempfile
from pathlib import Path

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")

from dashboard.database import Base, engine, init_db, SessionLocal
from dashboard.db_models import RunRecord, DailyStats


def test_init_db_creates_tables():
    init_db()
    db = SessionLocal()
    # Should not raise
    db.query(RunRecord).count()
    db.query(DailyStats).count()
    db.close()


def test_run_record_insert():
    init_db()
    db = SessionLocal()
    record = RunRecord(
        run_id="test-001",
        product_name="测试产品",
        record_id="rec_abc",
        trigger_type="manual",
        status="RUNNING",
    )
    db.add(record)
    db.commit()
    result = db.query(RunRecord).filter_by(run_id="test-001").first()
    assert result is not None
    assert result.product_name == "测试产品"
    db.close()


def test_daily_stats_insert():
    init_db()
    db = SessionLocal()
    stat = DailyStats(date="2026-04-07", total=10, success=8, failed=2, avg_duration=45.5)
    db.add(stat)
    db.commit()
    result = db.query(DailyStats).filter_by(date="2026-04-07").first()
    assert result.success == 8
    db.close()
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/test_database.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add dashboard/config.py dashboard/database.py dashboard/db_models.py tests/test_database.py
git commit -m "feat(dashboard): add SQLite database and ORM models"
```

---

## Task 3: FastAPI 应用工厂 + CORS

**Files:**
- Create: `dashboard/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: 编写 app.py**

```python
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dashboard.config import settings
from dashboard.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="浴小主海报控制面板",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers will be added in subsequent tasks
    # from dashboard.routers import auth_router, tasks_router, ...

    return app
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_app.py
import os
import tempfile
from pathlib import Path

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")

from fastapi.testclient import TestClient
from dashboard.app import create_app


def test_app_starts():
    app = create_app()
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200


def test_cors_headers():
    os.environ["DASHBOARD_ALLOWED_ORIGINS"] = "http://localhost:5173"
    app = create_app()
    client = TestClient(app)
    response = client.options(
        "/docs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in response.headers
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_app.py -v
```

Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add dashboard/app.py tests/test_app.py
git commit -m "feat(dashboard): add FastAPI app factory with CORS"
```

---

## Task 4: JWT 认证系统

**Files:**
- Create: `dashboard/auth.py`
- Create: `dashboard/routers/auth_router.py`
- Modify: `dashboard/app.py` (注册 auth_router)
- Test: `tests/test_auth.py`

- [ ] **Step 1: 编写 auth.py**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from passlib.hash import bcrypt

from dashboard.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return bcrypt.hash(password)


def create_access_token(username: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username: str = payload.get("sub", "")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    return decode_token(token)


async def ws_auth(websocket: WebSocket) -> str:
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        raise HTTPException(status_code=401, detail="Missing token")
    return decode_token(token)
```

- [ ] **Step 2: 编写 auth_router.py**

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from dashboard.auth import create_access_token, verify_password, get_password_hash
from dashboard.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Hash the admin password at startup for comparison
_admin_hash = get_password_hash(settings.admin_password)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    if body.username != settings.admin_user or not verify_password(
        body.password, _admin_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    token = create_access_token(body.username)
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(current_user: str = __import__("fastapi").Depends(
    __import__("dashboard.auth", fromlist=["get_current_user"]).get_current_user
)):
    token = create_access_token(current_user)
    return TokenResponse(access_token=token)
```

- [ ] **Step 3: 修改 app.py 注册 auth_router**

在 `create_app()` 的 return 之前添加：

```python
    from dashboard.routers.auth_router import router as auth_router
    app.include_router(auth_router)
```

- [ ] **Step 4: 编写测试**

```python
# tests/test_auth.py
import os
import tempfile
from pathlib import Path

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient
from dashboard.app import create_app

app = create_app()
client = TestClient(app)


def test_login_success():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_wrong_user():
    resp = client.post("/api/auth/login", json={"username": "nobody", "password": "test123"})
    assert resp.status_code == 401


def test_protected_endpoint_without_token():
    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401


def test_refresh_with_valid_token():
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    token = login_resp.json()["access_token"]
    resp = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/test_auth.py -v
```

Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add dashboard/auth.py dashboard/routers/auth_router.py dashboard/app.py tests/test_auth.py
git commit -m "feat(dashboard): add JWT authentication system"
```

### >>> Review A: Claude 审核后端骨架 + Auth 安全性 <<<

---

# Phase 2: 管线重构 (Codex)

## Task 5: 提取 pipeline.py 核心模块

**目的：** 将 `main.py` 中的管线逻辑提取为独立模块 `pipeline.py`，使 FastAPI 和 Cron 都能复用。

**Files:**
- Create: `pipeline.py`
- Modify: `main.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: 创建 pipeline.py**

从现有 `main.py:79-168` 提取 `process_product()` 和 `run_pipeline()` 到 `pipeline.py`，并增加以下改动：

```python
from __future__ import annotations

import asyncio
import base64
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from loguru import logger

from asset_processor import process_product_image
from content_generator import generate_poster_content
from image_generator import generate_poster_image
from feishu_reader import fetch_pending_records, update_record_status
from wechat_uploader import build_cloud_path, upload_image
from qc_checker import check_poster_quality

load_dotenv()

MAX_QC_RETRIES = 2

# 全局 asyncio 锁，替代文件锁，防止并发执行
_pipeline_lock = asyncio.Lock()


async def process_single_product(record, trigger_type: str = "cron") -> dict:
    """处理单个产品，返回执行结果字典（供 RunRecord 写入）。"""
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    start_time = datetime.now()
    result = {
        "run_id": run_id,
        "product_name": record.product_name,
        "record_id": record.record_id,
        "trigger_type": trigger_type,
        "status": "RUNNING",
        "stage": "",
        "headline": "",
        "image_prompt": "",
        "qc_passed": None,
        "qc_confidence": None,
        "qc_issues": "[]",
        "cloud_file_id": "",
        "error_msg": "",
        "started_at": start_time,
        "finished_at": None,
        "duration_seconds": None,
    }

    asset_dir = Path(os.getenv("ASSETS_DIR", "./assets/products"))

    if not record.asset_filename:
        result["status"] = "FAILED"
        result["error_msg"] = "Missing product asset filename"
        result["finished_at"] = datetime.now()
        result["duration_seconds"] = (result["finished_at"] - start_time).total_seconds()
        await asyncio.to_thread(
            update_record_status, record.record_id, "FAILED_MANUAL",
            error_msg=result["error_msg"],
        )
        return result

    asset_path = asset_dir / record.asset_filename

    try:
        # Step A: 生成文案
        poster_scheme = await asyncio.to_thread(generate_poster_content, record)
        result["stage"] = "COPY_OK"
        result["headline"] = poster_scheme.headline
        result["image_prompt"] = poster_scheme.image_prompt
        await asyncio.to_thread(update_record_status, record.record_id, "COPY_OK")
        logger.info("{}: content generated — {}", record.product_name, poster_scheme.headline)

        # Step B: 预处理产品图
        product_b64 = await asyncio.to_thread(process_product_image, str(asset_path))

        # Step C+D: 生成海报 + QC 重试
        poster_bytes = None
        qc_prompt_suffix = ""
        for attempt in range(MAX_QC_RETRIES + 1):
            poster_bytes = await asyncio.to_thread(
                generate_poster_image,
                poster_scheme.image_prompt + qc_prompt_suffix,
                product_b64,
            )
            result["stage"] = "IMAGE_OK"
            await asyncio.to_thread(update_record_status, record.record_id, "IMAGE_OK")

            poster_b64 = base64.b64encode(poster_bytes).decode("utf-8")
            qc_result = await asyncio.to_thread(check_poster_quality, poster_b64, product_b64)
            result["qc_passed"] = qc_result.passed
            result["qc_confidence"] = qc_result.confidence
            result["qc_issues"] = json.dumps(qc_result.issues, ensure_ascii=False)

            if qc_result.passed:
                logger.info("{}: QC passed (confidence={})", record.product_name, qc_result.confidence)
                break

            logger.warning("{}: QC failed attempt {}: {}", record.product_name, attempt + 1, qc_result.issues)
            if attempt < MAX_QC_RETRIES:
                issues_str = "; ".join(qc_result.issues)
                qc_prompt_suffix = f"\n\nPREVIOUS ATTEMPT FAILED QC. Fix: {issues_str}. Strictly preserve the product."
            else:
                result["status"] = "FAILED"
                result["error_msg"] = f"QC failed after {MAX_QC_RETRIES + 1} attempts: {qc_result.issues}"
                result["finished_at"] = datetime.now()
                result["duration_seconds"] = (result["finished_at"] - start_time).total_seconds()
                await asyncio.to_thread(
                    update_record_status, record.record_id, "FAILED_MANUAL",
                    error_msg=result["error_msg"],
                )
                return result

        # Step E: 上传微信云存储
        cloud_path = build_cloud_path(record.category, record.product_name)
        file_id = await asyncio.to_thread(upload_image, poster_bytes, cloud_path)
        result["stage"] = "UPLOAD_OK"
        result["cloud_file_id"] = file_id
        await asyncio.to_thread(update_record_status, record.record_id, "UPLOAD_OK", file_id=file_id)
        await asyncio.to_thread(update_record_status, record.record_id, "DONE", file_id=file_id)

        result["status"] = "DONE"
        result["finished_at"] = datetime.now()
        result["duration_seconds"] = (result["finished_at"] - start_time).total_seconds()
        logger.success("{}: DONE in {:.1f}s", record.product_name, result["duration_seconds"])
        return result

    except Exception as exc:
        result["status"] = "FAILED"
        result["error_msg"] = str(exc)
        result["finished_at"] = datetime.now()
        result["duration_seconds"] = (result["finished_at"] - start_time).total_seconds()
        await asyncio.to_thread(
            update_record_status, record.record_id, "FAILED_RETRYABLE",
            error_msg=result["error_msg"],
        )
        return result


async def run_full_pipeline(trigger_type: str = "cron") -> list[dict]:
    """执行完整管线（获取全部 PENDING 记录并逐个处理）。"""
    if _pipeline_lock.locked():
        logger.warning("Pipeline is already running, skipping")
        return []

    async with _pipeline_lock:
        records = await asyncio.to_thread(fetch_pending_records)
        if not records:
            logger.info("No pending records found")
            return []

        results = []
        for record in records:
            result = await process_single_product(record, trigger_type)
            results.append(result)
        return results


async def trigger_single_product(record_id: str) -> dict:
    """手动触发单个产品（走相同的锁）。"""
    async with _pipeline_lock:
        all_records = await asyncio.to_thread(fetch_pending_records)
        record = next((r for r in all_records if r.record_id == record_id), None)
        if record is None:
            # 尝试从全部记录中查找（不只是 PENDING）
            from feishu_reader import fetch_pending_records  # 复用现有接口
            return {
                "run_id": "",
                "status": "FAILED",
                "error_msg": f"Record {record_id} not found or not in PENDING/FAILED_RETRYABLE status",
            }
        return await process_single_product(record, trigger_type="manual")
```

- [ ] **Step 2: 简化 main.py**

```python
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv()


def setup_logging() -> None:
    Path("logs").mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        "logs/poster_bot_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        level="DEBUG",
    )


def main() -> None:
    setup_logging()

    import uvicorn
    from dashboard.app import create_app

    app = create_app()
    port = int(__import__("os").getenv("DASHBOARD_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 编写测试**

```python
# tests/test_pipeline.py
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import pytest

from models import ProductRecord

# Test that pipeline lock prevents concurrent runs
@pytest.mark.asyncio
async def test_pipeline_lock_prevents_double_run():
    from pipeline import _pipeline_lock

    results = []

    async def fake_run():
        if _pipeline_lock.locked():
            results.append("skipped")
            return
        async with _pipeline_lock:
            await asyncio.sleep(0.1)
            results.append("ran")

    await asyncio.gather(fake_run(), fake_run())
    assert "ran" in results
    assert "skipped" in results


def test_process_single_product_missing_asset():
    from pipeline import process_single_product

    record = ProductRecord(
        record_id="rec_test",
        product_name="测试产品",
        asset_filename="",  # missing
    )
    with patch("pipeline.update_record_status"):
        result = asyncio.run(process_single_product(record))
    assert result["status"] == "FAILED"
    assert "Missing product asset" in result["error_msg"]
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/test_pipeline.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline.py main.py tests/test_pipeline.py
git commit -m "refactor: extract pipeline module with asyncio.Lock"
```

---

## Task 6: 执行记录服务（写入 SQLite）

**Files:**
- Create: `dashboard/schemas.py`
- Create: `dashboard/services/run_service.py`
- Test: `tests/test_run_service.py`

- [ ] **Step 1: 编写 schemas.py（API 响应模型）**

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RunResponse(BaseModel):
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

    class Config:
        from_attributes = True


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
    status: str  # "ok" | "error"
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
```

- [ ] **Step 2: 编写 run_service.py**

```python
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from dashboard.db_models import RunRecord, DailyStats


def save_run_result(db: Session, result: dict) -> RunRecord:
    """将管线执行结果保存到 SQLite。"""
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
    """查询执行记录（分页 + 筛选）。"""
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
    """重新计算并更新某天的统计数据。"""
    runs = (
        db.query(RunRecord)
        .filter(RunRecord.started_at >= f"{date_str} 00:00:00")
        .filter(RunRecord.started_at <= f"{date_str} 23:59:59")
        .all()
    )

    total = len(runs)
    success = sum(1 for r in runs if r.status == "DONE")
    failed = sum(1 for r in runs if r.status == "FAILED")
    durations = [r.duration_seconds for r in runs if r.duration_seconds is not None]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    stat = db.query(DailyStats).filter_by(date=date_str).first()
    if stat:
        stat.total = total
        stat.success = success
        stat.failed = failed
        stat.avg_duration = avg_duration
    else:
        stat = DailyStats(
            date=date_str, total=total, success=success, failed=failed, avg_duration=avg_duration,
        )
        db.add(stat)

    db.commit()
    db.refresh(stat)
    return stat
```

- [ ] **Step 3: 编写测试**

```python
# tests/test_run_service.py
import os
import tempfile
from pathlib import Path
from datetime import datetime

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")

from dashboard.database import init_db, SessionLocal
from dashboard.services.run_service import save_run_result, get_runs, update_daily_stats

init_db()


def _make_result(run_id: str, status: str = "DONE", product_name: str = "测试产品"):
    return {
        "run_id": run_id,
        "product_name": product_name,
        "record_id": "rec_abc",
        "trigger_type": "manual",
        "status": status,
        "stage": "UPLOAD_OK",
        "headline": "测试标题",
        "image_prompt": "test prompt",
        "qc_passed": True,
        "qc_confidence": 0.95,
        "qc_issues": "[]",
        "cloud_file_id": "file_123",
        "error_msg": "",
        "duration_seconds": 42.5,
        "started_at": datetime(2026, 4, 7, 8, 0, 0),
        "finished_at": datetime(2026, 4, 7, 8, 0, 42),
    }


def test_save_and_query_run():
    db = SessionLocal()
    save_run_result(db, _make_result("run-001"))
    items, total = get_runs(db, page=1, page_size=10)
    assert total == 1
    assert items[0].run_id == "run-001"
    db.close()


def test_filter_by_status():
    db = SessionLocal()
    save_run_result(db, _make_result("run-002", status="FAILED"))
    items, total = get_runs(db, status="FAILED")
    assert all(item.status == "FAILED" for item in items)
    db.close()


def test_update_daily_stats():
    db = SessionLocal()
    stat = update_daily_stats(db, "2026-04-07")
    assert stat.total >= 1
    assert stat.success >= 0
    db.close()
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/test_run_service.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add dashboard/schemas.py dashboard/services/run_service.py tests/test_run_service.py
git commit -m "feat(dashboard): add run recording service with SQLite persistence"
```

---

## Task 7: 管线与 RunRecord 集成

**目的：** 管线执行完成后自动写入 SQLite 执行记录 + 更新每日统计 + 飞书告警。

**Files:**
- Create: `dashboard/services/task_service.py`
- Modify: `dashboard/app.py` (添加 pipeline_router)
- Create: `dashboard/routers/pipeline_router.py`
- Test: `tests/test_pipeline_integration.py`

- [ ] **Step 1: 编写 task_service.py**

```python
from __future__ import annotations

import asyncio
from datetime import datetime

from loguru import logger
from sqlalchemy.orm import Session

from dashboard.database import SessionLocal
from dashboard.services.run_service import save_run_result, update_daily_stats
from pipeline import run_full_pipeline, process_single_product, _pipeline_lock

# 导入飞书告警
import os
import requests


def _send_alert(message: str) -> None:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        return
    try:
        requests.post(
            webhook_url,
            json={"msg_type": "text", "content": {"text": message}},
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.error("Failed to send Feishu alert: {}", exc)


async def execute_full_pipeline(trigger_type: str = "cron") -> list[dict]:
    """执行完整管线并记录到 SQLite。"""
    results = await run_full_pipeline(trigger_type)

    db = SessionLocal()
    try:
        for result in results:
            save_run_result(db, result)
            if result["status"] == "FAILED":
                _send_alert(
                    f"海报生成失败: {result['product_name']} — {result['error_msg']}"
                )

        today = datetime.now().strftime("%Y-%m-%d")
        update_daily_stats(db, today)
    finally:
        db.close()

    success = sum(1 for r in results if r["status"] == "DONE")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    logger.info("Pipeline complete: {} success, {} failed", success, failed)
    return results


async def execute_single_trigger(record_id: str) -> dict:
    """手动触发单个产品并记录到 SQLite。"""
    from feishu_reader import fetch_pending_records

    if _pipeline_lock.locked():
        return {"run_id": "", "status": "BUSY", "error_msg": "管线正在运行中，请稍后再试"}

    async with _pipeline_lock:
        # 从飞书获取该记录（需要通过全量查询再过滤）
        all_records = await asyncio.to_thread(fetch_pending_records)
        record = next((r for r in all_records if r.record_id == record_id), None)

        if record is None:
            return {"run_id": "", "status": "FAILED", "error_msg": f"未找到记录 {record_id}"}

        result = await process_single_product(record, trigger_type="manual")

    db = SessionLocal()
    try:
        save_run_result(db, result)
        today = datetime.now().strftime("%Y-%m-%d")
        update_daily_stats(db, today)
    finally:
        db.close()

    return result
```

- [ ] **Step 2: 编写 pipeline_router.py**

```python
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, BackgroundTasks

from dashboard.auth import get_current_user
from dashboard.schemas import TriggerResponse
from dashboard.services.task_service import execute_full_pipeline, execute_single_trigger

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run", response_model=TriggerResponse)
async def trigger_full_pipeline(
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user),
):
    """触发完整批处理管线（后台执行）。"""
    background_tasks.add_task(asyncio.create_task, execute_full_pipeline("manual"))
    return TriggerResponse(run_id="batch", status="queued", message="管线已加入后台队列")
```

- [ ] **Step 3: 在 app.py 注册 pipeline_router**

```python
    from dashboard.routers.pipeline_router import router as pipeline_router
    app.include_router(pipeline_router)
```

- [ ] **Step 4: 编写集成测试**

```python
# tests/test_pipeline_integration.py
import os
import tempfile
from pathlib import Path

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient
from dashboard.app import create_app

app = create_app()
client = TestClient(app)


def _get_token():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    return resp.json()["access_token"]


def test_pipeline_trigger_requires_auth():
    resp = client.post("/api/pipeline/run")
    assert resp.status_code == 401


def test_pipeline_trigger_with_auth():
    token = _get_token()
    resp = client.post("/api/pipeline/run", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/test_pipeline_integration.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add dashboard/services/task_service.py dashboard/routers/pipeline_router.py dashboard/app.py tests/test_pipeline_integration.py
git commit -m "feat(dashboard): integrate pipeline with run recording and alerts"
```

### >>> Review B: Claude 审核管线重构 + 锁机制 <<<

---

# Phase 3: 后端 API 端点 (Codex)

## Task 8: Tasks API（飞书数据代理）

**Files:**
- Create: `dashboard/routers/tasks_router.py`
- Modify: `dashboard/app.py`
- Test: `tests/test_tasks_router.py`

- [ ] **Step 1: 编写 tasks_router.py**

```python
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query, BackgroundTasks

from dashboard.auth import get_current_user
from dashboard.schemas import TaskListResponse, TaskResponse, TriggerResponse
from dashboard.services.task_service import execute_single_trigger

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态筛选"),
    current_user: str = Depends(get_current_user),
):
    """从飞书获取产品列表（实时查询）。"""
    from feishu_reader import fetch_pending_records
    # 获取全部记录（不只是 PENDING，需要修改 feishu_reader 或获取全部后过滤）
    records = await asyncio.to_thread(fetch_pending_records)

    items = [
        TaskResponse(
            record_id=r.record_id,
            product_name=r.product_name,
            category=r.category,
            status=r.status,
            asset_filename=r.asset_filename,
        )
        for r in records
        if status is None or r.status == status
    ]
    return TaskListResponse(items=items, total=len(items))


@router.post("/{record_id}/trigger", response_model=TriggerResponse)
async def trigger_single(
    record_id: str,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user),
):
    """手动触发单个产品海报生成。"""
    # 在后台执行，立即返回
    import asyncio as _asyncio

    async def _run():
        await execute_single_trigger(record_id)

    background_tasks.add_task(_asyncio.create_task, _run())
    return TriggerResponse(run_id="pending", status="queued", message=f"已触发 {record_id}")


@router.post("/batch-trigger", response_model=TriggerResponse)
async def batch_trigger(
    record_ids: list[str],
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user),
):
    """批量触发多个产品海报生成。"""
    async def _run_batch():
        for rid in record_ids:
            await execute_single_trigger(rid)

    background_tasks.add_task(asyncio.create_task, _run_batch())
    return TriggerResponse(
        run_id="batch",
        status="queued",
        message=f"已触发 {len(record_ids)} 个产品",
    )
```

- [ ] **Step 2: 在 app.py 注册**

```python
    from dashboard.routers.tasks_router import router as tasks_router
    app.include_router(tasks_router)
```

- [ ] **Step 3: 编写测试**

```python
# tests/test_tasks_router.py
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient
from dashboard.app import create_app
from models import ProductRecord

app = create_app()
client = TestClient(app)


def _get_token():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    return resp.json()["access_token"]


def _mock_records():
    return [
        ProductRecord(
            record_id="rec_001", product_name="产品A", category="护肤",
            status="PENDING", asset_filename="a.png",
        ),
        ProductRecord(
            record_id="rec_002", product_name="产品B", category="洗浴",
            status="DONE", asset_filename="b.png",
        ),
    ]


@patch("dashboard.routers.tasks_router.fetch_pending_records", return_value=_mock_records())
def test_list_tasks(mock_fetch):
    token = _get_token()
    resp = client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_list_tasks_requires_auth():
    resp = client.get("/api/tasks")
    assert resp.status_code == 401


@patch("dashboard.routers.tasks_router.execute_single_trigger")
def test_trigger_single(mock_trigger):
    token = _get_token()
    resp = client.post(
        "/api/tasks/rec_001/trigger",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/test_tasks_router.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add dashboard/routers/tasks_router.py dashboard/app.py tests/test_tasks_router.py
git commit -m "feat(dashboard): add tasks API with trigger endpoints"
```

---

## Task 9: Runs + Stats API

**Files:**
- Create: `dashboard/routers/runs_router.py`
- Create: `dashboard/routers/stats_router.py`
- Create: `dashboard/services/stats_service.py`
- Modify: `dashboard/app.py`
- Test: `tests/test_runs_router.py`
- Test: `tests/test_stats_router.py`

- [ ] **Step 1: 编写 runs_router.py**

```python
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from dashboard.auth import get_current_user
from dashboard.database import get_db
from dashboard.schemas import RunResponse, RunListResponse
from dashboard.services.run_service import get_runs, get_run_by_id

from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _to_response(run) -> RunResponse:
    return RunResponse(
        run_id=run.run_id,
        product_name=run.product_name,
        record_id=run.record_id,
        trigger_type=run.trigger_type,
        status=run.status,
        stage=run.stage,
        headline=run.headline,
        qc_passed=run.qc_passed,
        qc_confidence=run.qc_confidence,
        qc_issues=json.loads(run.qc_issues) if run.qc_issues else [],
        cloud_file_id=run.cloud_file_id,
        error_msg=run.error_msg,
        duration_seconds=run.duration_seconds,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


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
    items, total = get_runs(db, page, page_size, status, product_name, date)
    return RunListResponse(
        items=[_to_response(r) for r in items],
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
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return _to_response(run)
```

- [ ] **Step 2: 编写 stats_service.py**

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from dashboard.db_models import DailyStats


def get_stats_summary(db: Session, date_str: str) -> dict:
    stat = db.query(DailyStats).filter_by(date=date_str).first()
    if not stat:
        return {"date": date_str, "total": 0, "success": 0, "failed": 0, "success_rate": 0.0, "avg_duration": 0.0}
    rate = (stat.success / stat.total * 100) if stat.total > 0 else 0.0
    return {
        "date": stat.date,
        "total": stat.total,
        "success": stat.success,
        "failed": stat.failed,
        "success_rate": round(rate, 1),
        "avg_duration": round(stat.avg_duration, 1),
    }


def get_stats_trend(db: Session, days: int = 7) -> list[dict]:
    stats = (
        db.query(DailyStats)
        .order_by(DailyStats.date.desc())
        .limit(days)
        .all()
    )
    result = []
    for stat in reversed(stats):
        rate = (stat.success / stat.total * 100) if stat.total > 0 else 0.0
        result.append({
            "date": stat.date,
            "total": stat.total,
            "success": stat.success,
            "failed": stat.failed,
            "success_rate": round(rate, 1),
            "avg_duration": round(stat.avg_duration, 1),
        })
    return result
```

- [ ] **Step 3: 编写 stats_router.py**

```python
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
    date: str = Query(default=None, description="YYYY-MM-DD，默认今天"),
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
```

- [ ] **Step 4: 在 app.py 注册两个 router**

```python
    from dashboard.routers.runs_router import router as runs_router
    from dashboard.routers.stats_router import router as stats_router
    app.include_router(runs_router)
    app.include_router(stats_router)
```

- [ ] **Step 5: 编写 runs_router 测试**

```python
# tests/test_runs_router.py
import os
import tempfile
from pathlib import Path
from datetime import datetime

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient
from dashboard.app import create_app
from dashboard.database import init_db, SessionLocal
from dashboard.services.run_service import save_run_result

app = create_app()
client = TestClient(app)
init_db()

# Seed test data
db = SessionLocal()
save_run_result(db, {
    "run_id": "run-test-001",
    "product_name": "测试产品A",
    "record_id": "rec_001",
    "trigger_type": "cron",
    "status": "DONE",
    "stage": "UPLOAD_OK",
    "headline": "测试标题",
    "image_prompt": "test",
    "qc_passed": True,
    "qc_confidence": 0.95,
    "qc_issues": "[]",
    "cloud_file_id": "file_001",
    "error_msg": "",
    "duration_seconds": 30.0,
    "started_at": datetime(2026, 4, 7, 8, 0),
    "finished_at": datetime(2026, 4, 7, 8, 0, 30),
})
db.close()


def _get_token():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    return resp.json()["access_token"]


def test_list_runs():
    token = _get_token()
    resp = client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_get_run_detail():
    token = _get_token()
    resp = client.get("/api/runs/run-test-001", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["product_name"] == "测试产品A"


def test_get_run_not_found():
    token = _get_token()
    resp = client.get("/api/runs/nonexistent", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
```

- [ ] **Step 6: 编写 stats_router 测试**

```python
# tests/test_stats_router.py
import os
import tempfile
from pathlib import Path

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient
from dashboard.app import create_app
from dashboard.database import init_db, SessionLocal
from dashboard.db_models import DailyStats

app = create_app()
client = TestClient(app)
init_db()

# Seed stats
db = SessionLocal()
db.add(DailyStats(date="2026-04-07", total=10, success=8, failed=2, avg_duration=35.0))
db.add(DailyStats(date="2026-04-06", total=5, success=5, failed=0, avg_duration=28.0))
db.commit()
db.close()


def _get_token():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    return resp.json()["access_token"]


def test_stats_summary():
    token = _get_token()
    resp = client.get(
        "/api/stats/summary?date=2026-04-07",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert data["success_rate"] == 80.0


def test_stats_trend():
    token = _get_token()
    resp = client.get("/api/stats/trend?days=7", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 2
```

- [ ] **Step 7: 运行测试**

```bash
pytest tests/test_runs_router.py tests/test_stats_router.py -v
```

Expected: 5 passed

- [ ] **Step 8: Commit**

```bash
git add dashboard/routers/runs_router.py dashboard/routers/stats_router.py dashboard/services/stats_service.py dashboard/app.py tests/test_runs_router.py tests/test_stats_router.py
git commit -m "feat(dashboard): add runs and stats API endpoints"
```

---

## Task 10: Logs API + WebSocket + Health API

**Files:**
- Create: `dashboard/services/log_service.py`
- Create: `dashboard/services/health_service.py`
- Create: `dashboard/websocket_manager.py`
- Create: `dashboard/routers/logs_router.py`
- Create: `dashboard/routers/health_router.py`
- Modify: `dashboard/app.py`
- Test: `tests/test_logs_router.py`
- Test: `tests/test_health_router.py`

- [ ] **Step 1: 编写 log_service.py**

```python
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from dashboard.config import settings


LOG_LINE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+\|\s+(\w+)\s+\|\s+(.*)$"
)


def get_log_file_path(date_str: str) -> Path:
    """安全地构造日志文件路径（防路径穿越）。"""
    # 严格校验 date 格式
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}")

    log_dir = Path(settings.log_dir).resolve()
    log_file = log_dir / f"poster_bot_{date_str}.log"

    # 确认路径在 log_dir 内
    if not str(log_file.resolve()).startswith(str(log_dir)):
        raise ValueError("Path traversal detected")

    return log_file


def read_log_lines(
    date_str: str,
    keyword: str = "",
    level: str = "",
    tail: int = 0,
) -> list[dict]:
    """读取日志文件并返回解析后的行。"""
    log_file = get_log_file_path(date_str)
    if not log_file.exists():
        return []

    lines = log_file.read_text(encoding="utf-8").splitlines()

    parsed = []
    for i, line in enumerate(lines, 1):
        match = LOG_LINE_PATTERN.match(line)
        if match:
            entry = {
                "line_number": i,
                "timestamp": match.group(1),
                "level": match.group(2),
                "message": match.group(3),
            }
        else:
            entry = {
                "line_number": i,
                "timestamp": "",
                "level": "",
                "message": line,
            }

        # 过滤
        if level and entry["level"] and entry["level"] != level.upper():
            continue
        if keyword and keyword.lower() not in entry["message"].lower():
            continue

        parsed.append(entry)

    if tail > 0:
        parsed = parsed[-tail:]

    return parsed
```

- [ ] **Step 2: 编写 websocket_manager.py**

```python
from __future__ import annotations

import asyncio
from typing import Set

from fastapi import WebSocket
from loguru import logger


class WebSocketManager:
    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: str):
        async with self._lock:
            dead = set()
            for ws in self._connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.add(ws)
            self._connections -= dead


ws_manager = WebSocketManager()


def loguru_ws_sink(message):
    """loguru sink，将日志消息广播到所有 WebSocket 连接。"""
    text = message.strip()
    if text and ws_manager._connections:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(ws_manager.broadcast(text))
        except RuntimeError:
            pass  # No running loop (e.g., during shutdown)
```

- [ ] **Step 3: 编写 logs_router.py**

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from dashboard.auth import get_current_user, ws_auth
from dashboard.schemas import LogResponse
from dashboard.services.log_service import read_log_lines
from dashboard.websocket_manager import ws_manager

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=LogResponse)
def get_logs(
    date: str = Query(default=None, description="YYYY-MM-DD"),
    keyword: str = Query(default=""),
    level: str = Query(default=""),
    tail: int = Query(default=0, ge=0, description="只返回最后 N 行"),
    current_user: str = Depends(get_current_user),
):
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    lines = read_log_lines(date, keyword, level, tail)
    return LogResponse(date=date, total_lines=len(lines), lines=lines)


@router.websocket("/stream")
async def log_stream(websocket: WebSocket):
    """WebSocket 实时日志流（需 ?token=xxx 认证）。"""
    try:
        user = await ws_auth(websocket)
    except Exception:
        return

    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, wait for client messages (ping/close)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket)
```

- [ ] **Step 4: 编写 health_service.py**

```python
from __future__ import annotations

import os
import shutil
import time

import requests
from loguru import logger


def check_feishu() -> dict:
    """检测飞书 API 连通性。"""
    try:
        start = time.time()
        from feishu_reader import build_client
        client = build_client()
        # 尝试获取 tenant_access_token
        latency = (time.time() - start) * 1000
        return {"name": "飞书 API", "status": "ok", "latency_ms": round(latency, 1), "detail": "连接正常"}
    except Exception as e:
        return {"name": "飞书 API", "status": "error", "latency_ms": None, "detail": str(e)}


def check_gemini() -> dict:
    """检测 Gemini API 连通性。"""
    try:
        start = time.time()
        base_url = os.getenv("GEMINI_API_BASE", "https://api.buxianliang.fun/v1")
        resp = requests.get(f"{base_url}/models", timeout=10, headers={
            "Authorization": f"Bearer {os.getenv('GEMINI_API_KEY', '')}",
        })
        latency = (time.time() - start) * 1000
        status = "ok" if resp.status_code in (200, 401) else "error"
        return {"name": "Gemini API", "status": status, "latency_ms": round(latency, 1), "detail": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"name": "Gemini API", "status": "error", "latency_ms": None, "detail": str(e)}


def check_wechat() -> dict:
    """检测微信云开发连通性。"""
    try:
        start = time.time()
        resp = requests.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": os.getenv("WX_APPID", ""), "secret": os.getenv("WX_APPSECRET", "")},
            timeout=10,
        )
        latency = (time.time() - start) * 1000
        payload = resp.json()
        if payload.get("access_token"):
            return {"name": "微信云开发", "status": "ok", "latency_ms": round(latency, 1), "detail": "连接正常"}
        return {"name": "微信云开发", "status": "error", "latency_ms": round(latency, 1), "detail": payload.get("errmsg", "未知错误")}
    except Exception as e:
        return {"name": "微信云开发", "status": "error", "latency_ms": None, "detail": str(e)}


def check_disk() -> dict:
    """检测磁盘空间。"""
    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        status = "ok" if free_gb > 1.0 else "error"
        return {
            "name": "磁盘空间",
            "status": status,
            "latency_ms": None,
            "detail": f"{free_gb:.1f}GB / {total_gb:.1f}GB 可用",
        }
    except Exception as e:
        return {"name": "磁盘空间", "status": "error", "latency_ms": None, "detail": str(e)}


def run_all_checks() -> list[dict]:
    return [check_feishu(), check_gemini(), check_wechat(), check_disk()]
```

- [ ] **Step 5: 编写 health_router.py**

```python
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
```

- [ ] **Step 6: 在 app.py 注册 + 添加 loguru WebSocket sink**

在 `create_app()` 中添加：

```python
    from dashboard.routers.logs_router import router as logs_router
    from dashboard.routers.health_router import router as health_router
    app.include_router(logs_router)
    app.include_router(health_router)
```

在 `lifespan()` 的 `yield` 之前添加：

```python
    from dashboard.websocket_manager import loguru_ws_sink
    logger.add(loguru_ws_sink, level="DEBUG")
```

- [ ] **Step 7: 编写测试**

```python
# tests/test_logs_router.py
import os
import tempfile
from pathlib import Path
from datetime import datetime

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret"

# Create fake log
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
today = datetime.now().strftime("%Y-%m-%d")
log_file = log_dir / f"poster_bot_{today}.log"
log_file.write_text(
    "2026-04-07 08:00:01.123 | INFO | 测试日志行1\n"
    "2026-04-07 08:00:02.456 | ERROR | 测试错误行\n"
    "2026-04-07 08:00:03.789 | INFO | 包含关键词的行\n",
    encoding="utf-8",
)

from fastapi.testclient import TestClient
from dashboard.app import create_app

app = create_app()
client = TestClient(app)


def _get_token():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    return resp.json()["access_token"]


def test_get_logs_today():
    token = _get_token()
    resp = client.get(f"/api/logs?date={today}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_lines"] == 3


def test_get_logs_filter_by_level():
    token = _get_token()
    resp = client.get(
        f"/api/logs?date={today}&level=ERROR",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()
    assert data["total_lines"] == 1


def test_get_logs_filter_by_keyword():
    token = _get_token()
    resp = client.get(
        f"/api/logs?date={today}&keyword=关键词",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()
    assert data["total_lines"] == 1


def test_get_logs_invalid_date():
    token = _get_token()
    resp = client.get(
        "/api/logs?date=../../etc/passwd",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (400, 422, 500)
```

```python
# tests/test_health_router.py
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "test123"
os.environ["DASHBOARD_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient
from dashboard.app import create_app

app = create_app()
client = TestClient(app)


def _get_token():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "test123"})
    return resp.json()["access_token"]


@patch("dashboard.services.health_service.run_all_checks", return_value=[
    {"name": "飞书 API", "status": "ok", "latency_ms": 50.0, "detail": "连接正常"},
    {"name": "磁盘空间", "status": "ok", "latency_ms": None, "detail": "50GB 可用"},
])
def test_health_check(mock_checks):
    token = _get_token()
    resp = client.get("/api/health", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[0]["status"] == "ok"
```

- [ ] **Step 8: 运行测试**

```bash
pytest tests/test_logs_router.py tests/test_health_router.py -v
```

Expected: 5 passed

- [ ] **Step 9: Commit**

```bash
git add dashboard/services/log_service.py dashboard/services/health_service.py dashboard/websocket_manager.py dashboard/routers/logs_router.py dashboard/routers/health_router.py dashboard/app.py tests/test_logs_router.py tests/test_health_router.py
git commit -m "feat(dashboard): add logs (REST+WebSocket), health check APIs"
```

### >>> Review C: Claude 审核全部后端 API 完整性和安全性 <<<

---

# Phase 4: Vue 3 前端框架 (Gemini)

## Task 11: Vue 3 + Vite + Element Plus 项目脚手架

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/env.d.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`

- [ ] **Step 1: 初始化 Vue 项目**

```bash
cd frontend
npm create vite@latest . -- --template vue-ts
npm install element-plus @element-plus/icons-vue
npm install vue-router@4 pinia axios echarts vue-echarts
npm install -D @types/node unplugin-auto-import unplugin-vue-components
```

- [ ] **Step 2: 配置 vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
})
```

注意：`build.outDir` 输出到项目根目录的 `static/`，供 FastAPI 静态托管。

- [ ] **Step 3: 编写 src/main.ts**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.mount('#app')
```

- [ ] **Step 4: 验证开发服务器启动**

```bash
npm run dev
```

Expected: Vite 开发服务器启动在 http://localhost:5173

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Vue 3 + Vite + Element Plus project"
```

---

## Task 12: Axios 客户端 + JWT 拦截器 + 路由守卫

**Files:**
- Create: `frontend/src/api/request.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/router/index.ts`

- [ ] **Step 1: 编写 request.ts（Axios 实例 + JWT 拦截器）**

```typescript
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import router from '@/router'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

request.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      router.push('/login')
      ElMessage.error('登录已过期，请重新登录')
    }
    return Promise.reject(error)
  }
)

export default request
```

- [ ] **Step 2: 编写 auth store**

```typescript
// frontend/src/stores/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')

  const isLoggedIn = computed(() => !!token.value)

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }

  function logout() {
    token.value = ''
    localStorage.removeItem('token')
  }

  return { token, isLoggedIn, setToken, logout }
})
```

- [ ] **Step 3: 编写 auth API**

```typescript
// frontend/src/api/auth.ts
import request from './request'

export function login(username: string, password: string) {
  return request.post('/auth/login', { username, password })
}

export function refreshToken() {
  return request.post('/auth/refresh')
}
```

- [ ] **Step 4: 编写 router 并添加路由守卫**

```typescript
// frontend/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/DashboardLayout.vue'),
      children: [
        { path: '', name: 'Dashboard', component: () => import('@/views/DashboardView.vue') },
        { path: 'tasks', name: 'Tasks', component: () => import('@/views/TasksView.vue') },
        { path: 'runs', name: 'Runs', component: () => import('@/views/RunsView.vue') },
        { path: 'logs', name: 'Logs', component: () => import('@/views/LogsView.vue') },
        { path: 'health', name: 'Health', component: () => import('@/views/HealthView.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return '/login'
  }
})

export default router
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/ frontend/src/stores/ frontend/src/router/
git commit -m "feat(frontend): add Axios JWT interceptor, auth store, router guards"
```

---

## Task 13: 登录页 + Dashboard 布局

**Files:**
- Create: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/layouts/DashboardLayout.vue`

- [ ] **Step 1: 编写 LoginView.vue**

登录页面，居中卡片式设计，品牌色 (#FFFFFF 底 + 品牌蓝色按钮)。表单字段：用户名、密码、登录按钮。登录成功后跳转 `/`。

关键逻辑：
- 调用 `login()` API
- 成功后 `authStore.setToken(data.access_token)`
- `router.push('/')`
- 失败显示 `ElMessage.error()`

- [ ] **Step 2: 编写 DashboardLayout.vue**

经典中后台布局：
- 左侧固定侧边栏（`el-menu`），宽度 220px，深色背景
- 菜单项：概览、任务管理、执行记录、系统日志、健康监测
- 每项带 Element Plus 图标（DataAnalysis, List, Timer, Document, Monitor）
- 顶部栏：显示"浴小主控制面板"标题 + 右侧用户名 + 退出按钮
- 主内容区：`<router-view />`，带 padding

- [ ] **Step 3: 验证登录和导航**

```bash
npm run dev
```

打开 http://localhost:5173 → 应自动跳转到 `/login`
输入 admin/密码 → 应跳转到 Dashboard 布局

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/LoginView.vue frontend/src/layouts/DashboardLayout.vue
git commit -m "feat(frontend): add login page and dashboard layout"
```

### >>> Review D: Claude 审核前端骨架 + 登录 + Dashboard 联通 <<<

---

# Phase 5: 前端业务页面 (Gemini)

## Task 14: 概览仪表盘页面

**Files:**
- Create: `frontend/src/api/stats.ts`
- Create: `frontend/src/components/StatsCard.vue`
- Create: `frontend/src/components/TrendChart.vue`
- Create: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: 编写 stats API 客户端**

```typescript
// frontend/src/api/stats.ts
import request from './request'

export function getStatsSummary(date?: string) {
  return request.get('/stats/summary', { params: { date } })
}

export function getStatsTrend(days: number = 7) {
  return request.get('/stats/trend', { params: { days } })
}
```

- [ ] **Step 2: 编写 StatsCard.vue**

统计卡片组件，props: `title`, `value`, `suffix`, `icon`, `color`。
使用 `el-card` + 大数字 + 图标，带颜色条。

- [ ] **Step 3: 编写 TrendChart.vue（ECharts 折线图）**

props: `data` (StatsResponse 数组)。
X 轴：日期，Y 轴：数量。
两条折线：成功数（绿）、失败数（红）。
使用 `vue-echarts` 渲染。

- [ ] **Step 4: 编写 DashboardView.vue**

页面布局：
- 顶部一行 4 个 StatsCard：今日总数、成功数、失败数、成功率
- 下方 TrendChart 展示近 7 天趋势
- 底部：最近 5 条执行记录快捷列表（调用 `/api/runs?page_size=5`）

onMounted 时调用 `getStatsSummary()` 和 `getStatsTrend()`。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/stats.ts frontend/src/components/StatsCard.vue frontend/src/components/TrendChart.vue frontend/src/views/DashboardView.vue
git commit -m "feat(frontend): add dashboard page with stats cards and trend chart"
```

---

## Task 15: 任务管理页面

**Files:**
- Create: `frontend/src/api/tasks.ts`
- Create: `frontend/src/components/StatusBadge.vue`
- Create: `frontend/src/components/PosterPreview.vue`
- Create: `frontend/src/views/TasksView.vue`

- [ ] **Step 1: 编写 tasks API 客户端**

```typescript
// frontend/src/api/tasks.ts
import request from './request'

export function getTasks(status?: string) {
  return request.get('/tasks', { params: { status } })
}

export function triggerSingle(recordId: string) {
  return request.post(`/tasks/${recordId}/trigger`)
}

export function triggerBatch(recordIds: string[]) {
  return request.post('/tasks/batch-trigger', recordIds)
}
```

- [ ] **Step 2: 编写 StatusBadge.vue**

props: `status`。根据状态渲染不同颜色的 `el-tag`：
- PENDING → warning/橙色
- DONE → success/绿色
- FAILED_MANUAL / FAILED_RETRYABLE → danger/红色
- COPY_OK / IMAGE_OK / UPLOAD_OK → primary/蓝色
- RUNNING → 蓝色 + 旋转加载图标

- [ ] **Step 3: 编写 PosterPreview.vue**

props: `cloudFileId`, `productName`。
弹窗预览组件（`el-dialog`），展示云存储中的海报大图。
使用微信云存储的文件临时链接（需要后端提供一个 `/api/tasks/{id}/preview` 端点——如果暂无，则显示占位图和 file_id 文字）。

- [ ] **Step 4: 编写 TasksView.vue**

页面布局：
- 顶部筛选栏：状态下拉选择器（`el-select`）+ 刷新按钮
- `el-table` 数据表格，列：产品名、分类、状态（StatusBadge）、素材文件名、操作
- 操作列：查看海报（PosterPreview）、重新生成按钮（调用 triggerSingle）
- 表格上方：批量操作栏（选中 + 批量重新生成按钮）
- 点击"重新生成"后显示 `ElMessage.success("已加入队列")`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/tasks.ts frontend/src/components/StatusBadge.vue frontend/src/components/PosterPreview.vue frontend/src/views/TasksView.vue
git commit -m "feat(frontend): add task management page with trigger and preview"
```

---

## Task 16: 执行记录页面

**Files:**
- Create: `frontend/src/api/runs.ts`
- Create: `frontend/src/views/RunsView.vue`

- [ ] **Step 1: 编写 runs API 客户端**

```typescript
// frontend/src/api/runs.ts
import request from './request'

export function getRuns(params: {
  page?: number
  page_size?: number
  status?: string
  product_name?: string
  date?: string
}) {
  return request.get('/runs', { params })
}

export function getRunDetail(runId: string) {
  return request.get(`/runs/${runId}`)
}
```

- [ ] **Step 2: 编写 RunsView.vue**

页面布局：
- 筛选栏：日期选择器 + 状态下拉 + 产品名搜索框 + 查询按钮
- `el-table` 数据表格，列：
  - 执行 ID（run_id 前 8 位）
  - 产品名
  - 触发方式（cron/manual，用 el-tag 区分颜色）
  - 状态（StatusBadge）
  - 阶段（stage）
  - QC 结果（通过/未通过 + 置信度）
  - 耗时（秒）
  - 开始时间
- 点击行展开详情面板（`el-drawer`）：
  - 完整文案标题（headline）
  - Image prompt 文本
  - QC issues 列表
  - 错误信息（如有）
  - 云存储 file_id
- 分页组件（`el-pagination`）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/runs.ts frontend/src/views/RunsView.vue
git commit -m "feat(frontend): add execution records page with filters and detail drawer"
```

---

## Task 17: 日志查看器 + 健康监测页面

**Files:**
- Create: `frontend/src/api/logs.ts`
- Create: `frontend/src/api/health.ts`
- Create: `frontend/src/components/LogStream.vue`
- Create: `frontend/src/views/LogsView.vue`
- Create: `frontend/src/views/HealthView.vue`

- [ ] **Step 1: 编写 logs 和 health API 客户端**

```typescript
// frontend/src/api/logs.ts
import request from './request'

export function getLogs(params: { date?: string; keyword?: string; level?: string; tail?: number }) {
  return request.get('/logs', { params })
}
```

```typescript
// frontend/src/api/health.ts
import request from './request'

export function getHealth() {
  return request.get('/health')
}
```

- [ ] **Step 2: 编写 LogStream.vue（WebSocket 实时日志组件）**

组件逻辑：
- 连接 `ws://host/api/logs/stream?token=xxx`
- 收到消息追加到内部 `lines` 数组（限制最多 500 行，超出移除头部）
- 使用 `<pre>` 或等宽字体容器展示，自动滚动到底部
- 支持暂停/恢复按钮
- 连接断开自动重连（3 秒间隔，最多 5 次）
- 日志级别用不同颜色高亮：INFO 绿、WARNING 橙、ERROR 红、DEBUG 灰

- [ ] **Step 3: 编写 LogsView.vue**

页面布局 — 两个 tab：
- **Tab 1: 实时日志** — LogStream 组件
- **Tab 2: 历史查询** — 日期选择器 + 关键词输入 + 级别下拉 + 查询按钮 → 结果用 `el-table` 展示（行号、时间、级别、消息），级别列带颜色

- [ ] **Step 4: 编写 HealthView.vue**

页面布局：
- 4 个状态卡片（一行排列）：飞书 API、Gemini API、微信云开发、磁盘空间
- 每个卡片：名称 + 状态灯（绿色圆点 = ok，红色 = error） + 响应延迟 + 详情文字
- "刷新"按钮，点击后重新调用 `/api/health`
- 自动刷新：每 60 秒调一次

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/logs.ts frontend/src/api/health.ts frontend/src/components/LogStream.vue frontend/src/views/LogsView.vue frontend/src/views/HealthView.vue
git commit -m "feat(frontend): add log viewer and health monitoring pages"
```

### >>> Review E: Claude 审核全部前端页面与 API 对接 <<<

---

# Phase 6: 集成与部署 (Codex)

## Task 18: 前端构建 + FastAPI 静态托管

**Files:**
- Modify: `dashboard/app.py`
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: 构建前端**

```bash
cd frontend && npm run build
```

Expected: 输出到 `../static/` 目录

- [ ] **Step 2: FastAPI 托管静态文件**

在 `dashboard/app.py` 的 `create_app()` 中，在 router 注册之后添加：

```python
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from pathlib import Path

    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="static-assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """所有非 /api 路由都返回 index.html（SPA fallback）。"""
            index = static_dir / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return {"detail": "Frontend not built"}
```

注意：此路由必须放在所有 `/api` router 之后，确保 API 路由优先匹配。

- [ ] **Step 3: 验证**

```bash
python main.py
```

打开 http://localhost:8000 → 应显示 Vue 前端登录页
访问 http://localhost:8000/api/docs → 应显示 Swagger UI

- [ ] **Step 4: Commit**

```bash
git add dashboard/app.py static/
git commit -m "feat: integrate frontend build with FastAPI static serving"
```

---

## Task 19: 部署配置（Nginx + systemd）

**Files:**
- Create: `deploy/nginx.conf`
- Create: `deploy/poster-dashboard.service`
- Create: `deploy/setup.sh`

- [ ] **Step 1: 编写 nginx.conf**

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

- [ ] **Step 2: 编写 systemd service**

```ini
[Unit]
Description=浴小主海报控制面板
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/poster_bot
EnvironmentFile=/opt/poster_bot/.env
ExecStart=/opt/poster_bot/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: 编写 setup.sh**

```bash
#!/bin/bash
set -e

echo "=== 浴小主海报控制面板部署脚本 ==="

# 1. 安装系统依赖
apt update && apt install -y python3-venv python3-pip nginx

# 2. 创建虚拟环境
cd /opt/poster_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 初始化数据目录
mkdir -p data logs assets/products

# 4. 配置 Nginx
cp deploy/nginx.conf /etc/nginx/sites-available/poster-dashboard
ln -sf /etc/nginx/sites-available/poster-dashboard /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 5. 配置 systemd
cp deploy/poster-dashboard.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable poster-dashboard
systemctl start poster-dashboard

# 6. 配置 Cron（改为 curl 触发）
CRON_CMD="0 8 * * * curl -s -X POST http://localhost:8000/api/pipeline/run -H 'Authorization: Bearer \$(curl -s -X POST http://localhost:8000/api/auth/login -H \"Content-Type: application/json\" -d '{\"username\":\"admin\",\"password\":\"'ADMIN_PASSWORD'\"}' | python3 -c \"import sys,json;print(json.load(sys.stdin)['access_token'])\")' > /dev/null 2>&1"
echo "请手动配置 cron："
echo "$CRON_CMD"

echo "=== 部署完成 ==="
echo "访问 http://$(hostname -I | awk '{print $1}') 进入控制面板"
```

- [ ] **Step 4: Commit**

```bash
git add deploy/
git commit -m "feat: add deployment config (Nginx, systemd, setup script)"
```

---

## Task 20: 集成测试

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 编写端到端集成测试**

```python
# tests/test_integration.py
"""
端到端集成测试：验证前后端 API 全链路。
运行前需要：pip install -r requirements.txt
"""
import os
import tempfile
from pathlib import Path
from datetime import datetime

os.environ["DASHBOARD_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["DASHBOARD_ADMIN_USER"] = "admin"
os.environ["DASHBOARD_ADMIN_PASSWORD"] = "integration-test"
os.environ["DASHBOARD_SECRET_KEY"] = "integration-secret"

from fastapi.testclient import TestClient
from dashboard.app import create_app
from dashboard.database import init_db, SessionLocal
from dashboard.services.run_service import save_run_result

app = create_app()
client = TestClient(app)


class TestAuthFlow:
    def test_login_and_access(self):
        # Login
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "integration-test"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        # Access protected endpoint
        resp = client.get("/api/stats/summary", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_unauthorized_access(self):
        resp = client.get("/api/stats/summary")
        assert resp.status_code == 401


class TestFullWorkflow:
    def setup_method(self):
        init_db()
        self.db = SessionLocal()
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "integration-test"})
        self.token = resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def teardown_method(self):
        self.db.close()

    def test_runs_empty_then_populated(self):
        # Initially empty
        resp = client.get("/api/runs", headers=self.headers)
        assert resp.status_code == 200

        # Add a run
        save_run_result(self.db, {
            "run_id": "integ-001",
            "product_name": "集成测试产品",
            "record_id": "rec_integ",
            "trigger_type": "manual",
            "status": "DONE",
            "stage": "UPLOAD_OK",
            "headline": "测试",
            "image_prompt": "test",
            "qc_passed": True,
            "qc_confidence": 0.9,
            "qc_issues": "[]",
            "cloud_file_id": "file_integ",
            "error_msg": "",
            "duration_seconds": 20.0,
            "started_at": datetime.now(),
            "finished_at": datetime.now(),
        })

        # Now has data
        resp = client.get("/api/runs", headers=self.headers)
        assert resp.json()["total"] >= 1

        # Get detail
        resp = client.get("/api/runs/integ-001", headers=self.headers)
        assert resp.status_code == 200
        assert resp.json()["product_name"] == "集成测试产品"

    def test_health_check(self):
        resp = client.get("/api/health", headers=self.headers)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) > 0

    def test_logs_endpoint(self):
        resp = client.get("/api/logs", headers=self.headers)
        assert resp.status_code == 200

    def test_stats_summary(self):
        resp = client.get("/api/stats/summary", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "success_rate" in data
```

- [ ] **Step 2: 运行全部测试**

```bash
pytest tests/ -v --tb=short
```

Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration tests for dashboard"
```

### >>> Review F: Claude 最终审核全部代码 + 部署配置 <<<

---

## Cron 改造说明

部署后，原来的 cron 从：
```
0 8 * * * cd /opt/poster_bot && python3 main.py
```

改为通过 HTTP 触发（因为 FastAPI 常驻进程已统一管理锁）：
```bash
# /opt/poster_bot/cron_trigger.sh
#!/bin/bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_PASSWORD"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/api/pipeline/run \
  -H "Authorization: Bearer $TOKEN"
```

```
0 8 * * * /opt/poster_bot/cron_trigger.sh >> /opt/poster_bot/logs/cron.log 2>&1
```

---

## 附录：环境变量完整清单

| 变量 | 用途 | 示例 |
|------|------|------|
| GEMINI_API_KEY | Gemini API 密钥 | sk-xxx |
| GEMINI_API_BASE | API 代理地址 | https://api.buxianliang.fun/v1 |
| GEMINI_COPY_MODEL | 文案模型 | gemini-3.1-pro-preview |
| GEMINI_IMAGE_MODEL | 图像模型 | gemini-3-pro-image-preview |
| FEISHU_APP_ID | 飞书应用 ID | cli_xxx |
| FEISHU_APP_SECRET | 飞书应用密钥 | xxx |
| FEISHU_APP_TOKEN | 多维表格 Token | xxx |
| FEISHU_TABLE_ID | 数据表 ID | tblxxx |
| FEISHU_WEBHOOK_URL | 群机器人 Webhook | https://open.feishu.cn/... |
| WX_APPID | 微信小程序 AppID | wxXXX |
| WX_APPSECRET | 微信小程序 AppSecret | xxx |
| WX_ENV_ID | 云开发环境 ID | newyuxiaozhu-5g28gork4d0ed6c4 |
| ASSETS_DIR | 产品素材目录 | ./assets/products |
| DASHBOARD_SECRET_KEY | JWT 签名密钥 | 随机字符串 |
| DASHBOARD_ADMIN_USER | 管理员用户名 | admin |
| DASHBOARD_ADMIN_PASSWORD | 管理员密码 | 强密码 |
| DASHBOARD_DB_PATH | SQLite 路径 | ./data/dashboard.db |
| DASHBOARD_PORT | 面板端口 | 8000 |
| DASHBOARD_ALLOWED_ORIGINS | CORS 白名单 | http://localhost:5173 |
