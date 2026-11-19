from pathlib import Path

from victory_engine.readers import read_markdown_paragraphs, read_txt_paragraphs


def test_txt_blank_line_paragraphs(tmp_path: Path):
    path = tmp_path / "doc.txt"
    path.write_text("First paragraph.\n\nSecond paragraph\nstill second.\n", encoding="utf-8")
    paragraphs = read_txt_paragraphs(path)
    assert paragraphs == ["First paragraph.", "Second paragraph still second."]


def test_txt_force_flush_on_key_line_mid_paragraph(tmp_path: Path):
    path = tmp_path / "doc.txt"
    path.write_text("Some trailing narration\nLESSON: 2.1 Next Lesson\nMore narration.\n", encoding="utf-8")
    paragraphs = read_txt_paragraphs(path)
    assert paragraphs == ["Some trailing narration", "LESSON: 2.1 Next Lesson", "More narration."]


def test_markdown_heading_and_list_marker_stripped(tmp_path: Path):
    path = tmp_path / "doc.md"
    path.write_text("## MODULE 1: Foundations\n\n- A bullet point paragraph.\n", encoding="utf-8")
    paragraphs = read_markdown_paragraphs(path)
    assert paragraphs[0] == "MODULE 1: Foundations"
    assert paragraphs[1] == "A bullet point paragraph."


def test_markdown_bold_key_is_recognized(tmp_path: Path):
    path = tmp_path / "doc.md"
    path.write_text(
        "**VIDEO DESCRIPTION:** A quick intro to the lesson.\n\n"
        "Some narration paragraph that follows.\n",
        encoding="utf-8",
    )
    paragraphs = read_markdown_paragraphs(path)
    assert paragraphs[0] == "VIDEO DESCRIPTION: A quick intro to the lesson."
    assert paragraphs[1] == "Some narration paragraph that follows."


def test_markdown_bold_label_mid_line_is_stripped(tmp_path: Path):
    path = tmp_path / "doc.md"
    path.write_text("**RESOURCE TYPE:** pdf\n", encoding="utf-8")
    paragraphs = read_markdown_paragraphs(path)
    assert paragraphs[0] == "RESOURCE TYPE: pdf"
