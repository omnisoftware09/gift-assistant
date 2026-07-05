"""Render greeting cards as JPEG/GIF images for Slack download."""

from __future__ import annotations

import io
import random
import textwrap
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont, ImageOps

from src.agents.subagents.ecard_generator.visual_hints import COLOR_HINTS, wants_animation

CARD_WIDTH = 720
CARD_HEIGHT = 1080
PREVIEW_SCALE = 0.34

STYLE_THEMES = {
    "heartfelt": {
        "top": (255, 245, 248),
        "bottom": (255, 210, 220),
        "accent": (180, 80, 100),
        "text": (60, 30, 40),
        "ornament": "✦",
    },
    "funny": {
        "top": (255, 252, 220),
        "bottom": (255, 200, 160),
        "accent": (220, 100, 60),
        "text": (50, 40, 30),
        "ornament": "★",
    },
    "formal": {
        "top": (248, 246, 242),
        "bottom": (220, 225, 240),
        "accent": (70, 80, 120),
        "text": (30, 35, 50),
        "ornament": "❋",
    },
}


@dataclass
class RenderedCard:
    data: bytes
    filename: str
    title: str
    mime_type: str


def _find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient_background(
    width: int,
    height: int,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> Image.Image:
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        color = _lerp_color(top, bottom, y / max(height - 1, 1))
        draw.line([(0, y), (width, y)], fill=color)
    return img


def _prepare_photo_background(background: Image.Image, width: int, height: int) -> Image.Image:
    """Fit DALL-E art to card size and add a readable text panel."""
    fitted = ImageOps.fit(background.convert("RGB"), (width, height), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([(36, 130), (width - 36, height - 110)], fill=(255, 255, 255, 175))
    draw.rectangle([(0, 0), (width, height)], outline=(255, 255, 255, 40), width=0)
    for edge in range(80):
        alpha = int(edge * 1.2)
        draw.rectangle([(0, edge), (width, edge + 1)], fill=(255, 255, 255, min(alpha, 90)))
        draw.rectangle(
            [(0, height - edge - 1), (width, height - edge)],
            fill=(255, 255, 255, min(alpha, 90)),
        )
    return Image.alpha_composite(fitted.convert("RGBA"), overlay).convert("RGB")


def _apply_color_hint(theme: dict, hints: list[str]) -> dict:
    theme = dict(theme)
    for hint in hints:
        if hint in COLOR_HINTS:
            accent = COLOR_HINTS[hint]
            theme["bottom"] = accent
            theme["accent"] = _lerp_color(accent, (40, 40, 40), 0.45)
            break
    return theme


def _wrap_text(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width) or [""]


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    x: int,
    y: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    spacing: int = 8,
    align: str = "center",
    max_width: int,
    shadow: bool = False,
) -> int:
    line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1] + spacing
    shadow_fill = (30, 30, 30) if shadow else None
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        tx = x if align == "left" else x + (max_width - line_w) // 2
        if shadow and shadow_fill:
            draw.text((tx + 2, y + 2), line, font=font, fill=shadow_fill)
        draw.text((tx, y), line, font=font, fill=fill)
        y += line_height
    return y


def _draw_border(draw: ImageDraw.ImageDraw, width: int, height: int, accent: tuple[int, int, int]) -> None:
    inset = 28
    draw.rounded_rectangle(
        [(inset, inset), (width - inset, height - inset)],
        radius=24,
        outline=accent,
        width=4,
    )
    draw.rounded_rectangle(
        [(inset + 10, inset + 10), (width - inset - 10, height - inset - 10)],
        radius=18,
        outline=_lerp_color(accent, (255, 255, 255), 0.35),
        width=2,
    )


def _draw_corners(draw: ImageDraw.ImageDraw, width: int, height: int, accent: tuple[int, int, int], ornament: str, font: ImageFont.ImageFont) -> None:
    positions = [(48, 48), (width - 48, 48), (48, height - 48), (width - 48, height - 48)]
    for x, y in positions:
        draw.text((x - 8, y - 8), ornament, font=font, fill=accent)


def _draw_floral_accents(draw: ImageDraw.ImageDraw, width: int, height: int, accent: tuple[int, int, int]) -> None:
    random.seed(42)
    for _ in range(14):
        cx = random.randint(60, width - 60)
        cy = random.randint(80, height - 80)
        r = random.randint(6, 14)
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=accent, width=2)
        draw.line([(cx - r, cy), (cx + r, cy)], fill=accent, width=1)
        draw.line([(cx, cy - r), (cx, cy + r)], fill=accent, width=1)


