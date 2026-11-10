"""Slide rendering — reproduces the legacy visual design exactly (see VIDEO_ENGINE.md §5).

Seven slide "kinds" from the reference package: cover, statement, map, comparison, flow, quote,
close. Each is a pure function `(draw_context, spec) -> None` that paints onto a fresh canvas at
`brand.width x brand.height`. `make_slide_specs()` reproduces the legacy content-selection
heuristic (how many slides a lesson gets and which kind each one is) from the lesson's parsed
script, video description and knowledge checks.

New, additive-only features not in the legacy engine: an optional brand logo overlay (top-right)
and a global `text_scale` multiplier. Both default to no-ops that reproduce the legacy pixel
output byte-for-byte when the brand is DEFAULT_BRAND.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from PIL import Image, ImageDraw

from .brand import BrandTheme, DEFAULT_BRAND
from .fonts import get_font
from .parser import ParsedLesson
from .text_utils import extract_keywords, short_sentence

MARGIN = 120


@dataclass
class SlideSpec:
    kind: str
    heading: str = ""
    subheading: str = ""
    body: str = ""
    bullets: List[str] = field(default_factory=list)
    left_label: str = ""
    right_label: str = ""
    left_points: List[str] = field(default_factory=list)
    right_points: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    quote: str = ""
    attribution: str = ""


def _scaled(brand: BrandTheme, size: int) -> int:
    return max(10, round(size * brand.text_scale))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
    if not text:
        return []
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, box, radius: int, fill=None, outline=None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _draw_logo(img: Image.Image, brand: BrandTheme) -> None:
    if not brand.logo_path:
        return
    path = Path(brand.logo_path)
    if not path.exists():
        return
    try:
        logo = Image.open(path).convert("RGBA")
    except Exception:
        return
    max_h = 90
    ratio = max_h / logo.height
    logo = logo.resize((max(1, round(logo.width * ratio)), max_h))
    x = img.width - MARGIN - logo.width
    y = MARGIN // 2
    img.paste(logo, (x, y), logo)


def _base_canvas(brand: BrandTheme, top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (brand.width, brand.height), top)
    draw = ImageDraw.Draw(img)
    steps = brand.height
    for i in range(steps):
        t = i / steps
        r = round(top[0] + (bottom[0] - top[0]) * t)
        g = round(top[1] + (bottom[1] - top[1]) * t)
        b = round(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, i), (brand.width, i)], fill=(r, g, b))
    return img


def render_cover_slide(brand: BrandTheme, lesson_title: str, module_title: str) -> Image.Image:
    img = _base_canvas(brand, brand.maroon_black, brand.maroon_deep)
    draw = ImageDraw.Draw(img)

    kicker_font = get_font(brand.body_font, _scaled(brand, 30))
    heading_font = get_font(brand.heading_font, _scaled(brand, 86))
    sub_font = get_font(brand.body_font, _scaled(brand, 34))
    bullet_font = get_font(brand.body_font, _scaled(brand, 28))

    draw.text((MARGIN, 150), brand.cover_kicker, font=kicker_font, fill=brand.gold)
    draw.line([(MARGIN, 200), (MARGIN + 140, 200)], fill=brand.gold, width=4)

    title_lines = _wrap(draw, lesson_title, heading_font, brand.width - 2 * MARGIN)
    y = 280
    for line in title_lines[:3]:
        draw.text((MARGIN, y), line, font=heading_font, fill=brand.off_white)
        y += 100

    draw.text((MARGIN, y + 20), module_title, font=sub_font, fill=brand.warm_gray)

    card_y = brand.height - 220
    card_w = (brand.width - 2 * MARGIN - 2 * 30) // 3
    for i, bullet in enumerate(brand.cover_bullets):
        x = MARGIN + i * (card_w + 30)
        _draw_rounded_rect(draw, [x, card_y, x + card_w, card_y + 120], radius=14,
                            fill=(brand.maroon[0], brand.maroon[1], brand.maroon[2]))
        lines = _wrap(draw, bullet, bullet_font, card_w - 40)
        ty = card_y + 35
        for line in lines[:2]:
            draw.text((x + 20, ty), line, font=bullet_font, fill=brand.off_white)
            ty += 36

    _draw_logo(img, brand)
    return img


def render_statement_slide(brand: BrandTheme, spec: SlideSpec) -> Image.Image:
    img = _base_canvas(brand, brand.maroon_deep, brand.ink)
    draw = ImageDraw.Draw(img)
    heading_font = get_font(brand.heading_font, _scaled(brand, 58))
    body_font = get_font(brand.body_font, _scaled(brand, 32))

    draw.text((MARGIN, 140), spec.heading, font=heading_font, fill=brand.gold)
    y = 260
    for bullet in spec.bullets[:5]:
        lines = _wrap(draw, bullet, body_font, brand.width - 2 * MARGIN - 50)
        draw.ellipse([MARGIN, y + 12, MARGIN + 14, y + 26], fill=brand.gold)
        for j, line in enumerate(lines):
            draw.text((MARGIN + 40, y + j * 42), line, font=body_font, fill=brand.off_white)
        y += max(42, 42 * len(lines)) + 24

    _draw_logo(img, brand)
    return img


def render_map_slide(brand: BrandTheme, spec: SlideSpec) -> Image.Image:
    img = _base_canvas(brand, brand.parchment, brand.cream)
    draw = ImageDraw.Draw(img)
    heading_font = get_font(brand.heading_font, _scaled(brand, 54))
    body_font = get_font(brand.body_font, _scaled(brand, 28))

    draw.text((MARGIN, 120), spec.heading, font=heading_font, fill=brand.maroon)

    n = max(1, len(spec.bullets))
    card_w = (brand.width - 2 * MARGIN - (n - 1) * 30) // n
    y = 280
    for i, bullet in enumerate(spec.bullets[:5]):
        x = MARGIN + i * (card_w + 30)
        _draw_rounded_rect(draw, [x, y, x + card_w, y + 420], radius=18,
                            fill=brand.off_white, outline=brand.border, width=2)
        draw.text((x + 24, y + 24), str(i + 1), font=get_font(brand.heading_font, _scaled(brand, 44)), fill=brand.gold_dark)
        lines = _wrap(draw, bullet, body_font, card_w - 48)
        ty = y + 100
        for line in lines[:6]:
            draw.text((x + 24, ty), line, font=body_font, fill=brand.charcoal)
            ty += 36

    _draw_logo(img, brand)
    return img


def render_comparison_slide(brand: BrandTheme, spec: SlideSpec) -> Image.Image:
    img = _base_canvas(brand, brand.cream, brand.parchment)
    draw = ImageDraw.Draw(img)
    heading_font = get_font(brand.heading_font, _scaled(brand, 54))
    label_font = get_font(brand.heading_font, _scaled(brand, 34))
    body_font = get_font(brand.body_font, _scaled(brand, 28))

    draw.text((MARGIN, 110), spec.heading, font=heading_font, fill=brand.maroon)

    col_w = (brand.width - 2 * MARGIN - 40) // 2
    top = 240
    left_box = [MARGIN, top, MARGIN + col_w, brand.height - 120]
    right_box = [MARGIN + col_w + 40, top, brand.width - MARGIN, brand.height - 120]
    _draw_rounded_rect(draw, left_box, radius=18, fill=brand.off_white, outline=brand.border, width=2)
    _draw_rounded_rect(draw, right_box, radius=18, fill=brand.off_white, outline=brand.border, width=2)

    draw.text((left_box[0] + 30, top + 24), spec.left_label, font=label_font, fill=brand.maroon)
    draw.text((right_box[0] + 30, top + 24), spec.right_label, font=label_font, fill=brand.gold_dark)

    for col_box, points in ((left_box, spec.left_points), (right_box, spec.right_points)):
        y = top + 100
        for point in points[:5]:
            lines = _wrap(draw, point, body_font, (col_box[2] - col_box[0]) - 60)
            for line in lines[:3]:
                draw.text((col_box[0] + 30, y), line, font=body_font, fill=brand.charcoal)
                y += 36
            y += 14

    _draw_logo(img, brand)
    return img


def render_flow_slide(brand: BrandTheme, spec: SlideSpec) -> Image.Image:
    img = _base_canvas(brand, brand.maroon_black, brand.maroon)
    draw = ImageDraw.Draw(img)
    heading_font = get_font(brand.heading_font, _scaled(brand, 54))
    body_font = get_font(brand.body_font, _scaled(brand, 26))

    draw.text((MARGIN, 110), spec.heading, font=heading_font, fill=brand.gold)

    steps = spec.steps[:6] or ["Step"]
    n = len(steps)
    box_w = (brand.width - 2 * MARGIN - (n - 1) * 60) // n
    y = 320
    for i, step in enumerate(steps):
        x = MARGIN + i * (box_w + 60)
        _draw_rounded_rect(draw, [x, y, x + box_w, y + 220], radius=16, fill=brand.off_white)
        lines = _wrap(draw, step, body_font, box_w - 32)
        ty = y + 24
        for line in lines[:5]:
            draw.text((x + 16, ty), line, font=body_font, fill=brand.ink)
            ty += 32
        if i < n - 1:
            arrow_y = y + 110
            ax = x + box_w + 10
            draw.line([(ax, arrow_y), (ax + 40, arrow_y)], fill=brand.gold, width=4)
            draw.polygon([(ax + 40, arrow_y - 10), (ax + 40, arrow_y + 10), (ax + 56, arrow_y)], fill=brand.gold)

    _draw_logo(img, brand)
    return img


def render_quote_slide(brand: BrandTheme, spec: SlideSpec) -> Image.Image:
    img = _base_canvas(brand, brand.ink, brand.maroon_black)
    draw = ImageDraw.Draw(img)
    quote_font = get_font(brand.heading_font_italic, _scaled(brand, 48))
    attr_font = get_font(brand.body_font, _scaled(brand, 28))

    draw.text((MARGIN, 160), "“", font=get_font(brand.heading_font, _scaled(brand, 140)), fill=brand.gold)
    lines = _wrap(draw, spec.quote, quote_font, brand.width - 2 * MARGIN - 80)
    y = 330
    for line in lines[:6]:
        draw.text((MARGIN + 60, y), line, font=quote_font, fill=brand.off_white)
        y += 64

    if spec.attribution:
        draw.line([(MARGIN + 60, y + 20), (MARGIN + 160, y + 20)], fill=brand.gold, width=3)
        draw.text((MARGIN + 60, y + 40), spec.attribution, font=attr_font, fill=brand.warm_gray)

    _draw_logo(img, brand)
    return img


def render_close_slide(brand: BrandTheme, spec: SlideSpec) -> Image.Image:
    img = _base_canvas(brand, brand.maroon_deep, brand.maroon_black)
    draw = ImageDraw.Draw(img)
    heading_font = get_font(brand.heading_font, _scaled(brand, 64))
    body_font = get_font(brand.body_font, _scaled(brand, 30))

    heading_lines = _wrap(draw, spec.heading or "Key Takeaways", heading_font, brand.width - 2 * MARGIN)
    y = 180
    for line in heading_lines[:2]:
        draw.text((MARGIN, y), line, font=heading_font, fill=brand.gold)
        y += 76

    y += 20
    for bullet in spec.bullets[:5]:
        lines = _wrap(draw, bullet, body_font, brand.width - 2 * MARGIN - 50)
        draw.ellipse([MARGIN, y + 12, MARGIN + 14, y + 26], fill=brand.off_white)
        for j, line in enumerate(lines):
            draw.text((MARGIN + 40, y + j * 40), line, font=body_font, fill=brand.off_white)
        y += max(40, 40 * len(lines)) + 22

    _draw_logo(img, brand)
    return img


_RENDERERS = {
    "statement": render_statement_slide,
    "map": render_map_slide,
    "comparison": render_comparison_slide,
    "flow": render_flow_slide,
    "quote": render_quote_slide,
    "close": render_close_slide,
}


def render_slide(brand: BrandTheme, spec: SlideSpec, module_title: str = "") -> Image.Image:
    if spec.kind == "cover":
        return render_cover_slide(brand, spec.heading, module_title)
    renderer = _RENDERERS.get(spec.kind)
    if renderer is None:
        raise ValueError(f"Unknown slide kind: {spec.kind}")
    return renderer(brand, spec)


def make_slide_specs(lesson: ParsedLesson) -> List[SlideSpec]:
    """Reproduces the legacy content-selection heuristic: a cover slide, then one statement
    slide per narration paragraph (up to a reasonable cap), a map slide of extracted keywords if
    there are enough paragraphs to warrant one, a knowledge-check quote slide if present, and a
    close slide summarizing the lesson."""
    paragraphs = [p for p in lesson.script_lines if p.strip()] or (
        [lesson.video_description] if lesson.video_description else ["This lesson has no narration yet."]
    )

    specs: List[SlideSpec] = [SlideSpec(kind="cover", heading=lesson.title)]

    for paragraph in paragraphs[:6]:
        specs.append(SlideSpec(
            kind="statement",
            heading=short_sentence(paragraph, max_chars=70),
            bullets=[s.strip() for s in paragraph.split(". ") if s.strip()][:4],
        ))

    if len(paragraphs) >= 3:
        keywords = extract_keywords(lesson.script_text or lesson.video_description, limit=4)
        specs.append(SlideSpec(kind="map", heading="Key Concepts", bullets=keywords))

    if lesson.knowledge_checks:
        specs.append(SlideSpec(
            kind="quote",
            quote=lesson.knowledge_checks[0],
            attribution="Knowledge Check",
        ))

    closing_bullets = [short_sentence(p, max_chars=80) for p in paragraphs[-3:]]
    specs.append(SlideSpec(kind="close", heading="Key Takeaways", bullets=closing_bullets))

    return specs


def render_lesson_slides(lesson: ParsedLesson, brand: Optional[BrandTheme], module_title: str, output_dir: Path) -> List[Path]:
    brand = brand or DEFAULT_BRAND
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = make_slide_specs(lesson)
    paths: List[Path] = []
    for i, spec in enumerate(specs):
        img = render_slide(brand, spec, module_title=module_title)
        path = output_dir / f"slide_{i:03d}.png"
        img.save(path, "PNG")
        paths.append(path)
    return paths
