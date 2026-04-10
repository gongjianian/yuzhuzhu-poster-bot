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
    product_line: str = "未知产品线"
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
        "card",          # ★ recommended: panel + heading + items, auto-fit
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
    items: list[str] = Field(default_factory=list)  # bullet_list / card items
    bullet: str = "·"  # bullet marker
    max_w: float = 1.0  # text/bullet_list wrap width (normalized)
    # Vertical bound for text/bullet_list (normalized). 0 = unbounded.
    # Renderer auto-shrinks the font until content fits within max_h.
    max_h: float = 0.0
    font: Literal["NotoSansSC-Medium", "NotoSansSC-Regular"] = "NotoSansSC-Regular"
    # Font size: int → pixels; float < 1 → ratio of poster height.
    # Renderer handles both forms; we use float here so Pydantic doesn't reject 0.03.
    size: float = 22.0
    color: str = "#2D3A2D"
    align: Literal["left", "center", "right"] = "left"
    line_spacing: float = 1.4
    weight: Literal["normal", "bold"] = "normal"

    # ---- card-only fields ----
    # Optional heading text drawn above the items list inside the card.
    heading: str = ""
    # Font sizes for card heading and body. Use float < 1 for ratio of poster
    # height (recommended) or int for pixels. Renderer auto-shrinks if content
    # overflows the card's inner area.
    heading_size: float = 0.034
    body_size: float = 0.024
    # Optional left accent bar (e.g. brand color stripe). Empty = no bar.
    accent_color: str = ""
    # Inner padding as a fraction of min(w, h). 0.08 = 8%.
    padding: float = 0.08


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


class CategoryPosterTask(BaseModel):
    """One poster job: symptom subcategory × product line × matched products."""
    category_id: str           # e.g. "cat_pw_jstl"
    level1_category_id: str    # e.g. "cat_piwei"
    category_name: str         # e.g. "积食停滞类"
    product_line: str          # e.g. "五行泡浴"
    products: list[ProductRecord]


class CSSOverlayStyle(BaseModel):
    """CSS properties for the absolute-positioned overlay div."""

    left: str = "5%"
    top: str = "60%"
    width: str = "44%"
    height: str = "34%"
    background: str = "rgba(250,250,245,0.92)"
    border_radius: str = "16px"
    backdrop_filter: str = ""
    mix_blend_mode: str = "normal"
    padding: str = "5% 6%"


class CSSTextStyle(BaseModel):
    """CSS typography properties for heading or body items."""

    color: str = "#3A2C1F"
    font_size: str = "2.6vh"
    font_weight: str = "400"
    line_height: str = "1.55"
    mix_blend_mode: str = "normal"


class CSSLayoutSpec(BaseModel):
    """Full CSS layout returned by the vision AI for HTML compositor."""

    reasoning: str = ""
    overlay: CSSOverlayStyle = Field(default_factory=CSSOverlayStyle)
    heading_text: str = ""
    heading_style: CSSTextStyle = Field(
        default_factory=lambda: CSSTextStyle(font_size="3.2vh", font_weight="600")
    )
    items_style: CSSTextStyle = Field(default_factory=CSSTextStyle)
