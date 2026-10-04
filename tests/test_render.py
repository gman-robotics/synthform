import random

from PIL import Image

from scanform.fonts import load_font_faces
from scanform.render import draw_field
from scanform.scan import ScanParams, apply_scan, map_box, params_for
from scanform.styles import assign_row_styles


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
    text = "SUPERCALIFRAGILISTIC-VALUE-998877 " * 6
    draw_field(page, box, text, _style(), seed=9, field_name="notes")
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
