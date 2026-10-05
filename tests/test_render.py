import json
import random
from dataclasses import replace

import pytest
from PIL import Image, ImageChops, ImageFilter, ImageFont
from reportlab.pdfgen import canvas

from synthform.cli import main
from synthform.fields import FieldBox
from synthform.fonts import load_font_faces
from synthform.raster import points_to_pixels
from synthform.render import _fit, _text_width, draw_field, field_draw_params
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


SHRINK_TOKEN = "SUPERCALIFRAGILISTIC"
SHRINK_BOX_HEIGHT = 42


def _drawn_size(width: int) -> int | None:
    page = Image.new("RGB", (width + 40, 100), (255, 255, 255))
    jitter = draw_field(page, (20, 20, width, SHRINK_BOX_HEIGHT), SHRINK_TOKEN, _style(), seed=1, field_name="notes")
    return None if jitter is None else jitter.size_px


def _narrowest_width_for_size(size: int) -> int:
    for width in range(20, 200):
        if _drawn_size(width) == size:
            return width
    raise AssertionError(size)


def _fill_one_field(tmp_path, width: int) -> tuple[list[dict], dict]:
    form = tmp_path / "blank.pdf"
    pdf = canvas.Canvas(str(form), pagesize=(300, 200))
    pdf.rect(20, 100, width, SHRINK_BOX_HEIGHT, stroke=1, fill=0)
    pdf.save()
    boxes = tmp_path / "boxes.json"
    boxes.write_text(
        json.dumps([{"name": "notes", "page": 0, "x": 20, "y": 100, "w": width, "h": SHRINK_BOX_HEIGHT}]),
        encoding="utf-8",
    )
    data = tmp_path / "rows.csv"
    data.write_text(f"notes\n{SHRINK_TOKEN}\n", encoding="utf-8")
    out = tmp_path / "out"
    code = main(
        ["fill", "--form", str(form), "--data", str(data), "--boxes", str(boxes), "--out", str(out), "--dpi", "72", "--seed", "1"]
    )
    assert code == 0
    lines = (out / "labels.jsonl").read_text(encoding="utf-8").splitlines()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    return [json.loads(line) for line in lines], manifest


@pytest.mark.parametrize("size", [6, 8])
def test_unbreakable_token_that_fits_when_shrunk_keeps_its_label(tmp_path, size: int):
    start = field_draw_params(_style(), 1, "notes", 110, SHRINK_BOX_HEIGHT).size_px
    assert size < start
    width = _narrowest_width_for_size(size)
    labels, manifest = _fill_one_field(tmp_path, width)
    assert len(labels) == 1
    assert labels[0]["field"] == "notes"
    assert labels[0]["text"] == SHRINK_TOKEN
    assert labels[0]["jitter"]["size_px"] == size
    assert manifest["skipped_fields"] == []


def test_one_pixel_narrower_than_the_smallest_fit_is_skipped(tmp_path):
    width = _narrowest_width_for_size(6)
    assert _drawn_size(width - 1) is None
    labels, manifest = _fill_one_field(tmp_path, width - 1)
    assert labels == []
    assert manifest["skipped_fields"] == [{"row_id": "row-0001", "field": "notes"}]


def test_skip_floor_is_12_px_without_rotation_and_13_px_for_a_real_style():
    style = _style()
    params = field_draw_params(style, 1, "notes", 200, 13)
    for text in ("A", "Hello"):
        for height, expected in ((11, False), (12, False), (13, True)):
            page = Image.new("RGB", (240, 60), (255, 255, 255))
            drawn = draw_field(page, (20, 20, 200, height), text, style, seed=1, field_name="notes") is not None
            assert drawn is expected, (text, height)
        _, _, _, _, size, fits = _fit(text, style.font_path, 198, 10, params.size_px, params.tracking_em, 0.0)
        assert (size, fits) == (6, True)
        _, _, _, _, _, fits = _fit(text, style.font_path, 198, 9, params.size_px, params.tracking_em, 0.0)
        assert fits is False


def _difference_peak(first: Image.Image, second: Image.Image, mapped: dict) -> int:
    red, green, blue = ImageChops.difference(first, second).split()
    peak = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    mask = Image.new("L", peak.size, 0)
    mask.paste(255, (mapped["x"], mapped["y"], mapped["x"] + mapped["w"], mapped["y"] + mapped["h"]))
    return ImageChops.subtract(peak, mask).getextrema()[1]


BOX_OFFSETS_PT = ((0.0, 0.0), (0.7, 0.0), (0.0, 1.3), (5.1, 3.9))


@pytest.mark.parametrize(("dpi", "draws", "offset_draws"), [(100, 40, 8), (200, 40, 8), (300, 8, 4)])
def test_edge_fill_stays_inside_the_padded_box(dpi: int, draws: int, offset_draws: int):
    size = (round(420 * dpi / 72), round(300 * dpi / 72))
    white = Image.new("RGB", size, (255, 255, 255))
    cases = [(seed, BOX_OFFSETS_PT[0]) for seed in range(draws)]
    cases += [(seed, offset) for offset in BOX_OFFSETS_PT[1:] for seed in range(offset_draws)]
    assert {offset for _, offset in cases} == set(BOX_OFFSETS_PT)
    for seed, (offset_x, offset_y) in cases:
        box = points_to_pixels(FieldBox("field", 0, 36 + offset_x, 200 + offset_y, 340, 40), (420, 300), size)
        x, y, width, height = box
        filled = white.copy()
        filled.paste((20, 20, 20), (x + 2, y + 2, x + width - 2, y + height - 2))
        rng = random.Random(seed)
        params = params_for(rng)
        scanned_filled = apply_scan(filled, params, rng)
        rng = random.Random(seed)
        scanned_white = apply_scan(white, params_for(rng), rng)
        mapped = map_box(box, size, params)
        assert _difference_peak(scanned_filled, scanned_white, mapped) <= OUTSIDE_TOL, (seed, offset_x, offset_y)


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