def _draw_confetti(draw: ImageDraw.ImageDraw, width: int, height: int, frame: int, accent: tuple[int, int, int]) -> None:
    random.seed(7 + frame)
    colors = [accent, _lerp_color(accent, (255, 255, 255), 0.4), _lerp_color(accent, (255, 220, 100), 0.3)]
    for _ in range(18):
        x = random.randint(40, width - 40)
        y = random.randint(40, height - 40) + (frame * 6) % 40
        size = random.randint(4, 10)
        color = random.choice(colors)
        if random.random() > 0.5:
            draw.rectangle([(x, y), (x + size, y + size)], fill=color)
        else:
            draw.ellipse([(x, y), (x + size, y + size)], fill=color)


def _draw_sparkles(draw: ImageDraw.ImageDraw, width: int, height: int, frame: int, accent: tuple[int, int, int]) -> None:
    random.seed(19 + frame)
    for _ in range(12):
        x = random.randint(50, width - 50)
        y = random.randint(50, height - 50)
        s = random.randint(3, 7)
        twinkle = (frame + _) % 3 == 0
        color = accent if twinkle else _lerp_color(accent, (255, 255, 255), 0.5)
        draw.line([(x - s, y), (x + s, y)], fill=color, width=2)
        draw.line([(x, y - s), (x, y + s)], fill=color, width=2)


