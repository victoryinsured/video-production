"""Brand/theme configuration for the Victory rendering engine.

Every value in this module was a hardcoded module-level constant in the original
`agent/pipeline.py` (see VIDEO_ENGINE.md §5). They are reproduced here byte-for-byte as
``DEFAULT_BRAND`` so the out-of-the-box look is identical to the reference package. The web
app's Brand Editor persists a ``BrandTemplate`` row per course/template and passes it in as a
plain dict; :func:`brand_from_dict` deep-merges that onto ``DEFAULT_BRAND`` so a course that
only overrides its accent color still gets every other default untouched.

Fonts: the original engine looked in ``%WINDIR%/Fonts`` first, which only exists on Windows,
then fell back to whatever Linux font happened to be installed on the machine running it. That
made the *default* rendered look dependent on the deployment environment. This module instead
bundles Liberation Sans (SIL Open Font License 1.1 — see ``assets/fonts/LICENSE.txt``; metric-
compatible with Arial, the original engine's first-choice font) directly in the package, so the
reference look renders identically on any server, with no system font dependency. A brand
template may still point at custom uploaded font files, which take priority.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

RGB = Tuple[int, int, int]

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
BUNDLED_FONTS_DIR = ASSETS_DIR / "fonts"

# --- Exact reference palette, transplanted from agent/pipeline.py -----------------------
INK: RGB = (33, 24, 24)
MAROON_BLACK: RGB = (42, 12, 20)
MAROON_DEEP: RGB = (73, 18, 31)
MAROON: RGB = (99, 25, 41)
CREAM: RGB = (249, 244, 235)
PARCHMENT: RGB = (238, 226, 208)
WARM_GRAY: RGB = (198, 181, 160)
GOLD: RGB = (196, 145, 77)
GOLD_DARK: RGB = (151, 105, 52)
OFF_WHITE: RGB = (255, 252, 246)
CHARCOAL: RGB = (53, 48, 46)
BORDER: RGB = (226, 205, 176)


@dataclass
class BrandTheme:
    """Everything the renderer needs to draw a slide. Defaults reproduce the reference look."""

    name: str = "Victory Framework (Default)"

    # Palette — identical names/values to the legacy module constants.
    ink: RGB = INK
    maroon_black: RGB = MAROON_BLACK
    maroon_deep: RGB = MAROON_DEEP
    maroon: RGB = MAROON
    cream: RGB = CREAM
    parchment: RGB = PARCHMENT
    warm_gray: RGB = WARM_GRAY
    gold: RGB = GOLD
    gold_dark: RGB = GOLD_DARK
    off_white: RGB = OFF_WHITE
    charcoal: RGB = CHARCOAL
    border: RGB = BORDER

    # Fonts. A value here is either "bundled" (ship with the engine), an absolute path to a
    # brand-uploaded .ttf/.otf, or a platform font family name to look up via fontconfig/OS
    # fallback chain (kept for parity with the legacy Windows/Linux search order).
    heading_font: str = "bundled:LiberationSans-Bold.ttf"
    heading_font_italic: str = "bundled:LiberationSans-BoldItalic.ttf"
    body_font: str = "bundled:LiberationSans-Regular.ttf"
    body_font_italic: str = "bundled:LiberationSans-Italic.ttf"

    # Feature-card copy on the cover slide ("VICTORY FRAMEWORK" + the three bullet lines).
    cover_kicker: str = "VICTORY FRAMEWORK"
    cover_bullets: Tuple[str, str, str] = ("Professional thinking", "Defensible decisions", "Portable strategy")

    # Assets.
    logo_path: Optional[str] = None
    intro_video_path: Optional[str] = None
    outro_video_path: Optional[str] = None

    # Video/slide dimensions — identical defaults to legacy config["video"].
    width: int = 1920
    height: int = 1080
    fps: int = 30
    audio_bitrate: str = "192k"

    # Caption style is new configurability (legacy engine burned no captions into video).
    captions_enabled: bool = False
    caption_font_size: int = 34
    caption_position: str = "bottom"  # "bottom" | "top"

    # Global text-size multiplier so a course can bump legibility without redesigning layouts.
    text_scale: float = 1.0


DEFAULT_BRAND = BrandTheme()


def brand_to_dict(brand: BrandTheme) -> Dict[str, Any]:
    return {
        "name": brand.name,
        "colors": {
            "ink": brand.ink, "maroon_black": brand.maroon_black, "maroon_deep": brand.maroon_deep,
            "maroon": brand.maroon, "cream": brand.cream, "parchment": brand.parchment,
            "warm_gray": brand.warm_gray, "gold": brand.gold, "gold_dark": brand.gold_dark,
            "off_white": brand.off_white, "charcoal": brand.charcoal, "border": brand.border,
        },
        "fonts": {
            "heading_font": brand.heading_font, "heading_font_italic": brand.heading_font_italic,
            "body_font": brand.body_font, "body_font_italic": brand.body_font_italic,
        },
        "cover": {"kicker": brand.cover_kicker, "bullets": list(brand.cover_bullets)},
        "assets": {"logo_path": brand.logo_path, "intro_video_path": brand.intro_video_path, "outro_video_path": brand.outro_video_path},
        "video": {"width": brand.width, "height": brand.height, "fps": brand.fps, "audio_bitrate": brand.audio_bitrate},
        "captions": {"enabled": brand.captions_enabled, "font_size": brand.caption_font_size, "position": brand.caption_position},
        "text_scale": brand.text_scale,
    }


def _tuple3(value: Any, default: RGB) -> RGB:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return (int(value[0]), int(value[1]), int(value[2]))
    return default


def brand_from_dict(overrides: Optional[Dict[str, Any]]) -> BrandTheme:
    """Deep-merge a partial brand dict (as stored by the web app) onto DEFAULT_BRAND."""
    if not overrides:
        return replace(DEFAULT_BRAND)
    b = replace(DEFAULT_BRAND)
    colors = overrides.get("colors", {}) or {}
    for key in ["ink", "maroon_black", "maroon_deep", "maroon", "cream", "parchment", "warm_gray", "gold", "gold_dark", "off_white", "charcoal", "border"]:
        if key in colors:
            setattr(b, key, _tuple3(colors[key], getattr(b, key)))
    fonts = overrides.get("fonts", {}) or {}
    for key in ["heading_font", "heading_font_italic", "body_font", "body_font_italic"]:
        if fonts.get(key):
            setattr(b, key, fonts[key])
    cover = overrides.get("cover", {}) or {}
    if cover.get("kicker"):
        b.cover_kicker = cover["kicker"]
    if cover.get("bullets") and len(cover["bullets"]) == 3:
        b.cover_bullets = tuple(cover["bullets"])
    assets = overrides.get("assets", {}) or {}
    for key in ["logo_path", "intro_video_path", "outro_video_path"]:
        if key in assets:
            setattr(b, key, assets[key])
    video = overrides.get("video", {}) or {}
    for key, cast in [("width", int), ("height", int), ("fps", int), ("audio_bitrate", str)]:
        if key in video and video[key] not in (None, ""):
            setattr(b, key, cast(video[key]))
    captions = overrides.get("captions", {}) or {}
    if "enabled" in captions:
        b.captions_enabled = bool(captions["enabled"])
    if "font_size" in captions and captions["font_size"]:
        b.caption_font_size = int(captions["font_size"])
    if captions.get("position"):
        b.caption_position = captions["position"]
    if overrides.get("text_scale"):
        b.text_scale = float(overrides["text_scale"])
    if overrides.get("name"):
        b.name = overrides["name"]
    return b


if __name__ == "__main__":  # pragma: no cover - manual sanity check
    import json
    print(json.dumps(brand_to_dict(DEFAULT_BRAND), indent=2))
