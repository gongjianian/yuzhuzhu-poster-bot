from __future__ import annotations

import base64
import io
import os
import urllib.parse
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from models import LayoutElement, LayoutSpec, SmallTextZone


class RateLimitError(RuntimeError):
    """Raised when the upstream API reports rate limiting / quota exhaustion.

    Tenacity is configured to NOT retry this error - retrying a cooldown
    just wastes time until the user picks a different model or waits.
    """


load_dotenv()


FUSION_RULES = (
    "You will receive TWO reference images in this request:\n"
    "  [Image 1] Product package — preserve the exact product silhouette, logo, "
    "label text, barcode, and packaging colors. Do NOT redesign the product or "
    "rewrite any text on it. Keep proportions unchanged. This is the authoritative "
    "reference for the physical product.\n"
    "  [Image 2] Brand logo (浴小主) — place this logo in the top-right corner of "
    "the final poster. IMPORTANT LOGO RULES:\n"
    "    • Position: top-right corner with small padding (roughly 4-6% from the "
    "top and right edges).\n"
    "    • Size: small and elegant, about 12-16% of the poster width.\n"
    "    • Color: recolor the logo to a SINGLE harmonizing color that blends with "
    "the poster background at that corner. Pick a tone that is visible but not "
    "jarring — think of it as a subtle brand watermark, not a loud stamp. If the "
    "background is light, use a dark muted version of the brand color; if dark, "
    "use a soft light tint.\n"
    "    • Preserve the logo's exact shape, all characters (浴小主), and the ® "
    "symbol — do not rewrite or distort the text.\n"
    "    • Do not add any extra text, box, border, or shadow around the logo.\n"
)


# ---------- Logo loading ----------

DEFAULT_LOGO_PATH = "assets/logo/logo.png"


def _load_logo_b64() -> str | None:
    """Load the brand logo as base64. Returns None if the file doesn't exist
    so the pipeline can still run (Gemini just won't get a logo reference)."""
    logo_path = Path(os.getenv("LOGO_PATH", DEFAULT_LOGO_PATH))
    if not logo_path.is_absolute():
        logo_path = Path(__file__).parent / logo_path

    if not logo_path.exists():
        logger.warning("Logo file not found, skipping logo reference: {}", logo_path)
        return None

    try:
        return base64.b64encode(logo_path.read_bytes()).decode("utf-8")
    except OSError as exc:
        logger.exception("Failed to read logo file: {}", exc)
        return None


# ---------- Body copy text overlay (PIL + CJK font) ----------

DEFAULT_FONT_BOLD = "assets/fonts/NotoSansSC-Medium.otf"
DEFAULT_FONT_REGULAR = "assets/fonts/NotoSansSC-Regular.otf"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Parse '#RRGGBB' or 'RRGGBB' into an (R, G, B) tuple. Falls back to
    neutral gray on parse errors."""
    h = (hex_color or "").lstrip("#").strip()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (240, 240, 240)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return (240, 240, 240)


def _wrap_cjk(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Line-wrap CJK text by pixel width, character by character.
    Unlike English, Chinese has no word boundaries so we wrap per char."""
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for ch in text:
        test = current + ch
        # Use getbbox for accurate width measurement
        bbox = font.getbbox(test)
        width = bbox[2] - bbox[0]
        if width <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def _font_path(rel_path: str) -> Path:
    p = Path(rel_path)
    if not p.is_absolute():
        p = Path(__file__).parent / p
    return p


# ---------- LayoutSpec renderer (AI-directed PIL layout) ----------
#
# The vision AI returns a list of LayoutElement primitives. We iterate the
# list in order and dispatch each element to its renderer. All coordinates
# are normalized 0..1 against the poster canvas.


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, f))


def _alpha(opacity: float) -> int:
    return max(0, min(255, int(round(_clamp(opacity) * 255))))


