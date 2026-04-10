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


def _resolve_size_px(raw: float, H: int, min_px: int = 10) -> int:
    """Convert a `size` field (px int or 0..1 ratio of H) to pixels."""
    raw = float(raw or 22)
    if raw < 1.0:
        return max(min_px, int(round(raw * H)))
    return max(min_px, int(round(raw)))


def _fit_text_to_box(
    content: str,
    font_name: str,
    initial_px: int,
    max_w_px: int,
    max_h_px: int,
    line_spacing: float,
    min_px: int = 10,
) -> tuple[ImageFont.FreeTypeFont, list[str], int, int]:
    """Find the largest font size <= initial_px such that wrapped lines of
    `content` fit inside a (max_w_px, max_h_px) box.

    max_h_px == 0 disables vertical fitting (returns initial size).
    Returns: (font, wrapped_lines, line_height_px, chosen_size_px).
    """
    size = max(min_px, initial_px)
    while size >= min_px:
        font = _resolve_font(font_name, size)
        lines = _wrap_cjk(content, font, max_w_px)
        line_h = int(round(size * (line_spacing or 1.4)))
        if max_h_px == 0 or len(lines) * line_h <= max_h_px:
            return font, lines, line_h, size
        size -= 1
    # Couldn't fit even at minimum size — return min and let caller truncate
    font = _resolve_font(font_name, min_px)
    lines = _wrap_cjk(content, font, max_w_px)
    return font, lines, int(round(min_px * (line_spacing or 1.4))), min_px


def _measure_bullet_list_height(
    items: list[str],
    body_font: ImageFont.FreeTypeFont,
    bold_font: ImageFont.FreeTypeFont,
    bullet: str,
    wrap_w: int,
    line_h: int,
    item_gap: int,
) -> tuple[int, list[list[str]]]:
    """Measure total vertical space the bullet list will take. Returns
    (total_h, list_of_wrapped_items)."""
    wrapped_all: list[list[str]] = []
    total = 0
    for item in items:
        wrapped = _wrap_cjk(item, body_font, wrap_w)
        if not wrapped:
            wrapped_all.append([])
            continue
        wrapped_all.append(wrapped)
        total += len(wrapped) * line_h + item_gap
    if total > 0:
        total -= item_gap  # no gap after last item
    return total, wrapped_all


def _fit_bullet_list_to_box(
    items: list[str],
    font_name: str,
    bullet: str,
    initial_px: int,
    max_w_px: int,
    max_h_px: int,
    line_spacing: float,
    min_px: int = 10,
) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, int, int, list[list[str]], int]:
    """Find the largest font size such that the bullet list fits in
    (max_w_px, max_h_px). Returns (body_font, bold_font, line_h, text_x_offset,
    wrapped_items, chosen_size)."""
    size = max(min_px, initial_px)
    while size >= min_px:
        body_font = _resolve_font(font_name, size)
        bold_font = _resolve_font("NotoSansSC-Medium", size)
        line_h = int(round(size * (line_spacing or 1.4)))
        item_gap = int(round(size * 0.35))
        bullet_box = bold_font.getbbox(bullet + " ")
        bullet_w = bullet_box[2] - bullet_box[0]
        text_x_offset = bullet_w + max(4, int(round(size * 0.25)))
        wrap_w = max(20, max_w_px - text_x_offset)
        total_h, wrapped = _measure_bullet_list_height(
            items, body_font, bold_font, bullet, wrap_w, line_h, item_gap
        )
        if max_h_px == 0 or total_h <= max_h_px:
            return body_font, bold_font, line_h, text_x_offset, wrapped, size
        size -= 1
    # Couldn't fit — return min size, caller will truncate
    body_font = _resolve_font(font_name, min_px)
    bold_font = _resolve_font("NotoSansSC-Medium", min_px)
    line_h = int(round(min_px * (line_spacing or 1.4)))
    bullet_box = bold_font.getbbox(bullet + " ")
    bullet_w = bullet_box[2] - bullet_box[0]
    text_x_offset = bullet_w + max(4, int(round(min_px * 0.25)))
    wrap_w = max(20, max_w_px - text_x_offset)
    _, wrapped = _measure_bullet_list_height(
        items, body_font, bold_font, bullet, wrap_w, line_h, int(round(min_px * 0.35))
    )
    return body_font, bold_font, line_h, text_x_offset, wrapped, min_px


