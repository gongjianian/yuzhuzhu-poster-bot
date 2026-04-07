from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class DashboardSettings(BaseSettings):
    secret_key: str = os.getenv("DASHBOARD_SECRET_KEY", "")
    admin_user: str = os.getenv("DASHBOARD_ADMIN_USER", "")
    admin_password: str = os.getenv("DASHBOARD_ADMIN_PASSWORD", "")
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