def _resolve_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """Look up a Noto Sans SC font file by name. Falls back to PIL's default
    bitmap font (which can't render CJK well) only if both font files are
    missing — the renderer will log a warning earlier in apply_layout()."""
    bold_path = _font_path(os.getenv("FONT_BOLD_PATH", DEFAULT_FONT_BOLD))
    regular_path = _font_path(os.getenv("FONT_REGULAR_PATH", DEFAULT_FONT_REGULAR))
    if font_name == "NotoSansSC-Medium" and bold_path.exists():
        return ImageFont.truetype(str(bold_path), max(8, int(size)))
    if regular_path.exists():
        return ImageFont.truetype(str(regular_path), max(8, int(size)))
    if bold_path.exists():
        return ImageFont.truetype(str(bold_path), max(8, int(size)))
    return ImageFont.load_default()


def _draw_rounded_rect(
    canvas: Image.Image,
    el: LayoutElement,
    W: int,
    H: int,
) -> None:
    x = int(_clamp(el.x) * W)
    y = int(_clamp(el.y) * H)
    w = int(_clamp(el.w) * W)
    h = int(_clamp(el.h) * H)
    if w <= 0 or h <= 0:
        return

    rgb = _hex_to_rgb(el.fill)
    alpha = _alpha(el.opacity)
    radius = max(0, int(el.radius))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # Optional drop-shadow: draw a slightly larger soft black rect first.
    if el.shadow:
        from PIL import ImageFilter

        shadow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        offset = max(2, int(min(w, h) * 0.02))
        if radius > 0:
            sd.rounded_rectangle(
                [x + offset, y + offset, x + w + offset, y + h + offset],
                radius=radius,
                fill=(0, 0, 0, int(alpha * 0.35)),
            )
        else:
            sd.rectangle(
                [x + offset, y + offset, x + w + offset, y + h + offset],
                fill=(0, 0, 0, int(alpha * 0.35)),
            )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=offset))
        canvas.alpha_composite(shadow_layer)

    if radius > 0:
        draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=(*rgb, alpha))
    else:
        draw.rectangle([x, y, x + w, y + h], fill=(*rgb, alpha))
    canvas.alpha_composite(layer)


def _draw_accent_bar(canvas: Image.Image, el: LayoutElement, W: int, H: int) -> None:
    """A thin filled rectangle. Identical to a rounded_rect with radius=0,
    but exposed separately so the AI's intent stays readable in logs."""
    x = int(_clamp(el.x) * W)
    y = int(_clamp(el.y) * H)
    w = max(1, int(_clamp(el.w) * W))
    h = max(1, int(_clamp(el.h) * H))
    rgb = _hex_to_rgb(el.fill)
    alpha = _alpha(el.opacity)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle([x, y, x + w, y + h], fill=(*rgb, alpha))
    canvas.alpha_composite(layer)


def _draw_text_block(canvas: Image.Image, el: LayoutElement, W: int, H: int) -> None:
    if not el.content:
        return
    x = int(_clamp(el.x) * W)
    y = int(_clamp(el.y) * H)
    max_w_px = max(20, int(_clamp(el.max_w, 0.05, 1.0) * W))

    # Convert size: AI may return px directly, or a fractional value < 1
    # interpreted as ratio of poster height. Treat anything < 1 as ratio.
    raw_size = float(el.size or 22)
    if raw_size < 1.0:
        size_px = max(10, int(raw_size * H))
    else:
        size_px = max(10, int(raw_size))

    font = _resolve_font(el.font, size_px)
    rgb = _hex_to_rgb(el.color)
    alpha = _alpha(el.opacity)

    lines = _wrap_cjk(el.content, font, max_w_px)
    line_h = int(size_px * float(el.line_spacing or 1.4))

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cy = y
    for line in lines:
        if cy >= H:
            break
        bbox = font.getbbox(line)
        line_w = bbox[2] - bbox[0]
        if el.align == "center":
            cx = x + (max_w_px - line_w) // 2
        elif el.align == "right":
            cx = x + max_w_px - line_w
        else:
            cx = x
        draw.text((cx, cy), line, font=font, fill=(*rgb, alpha))
        cy += line_h
    canvas.alpha_composite(layer)


