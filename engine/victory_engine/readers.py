"""Document readers: DOCX, PDF, TXT, and Markdown -> a flat list of paragraph strings.

The legacy engine only read `.docx` (python-docx) and `.txt` (blank-line paragraphs, forcing a
flush whenever a lesson-heading line was detected mid-run). This module keeps both readers and
adds PDF (pypdf) and Markdown, normalizing all four formats to the same paragraph-list shape so
`parser.py` has exactly one grammar to parse regardless of upload format.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".txt", ".md", ".markdown"}


def _flush_on_key_lines(text: str) -> List[str]:
    """Blank-line paragraph splitting, but also force a flush on any recognized key line
    (COURSE:, MODULE:, LESSON:, RESOURCE:, etc.) even without a blank line before it — mirrors
    the legacy `read_text_paragraphs` behavior for lesson headings, generalized to every key
    line the parser understands."""
    from .parser import match_key_line  # local import avoids a circular import at module load

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs: List[str] = []
    current: List[str] = []

    def flush() -> None:
        if current:
            paragraphs.append(" ".join(line.strip() for line in current if line.strip()))
            current.clear()

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if match_key_line(line) is not None:
            flush()
            paragraphs.append(line)
            continue
        current.append(line)
    flush()
    return [p for p in paragraphs if p]


def read_docx_paragraphs(path: Path) -> List[str]:
    try:
        from docx import Document
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("python-docx is not installed. Run `pip install -r requirements.txt`.") from exc
    doc = Document(str(path))
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def read_pdf_paragraphs(path: Path) -> List[str]:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pypdf is not installed. Run `pip install -r requirements.txt`.") from exc
    reader = PdfReader(str(path))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return _flush_on_key_lines("\n\n".join(pages_text))


def read_txt_paragraphs(path: Path) -> List[str]:
    return _flush_on_key_lines(path.read_text(encoding="utf-8"))


def read_markdown_paragraphs(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8")
    # Strip Markdown heading markers ("## MODULE 1: Title" -> "MODULE 1: Title"), list/quote
    # markers, and bold emphasis ("**VIDEO DESCRIPTION:**" -> "VIDEO DESCRIPTION:") so the same
    # key-line grammar recognizes a key line however it was formatted; content lines are
    # otherwise untouched. Bold is stripped globally per line, not just at the start, since
    # authors commonly bold just the label before the colon rather than the whole line.
    lines = []
    for raw_line in text.split("\n"):
        line = re.sub(r"^\s*#{1,6}\s*", "", raw_line)
        line = re.sub(r"^\s*[-*>]\s+", "", line)
        line = re.sub(r"\*\*|__", "", line)
        lines.append(line)
    return _flush_on_key_lines("\n".join(lines))


def read_paragraphs(path: Path) -> List[str]:
    ext = path.suffix.lower()
    if ext == ".docx":
        return read_docx_paragraphs(path)
    if ext == ".pdf":
        return read_pdf_paragraphs(path)
    if ext in (".md", ".markdown"):
        return read_markdown_paragraphs(path)
    if ext == ".txt":
        return read_txt_paragraphs(path)
    raise ValueError(f"Unsupported curriculum document type: {ext}. Supported: {sorted(SUPPORTED_EXTENSIONS)}")
