from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class ProductRecord(BaseModel):
    record_id: str
    product_name: str
    ingredients: str = ""
    benefits: str = ""
    xiaohongshu_topics: str = ""
    category: str = "\u672a\u5206\u7c7b"
    visual_style: str = "\u6781\u7b80\u6241\u5e73"
    brand_colors: str = "#FFFFFF"
    asset_filename: str = ""
    status: str = "PENDING"
    idempotency_key: str = ""
    cloud_file_id: str = ""


class SmallTextZone(BaseModel):
    """Rectangular region + style descriptor for body-copy text overlay.

    The vision model picks this by analyzing the actual generated image,
    so each poster gets a layout that fits its real visual content.
    PIL then renders the text using one of several style templates.
    """

    # Semantic position label (used in the image prompt sent to Gemini)
    position: str = "bottom-left"
    # Normalized coordinates (0.0 - 1.0), top-left origin
    x_ratio: float = 0.05
    y_ratio: float = 0.58
    width_ratio: float = 0.42
    height_ratio: float = 0.36
    # Hex colors for PIL rendering
    bg_color: str = "#F5F7F0"
    text_color: str = "#2D3A2D"
    # Optional label above the bullet list (e.g. "产品亮点")
    heading: str = ""
    # PIL rendering style
    # One of: card | minimal | card-accent | overlay-dark | banner
    style: str = "card"
    # Accent color for "card-accent" style (left sidebar)
    accent_color: str = "#8B4513"


class LayoutElement(BaseModel):
    """One drawing primitive in an AI-directed PIL layout.

    All coordinates and sizes are normalized 0.0-1.0 against the poster
    canvas. The renderer clamps out-of-range values defensively.

    type field selects the renderer:
      - rounded_rect : background panel (filled rectangle, optional radius/shadow)
      - accent_bar   : thin colored bar (left sidebar / underline)
      - text         : single text block (title, subtitle, label)
      - bullet_list  : multi-item list with bullet markers
      - divider      : horizontal/vertical line
    """

    type: Literal[
        "rounded_rect",
        "accent_bar",
        "text",
        "bullet_list",
        "divider",
    ]

    # Geometry (normalized 0-1). Different element types use different subsets.
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    x2: float = 0.0  # for divider end-point
    y2: float = 0.0

    # Fill / stroke
    fill: str = "#FFFFFF"  # hex
    opacity: float = 1.0  # 0..1
    radius: int = 0  # rounded_rect corner radius (px)
    shadow: bool = False  # rounded_rect drop-shadow
    stroke_width: int = 1  # divider line width

    # Text-specific
    content: str = ""  # text element body
    items: list[str] = Field(default_factory=list)  # bullet_list items
    bullet: str = "·"  # bullet marker
    max_w: float = 1.0  # text/bullet_list wrap width (normalized)
    font: Literal["NotoSansSC-Medium", "NotoSansSC-Regular"] = "NotoSansSC-Regular"
    # Font size: int → pixels; float < 1 → ratio of poster height.
    # Renderer handles both forms; we use float here so Pydantic doesn't reject 0.03.
    size: float = 22.0
    color: str = "#2D3A2D"
    align: Literal["left", "center", "right"] = "left"
    line_spacing: float = 1.4
    weight: Literal["normal", "bold"] = "normal"


class LayoutSpec(BaseModel):
    """Complete layout instruction set returned by the vision AI.

    PIL iterates `elements` in order and draws each one. Later elements
    paint on top of earlier ones, so background panels should come first.

    `reasoning` is for debugging logs only — never rendered.
    """

    elements: list[LayoutElement] = Field(default_factory=list)
    reasoning: str = ""


class PosterScheme(BaseModel):
    scheme_name: str
    visual_style: str
    headline: str
    subheadline: str
    body_copy: list[str]
    cta: str
    image_prompt: str
    aspect_ratio: str = "3:4"
    small_text_zone: Optional[SmallTextZone] = None


class QCResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    confidence: float = 1.0
