"""Curriculum grammar: paragraphs -> Course/Module/Lesson/Resource structure.

This is a strict superset of the legacy `agent/pipeline.py` grammar (see VIDEO_ENGINE.md §4):
every legacy document still parses identically (narration text is never rewritten, sequential
numbering still applies when LESSON ORDER: is absent), and the additive keys below only add
structure that the legacy parser had no slot for.

Key lines recognized (case-insensitive, "KEY: value" or bare "KEY:" with the value starting on
the next non-key line):
    COURSE: <title>                MODULE: <number>. <title>  (or "MODULE <n>: <title>")
    COURSE DESCRIPTION: <text>      MODULE DESCRIPTION: <text>
    LESSON: <number>. <title>      (or "LESSON <n>: <title>", or "Lesson 3.1: Title")
    LESSON ORDER: <number>          TYPE: <video|resource|quiz>
    SCRIPT:                         VIDEO DESCRIPTION: <text>
    LESSON DESCRIPTION: <text>      RESOURCE: <title>
    RESOURCE TITLE: <text>          RESOURCE DESCRIPTION: <text>
    RESOURCE INSTRUCTIONS: <text>   RESOURCE FILENAME: <text>
    RESOURCE TYPE: <pdf|doc|link|file>
    KNOWLEDGE CHECK: <text>         PRODUCTION INSTRUCTIONS: <text>
    TAGS: <comma, separated, tags>
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .text_utils import slugify

_KEY_PATTERN = re.compile(
    r"^(COURSE DESCRIPTION|MODULE DESCRIPTION|LESSON DESCRIPTION|LESSON ORDER|"
    r"VIDEO DESCRIPTION|RESOURCE TITLE|RESOURCE DESCRIPTION|RESOURCE INSTRUCTIONS|"
    r"RESOURCE FILENAME|RESOURCE TYPE|KNOWLEDGE CHECK|PRODUCTION INSTRUCTIONS|"
    r"COURSE|MODULE|LESSON|TYPE|SCRIPT|RESOURCE|TAGS)\s*:\s*(.*)$",
    re.IGNORECASE,
)

_MODULE_HEADING = re.compile(r"^MODULE\s+(\d+)\s*[:.]\s*(.*)$", re.IGNORECASE)
_LESSON_HEADING = re.compile(r"^LESSON\s+(\d+(?:\.\d+)?)\s*[:.]\s*(.*)$", re.IGNORECASE)
# Legacy numbered-heading fallback: "Lesson 3.1: Title" or "3.1 Title" with no explicit key line.
_NUMBERED_FALLBACK = re.compile(r"^(?:Lesson\s+)?(\d+)\.(\d+)\s*[:.\-]?\s*(.+)$", re.IGNORECASE)


def match_key_line(line: str) -> Optional[tuple]:
    """Return (KEY, value) if `line` opens a recognized key line, else None. Used by readers.py
    to force a paragraph flush at document structure boundaries regardless of source format."""
    m = _KEY_PATTERN.match(line.strip())
    if m:
        return (m.group(1).upper(), m.group(2).strip())
    if _MODULE_HEADING.match(line.strip()):
        return ("MODULE", line.strip())
    if _LESSON_HEADING.match(line.strip()):
        return ("LESSON", line.strip())
    return None


@dataclass
class ParsedResource:
    title: str = ""
    description: str = ""
    instructions: str = ""
    filename: str = ""
    resource_type: str = "file"


@dataclass
class ParsedLesson:
    number: str = ""
    order: Optional[int] = None
    title: str = "Untitled Lesson"
    lesson_type: str = "video"
    description: str = ""
    video_description: str = ""
    script_lines: List[str] = field(default_factory=list)
    knowledge_checks: List[str] = field(default_factory=list)
    production_instructions: str = ""
    tags: List[str] = field(default_factory=list)
    resources: List[ParsedResource] = field(default_factory=list)
    sequence_index: int = 0

    @property
    def script_text(self) -> str:
        return "\n\n".join(self.script_lines).strip()

    @property
    def script_hash(self) -> str:
        return hashlib.sha256(self.script_text.encode("utf-8")).hexdigest()

    @property
    def slug(self) -> str:
        return slugify(f"{self.number or self.sequence_index}-{self.title}")

    @property
    def sort_key(self) -> tuple:
        if self.order is not None:
            return (self.order, self.sequence_index)
        try:
            return (float(self.number), self.sequence_index)
        except (TypeError, ValueError):
            return (float("inf"), self.sequence_index)


@dataclass
class ParsedModule:
    number: str = ""
    title: str = "Untitled Module"
    description: str = ""
    lessons: List[ParsedLesson] = field(default_factory=list)
    sequence_index: int = 0

    @property
    def slug(self) -> str:
        return slugify(f"{self.number or self.sequence_index}-{self.title}")

    @property
    def sort_key(self) -> tuple:
        try:
            return (float(self.number), self.sequence_index)
        except (TypeError, ValueError):
            return (float("inf"), self.sequence_index)


@dataclass
class ParsedCourse:
    title: str = "Untitled Course"
    description: str = ""
    modules: List[ParsedModule] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slugify(self.title)


class _Cursor:
    """Tracks which lesson/resource/module a non-key paragraph currently belongs to."""

    def __init__(self, course: ParsedCourse, fallback_title: str):
        self.course = course
        self.fallback_title = fallback_title
        self.module: Optional[ParsedModule] = None
        self.lesson: Optional[ParsedLesson] = None
        self.resource: Optional[ParsedResource] = None
        self.active_field: Optional[str] = None  # which multi-line field free text appends to

    def ensure_module(self) -> ParsedModule:
        if self.module is None:
            self.module = ParsedModule(sequence_index=len(self.course.modules))
            self.course.modules.append(self.module)
        return self.module

    def ensure_lesson(self) -> ParsedLesson:
        module = self.ensure_module()
        if self.lesson is None:
            self.lesson = ParsedLesson(sequence_index=len(module.lessons))
            module.lessons.append(self.lesson)
        return self.lesson

    def new_module(self, number: str, title: str) -> ParsedModule:
        module = ParsedModule(number=number, title=title or f"Module {number}", sequence_index=len(self.course.modules))
        self.course.modules.append(module)
        self.module = module
        self.lesson = None
        self.resource = None
        return module

    def new_lesson(self, number: str, title: str) -> ParsedLesson:
        module = self.ensure_module()
        lesson = ParsedLesson(number=number, title=title or f"Lesson {number}", sequence_index=len(module.lessons))
        module.lessons.append(lesson)
        self.lesson = lesson
        self.resource = None
        return lesson

    def new_resource(self, title: str) -> ParsedResource:
        lesson = self.ensure_lesson()
        resource = ParsedResource(title=title)
        lesson.resources.append(resource)
        self.resource = resource
        return resource

    def append_free_text(self, text: str) -> None:
        """A paragraph with no key line attaches to whichever field was most recently opened."""
        if not text:
            return
        target = self.active_field
        if target == "course_description":
            self.course.description = (self.course.description + "\n\n" + text).strip()
        elif target == "module_description" and self.module:
            self.module.description = (self.module.description + "\n\n" + text).strip()
        elif target == "lesson_description" and self.lesson:
            self.lesson.description = (self.lesson.description + "\n\n" + text).strip()
        elif target == "video_description" and self.lesson:
            self.lesson.video_description = (self.lesson.video_description + "\n\n" + text).strip()
        elif target == "resource_description" and self.resource:
            self.resource.description = (self.resource.description + "\n\n" + text).strip()
        elif target == "resource_instructions" and self.resource:
            self.resource.instructions = (self.resource.instructions + "\n\n" + text).strip()
        elif target == "production_instructions" and self.lesson:
            self.lesson.production_instructions = (self.lesson.production_instructions + "\n\n" + text).strip()
        elif target == "script" and self.lesson:
            self.lesson.script_lines.append(text)
        else:
            # No active field: legacy behavior is to treat untagged paragraphs as narration for
            # whatever lesson is currently open (preserves old scripts with no SCRIPT: marker).
            if self.lesson is not None:
                self.lesson.script_lines.append(text)


def _numbered_fallback_lesson(cursor: _Cursor, line: str) -> bool:
    m = _NUMBERED_FALLBACK.match(line.strip())
    if not m:
        return False
    module_no, lesson_no, title = m.group(1), m.group(2), m.group(3).strip()
    number = f"{module_no}.{lesson_no}"
    if cursor.module is None or cursor.module.number != module_no:
        cursor.new_module(module_no, f"Module {module_no}")
    cursor.new_lesson(number, title)
    cursor.active_field = "script"
    return True


def parse_curriculum(paragraphs: List[str], fallback_title: str = "Untitled Course") -> ParsedCourse:
    course = ParsedCourse(title=fallback_title)
    cursor = _Cursor(course, fallback_title)
    course_title_set = False

    for raw in paragraphs:
        line = raw.strip()
        if not line:
            continue

        matched = _KEY_PATTERN.match(line)
        module_heading = _MODULE_HEADING.match(line)
        lesson_heading = _LESSON_HEADING.match(line)

        if module_heading and not matched:
            cursor.new_module(module_heading.group(1), module_heading.group(2).strip())
            cursor.active_field = None
            continue

        if lesson_heading and not matched:
            cursor.new_lesson(lesson_heading.group(1), lesson_heading.group(2).strip())
            cursor.active_field = "script"
            continue

        if not matched:
            if _numbered_fallback_lesson(cursor, line):
                continue
            cursor.append_free_text(line)
            continue

        key, value = matched.group(1).upper(), matched.group(2).strip()

        if key == "COURSE":
            course.title = value or course.title
            course_title_set = True
            cursor.active_field = None
        elif key == "COURSE DESCRIPTION":
            course.description = value
            cursor.active_field = "course_description"
        elif key == "MODULE":
            m = re.match(r"^(\d+)\s*(?:[:.]\s*)?(.*)$", value)
            number, title = (m.group(1), m.group(2).strip()) if m else ("", value)
            cursor.new_module(number, title)
            cursor.active_field = None
        elif key == "MODULE DESCRIPTION":
            cursor.ensure_module().description = value
            cursor.active_field = "module_description"
        elif key == "LESSON":
            m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:[:.]\s*)?(.*)$", value)
            number, title = (m.group(1), m.group(2).strip()) if m else ("", value)
            cursor.new_lesson(number, title)
            cursor.active_field = "script"
        elif key == "LESSON ORDER":
            try:
                cursor.ensure_lesson().order = int(value)
            except ValueError:
                pass
            cursor.active_field = None
        elif key == "TYPE":
            cursor.ensure_lesson().lesson_type = value.lower() or "video"
            cursor.active_field = None
        elif key == "LESSON DESCRIPTION":
            cursor.ensure_lesson().description = value
            cursor.active_field = "lesson_description"
        elif key == "VIDEO DESCRIPTION":
            cursor.ensure_lesson().video_description = value
            cursor.active_field = "video_description"
        elif key == "SCRIPT":
            lesson = cursor.ensure_lesson()
            if value:
                lesson.script_lines.append(value)
            cursor.active_field = "script"
        elif key == "RESOURCE":
            cursor.new_resource(value or "Resource")
            cursor.active_field = None
        elif key == "RESOURCE TITLE":
            (cursor.resource or cursor.new_resource(value)).title = value or (cursor.resource.title if cursor.resource else "Resource")
            cursor.active_field = None
        elif key == "RESOURCE DESCRIPTION":
            cursor.ensure_lesson()
            if cursor.resource is None:
                cursor.new_resource("Resource")
            cursor.resource.description = value
            cursor.active_field = "resource_description"
        elif key == "RESOURCE INSTRUCTIONS":
            cursor.ensure_lesson()
            if cursor.resource is None:
                cursor.new_resource("Resource")
            cursor.resource.instructions = value
            cursor.active_field = "resource_instructions"
        elif key == "RESOURCE FILENAME":
            cursor.ensure_lesson()
            if cursor.resource is None:
                cursor.new_resource(title_from_filename_str(value))
            cursor.resource.filename = value
            cursor.active_field = None
        elif key == "RESOURCE TYPE":
            cursor.ensure_lesson()
            if cursor.resource is None:
                cursor.new_resource("Resource")
            cursor.resource.resource_type = value.lower() or "file"
            cursor.active_field = None
        elif key == "KNOWLEDGE CHECK":
            cursor.ensure_lesson().knowledge_checks.append(value)
            cursor.active_field = None
        elif key == "PRODUCTION INSTRUCTIONS":
            cursor.ensure_lesson().production_instructions = value
            cursor.active_field = "production_instructions"
        elif key == "TAGS":
            cursor.ensure_lesson().tags = [t.strip() for t in value.split(",") if t.strip()]
            cursor.active_field = None

    if not course_title_set and course.modules and course.modules[0].lessons:
        pass  # keep fallback_title; nothing in the doc supplied an explicit COURSE: line.

    _assign_sequential_numbers(course)
    for module in course.modules:
        module.lessons.sort(key=lambda l: l.sort_key)
    course.modules.sort(key=lambda m: m.sort_key)
    return course


def title_from_filename_str(value: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", value)
    title = re.sub(r"[_\-]+", " ", stem).strip()
    return title.title() if title else "Resource"


def _assign_sequential_numbers(course: ParsedCourse) -> None:
    """Legacy behavior: when a module/lesson had no explicit number, number it sequentially in
    document order rather than leaving it blank."""
    for m_idx, module in enumerate(course.modules, start=1):
        if not module.number:
            module.number = str(m_idx)
        for l_idx, lesson in enumerate(module.lessons, start=1):
            if not lesson.number:
                lesson.number = f"{module.number}.{l_idx}"
