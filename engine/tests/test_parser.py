from victory_engine.parser import match_key_line, parse_curriculum


def _paragraphs_from_text(text: str):
    """Mirror readers._flush_on_key_lines without importing readers (avoids the docx/pypdf
    import chain for pure-parser tests)."""
    paragraphs = []
    current = []

    def flush():
        if current:
            paragraphs.append(" ".join(l.strip() for l in current if l.strip()))
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


SAMPLE = """COURSE: Negotiation Mastery
COURSE DESCRIPTION: Learn to negotiate well.

MODULE: 1. Foundations
MODULE DESCRIPTION: The basics.

LESSON: 1.1 Introduction
TYPE: video
VIDEO DESCRIPTION: A quick intro.
SCRIPT:
Welcome to the course.

This is the second paragraph of narration.

RESOURCE: Cheat Sheet
RESOURCE DESCRIPTION: A quick reference.
RESOURCE FILENAME: cheat_sheet.pdf
RESOURCE TYPE: pdf

LESSON 1.2: Core Concepts
This is narration with no SCRIPT: marker (legacy style).

KNOWLEDGE CHECK: What are the four phases of a negotiation?
TAGS: negotiation, business, communication
"""


def test_course_and_module_metadata():
    course = parse_curriculum(_paragraphs_from_text(SAMPLE))
    assert course.title == "Negotiation Mastery"
    assert course.description == "Learn to negotiate well."
    assert len(course.modules) == 1
    assert course.modules[0].number == "1"
    assert course.modules[0].title == "Foundations"
    assert course.modules[0].description == "The basics."


def test_lesson_numbers_with_dotted_notation():
    course = parse_curriculum(_paragraphs_from_text(SAMPLE))
    lessons = course.modules[0].lessons
    assert len(lessons) == 2
    assert lessons[0].number == "1.1"
    assert lessons[0].title == "Introduction"
    assert lessons[1].number == "1.2"
    assert lessons[1].title == "Core Concepts"


def test_script_text_never_rewritten():
    course = parse_curriculum(_paragraphs_from_text(SAMPLE))
    lesson = course.modules[0].lessons[0]
    assert lesson.script_text == "Welcome to the course.\n\nThis is the second paragraph of narration."
    assert lesson.video_description == "A quick intro."


def test_legacy_style_lesson_with_no_script_marker():
    course = parse_curriculum(_paragraphs_from_text(SAMPLE))
    lesson = course.modules[0].lessons[1]
    assert "This is narration with no SCRIPT" in lesson.script_text
    assert lesson.knowledge_checks == ["What are the four phases of a negotiation?"]
    assert lesson.tags == ["negotiation", "business", "communication"]


def test_resource_parsing():
    course = parse_curriculum(_paragraphs_from_text(SAMPLE))
    lesson = course.modules[0].lessons[0]
    assert len(lesson.resources) == 1
    resource = lesson.resources[0]
    assert resource.title == "Cheat Sheet"
    assert resource.description == "A quick reference."
    assert resource.filename == "cheat_sheet.pdf"
    assert resource.resource_type == "pdf"


def test_numbered_heading_fallback_with_no_key_lines():
    text = "3.1 Advanced Tactics\n\nSome narration paragraph here about advanced tactics."
    course = parse_curriculum(_paragraphs_from_text(text), fallback_title="Fallback Course")
    assert course.title == "Fallback Course"
    assert len(course.modules) == 1
    assert course.modules[0].number == "3"
    lesson = course.modules[0].lessons[0]
    assert lesson.number == "3.1"
    assert lesson.title == "Advanced Tactics"
    assert "Some narration paragraph" in lesson.script_text


def test_sequential_numbering_when_no_explicit_numbers():
    text = (
        "MODULE: Getting Started\n"
        "LESSON: Welcome\n"
        "Some narration.\n"
        "LESSON: Next Steps\n"
        "More narration.\n"
    )
    course = parse_curriculum(_paragraphs_from_text(text), fallback_title="Course")
    assert course.modules[0].number == "1"
    assert course.modules[0].lessons[0].number == "1.1"
    assert course.modules[0].lessons[1].number == "1.2"
