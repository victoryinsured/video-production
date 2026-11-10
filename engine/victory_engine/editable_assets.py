"""Editable PPTX export (see VIDEO_ENGINE.md §10).

Produces an editable PowerPoint deck mirroring each rendered slide's text content (not a
re-import of the PNGs) so an instructor can tweak wording in PowerPoint without touching the
render pipeline. Background colors approximate each slide kind's palette; exact pixel-for-pixel
fidelity is intentionally not a goal here — the rendered video is the canonical visual output,
this file is a convenience editable artifact (same relationship as in the legacy package).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from .brand import BrandTheme, DEFAULT_BRAND
from .render import SlideSpec

_KIND_BG = {
    "cover": "maroon_black",
    "statement": "maroon_deep",
    "map": "parchment",
    "comparison": "cream",
    "flow": "maroon_black",
    "quote": "ink",
    "close": "maroon_deep",
}
_KIND_FG = {
    "cover": "off_white",
    "statement": "off_white",
    "map": "charcoal",
    "comparison": "charcoal",
    "flow": "off_white",
    "quote": "off_white",
    "close": "off_white",
}


def _rgb(brand: BrandTheme, name: str) -> RGBColor:
    return RGBColor(*getattr(brand, name))


def build_editable_deck(lesson_title: str, specs: List[SlideSpec], brand: BrandTheme, output_path: Path) -> Path:
    brand = brand or DEFAULT_BRAND
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    for spec in specs:
        slide = prs.slides.add_slide(blank_layout)
        bg = slide.background
        bg.fill.solid()
        bg.fill.fore_color.rgb = _rgb(brand, _KIND_BG.get(spec.kind, "maroon_deep"))
        fg = _rgb(brand, _KIND_FG.get(spec.kind, "off_white"))

        title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.5), Inches(12), Inches(1.2))
        title_tf = title_box.text_frame
        title_tf.word_wrap = True
        title_run = title_tf.paragraphs[0].add_run()
        title_run.text = spec.heading or lesson_title
        title_run.font.size = Pt(32)
        title_run.font.bold = True
        title_run.font.color.rgb = fg

        body_lines: List[str] = []
        body_lines += spec.bullets
        body_lines += [f"{spec.left_label}: " + "; ".join(spec.left_points)] if spec.left_points else []
        body_lines += [f"{spec.right_label}: " + "; ".join(spec.right_points)] if spec.right_points else []
        body_lines += spec.steps
        if spec.quote:
            body_lines.append(f"“{spec.quote}”")
        if spec.attribution:
            body_lines.append(f"— {spec.attribution}")
        if spec.body:
            body_lines.append(spec.body)

        if body_lines:
            body_box = slide.shapes.add_textbox(Inches(0.6), Inches(1.9), Inches(12), Inches(5))
            body_tf = body_box.text_frame
            body_tf.word_wrap = True
            for i, line in enumerate(body_lines):
                p = body_tf.paragraphs[0] if i == 0 else body_tf.add_paragraph()
                run = p.add_run()
                run.text = line
                run.font.size = Pt(20)
                run.font.color.rgb = fg

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return output_path
