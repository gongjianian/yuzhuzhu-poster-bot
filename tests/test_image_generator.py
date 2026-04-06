import base64
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import image_generator


def test_generate_poster_image_uses_fusion_rules_and_returns_bytes() -> None:
    image_bytes = b"fake-image-bytes"
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=[
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded}",
                            },
                        }
                    ]
                )
            )
        ]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=Mock(return_value=response))
        )
    )

    with patch("image_generator._build_client", return_value=client):
        result = image_generator.generate_poster_image(
            image_prompt="Create a poster for the product",
            product_image_b64="source-b64",
        )

    assert result == image_bytes
    call_kwargs = client.chat.completions.create.call_args.kwargs
    message_content = call_kwargs["messages"][0]["content"]
    assert image_generator.FUSION_RULES in message_content[0]["text"]
    assert message_content[1]["image_url"]["url"] == "data:image/png;base64,source-b64"


def test_extract_image_bytes_supports_b64_json() -> None:
    image_bytes = b"json-image-bytes"
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    response = SimpleNamespace(data=[SimpleNamespace(b64_json=encoded)])

    result = image_generator._extract_image_bytes(response)

    assert result == image_bytes


@patch("image_generator.requests.get")
def test_extract_image_bytes_downloads_remote_image(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.content = b"remote-image"
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=[
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.com/image.png"},
                        }
                    ]
                )
            )
        ]
    )

    result = image_generator._extract_image_bytes(response)

    assert result == b"remote-image"
    mock_get.assert_called_once_with("https://example.com/image.png", timeout=30)


def test_extract_image_bytes_raises_when_missing() -> None:
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=[]))])

    with pytest.raises(ValueError):
        image_generator._extract_image_bytes(response)