def _draw_text_block(canvas: Image.Image, el: LayoutElement, W: int, H: int) -> None:
    if not el.content:
        return
    x = int(_clamp(el.x) * W)
    y = int(_clamp(el.y) * H)
    max_w_px = max(20, int(_clamp(el.max_w, 0.05, 1.0) * W))
    max_h_px = int(_clamp(el.max_h, 0.0, 1.0) * H) if el.max_h > 0 else 0

    initial_px = _resolve_size_px(el.size, H)
    font, lines, line_h, _ = _fit_text_to_box(
        el.content, el.font, initial_px, max_w_px, max_h_px,
        float(el.line_spacing or 1.4),
    )

    rgb = _hex_to_rgb(el.color)
    alpha = _alpha(el.opacity)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cy = y
    bottom = (y + max_h_px) if max_h_px > 0 else H
    for line in lines:
        if cy + line_h > bottom:
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
    max_h_px = int(_clamp(el.max_h, 0.0, 1.0) * H) if el.max_h > 0 else 0

    initial_px = _resolve_size_px(el.size, H)
    bullet = el.bullet or "·"
    body_font, bold_font, line_h, text_x_offset, wrapped_items, chosen = _fit_bullet_list_to_box(
        list(el.items), el.font, bullet, initial_px, max_w_px, max_h_px,
        float(el.line_spacing or 1.4),
    )

    rgb = _hex_to_rgb(el.color)
    alpha = _alpha(el.opacity)
    item_gap = int(round(chosen * 0.35))
    bottom = (y + max_h_px) if max_h_px > 0 else H

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cy = y
    for wrapped in wrapped_items:
        if not wrapped:
            continue
        if cy + line_h > bottom:
            break
        # First line: bullet + first chunk
        draw.text((x, cy), bullet, font=bold_font, fill=(*rgb, alpha))
        draw.text((x + text_x_offset, cy), wrapped[0], font=body_font, fill=(*rgb, alpha))
        cy += line_h
        # Continuation lines (indented)
        overflow = False
        for cont in wrapped[1:]:
            if cy + line_h > bottom:
                overflow = True
                break
            draw.text((x + text_x_offset, cy), cont, font=body_font, fill=(*rgb, alpha))
            cy += line_h
        if overflow:
            break
        cy += item_gap
    canvas.alpha_composite(layer)


# ---------- card (compound element: panel + heading + bullets, auto-fit) ----------


