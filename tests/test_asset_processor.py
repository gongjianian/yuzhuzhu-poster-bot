import base64
import io

import pytest
from PIL import Image

from asset_processor import MAX_SIZE, process_product_image


def _png_bytes(size: tuple[int, int]) -> bytes:
    image = Image.new("RGBA", size=size, color=(255, 0, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_process_product_image_success(tmp_path, monkeypatch) -> None:
    source = tmp_path / "product.png"
    source.write_bytes(_png_bytes((1600, 1200)))
    monkeypatch.setattr("asset_processor._load_remove", lambda: (lambda raw: raw))

    encoded = process_product_image(str(source))

    decoded = base64.b64decode(encoded)
    image = Image.open(io.BytesIO(decoded))
    assert image.format == "PNG"
    assert image.size[0] <= MAX_SIZE[0]
    assert image.size[1] <= MAX_SIZE[1]


def test_process_product_image_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        process_product_image("missing-product.png")
