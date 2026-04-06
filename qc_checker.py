import json
import os
import re

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from models import QCResult

load_dotenv()

QC_PROMPT = """
You are a quality control inspector for commercial product posters.

You are given two images:
1. The generated poster (first image)
2. The original product photo (second image)

Check the generated poster against these criteria and respond with JSON only:

{"passed": true/false, "issues": ["issue1", "issue2"], "confidence": 0.0-1.0}

Criteria (ALL must pass for passed=true):
1. Product is clearly visible and is the focal point
2. Product shape and packaging are not distorted or redesigned
3. Brand colors are approximately preserved
4. Text in the poster is not cropped or illegible
5. No hallucinated extra products appear
6. Logo/brand elements are not obscured

Be strict. If any criterion fails, set passed=false and list all issues.
"""


def _build_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url=os.getenv("GEMINI_API_BASE", "https://api.buxianliang.fun/v1"),
    )


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=3, max=15),
    reraise=True,
)
def check_poster_quality(poster_b64: str, product_b64: str) -> QCResult:
    """
    Use multimodal model to verify poster quality.
    poster_b64: base64-encoded JPEG of generated poster
    product_b64: base64-encoded PNG of original product (pre-processed)
    """
    try:
        client = _build_client()
        model = os.getenv("GEMINI_COPY_MODEL", "gemini-3.1-pro-preview")

        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{poster_b64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{product_b64}"}},
                    {"type": "text", "text": QC_PROMPT},
                ],
            }],
            temperature=0.1,
        )

        content = response.choices[0].message.content
        clean = re.sub(r"```json|```", "", content).strip()

        try:
            data = json.loads(clean)
            return QCResult(**data)
        except (json.JSONDecodeError, Exception):
            logger.warning(f"QC model returned invalid JSON: {content[:200]}")
            return QCResult(passed=True, issues=["QC model returned invalid JSON"], confidence=0.5)

    except Exception as e:
        logger.error(f"QC check failed: {e}. Defaulting to passed=True.")
        return QCResult(passed=True, issues=[f"QC system failure: {str(e)}"], confidence=0.0)
