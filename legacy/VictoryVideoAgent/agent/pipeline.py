from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

try:
    from docx import Document
except Exception:  # pragma: no cover - handled at runtime
    Document = None


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.json"
OUTPUT = ROOT / "output"
INPUT = ROOT / "input_scripts"
MANIFESTS = OUTPUT / "manifests"
LOGS = OUTPUT / "logs"

W, H = 1920, 1080

INK = (33, 24, 24)
MAROON_BLACK = (42, 12, 20)
MAROON_DEEP = (73, 18, 31)
MAROON = (99, 25, 41)
CREAM = (249, 244, 235)
PARCHMENT = (238, 226, 208)
WARM_GRAY = (198, 181, 160)
GOLD = (196, 145, 77)
GOLD_DARK = (151, 105, 52)
OFF_WHITE = (255, 252, 246)
CHARCOAL = (53, 48, 46)
BORDER = (226, 205, 176)

DEFAULT_CONFIG: Dict[str, Any] = {
    "course_name": "Victory Framework",
    "module_number": 2,
    "module_name": "New Victory Framework Module",
    "input_pattern": "*.docx",
    "overwrite_existing_audio": False,
    "overwrite_existing_videos": True,
    "treat_lesson_headings_as_metadata": True,
    "elevenlabs": {
        "enabled": True,
        "api_key": "",
        "api_key_env_var": "ELEVENLABS_API_KEY",
        "voice_id": "Victoria Voice",
        "model_id": "eleven_multilingual_v2",
        "stability": 0.55,
        "similarity_boost": 0.80,
        "style": 0.05,
        "use_speaker_boost": True,
        "max_chars_per_request": 4500,
    },
    "video": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "audio_bitrate": "192k",
    },
    "delivery": {
        "copy_to_google_drive_sync_folder": False,
        "google_drive_sync_folder": "",
    },
}


@dataclass
class Logger:
    path: Path

    def info(self, message: str) -> None:
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        print(line)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


