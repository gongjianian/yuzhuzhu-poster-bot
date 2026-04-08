from __future__ import annotations

import base64
import os
from typing import Any

import requests
from dotenv import load_dotenv
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


load_dotenv()


FUSION_RULES = (
    "Product fusion rules: preserve the exact product silhouette, logo, label text, "
    "and packaging colors. Do not redesign the product. Keep proportions unchanged. "
    "Use the supplied product image as the authoritative reference."
)


def _build_endpoint(model: str) -> str:
    base = os.getenv("GEMINI_API_BASE", "https://api.buxianliang.fun/v1").rstrip("/")
    # OpenAI-compatible base ends in /v1; native Gemini endpoint lives at /v1beta
    if base.endswith("/v1"):
        base = base[:-3] + "/v1beta"
    elif not base.endswith("/v1beta"):
        base = base + "/v1beta"
    return f"{base}/models/{model}:generateContent"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=60), reraise=True)
def generate_poster_image(image_prompt: str, product_image_b64: str) -> bytes:
    """Generate a poster image using Gemini's native generateContent API.

    The OpenAI-compatible chat.completions endpoint silently returns content=null
    for image generation models on this proxy, so we use the native Gemini format
    which returns inline_data parts containing the image bytes.
    """
    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
    api_key = os.getenv("GEMINI_API_KEY", "")
    prompt = f"{image_prompt}\n\n{FUSION_RULES}"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": product_image_b64,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
        },
    }

    response = requests.post(
        _build_endpoint(model),
        headers={
            "x-goog-api-key": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=300,
    )

    if response.status_code != 200:
        snippet = response.text[:500]
        raise RuntimeError(
            f"Gemini image generation failed: HTTP {response.status_code} - {snippet}"
        )

    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError(f"No candidates in Gemini response: {str(data)[:300]}")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline:
            b64_data = inline.get("data", "")
            if b64_data:
                return base64.b64decode(b64_data)

    raise ValueError(
        f"No image data found in Gemini response. Parts: {[list(p.keys()) for p in parts]}"
    )
