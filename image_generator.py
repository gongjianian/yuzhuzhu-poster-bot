from __future__ import annotations

import base64
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
import requests
from tenacity import retry, stop_after_attempt, wait_exponential


load_dotenv()


FUSION_RULES = (
    "Product fusion rules: preserve the exact product silhouette, logo, label text, "
    "and packaging colors. Do not redesign the product. Keep proportions unchanged. "
    "Use the supplied product image as the authoritative reference."
)


def _build_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url=os.getenv("GEMINI_API_BASE", "https://api.buxianliang.fun/v1"),
    )


def _get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _decode_image_url(url: str) -> bytes:
    if url.startswith("data:"):
        _, encoded = url.split(",", 1)
        return base64.b64decode(encoded)

    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def _extract_image_bytes(response: Any) -> bytes:
    data_items = _get_value(response, "data", []) or []
    for item in data_items:
        b64_json = _get_value(item, "b64_json")
        if b64_json:
            return base64.b64decode(b64_json)

        url = _get_value(item, "url")
        if url:
            return _decode_image_url(url)

    choices = _get_value(response, "choices", []) or []
    for choice in choices:
        message = _get_value(choice, "message", {})
        content = _get_value(message, "content", [])
        if isinstance(content, (str, bytes)):
            continue
        if isinstance(content, dict):
            content = [content]

        for part in content:
            part_type = _get_value(part, "type", "")
            if part_type in {"output_image", "image"}:
                image_b64 = (
                    _get_value(part, "image_base64")
                    or _get_value(part, "b64_json")
                    or _get_value(part, "data")
                )
                if image_b64:
                    return base64.b64decode(image_b64)

            if part_type == "image_url":
                image_url = _get_value(part, "image_url")
                if isinstance(image_url, dict):
                    url = image_url.get("url", "")
                else:
                    url = image_url or ""
                if url:
                    return _decode_image_url(url)

    raise ValueError("No image content found in model response")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
def generate_poster_image(image_prompt: str, product_image_b64: str) -> bytes:
    client = _build_client()
    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
    prompt = f"{image_prompt}\n\n{FUSION_RULES}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{product_image_b64}",
                        },
                    },
                ],
            }
        ],
    )

    return _extract_image_bytes(response)