_LOGGER: Optional[Logger] = None
_BASE_BG: Optional[Image.Image] = None
_FONT_CACHE: Dict[Tuple[str, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def get_logger() -> Logger:
    global _LOGGER
    if _LOGGER is None:
        LOGS.mkdir(parents=True, exist_ok=True)
        _LOGGER = Logger(LOGS / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    return _LOGGER


def ensure_dirs() -> None:
    for path in [
        INPUT,
        OUTPUT / "audio",
        OUTPUT / "concat_lists",
        OUTPUT / "logs",
        OUTPUT / "manifests",
        OUTPUT / "moodle_descriptions",
        OUTPUT / "review_package",
        OUTPUT / "scripts",
        OUTPUT / "slides",
        OUTPUT / "trackers",
        OUTPUT / "videos",
        OUTPUT / "editable_assets",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Path = CONFIG_PATH) -> Dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Missing configuration file: {config_path}. Copy config.example.json to config.json first.")
    with config_path.open("r", encoding="utf-8") as f:
        user_config = json.load(f)
    cfg = deep_merge(DEFAULT_CONFIG, user_config)
    return cfg


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def slugify(text: str) -> str:
    text = text.replace("—", "-").replace("–", "-").replace("’", "")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    text = re.sub(r"_+", "_", text)
    return text[:110].strip("_") or "lesson"


def normalize_paragraphs(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"\n\s*\n+", text)
    cleaned = []
    for part in parts:
        lines = [line.strip() for line in part.split("\n") if line.strip()]
        if lines:
            cleaned.append(" ".join(lines))
    return cleaned


def read_docx_paragraphs(path: Path) -> List[str]:
    if Document is None:
        raise RuntimeError("python-docx is not installed. Run SETUP_WINDOWS.bat or pip install -r requirements.txt.")
    doc = Document(str(path))
    paragraphs = []
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt:
            paragraphs.append(txt)
    return paragraphs


def read_text_paragraphs(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs: List[str] = []
    current_lines: List[str] = []

    def flush_current() -> None:
        nonlocal current_lines
        if current_lines:
            paragraphs.append(" ".join(line.strip() for line in current_lines if line.strip()))
            current_lines = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            flush_current()
            continue
        if detect_lesson_heading(line):
            flush_current()
            paragraphs.append(line)
            continue
        current_lines.append(line)
    flush_current()
    return [p for p in paragraphs if p]


def read_input_file(path: Path) -> List[str]:
    if path.suffix.lower() == ".docx":
        return read_docx_paragraphs(path)
    return read_text_paragraphs(path)


def detect_lesson_heading(line: str) -> Optional[Tuple[str, str]]:
    cleaned = line.strip()
    patterns = [
        r"^lesson\s+((?:\d+\.)?\d+)\s*[:\-–—]\s*(.+)$",
        r"^module\s+\d+\s+lesson\s+((?:\d+\.)?\d+)\s*[:\-–—]\s*(.+)$",
        r"^((?:\d+\.)?\d+)\s*[:\-–—]\s*(.+)$",
    ]
    for pattern in patterns:
        m = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if m:
            return m.group(1), m.group(2).strip()
    return None


def title_from_filename(path: Path) -> str:
    title = re.sub(r"[_\-]+", " ", path.stem).strip()
    return title.title() if title else "Untitled Lesson"


def detect_script_metadata(line: str) -> Optional[Tuple[str, str]]:
    """Return simple script metadata such as COURSE, MODULE, LESSON, or TYPE.

    Several Victory Framework source scripts are formatted as repeated editable
    blocks that begin with COURSE, MODULE, LESSON, and TYPE instead of numbered
    lesson headings. The narrator text must not include those metadata labels,
    and every LESSON line should start a new lesson block.
    """
    m = re.match(r"^\s*(course|module|lesson|type)\s*:\s*(.+?)\s*$", line.strip(), flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).lower(), m.group(2).strip()


def split_lessons_from_paragraphs(paragraphs: List[str], source_path: Path, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    lessons: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    treat_headings = bool(cfg.get("treat_lesson_headings_as_metadata", True))
    sequential_lesson_number = 0
    has_lesson_metadata = any((detect_script_metadata(p) or (None, None))[0] == "lesson" for p in paragraphs)

    for paragraph in paragraphs:
        metadata = detect_script_metadata(paragraph)
        if metadata:
            key, value = metadata
            if key == "lesson":
                if current and current["paragraphs"]:
                    lessons.append(current)
                sequential_lesson_number += 1
                current = {"lesson_number": str(sequential_lesson_number), "lesson_title": value, "paragraphs": []}
                if not treat_headings:
                    current["paragraphs"].append(paragraph)
            # COURSE, MODULE, and TYPE are source-file metadata, not narration.
            continue

        heading = detect_lesson_heading(paragraph)
        if heading:
            if current and current["paragraphs"]:
                lessons.append(current)
            lesson_number, title = heading
            current = {"lesson_number": lesson_number, "lesson_title": title, "paragraphs": []}
            if not treat_headings:
                current["paragraphs"].append(paragraph)
            continue
        if current is None:
            if has_lesson_metadata:
                # Ignore document-level notes that appear before the first LESSON block.
                continue
            current = {"lesson_number": "1", "lesson_title": title_from_filename(source_path), "paragraphs": []}
        current["paragraphs"].append(paragraph)

    if current and current["paragraphs"]:
        lessons.append(current)

    if not lessons:
        raise RuntimeError(f"No usable narration text found in {source_path.name}.")

    return lessons


def discover_input_files(cfg: Dict[str, Any]) -> List[Path]:
    pattern = cfg.get("input_pattern", "*.docx")
    files = sorted([p for p in INPUT.glob(pattern) if p.is_file() and not p.name.startswith("PUT_")])
    if not files and pattern != "*.txt":
        files = sorted([p for p in INPUT.glob("*.txt") if p.is_file() and not p.name.startswith("PUT_")])
    if not files:
        supported = sorted([p.name for p in INPUT.glob("*") if p.is_file()])
        raise FileNotFoundError(
            f"No script files found in {INPUT}. Add a .docx or .txt file. Current files: {supported or 'none'}"
        )
    return files


def extract_scripts(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    logger = get_logger()
    logger.info("Step 1/7: Extracting exact narration scripts.")
    script_dir = OUTPUT / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    input_files = discover_input_files(cfg)
    all_lessons: List[Dict[str, Any]] = []

    for source in input_files:
        paragraphs = read_input_file(source)
        lesson_blocks = split_lessons_from_paragraphs(paragraphs, source, cfg)
        for block in lesson_blocks:
            all_lessons.append({**block, "source_file": str(source)})

    module_number = str(cfg.get("module_number", "1"))
    for idx, lesson in enumerate(all_lessons, start=1):
        raw_number = str(lesson.get("lesson_number") or idx)
        if "." not in raw_number:
            lesson_number = f"{module_number}.{raw_number}"
        else:
            lesson_number = raw_number
        lesson["lesson_number"] = lesson_number
        lesson["lesson_index"] = idx
        lesson["module_number"] = cfg.get("module_number")
        lesson["course_name"] = cfg.get("course_name")
        lesson["module_name"] = cfg.get("module_name")
        script_text = "\n\n".join(lesson.pop("paragraphs")) + "\n"
        lesson_slug = slugify(f"{lesson_number}_{lesson['lesson_title']}")
        out_path = script_dir / f"{lesson_slug}.txt"
        out_path.write_text(script_text, encoding="utf-8")
        lesson["lesson_slug"] = lesson_slug
        lesson["narration_file"] = str(out_path)
        lesson["word_count"] = len(re.findall(r"\b\w+\b", script_text))
        lesson["paragraph_count"] = len(normalize_paragraphs(script_text))
        lesson["status"] = "script_extracted"

    manifest = {"course": cfg["course_name"], "module": cfg["module_name"], "module_number": cfg["module_number"], "lessons": all_lessons}
    write_json(MANIFESTS / "lessons_manifest.json", manifest)
    logger.info(f"Extracted {len(all_lessons)} lesson script(s) without rewriting narration text.")
    return all_lessons


def font_candidates(kind: str) -> List[Path]:
    windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    candidates = {
        "sans": [
            windows / "arial.ttf",
            windows / "calibri.ttf",
            Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf"),
        ],
        "sans_bold": [
            windows / "arialbd.ttf",
            windows / "calibrib.ttf",
            Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
            Path("/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf"),
        ],
    }
    return candidates.get(kind, candidates["sans"])


def font(kind: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    key = (kind, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    for p in font_candidates(kind):
        if p.exists():
            _FONT_CACHE[key] = ImageFont.truetype(str(p), size)
            return _FONT_CACHE[key]
    _FONT_CACHE[key] = ImageFont.load_default()
    return _FONT_CACHE[key]


def create_background() -> Image.Image:
    global _BASE_BG
    if _BASE_BG is not None:
        return _BASE_BG.copy()
    img = Image.new("RGBA", (W, H), MAROON_BLACK + (255,))
    pix = img.load()
    for y in range(H):
        ty = y / H
        for x in range(W):
            tx = x / W
            vignette = ((tx - 0.58) ** 2 + (ty - 0.38) ** 2) ** 0.5
            blend = max(0, min(1, 0.42 - vignette))
            r = int(MAROON_BLACK[0] * (1 - blend) + MAROON[0] * blend)
            g = int(MAROON_BLACK[1] * (1 - blend) + MAROON[1] * blend)
            b = int(MAROON_BLACK[2] * (1 - blend) + MAROON[2] * blend)
            pix[x, y] = (r, g, b, 255)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for x in range(96, W, 96):
        d.line((x, 0, x, H), fill=(255, 240, 210, 10), width=1)
    for y in range(96, H, 96):
        d.line((0, y, W, y), fill=(255, 240, 210, 7), width=1)
    d.rectangle((42, 42, W - 42, H - 42), outline=(220, 190, 145, 60), width=2)
    d.rectangle((68, 68, W - 68, H - 68), outline=(220, 190, 145, 22), width=1)
    d.polygon([(1300, 0), (1920, 0), (1920, 1080), (1640, 1080)], fill=(25, 18, 20, 82))
    img = Image.alpha_composite(img, overlay)
    _BASE_BG = img
    return img.copy()


def text_bbox(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> Tuple[int, int, int, int]:
    return draw.textbbox((0, 0), str(text), font=fnt)


def fit_lines(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_width: int, max_lines: Optional[int] = None) -> List[str]:
    words = str(text).split()
    lines: List[str] = []
    line = ""
    for word in words:
        test = (line + " " + word).strip()
        b = text_bbox(draw, test, fnt)
        if b[2] - b[0] <= max_width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    return lines


def draw_text(draw: ImageDraw.ImageDraw, text: str, xy: Tuple[int, int], fnt: ImageFont.ImageFont, fill: Tuple[int, ...], max_width: Optional[int] = None, line_gap: int = 10, max_lines: Optional[int] = None, align: str = "left") -> int:
    x, y = xy
    lines: List[str] = []
    if max_width is None:
        lines = str(text).split("\n")
    else:
        for part in str(text).split("\n"):
            lines.extend(fit_lines(draw, part, fnt, max_width, max_lines=max_lines))
    for line in lines:
        b = text_bbox(draw, line, fnt)
        tw, th = b[2] - b[0], b[3] - b[1]
        dx = x
        if align == "center":
            dx = int(x - tw / 2)
        elif align == "right":
            dx = x - tw
        draw.text((dx, y), line, font=fnt, fill=fill)
        y += th + line_gap
    return y


def card(img: Image.Image, box: Tuple[int, int, int, int], fill: Tuple[int, ...], outline: Tuple[int, ...] = BORDER + (120,), radius: int = 8, shadow: bool = True) -> ImageDraw.ImageDraw:
    if shadow:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        x1, y1, x2, y2 = box
        sd.rounded_rectangle((x1 + 10, y1 + 14, x2 + 10, y2 + 14), radius=radius, fill=(0, 0, 0, 70))
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        img.alpha_composite(sh)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)
    return d


def header_footer(draw: ImageDraw.ImageDraw, cfg: Dict[str, Any], lesson_number: str, slide_num: int, total: int, eyebrow: str) -> None:
    draw.text((96, 80), str(cfg["course_name"]).upper(), font=font("sans_bold", 22), fill=PARCHMENT)
    draw.text((96, 112), str(cfg["module_name"]), font=font("sans", 23), fill=(210, 190, 166))
    draw.line((96, 158, 1824, 158), fill=(226, 205, 176, 90), width=2)
    draw.text((96, 996), f"Lesson {lesson_number}", font=font("sans", 23), fill=(210, 190, 166))
    draw.text((1518, 996), f"{slide_num:02d} / {total:02d}", font=font("sans", 23), fill=(210, 190, 166))
    draw.rectangle((96, 944, 1824, 950), fill=(226, 205, 176, 45))
    draw.rectangle((96, 944, 96 + int(1728 * slide_num / total), 950), fill=GOLD)
    b = draw.textbbox((0, 0), eyebrow.upper(), font=font("sans_bold", 22))
    # Use an opaque cream badge with dark text. The final PNG export drops alpha,
    # so semi-transparent cream plus light text can become unreadable.
    draw.rounded_rectangle((96, 186, 132 + (b[2] - b[0]), 228), radius=6, fill=(248, 241, 229, 238), outline=(226, 205, 176, 150), width=1)
    draw.text((114, 198), eyebrow.upper(), font=font("sans_bold", 22), fill=MAROON_DEEP)


def extract_keywords(text: str, limit: int = 5) -> List[str]:
    stop = set("the a an and or but if then this that these those you your we our to of in for on with from as is are was were be being been it its at by into about through across not do does did can will would should could have has had they their them one all more most just very".split())
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z']+", text)]
    counts: Dict[str, int] = {}
    for w in words:
        if len(w) < 4 or w in stop:
            continue
        counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    result = []
    for word, _ in ranked:
        label = word.replace("'", "").title()
        if label not in result:
            result.append(label)
        if len(result) >= limit:
            break
    return result or ["Situation", "Rules", "Evidence", "Decision", "Communication"][:limit]


def short_sentence(paragraph: str, max_chars: int = 92) -> str:
    pieces = re.split(r"(?<=[.!?])\s+", paragraph.strip())
    sentence = pieces[0] if pieces and pieces[0] else paragraph.strip()
    sentence = re.sub(r"\s+", " ", sentence)
    if len(sentence) > max_chars:
        sentence = sentence[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return sentence


def make_slide_specs(lesson: Dict[str, Any]) -> List[Dict[str, Any]]:
    script = Path(lesson["narration_file"]).read_text(encoding="utf-8")
    paragraphs = normalize_paragraphs(script)
    keywords = extract_keywords(script, 8)
    title = lesson["lesson_title"]
    specs: List[Dict[str, Any]] = [
        {"kind": "cover", "eyebrow": f"Module {lesson['module_number']} · Lesson {lesson['lesson_number']}", "title": title, "subtitle": "Victory Framework training", "anchor": short_sentence(paragraphs[0]) if paragraphs else "Professional thinking creates portable value.", "idx": [0]},
    ]
    if paragraphs:
        specs.append({"kind": "statement", "eyebrow": "Core Idea", "title": short_sentence(paragraphs[0], 70), "body": [short_sentence(p, 100) for p in paragraphs[1:4]] or ["Use the framework to slow down, see the pattern, and make a defensible call."], "idx": list(range(0, min(4, len(paragraphs))))})
    specs.append({"kind": "map", "eyebrow": "Framework Lens", "title": "What This Lesson Helps You See", "items": keywords[:6], "idx": list(range(min(4, len(paragraphs))))})
    if len(paragraphs) >= 4:
        mid = len(paragraphs) // 2
        specs.append({"kind": "comparison", "eyebrow": "Professional Shift", "title": "From Task Work to Strategic Thinking", "left_title": "Before", "left": [short_sentence(p, 54) for p in paragraphs[max(0, mid-2):mid+1]][:3], "right_title": "After", "right": [short_sentence(p, 54) for p in paragraphs[mid+1:mid+4]][:3] or keywords[:3], "idx": list(range(max(0, mid-2), min(len(paragraphs), mid+4)))})
    specs.append({"kind": "flow", "eyebrow": "Apply It", "title": "Run the Lesson Through the Framework", "steps": keywords[:4] if len(keywords) >= 4 else ["Ask", "Find", "Decide", "Communicate"], "body": "The script remains the narration. The slides provide concise visual anchors.", "idx": list(range(max(0, len(paragraphs)-4), len(paragraphs)))})
    if len(paragraphs) >= 2:
        specs.append({"kind": "quote", "eyebrow": "Remember", "title": "The point is the thinking underneath the work.", "quote": short_sentence(paragraphs[-2], 110), "note": "Keep the frame professional, practical, and defensible.", "idx": [max(0, len(paragraphs)-2)]})
    specs.append({"kind": "close", "eyebrow": "Lock It In", "title": short_sentence(paragraphs[-1], 120) if paragraphs else "Use the framework on the next case.", "subtitle": "Ready for the next lesson.", "idx": [max(0, len(paragraphs)-1)] if paragraphs else []})
    return specs[:8]


def draw_title_block(draw: ImageDraw.ImageDraw, title: str, subtitle: Optional[str] = None, x: int = 118, y: int = 258, width: int = 860, title_size: int = 72) -> int:
    y = draw_text(draw, title, (x, y), font("sans_bold", title_size), CREAM, max_width=width, line_gap=14, max_lines=3)
    draw.rectangle((x, y + 18, x + 92, y + 25), fill=GOLD)
    if subtitle:
        y = draw_text(draw, subtitle, (x, y + 56), font("sans", 31), PARCHMENT, max_width=width, line_gap=11, max_lines=3)
    return y


def render_cover(img: Image.Image, draw: ImageDraw.ImageDraw, slide: Dict[str, Any]) -> None:
    draw_title_block(draw, slide["title"], slide.get("subtitle"), x=118, y=282, width=860, title_size=74)
    d = card(img, (1110, 230, 1788, 818), fill=(248, 241, 229, 238), outline=(226, 205, 176, 130), radius=8)
    d.rectangle((1160, 288, 1738, 304), fill=MAROON)
    d.text((1160, 350), "VICTORY FRAMEWORK", font=font("sans_bold", 28), fill=MAROON)
    d.line((1160, 397, 1738, 397), fill=(120, 80, 60, 90), width=2)
    for i, txt in enumerate(["Professional thinking", "Defensible decisions", "Portable strategy"]):
        d.text((1160, 448 + i * 64), txt, font=font("sans_bold", 42), fill=INK)
    d.rectangle((1160, 672, 1738, 674), fill=(120, 80, 60, 90))
    draw_text(d, slide.get("anchor", ""), (1160, 706), font("sans", 27), CHARCOAL, max_width=540, line_gap=8, max_lines=3)


def render_statement(img: Image.Image, draw: ImageDraw.ImageDraw, slide: Dict[str, Any]) -> None:
    draw_title_block(draw, slide["title"], None, x=118, y=250, width=1160, title_size=60)
    y = 520
    for item in slide.get("body", [])[:4]:
        # Cream cards need dark text for readability in the exported video frames.
        d = card(img, (160, y, 1745, y + 106), fill=(248, 241, 229, 238), outline=(226, 205, 176, 145), radius=8, shadow=False)
        d.rectangle((190, y + 26, 202, y + 82), fill=GOLD)
        draw_text(d, item, (232, y + 31), font("sans", 31), INK, max_width=1400, line_gap=8, max_lines=2)
        y += 132


def render_map(img: Image.Image, draw: ImageDraw.ImageDraw, slide: Dict[str, Any]) -> None:
    draw_title_block(draw, slide["title"], None, x=118, y=226, width=1120, title_size=60)
    items = slide.get("items", [])[:6]
    x0, y0 = 200, 480
    cols = 3
    for i, item in enumerate(items, start=1):
        col = (i - 1) % cols
        row = (i - 1) // cols
        x = x0 + col * 520
        y = y0 + row * 190
        d = card(img, (x, y, x + 420, y + 136), fill=(248, 241, 229, 235), outline=(226, 205, 176, 120), radius=8)
        d.text((x + 30, y + 28), f"{i:02d}", font=font("sans_bold", 38), fill=MAROON)
        draw_text(d, item, (x + 108, y + 36), font("sans", 30), INK, max_width=260, line_gap=7, max_lines=2)


def render_comparison(img: Image.Image, draw: ImageDraw.ImageDraw, slide: Dict[str, Any]) -> None:
    draw_title_block(draw, slide["title"], None, x=118, y=238, width=1050, title_size=58)
    boxes = [(142, 512, 894, 850), (1026, 512, 1778, 850)]
    for box, title, items, accent in [(boxes[0], slide.get("left_title", "Before"), slide.get("left", []), WARM_GRAY), (boxes[1], slide.get("right_title", "After"), slide.get("right", []), GOLD)]:
        d = card(img, box, fill=(248, 241, 229, 236), outline=(226, 205, 176, 130), radius=8)
        x1, y1, x2, _ = box
        d.rectangle((x1, y1, x2, y1 + 14), fill=accent)
        d.text((x1 + 52, y1 + 54), title.upper(), font=font("sans_bold", 28), fill=MAROON)
        y = y1 + 126
        for item in items[:3]:
            d.rectangle((x1 + 56, y + 8, x1 + 68, y + 20), fill=GOLD_DARK)
            draw_text(d, item, (x1 + 92, y), font("sans", 27), INK, max_width=560, line_gap=6, max_lines=2)
            y += 68


def render_flow(img: Image.Image, draw: ImageDraw.ImageDraw, slide: Dict[str, Any]) -> None:
    draw_title_block(draw, slide["title"], slide.get("body"), x=118, y=235, width=1220, title_size=58)
    y = 654
    steps = slide.get("steps", [])[:5]
    n = max(1, len(steps))
    gap = 34
    box_w = int((1620 - (n - 1) * gap) / n)
    x = 150
    for i, step in enumerate(steps, start=1):
        d = card(img, (x, y, x + box_w, y + 170), fill=(248, 241, 229, 236), outline=(226, 205, 176, 125), radius=8)
        d.text((x + 34, y + 34), f"{i:02d}", font=font("sans_bold", 38), fill=MAROON)
        d.rectangle((x + 34, y + 86, x + 102, y + 92), fill=GOLD)
        draw_text(d, step, (x + 34, y + 112), font("sans", 27), INK, max_width=box_w - 68, line_gap=7, max_lines=2)
        if i < n:
            draw.line((x + box_w + 8, y + 84, x + box_w + gap - 8, y + 84), fill=GOLD, width=4)
        x += box_w + gap


def render_quote(img: Image.Image, draw: ImageDraw.ImageDraw, slide: Dict[str, Any]) -> None:
    draw_title_block(draw, slide["title"], None, x=118, y=244, width=1020, title_size=56)
    d = card(img, (210, 528, 1710, 804), fill=(248, 241, 229, 238), outline=(226, 205, 176, 145), radius=8)
    d.text((270, 584), "KEY TRUTH", font=font("sans_bold", 28), fill=MAROON)
    d.rectangle((270, 632, 370, 638), fill=GOLD)
    draw_text(d, slide.get("quote", ""), (270, 675), font("sans_bold", 45), INK, max_width=1320, line_gap=12, max_lines=3)
    if slide.get("note"):
        d.text((270, 842), slide["note"], font=font("sans", 27), fill=PARCHMENT)


def render_close(img: Image.Image, draw: ImageDraw.ImageDraw, slide: Dict[str, Any]) -> None:
    draw.text((118, 308), slide.get("eyebrow", "Lock It In").upper(), font=font("sans_bold", 28), fill=GOLD)
    draw.rectangle((118, 358, 230, 365), fill=GOLD)
    draw_text(draw, slide["title"], (118, 425), font("sans_bold", 58), CREAM, max_width=1320, line_gap=14, max_lines=3)
    if slide.get("subtitle"):
        d = card(img, (118, 735, 1640, 828), fill=(248, 241, 229, 238), outline=(226, 205, 176, 145), radius=8, shadow=False)
        d.text((158, 764), slide["subtitle"], font=font("sans", 31), fill=INK)


RENDERERS = {
    "cover": render_cover,
    "statement": render_statement,
    "map": render_map,
    "comparison": render_comparison,
    "flow": render_flow,
    "quote": render_quote,
    "close": render_close,
}


def render_slides(cfg: Dict[str, Any], lessons: List[Dict[str, Any]]) -> Dict[str, Any]:
    logger = get_logger()
    logger.info("Step 2/7: Rendering professional Victory Framework slides.")
    slides_root = OUTPUT / "slides"
    storyboard_root = OUTPUT / "moodle_descriptions" / "storyboards"
    slides_root.mkdir(parents=True, exist_ok=True)
    storyboard_root.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {"course": cfg["course_name"], "module": cfg["module_name"], "template": "victory_professional_adult_training_local_v1", "lessons": []}

    for lesson in lessons:
        specs = make_slide_specs(lesson)
        paragraphs = normalize_paragraphs(Path(lesson["narration_file"]).read_text(encoding="utf-8"))
        lesson_dir = slides_root / lesson["lesson_slug"]
        lesson_dir.mkdir(parents=True, exist_ok=True)
        total = len(specs)
        rows = [
            f"# Storyboard — {lesson['lesson_number']} {lesson['lesson_title']}",
            "",
            "The narration source is the exact extracted script. On-screen text is a concise visual support layer only.",
            "",
            "| Slide | Visual Focus | Script Paragraphs | Image |",
            "|---:|---|---|---|",
        ]
        slide_records: List[Dict[str, Any]] = []
        for i, spec in enumerate(specs, start=1):
            img = create_background()
            draw = ImageDraw.Draw(img)
            header_footer(draw, cfg, lesson["lesson_number"], i, total, spec.get("eyebrow", ""))
            RENDERERS[spec["kind"]](img, draw, spec)
            out = lesson_dir / f"slide_{i:02d}.png"
            img.convert("RGB").save(out, quality=95)
            idxs = spec.get("idx", [])
            idx_label = ", ".join(str(x + 1) for x in idxs if x < len(paragraphs)) if idxs else "Visual transition"
            rows.append(f"| {i} | {spec['title']} | {idx_label} | `{out.name}` |")
            slide_records.append({"slide": i, "title": spec["title"], "image": str(out), "script_paragraph_indices": idxs, "kind": spec["kind"]})
        storyboard_path = storyboard_root / f"{lesson['lesson_slug']}_storyboard.md"
        storyboard_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        manifest["lessons"].append({**lesson, "slide_count": total, "slides_dir": str(lesson_dir), "storyboard": str(storyboard_path), "slides": slide_records})

    write_json(MANIFESTS / "slide_manifest.json", manifest)
    logger.info(f"Rendered slides for {len(lessons)} lesson(s).")
    return manifest


def require_command(command: str) -> bool:
    return shutil.which(command) is not None


def get_elevenlabs_api_key(cfg: Dict[str, Any]) -> str:
    e = cfg.get("elevenlabs", {})
    env_var = e.get("api_key_env_var", "ELEVENLABS_API_KEY")
    return os.environ.get(env_var, "") or e.get("api_key", "")


def resolve_voice_id(api_key: str, configured_voice: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{12,}", configured_voice or ""):
        return configured_voice
    headers = {"xi-api-key": api_key}
    resp = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers, timeout=30)
    resp.raise_for_status()
    voices = resp.json().get("voices", [])
    for voice in voices:
        if voice.get("name", "").strip().lower() == configured_voice.strip().lower():
            return voice.get("voice_id")
    available = ", ".join(v.get("name", "Unnamed") for v in voices[:20])
    raise RuntimeError(f"Could not find ElevenLabs voice named '{configured_voice}'. Available voices include: {available}")


def split_text_for_tts(text: str, max_chars: int) -> List[str]:
    paragraphs = normalize_paragraphs(text)
    chunks: List[str] = []
    current = ""
    for p in paragraphs:
        candidate = (current + "\n\n" + p).strip() if current else p
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(p) <= max_chars:
                current = p
            else:
                pieces = textwrap.wrap(p, width=max_chars, break_long_words=False, replace_whitespace=False)
                chunks.extend(pieces[:-1])
                current = pieces[-1]
    if current:
        chunks.append(current)
    return chunks


def call_elevenlabs_tts(api_key: str, voice_id: str, text: str, e_cfg: Dict[str, Any], out_path: Path) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    payload = {
        "text": text,
        "model_id": e_cfg.get("model_id", "eleven_multilingual_v2"),
        "voice_settings": {
            "stability": e_cfg.get("stability", 0.55),
            "similarity_boost": e_cfg.get("similarity_boost", 0.8),
            "style": e_cfg.get("style", 0.05),
            "use_speaker_boost": e_cfg.get("use_speaker_boost", True),
        },
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    if not resp.ok:
        raise RuntimeError(f"ElevenLabs TTS failed ({resp.status_code}): {resp.text[:500]}")
    out_path.write_bytes(resp.content)


def concat_audio_parts(parts: List[Path], out_path: Path) -> None:
    if len(parts) == 1:
        shutil.move(str(parts[0]), str(out_path))
        return
    if not require_command("ffmpeg"):
        raise RuntimeError("FFmpeg is required to join multi-part narration audio. Install FFmpeg and add it to PATH.")
    concat_path = out_path.with_suffix(".concat.txt")
    concat_lines = [f"file '{p.as_posix()}'" for p in parts]
    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-c:a", "libmp3lame", "-b:a", "192k", str(out_path)]
    subprocess.run(cmd, check=True)
    for p in parts:
        p.unlink(missing_ok=True)
    concat_path.unlink(missing_ok=True)


def ffprobe_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    return float(subprocess.check_output(cmd, text=True).strip())


def generate_narration(cfg: Dict[str, Any], lessons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    logger = get_logger()
    logger.info("Step 3/7: Generating ElevenLabs narration audio.")
    e_cfg = cfg.get("elevenlabs", {})
    audio_dir = OUTPUT / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []

    if not e_cfg.get("enabled", True):
        logger.info("ElevenLabs is disabled in config. Skipping narration generation.")
        write_json(MANIFESTS / "audio_manifest.json", records)
        return records

    api_key = get_elevenlabs_api_key(cfg)
    if not api_key:
        raise RuntimeError("Missing ElevenLabs API key. Set ELEVENLABS_API_KEY in Windows or add it to config/config.json.")
    voice_id = resolve_voice_id(api_key, e_cfg.get("voice_id", "Victoria Voice"))
    overwrite = bool(cfg.get("overwrite_existing_audio", False))
    max_chars = int(e_cfg.get("max_chars_per_request", 4500))

    for lesson in lessons:
        out_file = audio_dir / f"{lesson['lesson_slug']}.mp3"
        if out_file.exists() and not overwrite:
            logger.info(f"Audio exists; skipping ElevenLabs usage for {out_file.name}.")
        else:
            script_text = Path(lesson["narration_file"]).read_text(encoding="utf-8")
            chunks = split_text_for_tts(script_text, max_chars=max_chars)
            parts: List[Path] = []
            for part_idx, chunk in enumerate(chunks, start=1):
                part_path = audio_dir / f"{lesson['lesson_slug']}.part{part_idx:02d}.mp3"
                logger.info(f"Generating narration: {lesson['lesson_number']} part {part_idx}/{len(chunks)}.")
                call_elevenlabs_tts(api_key, voice_id, chunk, e_cfg, part_path)
                parts.append(part_path)
                time.sleep(0.5)
            concat_audio_parts(parts, out_file)
        duration = ffprobe_duration(out_file) if require_command("ffprobe") else None
        records.append({"lesson_number": lesson["lesson_number"], "lesson_title": lesson["lesson_title"], "lesson_slug": lesson["lesson_slug"], "audio_file": str(out_file), "duration_seconds": duration})

    write_json(MANIFESTS / "audio_manifest.json", records)
    logger.info(f"Prepared narration audio for {len(records)} lesson(s).")
    return records


def paragraph_weights(script_path: Path, slides: List[Dict[str, Any]], audio_duration: float) -> List[float]:
    paragraphs = normalize_paragraphs(script_path.read_text(encoding="utf-8"))
    weights: List[float] = []
    for slide in slides:
        idxs = [i for i in slide.get("script_paragraph_indices", []) if 0 <= i < len(paragraphs)]
        weight = sum(max(90, len(paragraphs[i])) for i in idxs) if idxs else 180
        weights.append(weight)
    if weights:
        weights[0] = max(weights[0], 500)
        weights[-1] = max(weights[-1], 360)
    total = sum(weights) or len(slides)
    raw = [audio_duration * w / total for w in weights]
    floors = [7.0 if i == 0 else 5.5 for i in range(len(raw))]
    durations = [max(floors[i], raw[i]) for i in range(len(raw))]
    scale = audio_duration / sum(durations)
    return [d * scale for d in durations]


def assemble_videos(cfg: Dict[str, Any], slide_manifest: Dict[str, Any], audio_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    logger = get_logger()
    logger.info("Step 4/7: Assembling MP4 videos with FFmpeg.")
    if not require_command("ffmpeg") or not require_command("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required. Install FFmpeg and add it to PATH before assembling videos.")
    audio_lookup = {a["lesson_number"]: a for a in audio_records}
    video_dir = OUTPUT / "videos"
    concat_dir = OUTPUT / "concat_lists"
    video_dir.mkdir(parents=True, exist_ok=True)
    concat_dir.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    module_number = cfg.get("module_number", 1)
    overwrite = bool(cfg.get("overwrite_existing_videos", True))

    for lesson in slide_manifest.get("lessons", []):
        lesson_no = lesson["lesson_number"]
        if lesson_no not in audio_lookup:
            logger.info(f"No audio found for lesson {lesson_no}; video assembly skipped.")
            continue
        audio_file = Path(audio_lookup[lesson_no]["audio_file"])
        duration = ffprobe_duration(audio_file)
        durations = paragraph_weights(Path(lesson["narration_file"]), lesson["slides"], duration)
        lesson_index = lesson.get("lesson_index", lesson_no.split(".")[-1])
        video_slug = slugify(f"victory_framework_m{module_number}_{lesson_no}_{lesson['lesson_title']}")
        concat_path = concat_dir / f"{video_slug}.txt"
        lines: List[str] = []
        for slide, dur in zip(lesson["slides"], durations):
            img_path = Path(slide["image"]).resolve().as_posix()
            lines.append(f"file '{img_path}'")
            lines.append(f"duration {dur:.6f}")
        lines.append(f"file '{Path(lesson['slides'][-1]['image']).resolve().as_posix()}'")
        concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out_file = video_dir / f"{video_slug}.mp4"
        if out_file.exists() and not overwrite:
            logger.info(f"Video exists; skipping {out_file.name}.")
        else:
            cmd = [
                "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(concat_path),
                "-i", str(audio_file),
                "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                "-r", str(cfg.get("video", {}).get("fps", 30)), "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", cfg.get("video", {}).get("audio_bitrate", "192k"), "-ar", "44100",
                "-shortest", "-movflags", "+faststart", str(out_file),
            ]
            logger.info(f"Rendering video: {out_file.name}")
            subprocess.run(cmd, check=True)
        records.append({"lesson_number": lesson_no, "lesson_title": lesson["lesson_title"], "lesson_slug": lesson["lesson_slug"], "video_file": str(out_file), "audio_file": str(audio_file), "concat_file": str(concat_path), "slide_count": len(lesson["slides"]), "audio_duration_seconds": duration, "allocated_slide_durations_seconds": [round(x, 3) for x in durations], "status": "video_ready"})

    write_json(MANIFESTS / "video_manifest.json", records)
    logger.info(f"Assembled {len(records)} video(s).")
    return records


def create_tracker(cfg: Dict[str, Any], lessons: List[Dict[str, Any]], audio_records: List[Dict[str, Any]], video_records: List[Dict[str, Any]]) -> Tuple[Path, Path]:
    logger = get_logger()
    logger.info("Step 5/7: Creating Excel and CSV production trackers.")
    audio_lookup = {a["lesson_number"]: a for a in audio_records}
    video_lookup = {v["lesson_number"]: v for v in video_records}
    rows: List[Dict[str, Any]] = []
    for lesson in lessons:
        a = audio_lookup.get(lesson["lesson_number"], {})
        v = video_lookup.get(lesson["lesson_number"], {})
        rows.append({
            "Course": cfg["course_name"],
            "Module Number": cfg["module_number"],
            "Module Name": cfg["module_name"],
            "Lesson Number": lesson["lesson_number"],
            "Lesson Title": lesson["lesson_title"],
            "Script File": lesson["narration_file"],
            "Word Count": lesson.get("word_count"),
            "Paragraph Count": lesson.get("paragraph_count"),
            "Audio File": a.get("audio_file", ""),
            "Runtime Seconds": round(a.get("duration_seconds") or v.get("audio_duration_seconds") or 0, 2),
            "Slide Count": v.get("slide_count", ""),
            "Video File": v.get("video_file", ""),
            "Status": "Video Ready" if v.get("video_file") else ("Audio Ready" if a.get("audio_file") else "Script/Slides Ready"),
            "Moodle Description": f"output/moodle_descriptions/individual_lessons/{lesson['lesson_slug']}.txt",
            "Notes": "Narration script preserved exactly from extracted lesson text.",
        })
    tracker_dir = OUTPUT / "trackers"
    tracker_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"victory_framework_module{cfg['module_number']}_production_tracker"
    csv_path = tracker_dir / f"{base_name}.csv"
    xlsx_path = tracker_dir / f"{base_name}.xlsx"
    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "Production Tracker"
    ws.append(fieldnames)
    for row in rows:
        ws.append([row[h] for h in fieldnames])
    header_fill = PatternFill("solid", fgColor="63192A")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for idx, column in enumerate(fieldnames, start=1):
        width = min(60, max(14, len(column) + 4))
        if column in {"Lesson Title", "Script File", "Audio File", "Video File", "Notes"}:
            width = 42
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.freeze_panes = "A2"
    wb.save(xlsx_path)
    logger.info(f"Tracker created: {xlsx_path.name}")
    return xlsx_path, csv_path


def runtime_label(seconds: float | int | None) -> str:
    if not seconds:
        return "Runtime pending"
    seconds = int(round(float(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def generate_moodle_descriptions(cfg: Dict[str, Any], lessons: List[Dict[str, Any]], video_records: List[Dict[str, Any]]) -> Path:
    logger = get_logger()
    logger.info("Step 6/7: Generating Moodle-ready descriptions.")
    video_lookup = {v["lesson_number"]: v for v in video_records}
    desc_dir = OUTPUT / "moodle_descriptions"
    indiv_dir = desc_dir / "individual_lessons"
    indiv_dir.mkdir(parents=True, exist_ok=True)
    module_lines = [f"# Moodle Descriptions — {cfg['course_name']} Module {cfg['module_number']}", "", f"**Module:** {cfg['module_name']}", ""]
    for lesson in lessons:
        script = Path(lesson["narration_file"]).read_text(encoding="utf-8")
        paragraphs = normalize_paragraphs(script)
        v = video_lookup.get(lesson["lesson_number"], {})
        rt = runtime_label(v.get("audio_duration_seconds"))
        summary = short_sentence(paragraphs[0], 180) if paragraphs else "This lesson introduces a Victory Framework concept and prepares learners to apply it in practice."
        keywords = ", ".join(extract_keywords(script, 4))
        filename = Path(v.get("video_file", f"{lesson['lesson_slug']}.mp4")).name
        text = (
            f"{lesson['lesson_number']} — {lesson['lesson_title']}\n\n"
            f"In this lesson, you will learn how to use the Victory Framework to strengthen professional judgment and make more defensible decisions. {summary}\n\n"
            f"Key focus: {keywords}.\n\n"
            f"Video file: {filename}\n"
            f"Estimated runtime: {rt}\n"
        )
        (indiv_dir / f"{lesson['lesson_slug']}.txt").write_text(text, encoding="utf-8")
        module_lines.extend([f"## {lesson['lesson_number']} — {lesson['lesson_title']}", "", text, ""])
    out = desc_dir / f"module{cfg['module_number']}_moodle_descriptions.md"
    out.write_text("\n".join(module_lines).strip() + "\n", encoding="utf-8")
    logger.info(f"Moodle descriptions created: {out.name}")
    return out


def copytree_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)




def flatten_slide_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(flatten_slide_text(v) for v in value)
    return str(value)


def write_slide_text_csv(path: Path, lesson: Dict[str, Any], specs: List[Dict[str, Any]], slide_manifest_lesson: Dict[str, Any], durations: List[float]) -> None:
    fieldnames = [
        "Slide",
        "Slide Type",
        "Eyebrow",
        "Title",
        "Subtitle Or Body",
        "Items Or Steps",
        "Script Paragraphs",
        "Approx Seconds",
        "Rendered Image",
    ]
    slides_by_number = {int(s.get("slide", 0)): s for s in slide_manifest_lesson.get("slides", [])}
    rows: List[Dict[str, Any]] = []
    for idx, spec in enumerate(specs, start=1):
        slide_record = slides_by_number.get(idx, {})
        body_bits = []
        for key in ["subtitle", "body", "quote", "note", "anchor", "left", "right"]:
            if spec.get(key):
                body_bits.append(f"{key}: {flatten_slide_text(spec.get(key))}")
        items_bits = []
        for key in ["items", "steps"]:
            if spec.get(key):
                items_bits.append(f"{key}: {flatten_slide_text(spec.get(key))}")
        rows.append({
            "Slide": idx,
            "Slide Type": spec.get("kind", ""),
            "Eyebrow": spec.get("eyebrow", ""),
            "Title": spec.get("title", ""),
            "Subtitle Or Body": " || ".join(body_bits),
            "Items Or Steps": " || ".join(items_bits),
            "Script Paragraphs": ", ".join(str(i + 1) for i in spec.get("idx", [])),
            "Approx Seconds": round(durations[idx - 1], 2) if idx - 1 < len(durations) else "",
            "Rendered Image": Path(slide_record.get("image", "")).name if slide_record.get("image") else "",
        })
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def safe_pptx_text(value: Any) -> str:
    text = flatten_slide_text(value).replace(" || ", "\n")
    return re.sub(r"\s+", " ", text).strip()


def create_editable_pptx(path: Path, cfg: Dict[str, Any], lesson: Dict[str, Any], specs: List[Dict[str, Any]]) -> bool:
    try:
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.util import Inches, Pt
    except Exception:
        return False

    def rgb(color: Tuple[int, int, int]) -> RGBColor:
        return RGBColor(color[0], color[1], color[2])

    def add_box(slide: Any, left: float, top: float, width: float, height: float, fill_color: Tuple[int, int, int], line_color: Tuple[int, int, int] = BORDER) -> Any:
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(fill_color)
        shape.line.color.rgb = rgb(line_color)
        shape.line.width = Pt(1.2)
        return shape

    def add_text(slide: Any, text: str, left: float, top: float, width: float, height: float, size: int = 24, bold: bool = False, color: Tuple[int, int, int] = INK) -> Any:
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        frame = box.text_frame
        frame.clear()
        frame.word_wrap = True
        p = frame.paragraphs[0]
        run = p.add_run()
        run.text = str(text or "")
        run.font.name = "Arial"
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = rgb(color)
        return box

    def add_card_text(slide: Any, text: str, left: float, top: float, width: float, height: float, size: int = 24) -> None:
        add_box(slide, left, top, width, height, CREAM, BORDER)
        accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left + 0.18), Inches(top + 0.16), Inches(0.06), Inches(height - 0.32))
        accent.fill.solid()
        accent.fill.fore_color.rgb = rgb(GOLD)
        accent.line.color.rgb = rgb(GOLD)
        add_text(slide, text, left + 0.42, top + 0.16, width - 0.58, height - 0.24, size=size, bold=False, color=INK)

    prs = Presentation()
    prs.slide_width = Inches(16)
    prs.slide_height = Inches(9)
    blank = prs.slide_layouts[6]

    for idx, spec in enumerate(specs, start=1):
        slide = prs.slides.add_slide(blank)
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = rgb(MAROON_BLACK)
        bg.line.color.rgb = rgb(MAROON_BLACK)
        add_text(slide, str(cfg.get("course_name", "Victory Framework")).upper(), 0.65, 0.42, 6.0, 0.28, size=15, bold=True, color=CREAM)
        add_text(slide, str(cfg.get("module_name", "")), 0.65, 0.72, 8.2, 0.32, size=14, color=PARCHMENT)
        add_box(slide, 0.65, 1.38, 1.55, 0.36, CREAM, BORDER)
        add_text(slide, str(spec.get("eyebrow", "")).upper(), 0.78, 1.46, 1.30, 0.22, size=11, bold=True, color=MAROON_DEEP)
        add_text(slide, f"Lesson {lesson.get('lesson_number', '')}", 0.65, 8.34, 2.2, 0.28, size=13, color=PARCHMENT)
        add_text(slide, f"{idx:02d} / {len(specs):02d}", 13.2, 8.34, 1.6, 0.28, size=13, color=PARCHMENT)

        kind = spec.get("kind", "")
        title = safe_pptx_text(spec.get("title", ""))
        if kind == "cover":
            add_text(slide, title, 0.78, 2.2, 7.2, 1.6, size=34, bold=True, color=CREAM)
            add_text(slide, safe_pptx_text(spec.get("subtitle", "")), 0.78, 3.95, 6.6, 0.55, size=19, color=PARCHMENT)
            add_box(slide, 9.1, 1.9, 5.4, 4.8, CREAM, BORDER)
            add_text(slide, "VICTORY FRAMEWORK", 9.55, 2.55, 4.4, 0.35, size=16, bold=True, color=MAROON)
            y = 3.35
            for line in ["Professional thinking", "Defensible decisions", "Portable strategy"]:
                add_text(slide, line, 9.55, y, 4.4, 0.45, size=24, bold=True, color=INK)
                y += 0.65
            add_text(slide, safe_pptx_text(spec.get("anchor", "")), 9.55, 5.55, 4.35, 0.85, size=16, color=CHARCOAL)
        elif kind == "statement":
            add_text(slide, title, 0.78, 2.0, 10.0, 1.35, size=31, bold=True, color=CREAM)
            y = 4.0
            for item in spec.get("body", [])[:4]:
                add_card_text(slide, safe_pptx_text(item), 1.05, y, 13.2, 0.72, size=18)
                y += 0.9
        elif kind == "map":
            add_text(slide, title, 0.78, 1.9, 9.4, 1.15, size=30, bold=True, color=CREAM)
            for i, item in enumerate(spec.get("items", [])[:6], start=1):
                col = (i - 1) % 3
                row = (i - 1) // 3
                left = 1.25 + col * 4.35
                top = 4.0 + row * 1.55
                add_box(slide, left, top, 3.55, 1.05, CREAM, BORDER)
                add_text(slide, f"{i:02d}", left + 0.22, top + 0.26, 0.65, 0.35, size=20, bold=True, color=MAROON)
                add_text(slide, safe_pptx_text(item), left + 0.85, top + 0.28, 2.35, 0.55, size=17, color=INK)
        elif kind == "comparison":
            add_text(slide, title, 0.78, 1.9, 9.4, 1.15, size=29, bold=True, color=CREAM)
            pairs = [("Before", spec.get("left", []), 1.1), ("After", spec.get("right", []), 8.45)]
            for heading, items, left in pairs:
                add_box(slide, left, 4.15, 6.1, 2.7, CREAM, BORDER)
                add_text(slide, heading.upper(), left + 0.45, 4.55, 4.9, 0.35, size=16, bold=True, color=MAROON)
                y = 5.15
                for item in items[:3]:
                    add_text(slide, f"• {safe_pptx_text(item)}", left + 0.55, y, 5.1, 0.36, size=15, color=INK)
                    y += 0.52
        elif kind == "flow":
            add_text(slide, title, 0.78, 1.9, 10.0, 1.1, size=29, bold=True, color=CREAM)
            add_text(slide, safe_pptx_text(spec.get("body", "")), 0.78, 3.1, 9.5, 0.55, size=17, color=PARCHMENT)
            steps = spec.get("steps", [])[:5]
            count = max(1, len(steps))
            box_w = min(2.6, 12.8 / count)
            left = 1.05
            for i, step in enumerate(steps, start=1):
                add_box(slide, left, 5.25, box_w, 1.35, CREAM, BORDER)
                add_text(slide, f"{i:02d}", left + 0.22, 5.48, 0.65, 0.35, size=18, bold=True, color=MAROON)
                add_text(slide, safe_pptx_text(step), left + 0.22, 6.0, box_w - 0.4, 0.45, size=15, color=INK)
                left += box_w + 0.28
        elif kind == "quote":
            add_text(slide, title, 0.78, 1.95, 8.6, 1.1, size=28, bold=True, color=CREAM)
            add_box(slide, 1.55, 4.25, 12.55, 2.15, CREAM, BORDER)
            add_text(slide, "KEY TRUTH", 2.0, 4.7, 3.0, 0.35, size=16, bold=True, color=MAROON)
            add_text(slide, safe_pptx_text(spec.get("quote", "")), 2.0, 5.25, 11.0, 0.8, size=24, bold=True, color=INK)
            add_text(slide, safe_pptx_text(spec.get("note", "")), 2.0, 6.75, 9.0, 0.35, size=16, color=PARCHMENT)
        else:
            add_text(slide, str(spec.get("eyebrow", "Lock It In")).upper(), 0.78, 2.25, 4.6, 0.4, size=16, bold=True, color=GOLD)
            add_text(slide, title, 0.78, 3.25, 11.0, 1.8, size=30, bold=True, color=CREAM)
            if spec.get("subtitle"):
                add_card_text(slide, safe_pptx_text(spec.get("subtitle", "")), 0.78, 6.35, 12.4, 0.65, size=18)

    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(path)
    return True


def create_editable_assets(cfg: Dict[str, Any], lessons: List[Dict[str, Any]], slide_manifest: Dict[str, Any], audio_records: List[Dict[str, Any]], video_records: List[Dict[str, Any]]) -> Path:
    logger = get_logger()
    logger.info("Creating editable Canva-friendly assets.")
    root = OUTPUT / "editable_assets"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    audio_lookup = {a["lesson_number"]: a for a in audio_records}
    video_lookup = {v["lesson_number"]: v for v in video_records}
    slide_lookup = {l["lesson_number"]: l for l in slide_manifest.get("lessons", [])}
    lesson_rows: List[Dict[str, Any]] = []

    readme_lines = [
        f"# Editable Assets — {cfg['course_name']} Module {cfg['module_number']}",
        "",
        "This folder is for future editing. The MP4 videos are still final flattened videos, but these files let you make small edits without rebuilding everything from scratch.",
        "",
        "| Folder Or File | How To Use It |",
        "|---|---|",
        "| `editable_slides.pptx` | Upload to Canva or open in PowerPoint. Most text is editable as real text boxes. |",
        "| `rendered_slides/` | Exact PNG slides used by the video. Use these when you only need overlays or quick Canva edits. |",
        "| `audio/` | Narration MP3 files. Reuse these when rebuilding a video after visual edits. |",
        "| `scripts/` | Exact narration text extracted from your module. |",
        "| `slide_text.csv` | Spreadsheet-style list of on-screen text, slide type, and timing notes. |",
        "| `edit_notes.md` | Simple instructions for that lesson. |",
        "",
    ]

    for lesson in lessons:
        lesson_dir = root / lesson["lesson_slug"]
        rendered_dir = lesson_dir / "rendered_slides"
        script_dir = lesson_dir / "scripts"
        audio_dir = lesson_dir / "audio"
        video_dir = lesson_dir / "video"
        for d in [rendered_dir, script_dir, audio_dir, video_dir]:
            d.mkdir(parents=True, exist_ok=True)

        slide_lesson = slide_lookup.get(lesson["lesson_number"], {})
        specs = make_slide_specs(lesson)
        audio = audio_lookup.get(lesson["lesson_number"], {})
        video = video_lookup.get(lesson["lesson_number"], {})
        durations = video.get("allocated_slide_durations_seconds") or []

        for slide in slide_lesson.get("slides", []):
            img = Path(slide.get("image", ""))
            if img.exists():
                shutil.copy2(img, rendered_dir / img.name)
        src_script = Path(lesson.get("narration_file", ""))
        if src_script.exists():
            shutil.copy2(src_script, script_dir / src_script.name)
        audio_value = audio.get("audio_file", "")
        audio_file = Path(audio_value) if audio_value else None
        if audio_file and audio_file.is_file():
            shutil.copy2(audio_file, audio_dir / audio_file.name)
        video_value = video.get("video_file", "")
        video_file = Path(video_value) if video_value else None
        if video_file and video_file.is_file():
            shutil.copy2(video_file, video_dir / video_file.name)

        write_slide_text_csv(lesson_dir / "slide_text.csv", lesson, specs, slide_lesson, [float(x) for x in durations] if durations else [])
        pptx_path = lesson_dir / "editable_slides.pptx"
        pptx_created = create_editable_pptx(pptx_path, cfg, lesson, specs)
        write_json(lesson_dir / "lesson_editing_manifest.json", {
            "lesson_number": lesson["lesson_number"],
            "lesson_title": lesson["lesson_title"],
            "lesson_slug": lesson["lesson_slug"],
            "editable_pptx": str(pptx_path) if pptx_created else "not_created_missing_python_pptx",
            "rendered_slides_dir": str(rendered_dir),
            "script_file": str(src_script) if src_script.exists() else "",
            "audio_file": str(audio_file) if audio_file and audio_file.is_file() else "",
            "video_file": str(video_file) if video_file and video_file.is_file() else "",
            "slide_count": len(slide_lesson.get("slides", [])),
            "note": "PPTX text boxes are editable. Rendered PNG slides match the final video exactly but are flattened images.",
        })

        edit_notes = [
            f"# Editing Notes — Lesson {lesson['lesson_number']} {lesson['lesson_title']}",
            "",
            "Use `editable_slides.pptx` when you want to edit text boxes, colors, or basic layout in PowerPoint or Canva. Use `rendered_slides/` when you only need to cover a small area and add text or graphics on top in Canva.",
            "",
            "If you change slide visuals but keep the same narration, reuse the MP3 in the `audio/` folder. If you change the narration wording, regenerate the MP3 first so the voice matches the new script.",
            "",
            "| Item | Location |",
            "|---|---|",
            f"| Editable slide deck | `{pptx_path.name if pptx_created else 'Not created. Run SETUP_WINDOWS.bat to install python-pptx, then rerun RUN_ME.bat.'}` |",
            f"| Exact rendered slides | `rendered_slides/` |",
            f"| Narration script | `scripts/{src_script.name if src_script.exists() else ''}` |",
            f"| Narration audio | `audio/{audio_file.name if audio_file and audio_file.is_file() else ''}` |",
            f"| Finished video | `video/{video_file.name if video_file and video_file.is_file() else ''}` |",
            "",
            "After editing in Canva, export a new MP4 from Canva and replace the original lesson video only after you review it.",
        ]
        (lesson_dir / "edit_notes.md").write_text("\n".join(edit_notes) + "\n", encoding="utf-8")
        lesson_rows.append({
            "Lesson Number": lesson["lesson_number"],
            "Lesson Title": lesson["lesson_title"],
            "Editable Folder": str(lesson_dir),
            "PPTX Created": "Yes" if pptx_created else "No - run setup to install python-pptx",
            "Rendered Slides": len(list(rendered_dir.glob("*.png"))),
            "Audio Included": "Yes" if audio_file and audio_file.is_file() else "No",
            "Video Included": "Yes" if video_file and video_file.is_file() else "No",
        })

    with (root / "editable_assets_index.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = list(lesson_rows[0].keys()) if lesson_rows else ["Lesson Number", "Lesson Title"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(lesson_rows)

    readme_lines.extend([f"## {row['Lesson Number']} — {row['Lesson Title']}" for row in lesson_rows])
    (root / "README_EDITABLE_ASSETS.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    logger.info(f"Editable assets created for {len(lesson_rows)} lesson(s).")
    return root

def build_review_package(cfg: Dict[str, Any], tracker_paths: Tuple[Path, Path], moodle_path: Path, video_records: List[Dict[str, Any]]) -> Path:
    review = OUTPUT / "review_package"
    if review.exists():
        shutil.rmtree(review)
    (review / "videos").mkdir(parents=True, exist_ok=True)
    (review / "trackers").mkdir(parents=True, exist_ok=True)
    (review / "moodle_descriptions").mkdir(parents=True, exist_ok=True)
    (review / "manifests").mkdir(parents=True, exist_ok=True)
    for v in video_records:
        vf = Path(v.get("video_file", ""))
        if vf.exists():
            shutil.copy2(vf, review / "videos" / vf.name)
    for p in tracker_paths:
        if p.exists():
            shutil.copy2(p, review / "trackers" / p.name)
    if moodle_path.exists():
        shutil.copy2(moodle_path, review / "moodle_descriptions" / moodle_path.name)
    indiv = OUTPUT / "moodle_descriptions" / "individual_lessons"
    if indiv.exists():
        copytree_contents(indiv, review / "moodle_descriptions" / "individual_lessons")
    for manifest in MANIFESTS.glob("*.json"):
        shutil.copy2(manifest, review / "manifests" / manifest.name)
    editable_assets = OUTPUT / "editable_assets"
    if editable_assets.exists():
        copytree_contents(editable_assets, review / "editable_assets")
    summary = [
        f"# Validation Summary — {cfg['course_name']} Module {cfg['module_number']}",
        "",
        f"**Module:** {cfg['module_name']}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Item | Count |",
        "|---|---:|",
        f"| Videos | {len([v for v in video_records if Path(v.get('video_file', '')).exists()])} |",
        f"| Manifests | {len(list((review / 'manifests').glob('*.json')))} |",
        f"| Tracker files | {len(list((review / 'trackers').glob('*')))} |",
        f"| Editable asset folders | {len(list((review / 'editable_assets').iterdir())) if (review / 'editable_assets').exists() else 0} |",
        "",
        "The narration scripts were extracted to `output/scripts` and used as the narration source without rewriting. Review all videos before uploading to Moodle. Future-editing assets are available in `editable_assets`.",
    ]
    (review / "VALIDATION_SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return review


def upload_to_drive(cfg: Dict[str, Any], review_package: Path) -> Optional[Path]:
    logger = get_logger()
    logger.info("Step 7/7: Handling optional Google Drive delivery copy.")
    delivery = cfg.get("delivery", {})
    if not delivery.get("copy_to_google_drive_sync_folder", False):
        logger.info("Google Drive sync copy is disabled. Review package remains local.")
        return None
    folder = delivery.get("google_drive_sync_folder", "")
    if not folder:
        raise RuntimeError("Google Drive sync copy is enabled, but google_drive_sync_folder is blank.")
    drive_root = Path(folder).expanduser()
    if not drive_root.exists():
        raise RuntimeError(f"Google Drive sync folder does not exist: {drive_root}")
    dest = drive_root / f"VictoryVideoAgent_Module{cfg['module_number']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(review_package, dest)
    logger.info(f"Copied review package to Google Drive sync folder: {dest}")
    return dest


def run_pipeline() -> Dict[str, Any]:
    ensure_dirs()
    logger = get_logger()
    cfg = load_config()
    logger.info("Starting Victory Video Production Agent.")
    lessons = extract_scripts(cfg)
    slide_manifest = render_slides(cfg, lessons)
    audio_records = generate_narration(cfg, lessons)
    video_records = assemble_videos(cfg, slide_manifest, audio_records) if audio_records else []
    editable_assets = create_editable_assets(cfg, lessons, slide_manifest, audio_records, video_records)
    tracker_paths = create_tracker(cfg, lessons, audio_records, video_records)
    moodle_path = generate_moodle_descriptions(cfg, lessons, video_records)
    review_package = build_review_package(cfg, tracker_paths, moodle_path, video_records)
    drive_copy = upload_to_drive(cfg, review_package)
    result = {
        "status": "complete",
        "review_package": str(review_package),
        "drive_copy": str(drive_copy) if drive_copy else "disabled",
        "videos": len(video_records),
        "editable_assets": str(editable_assets),
        "tracker_xlsx": str(tracker_paths[0]),
        "moodle_descriptions": str(moodle_path),
    }
    write_json(MANIFESTS / "run_result.json", result)
    logger.info("Victory Video Production Agent completed successfully.")
    return result


def main() -> None:
    try:
        result = run_pipeline()
        print("\nDONE. Review package:", result["review_package"])
        if result.get("drive_copy") and result["drive_copy"] != "disabled":
            print("Copied to Google Drive sync folder:", result["drive_copy"])
    except Exception as exc:
        logger = get_logger()
        logger.info(f"ERROR: {exc}")
        print("\nERROR:", exc)
        print(f"See logs in: {LOGS}")
        sys.exit(1)


if __name__ == "__main__":
    main()
