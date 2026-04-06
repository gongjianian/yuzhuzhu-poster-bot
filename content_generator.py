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

def _load_prompt(filename):
    with open(PROMPTS_DIR / filename, "r", encoding="utf-8") as f:
        return f.read()

def _build_client():
    return OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", "dummy"),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

def _extract_code_block(text, language=""):
    pattern = rf"```{language}(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback to general code block if language specific fails
    pattern = r"```(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        # Remove language identifier if it accidentally got captured at the start
        if content.startswith(language):
            content = content[len(language):].strip()
        return content
    return text.strip()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=30), reraise=True)
def generate_poster_content(record: ProductRecord) -> PosterScheme:
    client = _build_client()
    scheme_prompt_template = _load_prompt("scheme_prompt.txt")
    
    # Phase 1: Scheme Generation
    # Mock some data for the prompt as they are not all in ProductRecord directly
    selling_points = record.benefits if record.benefits else "好用实惠"
    idea = "结合宝妈日常场景"
    
    scheme_prompt = scheme_prompt_template.format(
        product_name=record.product_name,
        selling_points=selling_points,
        idea=idea,
        visual_style=record.visual_style,
        brand_colors=record.brand_colors
    )
    
    response_phase1 = client.chat.completions.create(
        model="gemini-3.1-pro-preview",
        messages=[{"role": "user", "content": scheme_prompt}],
        temperature=0.7
    )
    
    content1 = response_phase1.choices[0].message.content
    json_str = _extract_code_block(content1, "json")
    
    try:
        scheme_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        # If fallback extract failed, try parsing raw content directly
        try:
            # Often models return raw JSON without markdown
            scheme_data = json.loads(content1.strip())
        except json.JSONDecodeError:
            raise ValueError(f"Failed to parse JSON from response: {content1}") from e

    # Add missing fields to scheme_data
    scene_desc = scheme_data.pop("scene_description", "A scene")
    layout_desc = scheme_data.pop("layout_description", "A layout")

    
    # Phase 2: Image Prompt Generation
    image_prompt_template = _load_prompt("image_prompt.txt")
    body_copy_formatted = " ".join(scheme_data.get("body_copy", []))
    
    image_prompt = image_prompt_template.format(
        store_name=STORE_NAME,
        size="1024x1024", # Default size or map from aspect_ratio
        selling_points=selling_points,
        selected_scheme=scheme_data.get("scheme_name", "Scheme"),
        product_name=record.product_name,
        headline=scheme_data.get("headline", ""),
        subheadline=scheme_data.get("subheadline", ""),
        body_copy_formatted=body_copy_formatted,
        cta=scheme_data.get("cta", ""),
        scene_description=scene_desc,
        layout_description=layout_desc,
        visual_style=scheme_data.get("visual_style", record.visual_style)
    )
    
    response_phase2 = client.chat.completions.create(
        model="gemini-3.1-pro-preview",
        messages=[{"role": "user", "content": image_prompt}],
        temperature=0.7
    )
    
    content2 = response_phase2.choices[0].message.content
    final_image_prompt = _extract_code_block(content2)
    
    scheme_data["image_prompt"] = final_image_prompt
    
    return PosterScheme(**scheme_data)
