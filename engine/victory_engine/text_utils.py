"""Small text utilities shared by the parser and the slide renderer.

Transplanted from `agent/pipeline.py` with identical behavior (see VIDEO_ENGINE.md §4-5).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List


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


def title_from_filename(path: Path) -> str:
    title = re.sub(r"[_\-]+", " ", path.stem).strip()
    return title.title() if title else "Untitled"


def short_sentence(paragraph: str, max_chars: int = 92) -> str:
    pieces = re.split(r"(?<=[.!?])\s+", paragraph.strip())
    sentence = pieces[0] if pieces and pieces[0] else paragraph.strip()
    sentence = re.sub(r"\s+", " ", sentence)
    if len(sentence) > max_chars:
        sentence = sentence[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return sentence


_STOPWORDS = set(
    "the a an and or but if then this that these those you your we our to of in for on with "
    "from as is are was were be being been it its at by into about through across not do does "
    "did can will would should could have has had they their them one all more most just very"
    .split()
)


def extract_keywords(text: str, limit: int = 5) -> List[str]:
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z']+", text)]
    counts = {}
    for w in words:
        if len(w) < 4 or w in _STOPWORDS:
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


def runtime_label(seconds) -> str:
    if not seconds:
        return "Runtime pending"
    seconds = int(round(float(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"
