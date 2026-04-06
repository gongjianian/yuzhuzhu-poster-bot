import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from models import ProductRecord, PosterScheme

load_dotenv()

PROMPTS_DIR = Path(__file__).parent / "prompts"
STORE_NAME = os.getenv("STORE_NAME", "浴小主")


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
def generate_poster_content(record: ProductRecord) -> PosterScheme:
    client = _build_client()
    model = os.getenv("GEMINI_COPY_MODEL", "gemini-3.1-pro-preview")

    # --- Stage 1: Generate scheme ---
    scheme_template = _load_prompt("scheme_prompt.txt")
    selling_points = f"{record.benefits}；成分：{record.ingredients}"

    scheme_prompt = scheme_template.format(
        product_name=record.product_name,
        selling_points=selling_points,
        idea=record.xiaohongshu_topics or "（无特定话题，请自主发散）",
        visual_style=record.visual_style,
        brand_colors=record.brand_colors,
    )

    stage1_resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": scheme_prompt}],
        temperature=0.8,
    )
    stage1_content = stage1_resp.choices[0].message.content

    try:
        clean = re.sub(r"```json|```", "", stage1_content).strip()
        scheme_data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"Stage 1 JSON parse error: {e}\nResponse: {stage1_content[:300]}")

    # Extract scene/layout before passing to PosterScheme (not part of its schema)
    scene_desc = scheme_data.pop("scene_description", "")
    layout_desc = scheme_data.pop("layout_description", "")

    # --- Stage 2: Generate image prompt ---
    body_copy_formatted = "\n".join(
        f'  - "{line}"' for line in scheme_data.get("body_copy", [])
    )

    image_template = _load_prompt("image_prompt.txt")
    image_prompt_filled = image_template.format(
        store_name=STORE_NAME,
        size="3:4",
        selling_points=selling_points,
        selected_scheme=json.dumps(scheme_data, ensure_ascii=False),
        product_name=record.product_name,
        headline=scheme_data.get("headline", ""),
        subheadline=scheme_data.get("subheadline", ""),
        body_copy_formatted=body_copy_formatted,
        cta=scheme_data.get("cta", ""),
        scene_description=scene_desc,
        layout_description=layout_desc,
        visual_style=scheme_data.get("visual_style", record.visual_style),
    )

    stage2_resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": image_prompt_filled}],
        temperature=0.7,
    )
    image_prompt = _extract_code_block(stage2_resp.choices[0].message.content)

    return PosterScheme(
        scheme_name=scheme_data.get("scheme_name", "方案A"),
        visual_style=scheme_data.get("visual_style", record.visual_style),
        headline=scheme_data.get("headline", ""),
        subheadline=scheme_data.get("subheadline", ""),
        body_copy=scheme_data.get("body_copy", []),
        cta=scheme_data.get("cta", ""),
        image_prompt=image_prompt,
        aspect_ratio="3:4",
    )
