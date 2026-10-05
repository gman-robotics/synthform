from synthform.fonts import load_font_faces
from synthform.render import field_draw_params
from synthform.styles import assign_row_styles


def test_vendored_fonts_include_several_ofl_faces():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "synthform" / "fonts"
    families = sorted(path for path in root.iterdir() if path.is_dir())
    assert len(families) >= 6
    for family in families:
        license_text = (family / "OFL.txt").read_text(encoding="utf-8")
        assert "SIL Open Font License" in license_text
        assert list(family.glob("*.ttf")) or list(family.glob("*.otf"))
    font_ids = {face.font_id for face in load_font_faces()}
    assert any("Caveat" in font_id for font_id in font_ids)
    assert any("PatrickHand" in font_id for font_id in font_ids)


def test_small_batch_does_not_reuse_a_font_jitter_tuple():
    fonts = load_font_faces()
    styles = assign_row_styles(12, seed=11, fonts=fonts)
    keys = [style.key() for style in styles]
    assert len(keys) == len(set(keys))
    assert assign_row_styles(4, seed=3, fonts=fonts) == assign_row_styles(4, seed=3, fonts=fonts)


def test_palette_ink_is_not_pure_black():
    fonts = load_font_faces()
    for style in assign_row_styles(30, seed=2, fonts=fonts):
        assert style.ink != (0, 0, 0)
        assert min(style.ink) >= 8


def test_fields_in_one_row_do_not_share_jitter():
    fonts = load_font_faces()
    style = assign_row_styles(1, seed=4, fonts=fonts)[0]
    full_name = field_draw_params(style, seed=4, field_name="full_name", box_w=300, box_h=40)
    city = field_draw_params(style, seed=4, field_name="city", box_w=300, box_h=40)
    assert (full_name.rotation, full_name.dx, full_name.dy, full_name.tracking_em, full_name.ink) != (
        city.rotation,
        city.dx,
        city.dy,
        city.tracking_em,
        city.ink,
    )
    assert full_name.ink != (0, 0, 0)
    assert city.ink != (0, 0, 0)


def test_field_jitter_repeats_for_the_same_row():
    fonts = load_font_faces()
    style = assign_row_styles(1, seed=4, fonts=fonts)[0]
    first = field_draw_params(style, seed=4, field_name="city", box_w=300, box_h=40, row=3)
    again = field_draw_params(style, seed=4, field_name="city", box_w=300, box_h=40, row=3)
    assert first == again


def test_field_jitter_differs_between_rows_for_one_style_and_field():
    fonts = load_font_faces()
    style = assign_row_styles(1, seed=4, fonts=fonts)[0]
    jitters = [
        field_draw_params(style, seed=4, field_name="city", box_w=300, box_h=40, row=row)
        for row in range(1, 9)
    ]
    assert len({(item.rotation, item.tracking_em, item.dx, item.dy, item.ink) for item in jitters}) == 8


def test_row_zero_is_the_default_row():
    fonts = load_font_faces()
    style = assign_row_styles(1, seed=4, fonts=fonts)[0]
    default = field_draw_params(style, seed=4, field_name="city", box_w=300, box_h=40)
    explicit = field_draw_params(style, seed=4, field_name="city", box_w=300, box_h=40, row=0)
    assert default == explicit
