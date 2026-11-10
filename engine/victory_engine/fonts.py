"""Cross-platform font resolution.

Replaces `agent/pipeline.py::font_candidates()`, which looked in `%WINDIR%/Fonts` first (a
Windows-only path) and only fell back to Linux paths as an afterthought. Here the bundled
Liberation Sans files (see brand.py) are the primary source, so rendering is deployment-
independent by default; a brand template can still point at an uploaded custom font file, and a
platform system-font fallback chain is kept for local Windows/macOS development convenience.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Tuple

from PIL import ImageFont

from .brand import BUNDLED_FONTS_DIR

_FONT_CACHE: Dict[Tuple[str, int], "ImageFont.FreeTypeFont | ImageFont.ImageFont"] = {}

_PLATFORM_FALLBACKS = {
    "bundled:LiberationSans-Regular.ttf": [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "calibri.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ],
    "bundled:LiberationSans-Bold.ttf": [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arialbd.ttf",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "calibrib.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ],
    "bundled:LiberationSans-Italic.ttf": [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
    ],
    "bundled:LiberationSans-BoldItalic.ttf": [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"),
    ],
}


def resolve_font_path(font_ref: str) -> Path:
    """Resolve a brand font reference to a real file on disk.

    `font_ref` is either "bundled:<filename>" (ships with this package), an absolute path
    to a brand-uploaded font file, or a bare filename that is checked in the bundled fonts
    directory as a convenience.
    """
    if font_ref.startswith("bundled:"):
        candidate = BUNDLED_FONTS_DIR / font_ref.split(":", 1)[1]
        if candidate.exists():
            return candidate
    else:
        candidate = Path(font_ref).expanduser()
        if candidate.exists():
            return candidate
        as_bundled = BUNDLED_FONTS_DIR / font_ref
        if as_bundled.exists():
            return as_bundled

    for fallback in _PLATFORM_FALLBACKS.get(font_ref, []):
        if fallback.exists():
            return fallback

    # Last resort: the always-bundled regular weight, so rendering never hard-fails.
    return BUNDLED_FONTS_DIR / "LiberationSans-Regular.ttf"


def get_font(font_ref: str, size: int) -> "ImageFont.FreeTypeFont | ImageFont.ImageFont":
    key = (font_ref, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    path = resolve_font_path(font_ref)
    try:
        loaded = ImageFont.truetype(str(path), size)
    except Exception:
        loaded = ImageFont.load_default()
    _FONT_CACHE[key] = loaded
    return loaded
