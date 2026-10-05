"""Turn a composited page into a mild scan: rotation, blur, grain, paper cast, JPEG."""

from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass
from statistics import NormalDist

from PIL import Image, ImageChops, ImageFilter


JPEG_LEAK_PAD_PX = 8
MM_PER_INCH = 25.4
GRAIN_LEVELS = 256


@dataclass(frozen=True)
class ScanParams:
    angle: float
    blur_radius: float
    grain_sigma: float
    jpeg_quality: int
    cast_alpha: float
    cast_color: tuple[int, int, int]


def params_for(rng: random.Random, dpi: int) -> ScanParams:
    angle = rng.uniform(-1.2, 1.2)
    if abs(angle) < 0.25:
        angle = 0.35 if angle >= 0 else -0.35
    return ScanParams(
        angle=angle,
        blur_radius=rng.uniform(0.10, 0.22) * dpi / MM_PER_INCH,
        grain_sigma=rng.uniform(2.0, 5.0),
        jpeg_quality=rng.randint(68, 86),
        cast_alpha=rng.uniform(0.05, 0.12),
        cast_color=(
            rng.randint(214, 226),
            rng.randint(212, 224),
            rng.randint(206, 218),
        ),
    )


def apply_scan(image: Image.Image, params: ScanParams, rng: random.Random) -> Image.Image:
    with Image.open(io.BytesIO(scan_to_jpeg(image, params, rng))) as decoded:
        return decoded.convert("RGB")


def scan_to_jpeg(image: Image.Image, params: ScanParams, rng: random.Random) -> bytes:
    page = image.convert("RGB")
    page = page.rotate(
        params.angle,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        fillcolor=params.cast_color,
    )
    page = page.filter(ImageFilter.GaussianBlur(radius=params.blur_radius))
    page = _grain(page, rng, params.grain_sigma)
    cast = Image.new("RGB", page.size, params.cast_color)
    page = Image.blend(page, cast, params.cast_alpha)
    return _jpeg_bytes(page, params.jpeg_quality)


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
    box_left, box_upper, box_right, box_lower = left, upper, right, lower
    if right > left and lower > upper:
        xs, ys = _rotated_corners((left, upper, right, lower), image_size, params.angle)
        rotated = (
            max(0, math.floor(min(xs))),
            max(0, math.floor(min(ys))),
            min(image_w, math.ceil(max(xs))),
            min(image_h, math.ceil(max(ys))),
        )
        if rotated[2] > rotated[0] and rotated[3] > rotated[1]:
            box_left, box_upper, box_right, box_lower = rotated
        if (right - left) <= 2 and (lower - upper) <= 2:
            box_left = min(box_left, left)
            box_upper = min(box_upper, upper)
            box_right = max(box_right, right)
            box_lower = max(box_lower, lower)
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


def _rotated_corners(
    rect: tuple[int, int, int, int],
    image_size: tuple[int, int],
    angle: float,
) -> tuple[list[float], list[float]]:
    left, upper, right, lower = rect
    center_x = image_size[0] / 2
    center_y = image_size[1] / 2
    theta = math.radians(angle)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    xs: list[float] = []
    ys: list[float] = []
    for corner_x, corner_y in ((left, upper), (right, upper), (left, lower), (right, lower)):
        dx = corner_x - center_x
        dy = corner_y - center_y
        xs.append(center_x + dx * cos_t + dy * sin_t)
        ys.append(center_y - dx * sin_t + dy * cos_t)
    return xs, ys


def _grain_table(sigma: float) -> list[int]:
    normal = NormalDist()
    quantiles = [normal.inv_cdf((level + 0.5) / GRAIN_LEVELS) for level in range(GRAIN_LEVELS)]
    spread = math.sqrt(sum(value * value for value in quantiles) / GRAIN_LEVELS)
    return [min(255, max(0, 128 + round(value * sigma / spread))) for value in quantiles]


def _grain(image: Image.Image, rng: random.Random, sigma: float) -> Image.Image:
    raw = rng.randbytes(image.width * image.height)
    layer = Image.frombytes("L", image.size, raw).point(_grain_table(sigma))
    signed = Image.merge("RGB", (layer, layer, layer))
    return ImageChops.add(image, signed, 1.0, -128)


def _jpeg_bytes(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()
