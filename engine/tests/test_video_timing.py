from victory_engine.video import paragraph_weights, MIN_STATEMENT_SECONDS, MIN_SHORT_SECONDS


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
