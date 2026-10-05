import random
from dataclasses import replace

import pytest
from PIL import Image, ImageChops, ImageFilter, ImageFont

from synthform.fields import FieldBox
from synthform.fonts import load_font_faces
from synthform.raster import points_to_pixels
from synthform.render import _text_width, draw_field, field_draw_params
from synthform.scan import ScanParams, apply_scan, map_box, params_for
from synthform.styles import assign_row_styles

UNBREAKABLE_TOKEN = "SUPERCALIFRAGILISTIC-VALUE-998877" * 2
LOWEST_TRACKING_EM = -0.035
OUTSIDE_TOL = 8


def _style():
    return assign_row_styles(1, seed=1, fonts=load_font_faces())[0]


def test_draw_field_does_not_paint_outside_the_box():
    page = Image.new("RGB", (220, 90), (255, 255, 255))
    box = (28, 22, 110, 42)
    draw_field(page, box, "Ada Lovelace", _style(), seed=5, field_name="full_name")
    _assert_outside_unchanged(page, box)
    assert _ink_inside(page, box)


def test_long_text_stays_inside_the_box():
    page = Image.new("RGB", (220, 90), (255, 255, 255))
    box = (28, 22, 110, 42)
    text = "SUPERCALIFRAGILISTIC-VALUE-998877 " * 4
    jitter = draw_field(page, box, text, _style(), seed=9, field_name="notes")
    assert jitter is not None
    _assert_outside_unchanged(page, box)
    assert _ink_inside(page, box)


def test_scan_keeps_page_size():
    image = Image.new("RGB", (90, 70), (255, 255, 255))
    rng = random.Random(1)
    params = params_for(rng)
    scanned = apply_scan(image, params, rng)
    assert scanned.size == image.size
    assert scanned.getpixel((4, 4)) != (255, 255, 255)


def test_mapped_box_covers_rotated_rectangle():
    size = (140, 100)
    box = (24, 18, 48, 28)
    params = ScanParams(
        angle=1.0,
        blur_radius=0.0,
        noise_sigma=1.0,
        noise_alpha=0.0,
        jpeg_quality=90,
        cast_alpha=0.0,
        cast_color=(230, 228, 222),
    )
    mask = Image.new("L", size, 0)
    x, y, width, height = box
    mask.paste(255, (x, y, x + width, y + height))
    moved = mask.rotate(params.angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=0)
    mapped = map_box(box, size, params)
    for py in range(size[1]):
        for px in range(size[0]):
            if moved.getpixel((px, py)) < 8:
                continue
            assert mapped["x"] <= px < mapped["x"] + mapped["w"]
            assert mapped["y"] <= py < mapped["y"] + mapped["h"]


def test_unbreakable_token_that_cannot_fit_is_not_drawn():
    box = (28, 22, 110, 42)
    budget = box[2] - 2
    base_style = _style()
    for face in load_font_faces():
        style = replace(
            base_style,
            font_id=face.font_id,
            font_path=face.path,
            tracking=-0.02,
            rotation=0.0,
        )
        font = ImageFont.truetype(str(face.path), 6)
        assert _text_width(UNBREAKABLE_TOKEN, font, LOWEST_TRACKING_EM * 6) > budget, face.font_id
        page = Image.new("RGB", (220, 90), (255, 255, 255))
        assert draw_field(page, box, UNBREAKABLE_TOKEN, style, seed=3, field_name="notes") is None
        assert ImageChops.difference(page, Image.new("RGB", page.size, (255, 255, 255))).getbbox() is None


def test_unbreakable_token_that_fits_when_shrunk_keeps_its_label():
    page = Image.new("RGB", (220, 90), (255, 255, 255))
    box = (28, 22, 110, 42)
    style = _style()
    start = field_draw_params(style, 3, "notes", box[2], box[3]).size_px
    jitter = draw_field(page, box, "SUPERCALIFRAGILISTIC", style, seed=3, field_name="notes")
    assert jitter is not None
    assert 6 <= jitter.size_px < start
    _assert_outside_unchanged(page, box)
    assert _ink_inside(page, box)


def _difference_peak(first: Image.Image, second: Image.Image, mapped: dict) -> int:
    red, green, blue = ImageChops.difference(first, second).split()
    peak = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    mask = Image.new("L", peak.size, 0)
    mask.paste(255, (mapped["x"], mapped["y"], mapped["x"] + mapped["w"], mapped["y"] + mapped["h"]))
    return ImageChops.subtract(peak, mask).getextrema()[1]


@pytest.mark.parametrize(("dpi", "draws"), [(100, 40), (200, 40), (300, 8)])
def test_edge_fill_stays_inside_the_padded_box(dpi: int, draws: int):
    size = (round(420 * dpi / 72), round(300 * dpi / 72))
    box = points_to_pixels(FieldBox("field", 0, 36, 200, 340, 40), (420, 300), size)
    x, y, width, height = box
    white = Image.new("RGB", size, (255, 255, 255))
    filled = white.copy()
    filled.paste((20, 20, 20), (x + 2, y + 2, x + width - 2, y + height - 2))
    for seed in range(draws):
        rng = random.Random(seed)
        params = params_for(rng)
        scanned_filled = apply_scan(filled, params, rng)
        rng = random.Random(seed)
        scanned_white = apply_scan(white, params_for(rng), rng)
        mapped = map_box(box, size, params)
        assert _difference_peak(scanned_filled, scanned_white, mapped) <= OUTSIDE_TOL, seed


@pytest.mark.parametrize("blur", [0.6, 2.0, 4.0])
@pytest.mark.parametrize("angle", [-1.2, 1.2])
def test_mapped_box_covers_blurred_rotated_rectangle(blur: float, angle: float):
    size = (140, 100)
    box = (24, 18, 48, 28)
    params = ScanParams(
        angle=angle,
        blur_radius=blur,
        noise_sigma=1.0,
        noise_alpha=0.0,
        jpeg_quality=90,
        cast_alpha=0.0,
        cast_color=(230, 228, 222),
    )
    mask = Image.new("L", size, 0)
    x, y, width, height = box
    mask.paste(255, (x, y, x + width, y + height))
    moved = mask.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=0)
    blurred = moved.filter(ImageFilter.GaussianBlur(radius=blur))
    covered = blurred.point(lambda value: 255 if value >= OUTSIDE_TOL else 0).getbbox()
    mapped = map_box(box, size, params)
    assert covered is not None
    assert mapped["x"] <= covered[0] and covered[2] <= mapped["x"] + mapped["w"]
    assert mapped["y"] <= covered[1] and covered[3] <= mapped["y"] + mapped["h"]


def _assert_outside_unchanged(page: Image.Image, box: tuple[int, int, int, int]) -> None:
    x, y, width, height = box
    for py in range(page.height):
        for px in range(page.width):
            if x <= px < x + width and y <= py < y + height:
                continue
            assert page.getpixel((px, py)) == (255, 255, 255)


def _ink_inside(page: Image.Image, box: tuple[int, int, int, int]) -> bool:
    x, y, width, height = box
    for py in range(y, y + height):
        for px in range(x, x + width):
            if page.getpixel((px, py)) != (255, 255, 255):
                return True
    return False
