from __future__ import annotations

import asyncio
import base64
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dashboard.auth import get_current_user

router = APIRouter(prefix="/api/prompts", tags=["prompts"])

# Whitelist - only these filenames are editable (prevents path traversal)
ALLOWED_PROMPTS = {
    "scheme_prompt.txt": {
        "name": "scheme_prompt.txt",
        "title": "方案策划 Prompt",
        "description": "第一阶段：根据产品信息生成海报方案（标题、副标题、正文、场景）",
        "placeholders": [
            "{product_name}",
            "{selling_points}",
            "{idea}",
            "{visual_style}",
            "{brand_colors}",
        ],
    },
    "image_prompt.txt": {
        "name": "image_prompt.txt",
        "title": "视觉翻译 Prompt",
        "description": "第二阶段：将方案翻译为图像生成模型的 prompt（小字 body_copy 由后期 PIL 根据实际图像动态叠加）",
        "placeholders": [
            "{store_name}",
            "{size}",
            "{selling_points}",
            "{selected_scheme}",
            "{product_name}",
            "{headline}",
            "{subheadline}",
            "{cta}",
            "{scene_description}",
            "{layout_description}",
            "{visual_style}",
        ],
    },
}

# Project root / prompts directory
PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


class PromptMeta(BaseModel):
    name: str
    title: str
    description: str
    placeholders: list[str]
    size_bytes: int
    modified_at: str | None = None


class PromptDetail(PromptMeta):
    content: str


class PromptUpdateRequest(BaseModel):
    content: str


