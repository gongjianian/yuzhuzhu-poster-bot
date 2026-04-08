import base64
from unittest.mock import Mock, patch

import pytest

import image_generator


def _make_response(status_code: int, body: dict | None = None, text: str = "") -> Mock:
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = body or {}
    resp.text = text or (str(body) if body else "")
    return resp


def test_generate_poster_image_returns_decoded_bytes() -> None:
    image_bytes = b"fake-image-bytes"
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": encoded,
                            }
                        }
                    ]
                }
            }
        ]
    }

    with patch("image_generator.requests.post", return_value=_make_response(200, body)) as mock_post:
        result = image_generator.generate_poster_image(
            image_prompt="Create a poster for the product",
            product_image_b64="source-b64",
        )

    assert result == image_bytes

    call_kwargs = mock_post.call_args.kwargs
    payload = call_kwargs["json"]
    parts = payload["contents"][0]["parts"]
    assert image_generator.FUSION_RULES in parts[0]["text"]
    assert parts[1]["inline_data"]["data"] == "source-b64"
    assert payload["generationConfig"]["responseModalities"] == ["IMAGE", "TEXT"]


def test_generate_poster_image_supports_snake_case_inline_data() -> None:
    image_bytes = b"snake-case-bytes"
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"inline_data": {"mime_type": "image/png", "data": encoded}}
                    ]
                }
            }
        ]
    }

    with patch("image_generator.requests.post", return_value=_make_response(200, body)):
        result = image_generator.generate_poster_image("prompt", "src-b64")

    assert result == image_bytes


def test_generate_poster_image_raises_on_http_error() -> None:
    with patch(
        "image_generator.requests.post",
        return_value=_make_response(500, text="server error"),
    ):
        with pytest.raises(RuntimeError, match="HTTP 500"):
            image_generator.generate_poster_image("prompt", "src-b64")


def test_generate_poster_image_raises_when_no_image_part() -> None:
    body = {
        "candidates": [
            {"content": {"parts": [{"text": "no image here"}]}}
        ]
    }
    with patch(
        "image_generator.requests.post",
        return_value=_make_response(200, body),
    ):
        with pytest.raises(ValueError, match="No image data"):
            image_generator.generate_poster_image("prompt", "src-b64")


def test_build_endpoint_handles_v1_base() -> None:
    with patch.dict("os.environ", {"GEMINI_API_BASE": "https://api.example.com/v1"}):
        url = image_generator._build_endpoint("gemini-3-pro-image-preview")
    assert url == "https://api.example.com/v1beta/models/gemini-3-pro-image-preview:generateContent"


def test_build_endpoint_handles_v1beta_base() -> None:
    with patch.dict("os.environ", {"GEMINI_API_BASE": "https://api.example.com/v1beta"}):
        url = image_generator._build_endpoint("gemini-3-pro-image-preview")
    assert url == "https://api.example.com/v1beta/models/gemini-3-pro-image-preview:generateContent"
