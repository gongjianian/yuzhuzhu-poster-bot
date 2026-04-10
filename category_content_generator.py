"""Generate PosterScheme for a CategoryPosterTask (symptom × product-line group).

Uses prompts/category_scheme_prompt.txt which is designed for multi-product
symptom-oriented posters, unlike scheme_prompt.txt which is product-centric.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from models import CategoryPosterTask, PosterScheme

load_dotenv()

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _build_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url=os.getenv("GEMINI_API_BASE", "https://api.buxianliang.fun/v1"),
    )


def _resolve_copy_model() -> str:
    try:
        from dashboard.services import runtime_settings
        model = runtime_settings.get_copy_model()
    except Exception as exc:
        logger.debug("runtime_settings unavailable, using env: {}", exc)
        model = os.getenv("GEMINI_COPY_MODEL", "gemini-3.1-pro-preview")
    if model.startswith("models/"):
        model = model[len("models/"):]
    return model


def _load_prompt() -> str:
    return (PROMPTS_DIR / "category_scheme_prompt.txt").read_text(encoding="utf-8")


def _format_product_details(task: CategoryPosterTask) -> str:
    lines = []
    for i, p in enumerate(task.products, 1):
        lines.append(
            f"{i}. {p.product_name}\n"
            f"   功效：{p.benefits}\n"
            f"   成分：{p.ingredients}"
        )
    return "\n".join(lines)


def _parse_scheme(content: str) -> PosterScheme:
    clean = re.sub(r"```json|```", "", content).strip()
    data = json.loads(clean)
    return PosterScheme(
        scheme_name=data.get("scheme_name", ""),
        visual_style=data.get("visual_style", ""),
        headline=data.get("headline", ""),
        subheadline=data.get("subheadline", ""),
        body_copy=data.get("body_copy", []),
        cta=data.get("cta", ""),
        image_prompt=data.get("image_prompt", ""),
        aspect_ratio=data.get("aspect_ratio", "3:4"),
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
def generate_category_poster_content(task: CategoryPosterTask) -> PosterScheme:
    """Generate a PosterScheme for a symptom-category × product-line group."""
    client = _build_client()
    model = _resolve_copy_model()

    from symptom_categories import get_category_by_id
    category = get_category_by_id(task.category_id) or {}

    prompt_template = _load_prompt()
    prompt = prompt_template.format(
        category_name=task.category_name,
        description=category.get("description", ""),
        symptoms=category.get("symptoms", ""),
        product_line=task.product_line,
        product_details=_format_product_details(task),
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )
    content = resp.choices[0].message.content or ""

    try:
        scheme = _parse_scheme(content)
        logger.info(
            "category content generated: {} × {} → {}",
            task.category_name, task.product_line, scheme.headline,
        )
        return scheme
    except (json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Category content JSON parse error: {e}\n{content[:300]}")