def _safe_path(name: str) -> Path:
    """Resolve a prompt filename to a safe absolute path."""
    if name not in ALLOWED_PROMPTS:
        raise HTTPException(status_code=404, detail=f"Unknown prompt file: {name}")
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid prompt name")
    path = (PROMPTS_DIR / name).resolve()
    try:
        path.relative_to(PROMPTS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Path traversal detected")
    return path


def _build_meta(name: str, path: Path) -> PromptMeta:
    info = ALLOWED_PROMPTS[name]
    modified = None
    size = 0
    if path.exists():
        size = path.stat().st_size
        modified = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    return PromptMeta(
        name=info["name"],
        title=info["title"],
        description=info["description"],
        placeholders=info["placeholders"],
        size_bytes=size,
        modified_at=modified,
    )


@router.get("", response_model=list[PromptMeta])
def list_prompts(current_user: str = Depends(get_current_user)) -> list[PromptMeta]:
    result = []
    for name in ALLOWED_PROMPTS:
        path = _safe_path(name)
        result.append(_build_meta(name, path))
    return result


@router.get("/{name}", response_model=PromptDetail)
def get_prompt(name: str, current_user: str = Depends(get_current_user)) -> PromptDetail:
    path = _safe_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {name}")
    content = path.read_text(encoding="utf-8")
    meta = _build_meta(name, path)
    return PromptDetail(**meta.model_dump(), content=content)


async def _locate_record(record_id: str):
    """Fetch a single record from Feishu by id. Raises HTTPException if not found."""
    from feishu_reader import fetch_all_records
    records = await asyncio.to_thread(fetch_all_records)
    record = next((r for r in records if r.record_id == record_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Record not found: {record_id}")
    return record


class SchemeTestRequest(BaseModel):
    record_id: str


class SchemeTestResponse(BaseModel):
    product_name: str
    scheme: dict[str, Any]
    duration_ms: int
    error: str = ""


@router.post("/test/scheme", response_model=SchemeTestResponse)
async def test_scheme(
    body: SchemeTestRequest,
    current_user: str = Depends(get_current_user),
) -> SchemeTestResponse:
    """Stage 1 only: run scheme_prompt.txt against a product.

    Uses the CURRENT scheme_prompt.txt on disk (save first to test edits).
    Returns the scheme JSON, which can be piped into test/image-prompt later.
    Does NOT run the image prompt stage or image generation.
    """
    from content_generator import generate_scheme_only

    record = await _locate_record(body.record_id)
    start = time.time()
    try:
        scheme = await asyncio.to_thread(generate_scheme_only, record)
        return SchemeTestResponse(
            product_name=record.product_name,
            scheme=scheme,
            duration_ms=int((time.time() - start) * 1000),
        )
    except Exception as e:
        return SchemeTestResponse(
            product_name=record.product_name,
            scheme={},
            duration_ms=int((time.time() - start) * 1000),
            error=f"{type(e).__name__}: {e}",
        )


class ImagePromptTestRequest(BaseModel):
    record_id: str
    scheme: dict[str, Any]  # Output from test/scheme


class ImagePromptTestResponse(BaseModel):
    product_name: str
    image_prompt: str
    duration_ms: int
    error: str = ""


@router.post("/test/image-prompt", response_model=ImagePromptTestResponse)
async def test_image_prompt(
    body: ImagePromptTestRequest,
    current_user: str = Depends(get_current_user),
) -> ImagePromptTestResponse:
    """Stage 2 only: run image_prompt.txt using a provided scheme (from
    /test/scheme) to produce the final image prompt string.

    Uses the CURRENT image_prompt.txt on disk. Does NOT re-run stage 1
    or call the image generation model.
    """
    from content_generator import generate_image_prompt_only

    record = await _locate_record(body.record_id)
    start = time.time()
    try:
        image_prompt = await asyncio.to_thread(
            generate_image_prompt_only, record, body.scheme
        )
        return ImagePromptTestResponse(
            product_name=record.product_name,
            image_prompt=image_prompt,
            duration_ms=int((time.time() - start) * 1000),
        )
    except Exception as e:
        return ImagePromptTestResponse(
            product_name=record.product_name,
            image_prompt="",
            duration_ms=int((time.time() - start) * 1000),
            error=f"{type(e).__name__}: {e}",
        )


class ImageTestRequest(BaseModel):
    record_id: str
    image_prompt: str  # Output from test/image-prompt
    # Scheme from test/scheme — used to overlay body_copy text with PIL
    scheme: dict[str, Any] | None = None


class ImageTestResponse(BaseModel):
    product_name: str
    image_b64: str = ""
    image_size_bytes: int = 0
    asset_process_ms: int = 0
    image_gen_ms: int = 0
    overlay_ms: int = 0
    total_ms: int = 0
    error: str = ""


@router.post("/test/image", response_model=ImageTestResponse)
async def test_image(
    body: ImageTestRequest,
    current_user: str = Depends(get_current_user),
) -> ImageTestResponse:
    """Stage 3: run rembg + actual Gemini image generation using the provided
    image_prompt (from /test/image-prompt) and the record's product asset.

    If scheme is provided, also applies PIL body_copy text overlay using
    the CJK font, matching the production pipeline behavior.

    Does NOT run QC, does NOT upload to WeChat, does NOT touch Feishu status.
    Returns the generated image as base64 for browser preview.
    """
    import os as _os
    from asset_processor import process_product_image
    from image_generator import (
        analyze_layout_with_vision,
        apply_layout,
        generate_poster_image,
    )
    from content_generator import _parse_small_text_zone

    record = await _locate_record(body.record_id)
    if not record.asset_filename:
        return ImageTestResponse(
            product_name=record.product_name,
            error="Missing product asset filename",
        )

    asset_dir = Path(_os.getenv("ASSETS_DIR", "./assets/products"))
    asset_path = asset_dir / record.asset_filename

    total_start = time.time()

    # Asset processing
    stage_start = time.time()
    try:
        product_b64 = await asyncio.to_thread(process_product_image, str(asset_path))
        asset_ms = int((time.time() - stage_start) * 1000)
    except Exception as e:
        return ImageTestResponse(
            product_name=record.product_name,
            asset_process_ms=int((time.time() - stage_start) * 1000),
            total_ms=int((time.time() - total_start) * 1000),
            error=f"asset_processing failed: {type(e).__name__}: {e}",
        )

    # Image generation
    stage_start = time.time()
    try:
        poster_bytes = await asyncio.to_thread(
            generate_poster_image, body.image_prompt, product_b64
        )
        gen_ms = int((time.time() - stage_start) * 1000)
    except Exception as e:
        return ImageTestResponse(
            product_name=record.product_name,
            asset_process_ms=asset_ms,
            image_gen_ms=int((time.time() - stage_start) * 1000),
            total_ms=int((time.time() - total_start) * 1000),
            error=f"image_generation failed: {type(e).__name__}: {e}",
        )

    # Optional: vision-based layout design + PIL render (matches pipeline)
    overlay_ms = 0
    if body.scheme:
        overlay_start = time.time()
        try:
            fallback_zone = _parse_small_text_zone(body.scheme)
            body_copy = body.scheme.get("body_copy") or []
            if body_copy:
                # Vision AI designs a full LayoutSpec for this specific image
                layout_spec = await asyncio.to_thread(
                    analyze_layout_with_vision,
                    poster_bytes,
                    body_copy,
                    fallback_zone.heading,
                    fallback_zone,
                )
                poster_bytes = await asyncio.to_thread(
                    apply_layout,
                    poster_bytes,
                    layout_spec,
                )
            overlay_ms = int((time.time() - overlay_start) * 1000)
        except Exception as e:
            # Overlay failure is non-fatal — return the base image
            overlay_ms = int((time.time() - overlay_start) * 1000)
            return ImageTestResponse(
                product_name=record.product_name,
                image_b64=base64.b64encode(poster_bytes).decode("utf-8"),
                image_size_bytes=len(poster_bytes),
                asset_process_ms=asset_ms,
                image_gen_ms=gen_ms,
                overlay_ms=overlay_ms,
                total_ms=int((time.time() - total_start) * 1000),
                error=f"body_text_overlay failed: {type(e).__name__}: {e}",
            )

    return ImageTestResponse(
        product_name=record.product_name,
        image_b64=base64.b64encode(poster_bytes).decode("utf-8"),
        image_size_bytes=len(poster_bytes),
        asset_process_ms=asset_ms,
        image_gen_ms=gen_ms,
        overlay_ms=overlay_ms,
        total_ms=int((time.time() - total_start) * 1000),
    )


@router.put("/{name}", response_model=PromptDetail)
def update_prompt(
    name: str,
    body: PromptUpdateRequest,
    current_user: str = Depends(get_current_user),
) -> PromptDetail:
    path = _safe_path(name)

    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Prompt content cannot be empty")

    # Note: removing declared placeholders is allowed. Python's .format() ignores
    # unused keyword arguments, so dropping {store_name} just means that variable
    # won't be interpolated into the prompt. The frontend shows which placeholders
    # are used / unused as a guide only.

    # Backup previous version before overwriting
    if path.exists():
        backup_dir = PROMPTS_DIR / ".backups"
        backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{name}.{ts}.bak"
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    path.write_text(body.content, encoding="utf-8")

    meta = _build_meta(name, path)
    return PromptDetail(**meta.model_dump(), content=body.content)