def _draw_bullet_list(canvas: Image.Image, el: LayoutElement, W: int, H: int) -> None:
    if not el.items:
        return
    x = int(_clamp(el.x) * W)
    y = int(_clamp(el.y) * H)
    max_w_px = max(20, int(_clamp(el.max_w, 0.05, 1.0) * W))

    raw_size = float(el.size or 22)
    if raw_size < 1.0:
        size_px = max(10, int(raw_size * H))
    else:
        size_px = max(10, int(raw_size))

    font = _resolve_font(el.font, size_px)
    bold_font = _resolve_font("NotoSansSC-Medium", size_px)
    rgb = _hex_to_rgb(el.color)
    alpha = _alpha(el.opacity)
    line_h = int(size_px * float(el.line_spacing or 1.4))

    bullet = el.bullet or "·"
    bullet_box = bold_font.getbbox(bullet + " ")
    bullet_w = bullet_box[2] - bullet_box[0]
    text_x_offset = bullet_w + max(4, int(size_px * 0.25))
    wrap_w = max(20, max_w_px - text_x_offset)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cy = y
    for item in el.items:
        if cy >= H:
            break
        wrapped = _wrap_cjk(item, font, wrap_w)
        if not wrapped:
            continue
        # First line: bullet + first chunk
        draw.text((x, cy), bullet, font=bold_font, fill=(*rgb, alpha))
        draw.text((x + text_x_offset, cy), wrapped[0], font=font, fill=(*rgb, alpha))
        cy += line_h
        # Continuation lines (indented)
        for cont in wrapped[1:]:
            if cy >= H:
                break
            draw.text((x + text_x_offset, cy), cont, font=font, fill=(*rgb, alpha))
            cy += line_h
        # Inter-item gap
        cy += int(size_px * 0.35)
    canvas.alpha_composite(layer)


def _draw_divider(canvas: Image.Image, el: LayoutElement, W: int, H: int) -> None:
    x1 = int(_clamp(el.x) * W)
    y1 = int(_clamp(el.y) * H)
    x2 = int(_clamp(el.x2) * W)
    y2 = int(_clamp(el.y2) * H)
    rgb = _hex_to_rgb(el.fill)
    alpha = _alpha(el.opacity)
    width = max(1, int(el.stroke_width or 1))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).line([(x1, y1), (x2, y2)], fill=(*rgb, alpha), width=width)
    canvas.alpha_composite(layer)


_RENDERERS = {
    "rounded_rect": _draw_rounded_rect,
    "accent_bar": _draw_accent_bar,
    "text": _draw_text_block,
    "bullet_list": _draw_bullet_list,
    "divider": _draw_divider,
}


