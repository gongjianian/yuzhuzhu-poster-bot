import base64
import io
from pathlib import Path
from typing import Callable

from PIL import Image


MAX_SIZE = (800, 800)


def _load_remove() -> Callable[[bytes], bytes]:
    from rembg import remove

    return remove


def process_product_image(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Product image not found: {file_path}")

    with path.open("rb") as file:
        raw = file.read()

    output = _load_remove()(raw)
    image = Image.open(io.BytesIO(output)).convert("RGBA")
    image.thumbnail(MAX_SIZE, Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
