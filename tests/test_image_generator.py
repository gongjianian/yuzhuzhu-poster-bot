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


def test_generate_poster_image_is_retry_wrapped() -> None:
    assert hasattr(image_generator.generate_poster_image, "retry")


def test_generate_poster_image_adds_image_size_for_gemini_3_pro_image_models() -> None:
    body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64.b64encode(b"ok").decode("utf-8"),
                            }
                        }
                    ]
                }
            }
        ]
    }

    with patch("image_generator._resolve_image_model", return_value="gemini-3-pro-image-preview"), patch(
        "image_generator.requests.post",
        return_value=_make_response(200, body),
    ) as mock_post:
        image_generator.generate_poster_image("prompt", "src-b64")

    payload = mock_post.call_args.kwargs["json"]
    assert payload["generationConfig"]["imageConfig"]["imageSize"] == "2K"


def test_generate_poster_image_omits_image_size_for_other_models() -> None:
    body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64.b64encode(b"ok").decode("utf-8"),
                            }
                        }
                    ]
                }
            }
        ]
    }

    with patch("image_generator._resolve_image_model", return_value="gemini-2.5-flash-image"), patch(
        "image_generator.requests.post",
        return_value=_make_response(200, body),
    ) as mock_post:
        image_generator.generate_poster_image("prompt", "src-b64")

    payload = mock_post.call_args.kwargs["json"]
    assert "imageConfig" not in payload["generationConfig"]


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


def test_rate_limit_body_with_http_200_raises_rate_limit_error() -> None:
    """The proxy sometimes returns HTTP 200 with an error body for rate limits."""
    body = {
        "error": {
            "code": 429,
            "message": "Resource has been exhausted (e.g. check quota).",
            "status": "RESOURCE_EXHAUSTED",
        }
    }
    with patch(
        "image_generator.requests.post",
        return_value=_make_response(200, body, text=str(body)),
    ):
        with pytest.raises(image_generator.RateLimitError, match="限流"):
            image_generator.generate_poster_image("prompt", "src-b64")


def test_rate_limit_http_429_raises_rate_limit_error() -> None:
    body = {"error": {"code": "model_cooldown", "message": "All credentials cooling down"}}
    with patch(
        "image_generator.requests.post",
        return_value=_make_response(429, body, text=str(body)),
    ):
        with pytest.raises(image_generator.RateLimitError):
            image_generator.generate_poster_image("prompt", "src-b64")


def test_rate_limit_error_not_retried() -> None:
    """RateLimitError must skip tenacity retry - one call only."""
    body = {"error": {"code": 429, "message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
    mock_post = Mock(return_value=_make_response(200, body, text=str(body)))
    with patch("image_generator.requests.post", mock_post):
        with pytest.raises(image_generator.RateLimitError):
            image_generator.generate_poster_image("prompt", "src-b64")
    # Should only be called once (no retry)
    assert mock_post.call_count == 1


def test_build_endpoint_handles_v1_base() -> None:
    with patch.dict("os.environ", {"GEMINI_API_BASE": "https://api.example.com/v1"}):
        url = image_generator._build_endpoint("gemini-3-pro-image-preview")
    assert url == "https://api.example.com/v1beta/models/gemini-3-pro-image-preview:generateContent"


def test_build_endpoint_handles_v1beta_base() -> None:
    with patch.dict("os.environ", {"GEMINI_API_BASE": "https://api.example.com/v1beta"}):
        url = image_generator._build_endpoint("gemini-3-pro-image-preview")
    assert url == "https://api.example.com/v1beta/models/gemini-3-pro-image-preview:generateContent"


def test_build_endpoint_handles_google_openai_compat() -> None:
    """Google's OpenAI-compat base has an /openai subpath that must be stripped
    for the native generateContent endpoint."""
    with patch.dict(
        "os.environ",
        {"GEMINI_API_BASE": "https://generativelanguage.googleapis.com/v1beta/openai/"},
    ):
        url = image_generator._build_endpoint("gemini-3-pro-image-preview")
    assert (
        url
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent"
    )


def test_build_endpoint_url_encodes_model_with_spaces() -> None:
    """CLIProxyAPI uses display names with spaces (e.g., 'Nano Banana Pro')
    which must be URL-encoded in the path."""
    with patch.dict(
        "os.environ",
        {"GEMINI_API_BASE": "https://api.buxianliang.fun/v1/"},
    ):
        url = image_generator._build_endpoint("Nano Banana Pro")
    assert (
        url
        == "https://api.buxianliang.fun/v1beta/models/Nano%20Banana%20Pro:generateContent"
    )


def test_build_endpoint_strips_models_prefix_then_encodes() -> None:
    with patch.dict("os.environ", {"GEMINI_API_BASE": "https://api.example.com/v1"}):
        url = image_generator._build_endpoint("models/Nano Banana Pro")
    assert (
        url
        == "https://api.example.com/v1beta/models/Nano%20Banana%20Pro:generateContent"
    )