def apply_layout(poster_bytes: bytes, layout: LayoutSpec) -> bytes:
    """Render an AI-directed LayoutSpec onto the poster.

    Iterates `layout.elements` in order and dispatches each to a PIL
    renderer. Failures on individual elements are logged but never abort
    the whole render — the worst case is a partially-overlaid poster,
    which is still better than dropping the image.
    """
    if not layout or not layout.elements:
        return poster_bytes

    bold_path = _font_path(os.getenv("FONT_BOLD_PATH", DEFAULT_FONT_BOLD))
    regular_path = _font_path(os.getenv("FONT_REGULAR_PATH", DEFAULT_FONT_REGULAR))
    if not bold_path.exists() or not regular_path.exists():
        logger.warning(
            "CJK font not found (bold={}, regular={}), skipping layout overlay",
            bold_path,
            regular_path,
        )
        return poster_bytes

    try:
        poster = Image.open(io.BytesIO(poster_bytes)).convert("RGBA")
    except Exception as exc:
        logger.exception("Failed to open poster for layout overlay: {}", exc)
        return poster_bytes

    W, H = poster.width, poster.height

    for idx, el in enumerate(layout.elements):
        renderer = _RENDERERS.get(el.type)
        if renderer is None:
            logger.warning("Unknown layout element type: {}", el.type)
            continue
        try:
            renderer(poster, el, W, H)
        except Exception as exc:
            logger.exception(
                "Layout element {} ({}) failed: {}", idx, el.type, exc
            )

    out = io.BytesIO()
    poster.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def _build_fallback_layout(
    body_copy: list[str],
    heading: str = "",
    fallback_zone: SmallTextZone | None = None,
) -> LayoutSpec:
    """Build a minimal LayoutSpec used when the vision call fails or
    returns garbage. Mimics the old card-style overlay so the poster
    still gets *some* readable text rather than nothing."""
    z = fallback_zone or SmallTextZone()
    elements: list[LayoutElement] = []
    # Background panel
    elements.append(
        LayoutElement(
            type="rounded_rect",
            x=z.x_ratio,
            y=z.y_ratio,
            w=z.width_ratio,
            h=z.height_ratio,
            fill=z.bg_color,
            opacity=0.92,
            radius=24,
            shadow=False,
        )
    )
    pad = 0.025
    inner_x = z.x_ratio + pad
    inner_y = z.y_ratio + pad
    inner_w = max(0.05, z.width_ratio - 2 * pad)
    cy = inner_y
    if heading:
        elements.append(
            LayoutElement(
                type="text",
                x=inner_x,
                y=cy,
                max_w=inner_w,
                content=heading,
                font="NotoSansSC-Medium",
                size=0.034,  # ratio of H
                color=z.text_color,
                weight="bold",
            )
        )
        cy += 0.055
    if body_copy:
        elements.append(
            LayoutElement(
                type="bullet_list",
                x=inner_x,
                y=cy,
                max_w=inner_w,
                items=list(body_copy),
                bullet="·",
                font="NotoSansSC-Regular",
                size=0.024,
                color=z.text_color,
                line_spacing=1.45,
            )
        )
    return LayoutSpec(elements=elements, reasoning="fallback (vision unavailable)")


