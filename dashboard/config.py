from __future__ import annotations

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class DashboardSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DASHBOARD_",
        enable_decoding=False,
    )

    secret_key: str = ""
    admin_user: str = ""
    admin_password: str = ""
    db_path: str = "./data/dashboard.db"
    port: int = 8000
    allowed_origins: list[str] = ["http://localhost:5173"]
    log_dir: str = "logs"
    assets_dir: str = Field(default="./assets/products", validation_alias="ASSETS_DIR")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = DashboardSettings()


def get_settings() -> DashboardSettings:
    return DashboardSettings()
