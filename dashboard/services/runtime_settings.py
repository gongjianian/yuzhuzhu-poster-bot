"""Simple JSON-backed store for runtime-tunable settings.

These settings override environment variables when present, and are
persisted to disk so they survive service restarts. Writes go to
/opt/poster_bot/data/runtime_settings.json which is in ReadWritePaths.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dashboard.config import get_settings


def _settings_file() -> Path:
    db_path = Path(get_settings().db_path)
    return db_path.parent / "runtime_settings.json"


def load() -> dict[str, Any]:
    path = _settings_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save(updates: dict[str, Any]) -> dict[str, Any]:
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = load()
    current.update(updates)
    path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    return current


# --- Model resolution (read: runtime settings → env var → default) ---

DEFAULT_COPY_MODEL = "gemini-3.1-pro-preview"
DEFAULT_IMAGE_MODEL = "gemini-3-pro-image-preview"


def get_copy_model() -> str:
    settings = load()
    return (
        settings.get("gemini_copy_model")
        or os.getenv("GEMINI_COPY_MODEL")
        or DEFAULT_COPY_MODEL
    )


def get_image_model() -> str:
    settings = load()
    return (
        settings.get("gemini_image_model")
        or os.getenv("GEMINI_IMAGE_MODEL")
        or DEFAULT_IMAGE_MODEL
    )