def _draw_card(canvas: Image.Image, el: LayoutElement, W: int, H: int) -> None:
    """Draw a complete text card: rounded background + optional accent bar +
    optional heading + items list. The renderer measures the text and shrinks
    the font until everything fits inside (w, h), so the visible panel ALWAYS
    contains the text — no AI coordination required.
    """
    x = int(_clamp(el.x) * W)
    y = int(_clamp(el.y) * H)
    w = int(_clamp(el.w) * W)
    h = int(_clamp(el.h) * H)
    if w <= 0 or h <= 0:
        return

    bg_rgb = _hex_to_rgb(el.fill)
    bg_alpha = _alpha(el.opacity if el.opacity > 0 else 0.92)
    radius = max(0, int(el.radius))

    # ---- Step 1: shadow + background panel ----
    if el.shadow:
        from PIL import ImageFilter
        shadow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        offset = max(2, int(min(w, h) * 0.02))
        if radius > 0:
            sd.rounded_rectangle(
                [x + offset, y + offset, x + w + offset, y + h + offset],
                radius=radius,
                fill=(0, 0, 0, int(bg_alpha * 0.35)),
            )
        else:
            sd.rectangle(
                [x + offset, y + offset, x + w + offset, y + h + offset],
                fill=(0, 0, 0, int(bg_alpha * 0.35)),
            )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=offset))
        canvas.alpha_composite(shadow_layer)

    bg_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bg_layer)
    if radius > 0:
        bd.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=(*bg_rgb, bg_alpha))
    else:
        bd.rectangle([x, y, x + w, y + h], fill=(*bg_rgb, bg_alpha))
    canvas.alpha_composite(bg_layer)

    # ---- Step 2: optional accent bar (left side) ----
    accent_w = 0
    if el.accent_color:
        accent_w = max(3, int(round(w * 0.012)))
        accent_rgb = _hex_to_rgb(el.accent_color)
        ac_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ac_layer).rectangle(
            [x, y, x + accent_w, y + h],
            fill=(*accent_rgb, 255),
        )
        canvas.alpha_composite(ac_layer)

    # ---- Step 3: layout text inside the inner box ----
    pad = max(12, int(round(min(w, h) * float(el.padding or 0.08))))
    inner_x = x + pad + (accent_w + 6 if accent_w else 0)
    inner_y = y + pad
    inner_w = w - pad - (pad + (accent_w + 6 if accent_w else 0))
    inner_h = h - 2 * pad
    if inner_w <= 0 or inner_h <= 0:
        return

    text_rgb = _hex_to_rgb(el.color)
    text_alpha = 255  # text on top of panel — always opaque
    line_spacing = float(el.line_spacing or 1.4)

    has_heading = bool(el.heading and el.heading.strip())
    has_items = bool(el.items)

    # Reserve heading area first (target ~30% of inner_h if both present)
    heading_h_target = 0
    body_h_target = inner_h
    if has_heading and has_items:
        heading_h_target = int(inner_h * 0.30)
        body_h_target = inner_h - heading_h_target - max(6, int(inner_h * 0.04))
    elif has_heading:
        heading_h_target = inner_h
        body_h_target = 0

    # Fit heading
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cy = inner_y

    if has_heading:
        h_initial = _resolve_size_px(el.heading_size, H)
        h_font, h_lines, h_line_h, h_size = _fit_text_to_box(
            el.heading, "NotoSansSC-Medium", h_initial, inner_w, heading_h_target,
            line_spacing,
        )
        h_bottom = inner_y + heading_h_target
        for line in h_lines:
            if cy + h_line_h > h_bottom:
                break
            draw.text((inner_x, cy), line, font=h_font, fill=(*text_rgb, text_alpha))
            cy += h_line_h
        # Underline separator
        sep_y = cy + max(2, int(h_size * 0.15))
        draw.line(
            [(inner_x, sep_y), (inner_x + inner_w, sep_y)],
            fill=(*text_rgb, 110),
            width=max(1, int(h_size * 0.08)),
        )
        cy = sep_y + max(6, int(h_size * 0.30))
        # Recompute body box from current cy
        body_h_target = max(0, (y + h - pad) - cy)

    # Fit + draw bullet items
    if has_items and body_h_target > 0:
        b_initial = _resolve_size_px(el.body_size, H)
        bullet = el.bullet or "·"
        body_font, bold_font, b_line_h, text_x_offset, wrapped_items, b_size = _fit_bullet_list_to_box(
            list(el.items), "NotoSansSC-Regular", bullet, b_initial,
            inner_w, body_h_target, line_spacing,
        )
        item_gap = int(round(b_size * 0.35))
        bottom = inner_y + (heading_h_target + max(6, int(inner_h * 0.04)) if has_heading else 0) + body_h_target
        for wrapped in wrapped_items:
            if not wrapped:
                continue
            if cy + b_line_h > bottom:
                break
            draw.text((inner_x, cy), bullet, font=bold_font, fill=(*text_rgb, text_alpha))
            draw.text(
                (inner_x + text_x_offset, cy), wrapped[0],
                font=body_font, fill=(*text_rgb, text_alpha),
            )
            cy += b_line_h
            overflow = False
            for cont in wrapped[1:]:
                if cy + b_line_h > bottom:
                    overflow = True
                    break
                draw.text(
                    (inner_x + text_x_offset, cy), cont,
                    font=body_font, fill=(*text_rgb, text_alpha),
                )
                cy += b_line_h
            if overflow:
                break
            cy += item_gap
    elif has_items and body_h_target == 0:
        # Heading-only card got all the space; nothing more to draw
        pass
    elif not has_heading and not has_items and el.content:
        # Card used as a plain text panel
        c_initial = _resolve_size_px(el.body_size, H)
        c_font, c_lines, c_line_h, _ = _fit_text_to_box(
            el.content, el.font, c_initial, inner_w, inner_h, line_spacing,
        )
        for line in c_lines:
            if cy + c_line_h > inner_y + inner_h:
                break
            draw.text((inner_x, cy), line, font=c_font, fill=(*text_rgb, text_alpha))
            cy += c_line_h

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
    "card": _draw_card,
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
    returns garbage. Uses a single `card` element so the renderer
    auto-fits text to the panel — guaranteed visual coherence."""
    z = fallback_zone or SmallTextZone()
    return LayoutSpec(
        elements=[
            LayoutElement(
                type="card",
                x=z.x_ratio,
                y=z.y_ratio,
                w=z.width_ratio,
                h=z.height_ratio,
                fill=z.bg_color,
                opacity=0.92,
                radius=24,
                shadow=False,
                accent_color="",
                heading=heading or "",
                items=list(body_copy or []),
                color=z.text_color,
                heading_size=0.032,
                body_size=0.022,
                padding=0.08,
                line_spacing=1.45,
            )
        ],
        reasoning="fallback (vision unavailable)",
    )


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

## ⭐ 核心规则：用 "card" 元素，让渲染器对齐
**最重要的事**：你**首选** `card` 元素类型。`card` 是一个复合元素，包含 `背景面板 + 标题 + 列表`，**渲染器会自动处理对齐和字号缩放**，保证文字一定在面板内，不会溢出。

**❌ 不要做的事**：不要再用 `rounded_rect` + 单独的 `text` + `bullet_list` 三个元素手动拼装！那样需要你自己计算每个元素的 x/y/w/h 来对齐，**几乎一定会出错**（文字溢出面板、位置错位）。

**✅ 正确做法**：返回一个 `card` 元素，写好 x/y/w/h/fill/heading/items 就完事，对齐交给渲染器。

## 输出格式（严格 JSON，无 markdown 无解释）

```json
{{
  "reasoning": "一句话说明你为什么这样设计",
  "elements": [
    {{
      "type": "card",
      "x": 0.0-1.0, "y": 0.0-1.0,
      "w": 0.0-1.0, "h": 0.0-1.0,
      "fill": "#RRGGBB",
      "opacity": 0.0-1.0,
      "radius": 0-40,
      "shadow": true/false,
      "accent_color": "#RRGGBB 或留空",
      "heading": "可选标题文字",
      "items": ["要点1", "要点2", ...],
      "color": "#RRGGBB（文字颜色）",
      "heading_size": 0.025-0.040,
      "body_size": 0.018-0.028,
      "padding": 0.05-0.12,
      "line_spacing": 1.3-1.6
    }}
  ]
}}
```

## card 字段详解
- `x, y`: 卡片左上角位置（占海报宽/高的比例 0-1）
- `w, h`: 卡片宽和高（比例 0-1）。**这就是你要做的全部尺寸决策** —— 字号会自动缩放
- `fill`: 卡片背景色。透明白 `#FFFFFF` opacity 0.85；纯色卡 opacity 0.95
- `opacity`: 0.85-0.95 之间最常用。复杂背景上用 0.92+ 保可读性
- `radius`: 圆角，常用 12-24
- `shadow`: true 加柔和阴影（适合浮在产品上方）
- `accent_color`: 留空就是普通卡片；填颜色会在左侧加一道竖线（品牌色或对比色）
- `heading`: 可选小标题（2-4 字最佳，例如"产品亮点"、"核心成分"、"使用场景"）
- `items`: 要点数组，**直接复制我上面给你的内容**
- `color`: 文字颜色，要和 `fill` 形成强对比
- `heading_size` / `body_size`: 起始字号（占海报高度的比例）。**你不用算精确值** —— 渲染器会自动缩小字号让所有文字塞进卡片里
- `padding`: 内边距比例，0.06-0.10 最常用

## 设计原则（按优先级）
1. **不要遮挡产品和标题** —— 先看产品在画面里的位置，避开它
2. **靠近主标题或副标题，形成视觉一组** —— 卡片不能孤立漂浮在远处
3. **挑画面最干净的区域** —— 通常是背景留白处
4. **卡片尺寸建议**：宽 35%-50%、高 25%-40%。根据画面留白形状调整
5. **颜色取自画面本身**：fill 取背景区域的实际主色（略亮或略暗以保证对比），color 与 fill 强对比
6. **风格呼应整体海报**：极简风用浅色透明卡 + 无 accent_bar；复古/中式可加 accent_color；深色背景用深色卡 + 浅文字
7. **不确定就用单个 card** —— 不要返回多个元素叠加

## 设计示例（**全部用 card**）

**示例 A — 浅色透明卡（适合大多数情况）**
```json
{{
  "reasoning": "海报左下大块米色留白，用半透明白卡和棕色文字，简洁大方",
  "elements": [
    {{
      "type": "card",
      "x": 0.05, "y": 0.60, "w": 0.45, "h": 0.34,
      "fill": "#FAFAF5", "opacity": 0.92, "radius": 20, "shadow": true,
      "accent_color": "",
      "heading": "产品亮点",
      "items": ["天然艾草精萃，温和不刺激", "深层祛湿驱寒", "孕妇可用，宝宝可用"],
      "color": "#3A2C1F",
      "heading_size": 0.032, "body_size": 0.024, "padding": 0.08
    }}
  ]
}}
```

**示例 B — 深色背景上的浅卡 + 品牌色装饰条**
```json
{{
  "reasoning": "海报背景偏深棕，用米黄底卡 + 深棕文字 + 左侧砖红装饰条",
  "elements": [
    {{
      "type": "card",
      "x": 0.52, "y": 0.62, "w": 0.43, "h": 0.32,
      "fill": "#F5EDD8", "opacity": 0.95, "radius": 16, "shadow": true,
      "accent_color": "#8B3A1F",
      "heading": "核心成分",
      "items": ["..."],
      "color": "#3A2014",
      "heading_size": 0.034, "body_size": 0.024, "padding": 0.09
    }}
  ]
}}
```

**示例 C — 顶部横幅式 card**
```json
{{
  "reasoning": "海报顶部有大块天空留白，用横向窄高比 card 做成横幅",
  "elements": [
    {{
      "type": "card",
      "x": 0.08, "y": 0.06, "w": 0.84, "h": 0.16,
      "fill": "#1A2B3C", "opacity": 0.88, "radius": 12, "shadow": false,
      "accent_color": "#D4A95C",
      "heading": "三大功效",
      "items": ["..."],
      "color": "#F5E6CA",
      "heading_size": 0.028, "body_size": 0.020, "padding": 0.06
    }}
  ]
}}
```

## ⚠️ 关键约束（违反会被拒绝）
- **必须**返回 `card` 类型的元素（除非你有非常充分的理由用别的）
- **绝不要**返回多个独立的 `rounded_rect` + `text` + `bullet_list` 元素
- 卡片的 x+w 不能超过 1.0；y+h 不能超过 1.0
- items 直接复制我给你的列表，不要改写

现在请直接看图，输出一个 card 元素的 JSON。只返回 JSON。"""

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


def _image_size_config(model: str) -> dict:
    """Return optional imageConfig only for models that support imageSize."""
    model_lower = (model or "").lower()
    if not model_lower.startswith("gemini-3-pro-image"):
        return {}
    if "4k" in model_lower:
        return {"imageConfig": {"imageSize": "4K"}}
    return {"imageConfig": {"imageSize": "2K"}}


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
            **_image_size_config(model),
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
