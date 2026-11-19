"""Moodle lesson description text generation (see VIDEO_ENGINE.md §9).

The legacy engine never called the Moodle API directly — it only generated the HTML description
text a course author would paste into a Moodle activity by hand. The web app's Node layer now
calls the Moodle web services API directly (see server/src/integrations/moodle.ts) using this
same generated HTML as the activity's `intro` field, so the text this module produces is exactly
what ends up on the Moodle page — nothing is re-derived on the Node side.
"""
from __future__ import annotations

import html
from typing import List

from .parser import ParsedLesson


def _esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def lesson_description_html(lesson: ParsedLesson) -> str:
    parts: List[str] = []
    if lesson.description:
        parts.append(f"<p>{_esc(lesson.description)}</p>")
    elif lesson.video_description:
        parts.append(f"<p>{_esc(lesson.video_description)}</p>")

    if lesson.knowledge_checks:
        parts.append("<h4>Knowledge Check</h4><ul>")
        for check in lesson.knowledge_checks:
            parts.append(f"<li>{_esc(check)}</li>")
        parts.append("</ul>")

    if lesson.tags:
        tag_str = ", ".join(_esc(t) for t in lesson.tags)
        parts.append(f'<p class="victory-tags"><em>Tags: {tag_str}</em></p>')

    if not parts:
        parts.append(f"<p>{_esc(lesson.title)}</p>")

    return "\n".join(parts)


def module_description_html(module_title: str, module_description: str) -> str:
    if module_description:
        return f"<p>{_esc(module_description)}</p>"
    return f"<p>{_esc(module_title)}</p>"