def analyze_layout_with_vision(
    poster_bytes: bytes,
    body_copy: list[str],
    heading: str = "",
    fallback_zone: SmallTextZone | None = None,
) -> LayoutSpec:
    """Ask a vision-capable LLM to design a full PIL overlay layout for
    this specific poster. Returns a LayoutSpec (list of drawing primitives).

    The AI sees the actual generated image and decides:
      - Where each text block goes (avoiding product/title)
      - What background panel (if any) to put behind the text
      - Which colors harmonize with the existing palette
      - Whether to add accent bars, dividers, or just float text

    Falls back to a simple card layout on any error so the pipeline never
    breaks because of layout AI failures.
    """
    fallback = _build_fallback_layout(body_copy, heading, fallback_zone)

    try:
        import json as _json

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return fallback

        model = _resolve_vision_model()
        bullet_lines = "\n".join(f"  - {item}" for item in body_copy)
        heading_line = heading.strip() if heading else "（无标题）"

        prompt = f"""你是一位顶级海报视觉设计师。
我已经生成了一张商业海报（附在请求里），需要你**直接为这张图设计**一份小字 PIL 叠加布局。

## 任务背景
- 主标题、副标题、产品图、品牌 Logo 已经画好，**不要动它们**。
- 我现在要在海报上叠加一段小字说明，由 Python PIL 精确绘制。
- 你的工作：看图，决定小字怎么排版才**和这张图的实际构图最契合**。

## 待叠加的内容
- 小字标题: {heading_line}
- 小字要点（{len(body_copy)} 条）:
{bullet_lines}

## 输出格式（严格 JSON，无 markdown 无解释）
返回一个 LayoutSpec 对象，elements 是一个有序的绘制元素列表。后画的元素覆盖先画的，所以背景面板要排在前面。

```json
{{
  "reasoning": "一句话说明你为什么这样设计",
  "elements": [
    {{
      "type": "rounded_rect | accent_bar | text | bullet_list | divider",
      "x": 0.0-1.0, "y": 0.0-1.0, "w": 0.0-1.0, "h": 0.0-1.0,
      "fill": "#RRGGBB", "opacity": 0.0-1.0,
      "radius": 0-40, "shadow": true/false,
      "content": "(text 类型)",
      "items": ["(bullet_list 类型)"],
      "bullet": "·",
      "max_w": 0.0-1.0,
      "font": "NotoSansSC-Medium 或 NotoSansSC-Regular",
      "size": "可以填像素整数 (12-80)，也可以填占海报高度的比例 (0.01-0.06)",
      "color": "#RRGGBB",
      "align": "left | center | right",
      "line_spacing": 1.2-1.8,
      "stroke_width": 1-4,
      "x2": 0.0-1.0, "y2": 0.0-1.0
    }}
  ]
}}
```

## 元素类型字段说明
- **rounded_rect**: 用 x/y/w/h/fill/opacity/radius/shadow。背景面板，比如半透明卡片。
- **accent_bar**: 用 x/y/w/h/fill/opacity。细装饰条，比如左边一道竖线，或标题下面一根横线。
- **text**: 用 x/y/max_w/content/font/size/color/align/line_spacing。单段文本。会按 max_w 自动换行。
- **bullet_list**: 用 x/y/max_w/items/bullet/font/size/color/line_spacing。多条要点列表。
- **divider**: 用 x/y/x2/y2/fill/opacity/stroke_width。两点之间的直线。

## 设计原则（按优先级，非常重要）
1. **不要遮挡产品**：先看产品在画面里的位置，避开它。
2. **靠近主标题或副标题，形成视觉一组**：小字不能孤立漂浮在远处。
3. **挑画面最干净的区域**：通常是背景留白处。如果留白本身已经很干净（颜色均匀），可以**直接漂字不加背景面板**；如果留白纹理复杂或对比度不足，就**加一层半透明 rounded_rect 作为底**。
4. **颜色取自画面本身**：背景色取自该区域的实际主色（略偏亮/偏暗以保证对比），文字色与背景对比强烈。
5. **创意自由**：你可以加 accent_bar（左侧竖线/底部横线）或 divider 来分割段落，让设计有层次感。
6. **风格呼应整体海报**：如果海报偏极简风，就少加修饰元素；如果海报偏华丽风，可以加渐变背景和装饰条。
7. **size 字段可以用像素或比例两种写法**。比例更方便（例如 size: 0.028 表示字号 = 海报高度的 2.8%）。正文小字一般 0.02-0.028，标题 0.03-0.04。
8. **保持小字块紧凑**：不要让 bullet_list 太散，line_spacing 通常 1.4-1.5。

## 设计示例

**示例 A — 极简浮字（用于干净背景）**
```json
{{
  "reasoning": "海报右下大块留白且色彩均匀，无需背景板，字直接浮在上面更简洁",
  "elements": [
    {{"type": "accent_bar", "x": 0.55, "y": 0.65, "w": 0.003, "h": 0.20, "fill": "#8B4513", "opacity": 1.0}},
    {{"type": "text", "x": 0.57, "y": 0.65, "max_w": 0.40, "content": "产品亮点", "font": "NotoSansSC-Medium", "size": 0.032, "color": "#3A2C1F"}},
    {{"type": "bullet_list", "x": 0.57, "y": 0.71, "max_w": 0.40, "items": ["..."], "font": "NotoSansSC-Regular", "size": 0.024, "color": "#3A2C1F"}}
  ]
}}
```

**示例 B — 半透明卡片（用于复杂背景）**
```json
{{
  "reasoning": "海报左下背景纹理复杂，需要半透明白卡保证可读性",
  "elements": [
    {{"type": "rounded_rect", "x": 0.05, "y": 0.62, "w": 0.45, "h": 0.32, "fill": "#FAFAF5", "opacity": 0.92, "radius": 20, "shadow": true}},
    {{"type": "text", "x": 0.075, "y": 0.645, "max_w": 0.40, "content": "核心成分", "font": "NotoSansSC-Medium", "size": 0.030, "color": "#2D3A2D"}},
    {{"type": "divider", "x": 0.075, "y": 0.69, "x2": 0.475, "y2": 0.69, "fill": "#2D3A2D", "opacity": 0.4, "stroke_width": 1}},
    {{"type": "bullet_list", "x": 0.075, "y": 0.71, "max_w": 0.40, "items": ["..."], "font": "NotoSansSC-Regular", "size": 0.024, "color": "#2D3A2D"}}
  ]
}}
```

**示例 C — 顶部横幅**
```json
{{
  "reasoning": "海报顶部有大块天空留白，把要点做成横幅式排版",
  "elements": [
    {{"type": "rounded_rect", "x": 0.08, "y": 0.06, "w": 0.84, "h": 0.10, "fill": "#1A2B3C", "opacity": 0.85, "radius": 8}},
    {{"type": "text", "x": 0.10, "y": 0.085, "max_w": 0.80, "content": "产品亮点 / 三大优势", "font": "NotoSansSC-Medium", "size": 0.028, "color": "#F5E6CA", "align": "center"}}
  ]
}}
```

现在请直接看图，输出 JSON。只返回 JSON。"""

        endpoint = _build_endpoint(model)
        img_b64 = base64.b64encode(poster_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                    ],
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT"],
                "temperature": 0.6,
            },
        }

        response = requests.post(
            endpoint,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )

        if response.status_code != 200:
            logger.warning(
                "Vision layout HTTP {}: {}",
                response.status_code,
                response.text[:200],
            )
            return fallback

        data = response.json()
        if "error" in data:
            logger.warning("Vision layout returned error: {}", data["error"])
            return fallback

        parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        text_content = ""
        for part in parts:
            if isinstance(part, dict) and "text" in part:
                text_content += part["text"]

        if not text_content.strip():
            logger.warning("Vision layout returned empty text")
            return fallback

        import re as _re
        cleaned = _re.sub(r"```(?:json)?\s*|\s*```", "", text_content).strip()
        if not cleaned.startswith("{"):
            match = _re.search(r"\{.*\}", cleaned, _re.DOTALL)
            if match:
                cleaned = match.group(0)

        raw = _json.loads(cleaned)

        try:
            spec = LayoutSpec.model_validate(raw)
        except Exception as exc:
            logger.warning("LayoutSpec validation failed: {} — using fallback", exc)
            return fallback

        if not spec.elements:
            logger.warning("Vision returned empty elements list — using fallback")
            return fallback

        logger.info(
            "Vision layout: {} elements, reasoning={}",
            len(spec.elements),
            (spec.reasoning or "")[:100],
        )
        return spec

    except Exception as exc:
        logger.exception("Vision layout analysis failed, using fallback: {}", exc)
        return fallback


