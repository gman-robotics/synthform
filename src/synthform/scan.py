"""Turn a composited page into a mild scan: rotation, blur, noise, JPEG, paper cast."""

from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass

from PIL import Image, ImageFilter


JPEG_LEAK_PAD_PX = 4


@dataclass(frozen=True)
class ScanParams:
    angle: float
    blur_radius: float
    noise_sigma: float
    noise_alpha: float
    jpeg_quality: int
    cast_alpha: float
    cast_color: tuple[int, int, int]


def params_for(rng: random.Random) -> ScanParams:
    angle = rng.uniform(-1.2, 1.2)
    if abs(angle) < 0.25:
        angle = 0.35 if angle >= 0 else -0.35
    return ScanParams(
        angle=angle,
        blur_radius=rng.uniform(0.4, 0.85),
        noise_sigma=rng.uniform(6.0, 14.0),
        noise_alpha=rng.uniform(0.04, 0.08),
        jpeg_quality=rng.randint(68, 86),
        cast_alpha=rng.uniform(0.05, 0.12),
        cast_color=(
            rng.randint(214, 226),
            rng.randint(212, 224),
            rng.randint(206, 218),
        ),
    )


def apply_scan(image: Image.Image, params: ScanParams, rng: random.Random) -> Image.Image:
    page = image.convert("RGB")
    page = page.rotate(
        params.angle,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        fillcolor=params.cast_color,
    )
    page = page.filter(ImageFilter.GaussianBlur(radius=params.blur_radius))
    page = _sensor_noise(page, rng, params.noise_sigma, params.noise_alpha)
    page = _jpeg_roundtrip(page, params.jpeg_quality)
    cast = Image.new("RGB", page.size, params.cast_color)
    return Image.blend(page, cast, params.cast_alpha)


def map_box(
    box: tuple[int, int, int, int],
    image_size: tuple[int, int],
    params: ScanParams,
) -> dict[str, int]:
    """Field rectangle after the same page rotation, padded for blur."""
    image_w, image_h = image_size
    x, y, width, height = box
    left = min(image_w, max(0, x))
    upper = min(image_h, max(0, y))
    right = min(image_w, max(0, x + width))
    lower = min(image_h, max(0, y + height))
    mask = Image.new("L", image_size, 0)
    if right > left and lower > upper:
        mask.paste(255, (left, upper, right, lower))
    rotated = mask.rotate(
        params.angle,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        fillcolor=0,
    )
    binary = rotated.point(lambda value: 255 if value >= 8 else 0)
    bbox = binary.getbbox()
    if bbox is None:
        box_left, box_upper, box_right, box_lower = left, upper, right, lower
    else:
        box_left, box_upper, box_right, box_lower = bbox
    pad = int(math.ceil(params.blur_radius * 3 + 1)) + JPEG_LEAK_PAD_PX
    box_left = max(0, box_left - pad)
    box_upper = max(0, box_upper - pad)
    box_right = min(image_w, box_right + pad)
    box_lower = min(image_h, box_lower + pad)
    return {
        "x": int(box_left),
        "y": int(box_upper),
        "w": int(box_right - box_left),
        "h": int(box_lower - box_upper),
    }


def _sensor_noise(
    image: Image.Image,
    rng: random.Random,
    sigma: float,
    alpha: float,
) -> Image.Image:
    width, height = image.size
    cell = 4
    grid_w = (width + cell - 1) // cell
    grid_h = (height + cell - 1) // cell
    raw = bytearray(grid_w * grid_h)
    for index in range(grid_w * grid_h):
        sample = int(round(rng.gauss(128, sigma)))
        raw[index] = min(255, max(0, sample))
    small = Image.frombytes("L", (grid_w, grid_h), bytes(raw))
    layer = small.resize((width, height), Image.Resampling.BILINEAR)
    gray = Image.merge("RGB", (layer, layer, layer))
    return Image.blend(image, gray, alpha)


def _jpeg_roundtrip(image: Image.Image, quality: int) -> Image.Image:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    with Image.open(buffer) as decoded:
        decoded.load()
        return decoded.convert("RGB")
