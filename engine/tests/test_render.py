from victory_engine.brand import DEFAULT_BRAND
from victory_engine.render import SlideSpec, render_slide


def test_map_slide_renders_six_items_without_cropping():
    spec = SlideSpec(kind="map", heading="The Six Functions",
                      bullets=["Operations", "Money", "People", "Customers", "Risk & Compliance", "Strategy"])
    img = render_slide(DEFAULT_BRAND, spec)
    assert img.size == (DEFAULT_BRAND.width, DEFAULT_BRAND.height)


def test_map_slide_renders_single_item():
    spec = SlideSpec(kind="map", heading="One", bullets=["Solo"])
    img = render_slide(DEFAULT_BRAND, spec)
    assert img.size == (DEFAULT_BRAND.width, DEFAULT_BRAND.height)


def test_all_slide_kinds_render_without_error():
    specs = [
        SlideSpec(kind="cover", heading="Title"),
        SlideSpec(kind="statement", heading="H", bullets=["a", "b"]),
        SlideSpec(kind="map", heading="H", bullets=["a", "b", "c"]),
        SlideSpec(kind="comparison", heading="H", left_label="L", right_label="R", left_points=["a"], right_points=["b"]),
        SlideSpec(kind="flow", heading="H", steps=["a", "b", "c"]),
        SlideSpec(kind="quote", quote="Something said.", attribution="Someone"),
        SlideSpec(kind="close", heading="H", bullets=["a"]),
    ]
    for spec in specs:
        img = render_slide(DEFAULT_BRAND, spec)
        assert img.size == (DEFAULT_BRAND.width, DEFAULT_BRAND.height)