def _build_endpoint(model: str) -> str:
    """Derive the native Gemini generateContent endpoint from any supported
    base URL shape (direct Google API, Google OpenAI-compat, or proxy).

    Accepts:
      https://generativelanguage.googleapis.com/v1beta/openai/
      https://generativelanguage.googleapis.com/v1beta
      https://api.buxianliang.fun/v1
      https://custom-proxy.example/v1beta
    Also accepts model IDs with or without the "models/" prefix.
    All normalize to: <host>/v1beta/models/<model>:generateContent
    """
    base = os.getenv(
        "GEMINI_API_BASE",
        "https://generativelanguage.googleapis.com/v1beta",
    ).rstrip("/")
    # Strip Google's OpenAI compat subpath — native generateContent lives at v1beta root
    if base.endswith("/openai"):
        base = base[: -len("/openai")]
    if base.endswith("/v1"):
        base = base[:-3] + "/v1beta"
    elif not base.endswith("/v1beta"):
        base = base + "/v1beta"

    # Strip "models/" prefix if present (Google's list API returns full paths)
    clean_model = model
    if clean_model.startswith("models/"):
        clean_model = clean_model[len("models/"):]

    # URL-encode the model name — CLIProxyAPI uses display names like
    # "Nano Banana Pro" with spaces, which must become "Nano%20Banana%20Pro"
    encoded_model = urllib.parse.quote(clean_model, safe="")

    return f"{base}/models/{encoded_model}:generateContent"


def _resolve_image_model() -> str:
    """Resolve the current image model from runtime settings → env → default.

    Strips any "models/" prefix that Google's list API returns, since our
    endpoint builder adds it itself.
    """
    try:
        from dashboard.services import runtime_settings
        model = runtime_settings.get_image_model()
    except Exception:
        model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")
    if model.startswith("models/"):
        model = model[len("models/"):]
    return model


