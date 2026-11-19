from pathlib import Path

from victory_engine.brand import DEFAULT_BRAND
from victory_engine.video import (
    MAX_CAPTION_CHARS,
    MIN_SHORT_SECONDS,
    MIN_STATEMENT_SECONDS,
    SlideTiming,
    _captions_filter,
    _split_caption_cues,
    paragraph_weights,
    write_captions_srt,
)


def test_weights_sum_to_total_duration():
    texts = ["short", "a medium length paragraph of text", "a much longer paragraph with many more words in it than the others"]
    weights = paragraph_weights(texts, 60.0)
    assert len(weights) == 3
    assert abs(sum(weights) - 60.0) < 1e-6


def test_longer_text_gets_more_time_when_floor_not_binding():
    texts = ["short text here", "a substantially longer paragraph of narration text that should receive more screen time"]
    weights = paragraph_weights(texts, 120.0)
    assert weights[1] > weights[0]


def test_single_slide_gets_entire_duration():
    weights = paragraph_weights(["only slide"], 42.5)
    assert len(weights) == 1
    assert abs(weights[0] - 42.5) < 1e-6


def test_empty_list_returns_empty():
    assert paragraph_weights([], 30.0) == []


def test_floors_are_respected_when_total_duration_is_generous():
    texts = ["a", "b", "c"]
    floors = [MIN_STATEMENT_SECONDS, MIN_SHORT_SECONDS, MIN_SHORT_SECONDS]
    weights = paragraph_weights(texts, 100.0, floors=floors)
    # Equal-length texts with a generous total duration: each slide should clear its floor.
    assert weights[0] >= MIN_STATEMENT_SECONDS - 1e-6
    assert weights[1] >= MIN_SHORT_SECONDS - 1e-6
    assert abs(sum(weights) - 100.0) < 1e-6


def test_tight_total_duration_scales_floors_down_proportionally():
    # When the total duration can't fit every slide's floor, floors are soft: everything is
    # rescaled to fit exactly rather than overshooting the narration's real length.
    texts = ["a", "bb", "c"]
    weights = paragraph_weights(texts, 10.0)
    assert abs(sum(weights) - 10.0) < 1e-6
    assert all(w > 0 for w in weights)


def test_split_caption_cues_keeps_each_cue_short():
    # A real multi-sentence narration paragraph must never come back as a single long cue —
    # that's exactly what made a slide's entire narration render as one screen-filling caption.
    paragraph = (
        "Operations asks how we get the work done effectively. A hospital schedules patients "
        "and prepares equipment; an insurer processes claims; a retailer manages inventory. "
        "Money asks how we generate, manage and protect financial resources."
    )
    cues = _split_caption_cues(paragraph)
    assert len(cues) > 1
    assert all(len(c) <= MAX_CAPTION_CHARS for c in cues)


def test_split_caption_cues_reconstructs_the_text():
    paragraph = "First sentence here. Second sentence follows. Third one closes it out."
    cues = _split_caption_cues(paragraph)
    assert " ".join(cues) == paragraph


def test_split_caption_cues_handles_a_single_overlong_sentence():
    # No sentence-ending punctuation at all, and longer than the cap: must still split, not
    # return one giant cue.
    paragraph = " ".join(["word"] * 60)
    cues = _split_caption_cues(paragraph)
    assert len(cues) > 1
    assert all(len(c) <= MAX_CAPTION_CHARS for c in cues)


def test_write_captions_srt_splits_long_slide_text_into_multiple_timed_cues():
    long_text = (
        "Operations asks how we get the work done effectively. A hospital schedules patients "
        "and prepares equipment; an insurer processes claims; a retailer manages inventory. "
        "Money asks how we generate, manage and protect financial resources."
    )
    timing = SlideTiming(path=Path("unused.png"), start=10.0, duration=20.0, text=long_text)
    out_path = Path(__file__).parent / "_tmp_captions.srt"
    srt_path = write_captions_srt([timing], out_path)
    content = srt_path.read_text(encoding="utf-8")
    srt_path.unlink()

    # Multiple numbered cues, each within the slide's time window, none of them the whole text.
    assert content.count("\n\n") >= 2
    assert long_text not in content
    for line in content.split("\n"):
        if "-->" not in line and line.strip() and not line.strip().isdigit():
            assert len(line) <= MAX_CAPTION_CHARS


def test_captions_filter_pins_original_size_to_the_real_frame():
    # Without this, libass interprets FontSize against its 384x288 ASS default instead of the
    # actual video resolution, rendering captions roughly 4x too large on a 1920x1080 frame.
    filter_str = _captions_filter(Path("captions.srt"), DEFAULT_BRAND)
    assert f"original_size={DEFAULT_BRAND.width}x{DEFAULT_BRAND.height}" in filter_str
    assert f"FontSize={DEFAULT_BRAND.caption_font_size}" in filter_str
