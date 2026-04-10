"""Dashboard settings API - manage runtime-tunable configuration.

Currently supports model selection (copy model + image model). Users can
pick from the available models listed by the upstream API, save a choice,
and the next test or pipeline run will use it.
"""
from __future__ import annotations

import asyncio
import os

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dashboard.auth import get_current_user
from dashboard.services import runtime_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ModelInfo(BaseModel):
    id: str
    owned_by: str = ""
    object: str = ""


class AvailableModelsResponse(BaseModel):
    text_models: list[ModelInfo]
    image_models: list[ModelInfo]
    all_models: list[ModelInfo]


class ModelSettings(BaseModel):
    gemini_copy_model: str
    gemini_image_model: str


class ModelSettingsUpdate(BaseModel):
    gemini_copy_model: str | None = None
    gemini_image_model: str | None = None


# Models whose only/primary output is an image
IMAGE_KEYWORDS = (
    "image",          # gemini-3-pro-image-preview, gemini-2.5-flash-image, ...
    "imagen",         # imagen-4.0-generate-001, imagen-3.0-generate-002, ...
    "nano-banana",    # Google codename for Gemini 3 Pro Image Preview
    "dall-e",         # OpenAI DALL-E (if proxy forwards)
    "stable-diffusion",
    "flux",
)

# Models that are NOT text chat models (exclude from the text dropdown)
NON_TEXT_KEYWORDS = IMAGE_KEYWORDS + (
    "embedding",
    "tts",            # gemini-2.5-flash-preview-tts, gemini-2.5-pro-preview-tts
    "aqa",            # Attributed Question Answering
    "veo",            # Video generation models
)


def _normalize_for_match(s: str) -> str:
    """Strip spaces, hyphens, underscores and lowercase so 'Nano Banana Pro',
    'nano-banana-pro', and 'nano_banana_pro' all compare equal."""
    return s.lower().replace(" ", "").replace("-", "").replace("_", "")


def _is_image_model(model_id: str) -> bool:
    normalized = _normalize_for_match(model_id)
    return any(_normalize_for_match(kw) in normalized for kw in IMAGE_KEYWORDS)


def _is_text_model(model_id: str) -> bool:
    normalized = _normalize_for_match(model_id)
    return not any(_normalize_for_match(kw) in normalized for kw in NON_TEXT_KEYWORDS)


def _normalize_model_id(raw_id: str) -> str:
    """Strip Google's 'models/' prefix and any OpenAI-style 'publishers/.../models/' prefix."""
    if not raw_id:
        return raw_id
    if raw_id.startswith("models/"):
        return raw_id[len("models/"):]
    if "/models/" in raw_id:
        return raw_id.split("/models/", 1)[1]
    return raw_id


def _classify_models(models: list[dict]) -> tuple[list[ModelInfo], list[ModelInfo], list[ModelInfo]]:
    """Split the raw model list into text-capable and image-capable buckets.

    A model can appear in only one category at a time (image takes precedence).
    Models that don't fit either (embedding, TTS, video, ...) are in all_models
    but not in either text_models or image_models.

    Normalizes model IDs to strip any 'models/' prefix so the frontend and
    backend use consistent names.
    """
    all_models = [
        ModelInfo(
            id=_normalize_model_id(m.get("id", "")),
            owned_by=m.get("owned_by", ""),
            object=m.get("object", ""),
        )
        for m in models
        if m.get("id")
    ]
    all_models.sort(key=lambda m: m.id)

    image_models = [m for m in all_models if _is_image_model(m.id)]
    text_models = [m for m in all_models if _is_text_model(m.id)]

    return text_models, image_models, all_models


@router.get("/models/available", response_model=AvailableModelsResponse)
async def list_available_models(
    current_user: str = Depends(get_current_user),
) -> AvailableModelsResponse:
    """Fetch the list of models from the upstream API and classify them."""
    base = os.getenv("GEMINI_API_BASE", "").rstrip("/")
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not base or not api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_BASE and GEMINI_API_KEY must be configured",
        )

    def _fetch():
        resp = requests.get(
            f"{base}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    try:
        data = await asyncio.to_thread(_fetch)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream API error: {e}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach upstream API: {e}")

    models = data.get("data", []) if isinstance(data, dict) else []
    text_models, image_models, all_models = _classify_models(models)

    return AvailableModelsResponse(
        text_models=text_models,
        image_models=image_models,
        all_models=all_models,
    )


@router.get("/models", response_model=ModelSettings)
def get_model_settings(
    current_user: str = Depends(get_current_user),
) -> ModelSettings:
    return ModelSettings(
        gemini_copy_model=runtime_settings.get_copy_model(),
        gemini_image_model=runtime_settings.get_image_model(),
    )


@router.put("/models", response_model=ModelSettings)
def update_model_settings(
    body: ModelSettingsUpdate,
    current_user: str = Depends(get_current_user),
) -> ModelSettings:
    updates: dict[str, str] = {}
    if body.gemini_copy_model is not None:
        if not body.gemini_copy_model.strip():
            raise HTTPException(status_code=400, detail="gemini_copy_model cannot be empty")
        updates["gemini_copy_model"] = body.gemini_copy_model.strip()
    if body.gemini_image_model is not None:
        if not body.gemini_image_model.strip():
            raise HTTPException(status_code=400, detail="gemini_image_model cannot be empty")
        updates["gemini_image_model"] = body.gemini_image_model.strip()

    if not updates:
        raise HTTPException(status_code=400, detail="No changes provided")

    runtime_settings.save(updates)
    return ModelSettings(
        gemini_copy_model=runtime_settings.get_copy_model(),
        gemini_image_model=runtime_settings.get_image_model(),
    )