def _resolve_vision_model() -> str:
    """Model used for analyzing already-generated images.

    This is NOT the image generation model — it needs vision understanding
    to pick a good zone for text overlay. We default to the strongest
    multimodal reasoning model available because getting the position right
    matters more than latency/cost here.
    """
    return os.getenv("GEMINI_VISION_MODEL", "Gemini 3 Pro Preview")


def _classify_error(status_code: int, body_text: str, body_data: dict | None) -> Exception:
    """Map an upstream error into a Python exception.

    Returns RateLimitError for 429 / RESOURCE_EXHAUSTED / model_cooldown,
    which tenacity is configured to skip retrying.
    """
    # Extract error details from body if JSON
    err_obj = {}
    if isinstance(body_data, dict):
        err_obj = body_data.get("error") or {}

    err_code = err_obj.get("code") if isinstance(err_obj, dict) else None
    err_status = (err_obj.get("status") or "") if isinstance(err_obj, dict) else ""
    err_msg = (err_obj.get("message") or "") if isinstance(err_obj, dict) else ""

    is_rate_limited = (
        status_code == 429
        or err_code == 429
        or err_status in {"RESOURCE_EXHAUSTED"}
        or err_code == "model_cooldown"
        or "cooling down" in body_text.lower()
        or "quota" in err_msg.lower()
        or "rate limit" in err_msg.lower()
        or "exhausted" in err_msg.lower()
    )

    summary = err_msg or body_text[:300]
    if is_rate_limited:
        return RateLimitError(
            f"图像模型限流/配额耗尽: {summary}。"
            f"请在 Prompt 设置页换一个图像模型再试，或等 1-2 分钟后重试。"
        )
    return RuntimeError(
        f"Gemini image generation failed (HTTP {status_code}): {summary}"
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    retry=retry_if_not_exception_type(RateLimitError),
    reraise=True,
)
def generate_poster_image(image_prompt: str, product_image_b64: str) -> bytes:
    """Generate a poster image using Gemini's native generateContent API.

    The OpenAI-compatible chat.completions endpoint silently returns content=null
    for image generation models on this proxy, so we use the native Gemini format
    which returns inline_data parts containing the image bytes.
    """
    model = _resolve_image_model()
    api_key = os.getenv("GEMINI_API_KEY", "")
    prompt = f"{image_prompt}\n\n{FUSION_RULES}"

    # Build parts: prompt text + product image (Image 1) + optional logo (Image 2)
    parts: list[dict] = [
        {"text": prompt},
        {
            "inline_data": {
                "mime_type": "image/png",
                "data": product_image_b64,
            }
        },
    ]

    logo_b64 = _load_logo_b64()
    if logo_b64:
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": logo_b64,
            }
        })

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
        },
    }

    # Google's native generateContent accepts api keys ONLY via x-goog-api-key.
    # Sending Authorization: Bearer with an API key causes a 401 because Google
    # interprets it as an OAuth access token. Proxies like buxianliang.fun also
    # happen to accept x-goog-api-key, so a single header works for both.
    response = requests.post(
        _build_endpoint(model),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=300,
    )

    # Parse body (may contain error even with HTTP 200)
    try:
        data = response.json()
    except ValueError:
        data = None

    # Non-2xx or body contains an error object → classify
    has_body_error = isinstance(data, dict) and "error" in data
    if response.status_code != 200 or has_body_error:
        raise _classify_error(response.status_code, response.text[:500], data)

    candidates = (data or {}).get("candidates") or []
    if not candidates:
        raise ValueError(f"No candidates in Gemini response: {str(data)[:300]}")

    response_parts = (candidates[0].get("content") or {}).get("parts") or []
    for part in response_parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline:
            b64_data = inline.get("data", "")
            if b64_data:
                return base64.b64decode(b64_data)

    raise ValueError(
        f"No image data found in Gemini response. Parts: {[list(p.keys()) for p in response_parts]}"
    )
