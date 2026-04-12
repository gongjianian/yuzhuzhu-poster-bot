import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from models import ProductRecord, PosterScheme, SmallTextZone

load_dotenv()

PROMPTS_DIR = Path(__file__).parent / "prompts"
STORE_NAME = os.getenv("STORE_NAME", "浴小主")


def _resolve_copy_model() -> str:
    """Resolve the current copy model from runtime settings → env → default.

    Runtime settings (data/runtime_settings.json) take precedence so the
    dashboard can switch models without restarting the service. Strips any
    "models/" prefix that Google's list API returns.
    """
    try:
        from dashboard.services import runtime_settings
        model = runtime_settings.get_copy_model()
    except Exception:
        model = os.getenv("GEMINI_COPY_MODEL", "gemini-3.1-pro-preview")
    if model.startswith("models/"):
        model = model[len("models/"):]
    return model


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _build_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url=os.getenv("GEMINI_API_BASE", "https://api.buxianliang.fun/v1"),
    )


def _extract_code_block(text: str) -> str:
    """Extract content between first ``` and last ```."""
    match = re.search(r"```(?:\w*)\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
def generate_scheme_only(record: ProductRecord) -> dict:
    """Stage 1 only: run scheme_prompt.txt against the product to get the
    scheme JSON (headline, subheadline, body_copy, scene_description,
    layout_description, etc.).

    Reads the current scheme_prompt.txt file on every call - safe to use
    immediately after editing the prompt in the dashboard.
    """
    client = _build_client()
    model = _resolve_copy_model()

    scheme_template = _load_prompt("scheme_prompt.txt")
    selling_points = f"{record.benefits}；成分：{record.ingredients}"

    scheme_prompt = scheme_template.format(
        product_name=record.product_name,
        selling_points=selling_points,
        idea=record.xiaohongshu_topics or "（无特定话题，请自主发散）",
        visual_style=record.visual_style,
        brand_colors=record.brand_colors,
        random_seed=os.urandom(4).hex()
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": scheme_prompt}],
        temperature=0.8,
    )
    content = resp.choices[0].message.content or ""

    try:
        clean = re.sub(r"```json|```", "", content).strip()
        return json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"Stage 1 JSON parse error: {e}\nResponse: {content[:300]}")


def _parse_small_text_zone(scheme_data: dict) -> SmallTextZone:
    """Extract small_text_zone from scheme JSON, falling back to sensible
    defaults if the model didn't include it or gave malformed values."""
    raw = scheme_data.get("small_text_zone") or {}
    if not isinstance(raw, dict):
        raw = {}

    def _f(key: str, default: float) -> float:
        val = raw.get(key)
        try:
            f = float(val)
            # Clamp to [0, 1]
            return max(0.0, min(1.0, f))
        except (TypeError, ValueError):
            return default

    return SmallTextZone(
        position=str(raw.get("position") or "bottom-left").strip(),
        x_ratio=_f("x_ratio", 0.05),
        y_ratio=_f("y_ratio", 0.58),
        width_ratio=_f("width_ratio", 0.42),
        height_ratio=_f("height_ratio", 0.36),
        bg_color=str(raw.get("bg_color") or "#F5F7F0").strip(),
        text_color=str(raw.get("text_color") or "#2D3A2D").strip(),
        heading=str(raw.get("heading") or "").strip(),
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    reraise=True,
)
def generate_image_prompt_only(record: ProductRecord, scheme_data: dict) -> str:
    """Stage 2 only: given the output of stage 1 (scheme_data), run
    image_prompt.txt to produce the final image prompt string that will be
    fed to the image generation model.

    Reads the current image_prompt.txt file on every call.
    """
    client = _build_client()
    model = _resolve_copy_model()

    # Work on a copy so we don't mutate the caller's dict
    scheme_copy = dict(scheme_data)
    scene_desc = scheme_copy.pop("scene_description", "")
    layout_desc = scheme_copy.pop("layout_description", "")
    # small_text_zone is no longer used by image_prompt.txt — body_copy
    # placement is decided post-generation by analyze_layout_with_vision().
    # We still drop it from the scheme so it doesn't bloat the prompt.
    scheme_copy.pop("small_text_zone", None)

    selling_points = f"{record.benefits}；成分：{record.ingredients}"

    body_copy_list = scheme_data.get("body_copy", [])
    body_copy_formatted = (
        "\n".join(f"  • {item}" for item in body_copy_list)
        if body_copy_list
        else "  （暂无卖点文字）"
    )

    image_template = _load_prompt("image_prompt.txt")
    image_prompt_filled = image_template.format(
        store_name=STORE_NAME,
        size="3:4",
        selling_points=selling_points,
        selected_scheme=json.dumps(scheme_copy, ensure_ascii=False),
        product_name=record.product_name,
        headline=scheme_copy.get("headline", ""),
        subheadline=scheme_copy.get("subheadline", ""),
        cta=scheme_copy.get("cta", ""),
        body_copy=body_copy_formatted,
        scene_description=scene_desc,
        layout_description=layout_desc,
        visual_style=scheme_copy.get("visual_style", record.visual_style),
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": image_prompt_filled}],
        temperature=0.7,
    )
    content = resp.choices[0].message.content or ""
    return _extract_code_block(content)


def generate_poster_content(record: ProductRecord) -> PosterScheme:
    """End-to-end content generation: runs both stage 1 and stage 2.

    This is the function used by the production pipeline. The dashboard
    test endpoints call generate_scheme_only / generate_image_prompt_only
    directly so operators can tune each stage independently.
    """
    scheme_data = generate_scheme_only(record)
    image_prompt = generate_image_prompt_only(record, scheme_data)

    return PosterScheme(
        scheme_name=scheme_data.get("scheme_name", "方案A"),
        visual_style=scheme_data.get("visual_style", record.visual_style),
        headline=scheme_data.get("headline", ""),
        subheadline=scheme_data.get("subheadline", ""),
        body_copy=scheme_data.get("body_copy", []),
        cta=scheme_data.get("cta", ""),
        image_prompt=image_prompt,
        aspect_ratio="3:4",
        small_text_zone=_parse_small_text_zone(scheme_data),
    )