def render_card_image(
    card: dict,
    *,
    recipient: str,
    occasion: str | None = None,
    visual_hints: list[str] | None = None,
    frame: int = 0,
    animate: bool = False,
    background: Image.Image | None = None,
) -> Image.Image:
    style = card.get("style", "heartfelt")
    theme = _apply_color_hint(STYLE_THEMES.get(style, STYLE_THEMES["heartfelt"]), visual_hints or [])
    width, height = CARD_WIDTH, CARD_HEIGHT
    on_photo = background is not None

    if on_photo:
        img = _prepare_photo_background(background, width, height)
    else:
        img = _gradient_background(width, height, theme["top"], theme["bottom"])
    draw = ImageDraw.Draw(img)

    accent_font = _find_font(28)
    headline_font = _find_font(52, bold=True)
    body_font = _find_font(30)
    small_font = _find_font(24)
    sign_font = _find_font(28, bold=True)

    _draw_border(draw, width, height, theme["accent"])
    _draw_corners(draw, width, height, theme["accent"], theme["ornament"], accent_font)

    if "floral" in (visual_hints or []):
        _draw_floral_accents(draw, width, height, theme["accent"])
    elif style == "funny" and animate:
        _draw_confetti(draw, width, height, frame, theme["accent"])
    elif style == "heartfelt" and animate:
        _draw_sparkles(draw, width, height, frame, theme["accent"])

    if "minimal" not in (visual_hints or []):
        band_y = 70
        occasion_label = (occasion or "With Love").title()
        draw.rounded_rectangle(
            [(width // 2 - 180, band_y), (width // 2 + 180, band_y + 44)],
            radius=20,
            fill=_lerp_color(theme["accent"], (255, 255, 255), 0.15),
        )
        _draw_text_block(
            draw,
            [occasion_label],
            x=width // 2 - 160,
            y=band_y + 8,
            font=small_font,
            fill=theme["text"],
            max_width=320,
        )

    y = 170
    headline_lines = _wrap_text(card.get("headline", ""), 16)
    y = _draw_text_block(
        draw,
        headline_lines,
        x=60,
        y=y,
        font=headline_font,
        fill=theme["accent"],
        spacing=10,
        max_width=width - 120,
        shadow=on_photo,
    )

    y += 20
    draw.line([(120, y), (width - 120, y)], fill=_lerp_color(theme["accent"], (255, 255, 255), 0.4), width=2)
    y += 30

    message_lines = _wrap_text(card.get("message", ""), 28)
    y = _draw_text_block(
        draw,
        message_lines,
        x=80,
        y=y,
        font=body_font,
        fill=theme["text"],
        spacing=12,
        max_width=width - 160,
        shadow=on_photo,
    )

    sign_off = card.get("sign_off", "Best wishes,")
    sign_y = height - 160
    _draw_text_block(
        draw,
        [sign_off],
        x=80,
        y=sign_y,
        font=sign_font,
        fill=theme["accent"],
        align="left",
        max_width=width - 160,
        shadow=on_photo,
    )

    footer = f"For {recipient}"
    _draw_text_block(
        draw,
        [footer],
        x=80,
        y=height - 100,
        font=small_font,
        fill=_lerp_color(theme["text"], (255, 255, 255), 0.25),
        align="center",
        max_width=width - 160,
    )

    return img


def _resolve_background(
    card: dict,
    backgrounds: dict[str, Image.Image] | None,
) -> Image.Image | None:
    if not backgrounds:
        return None
    style = card.get("style", "heartfelt")
    return backgrounds.get(style)


def render_card_jpeg(
    card: dict,
    *,
    recipient: str,
    occasion: str | None = None,
    visual_hints: list[str] | None = None,
    backgrounds: dict[str, Image.Image] | None = None,
) -> bytes:
    img = render_card_image(
        card,
        recipient=recipient,
        occasion=occasion,
        visual_hints=visual_hints,
        animate=False,
        background=_resolve_background(card, backgrounds),
    )
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


def render_card_gif(
    card: dict,
    *,
    recipient: str,
    occasion: str | None = None,
    visual_hints: list[str] | None = None,
    backgrounds: dict[str, Image.Image] | None = None,
    frames: int = 10,
) -> bytes:
    bg = _resolve_background(card, backgrounds)
    images = [
        render_card_image(
            card,
            recipient=recipient,
            occasion=occasion,
            visual_hints=visual_hints,
            frame=i,
            animate=True,
            background=bg,
        )
        for i in range(frames)
    ]
    buf = io.BytesIO()
    images[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=180,
        loop=0,
        optimize=True,
    )
    return buf.getvalue()


def render_preview_sheet(
    variants: list[dict],
    *,
    recipient: str,
    occasion: str | None = None,
    visual_hints: list[str] | None = None,
    backgrounds: dict[str, Image.Image] | None = None,
) -> bytes:
    """Single image showing all 3 card options side-by-side."""
    thumb_w = int(CARD_WIDTH * PREVIEW_SCALE)
    thumb_h = int(CARD_HEIGHT * PREVIEW_SCALE)
    gap = 24
    label_h = 36
    sheet_w = thumb_w * len(variants) + gap * (len(variants) + 1)
    sheet_h = thumb_h + label_h + gap * 2

    sheet = Image.new("RGB", (sheet_w, sheet_h), (245, 245, 248))
    draw = ImageDraw.Draw(sheet)
    label_font = _find_font(22, bold=True)

    for i, card in enumerate(variants):
        card_img = render_card_image(
            card,
            recipient=recipient,
            occasion=occasion,
            visual_hints=visual_hints,
            background=_resolve_background(card, backgrounds),
        ).resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x = gap + i * (thumb_w + gap)
        y = gap + label_h
        sheet.paste(card_img, (x, y))
        draw.rounded_rectangle(
            [(x - 2, y - 2), (x + thumb_w + 2, y + thumb_h + 2)],
            radius=8,
            outline=(120, 120, 140),
            width=2,
        )
        style = card.get("style", "option").title()
        label = f"{i + 1}. {style}"
        bbox = draw.textbbox((0, 0), label, font=label_font)
        lw = bbox[2] - bbox[0]
        draw.text((x + (thumb_w - lw) // 2, 8), label, font=label_font, fill=(50, 50, 70))

    buf = io.BytesIO()
    sheet.save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue()


def render_final_card(
    card: dict,
    *,
    recipient: str,
    occasion: str | None,
    visual_hints: list[str] | None,
    backgrounds: dict[str, Image.Image] | None = None,
) -> RenderedCard:
    style = card.get("style", "heartfelt")
    safe_name = recipient.replace(" ", "_").lower()
    if wants_animation(visual_hints or [], style):
        data = render_card_gif(
            card,
            recipient=recipient,
            occasion=occasion,
            visual_hints=visual_hints,
            backgrounds=backgrounds,
        )
        return RenderedCard(
            data=data,
            filename=f"ecard_{safe_name}_{style}.gif",
            title=f"eCard for {recipient} ({style.title()})",
            mime_type="image/gif",
        )

    data = render_card_jpeg(
        card,
        recipient=recipient,
        occasion=occasion,
        visual_hints=visual_hints,
        backgrounds=backgrounds,
    )
    return RenderedCard(
        data=data,
        filename=f"ecard_{safe_name}_{style}.jpg",
        title=f"eCard for {recipient} ({style.title()})",
        mime_type="image/jpeg",
    )


def render_individual_previews(
    variants: list[dict],
    *,
    recipient: str,
    occasion: str | None = None,
    visual_hints: list[str] | None = None,
) -> list[RenderedCard]:
    """Full-size preview cards for each option (downloadable during refinement)."""
    rendered = []
    safe_name = recipient.replace(" ", "_").lower()
    for i, card in enumerate(variants, start=1):
        style = card.get("style", "heartfelt")
        data = render_card_jpeg(
            card,
            recipient=recipient,
            occasion=occasion,
            visual_hints=visual_hints,
        )
        rendered.append(
            RenderedCard(
                data=data,
                filename=f"ecard_preview_{safe_name}_{i}_{style}.jpg",
                title=f"Option {i} — {style.title()}",
                mime_type="image/jpeg",
            )
        )
    return rendered
