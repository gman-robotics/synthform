"""Draw handwriting inside a field box. Pixels outside the box stay untouched."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from synthform.rngutil import stable_seed
from synthform.styles import RowStyle


@dataclass(frozen=True)
class FieldJitter:
    size_px: int
    rotation: float
    tracking_em: float
    dx: int
    dy: int
    ink: tuple[int, int, int]

    def to_json(self) -> dict[str, object]:
        return {
            "size_px": self.size_px,
            "rotation": round(self.rotation, 3),
            "tracking_em": round(self.tracking_em, 4),
            "dx": self.dx,
            "dy": self.dy,
            "ink": list(self.ink),
        }


def field_draw_params(
    style: RowStyle,
    seed: int,
    field_name: str,
    box_w: int,
    box_h: int,
) -> FieldJitter:
    rng = random.Random(stable_seed(seed, "field", field_name, style.font_id))
    return FieldJitter(
        size_px=max(6, int(round(box_h * style.size_scale * rng.uniform(0.94, 1.06)))),
        rotation=style.rotation + rng.uniform(-1.0, 1.0),
        tracking_em=style.tracking + rng.uniform(-0.015, 0.02),
        dx=int(round(rng.uniform(-0.05, 0.05) * box_w)),
        dy=int(round((style.baseline + rng.uniform(-0.04, 0.04)) * box_h)),
        ink=_shift_ink(style.ink, rng),
    )


def draw_field(
    page: Image.Image,
    box: tuple[int, int, int, int],
    text: str,
    style: RowStyle,
    seed: int,
    field_name: str,
) -> FieldJitter:
    x, y, width, height = box
    params = field_draw_params(style, seed, field_name, width, height)
    fitted = params.size_px
    if width >= 2 and height >= 2 and text.strip():
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        fitted = _paint_text(layer, text, style.font_path, params)
        page.paste(layer, (x, y), layer)
    if fitted == params.size_px:
        return params
    return FieldJitter(
        size_px=fitted,
        rotation=params.rotation,
        tracking_em=params.tracking_em,
        dx=params.dx,
        dy=params.dy,
        ink=params.ink,
    )


def _shift_ink(ink: tuple[int, int, int], rng: random.Random) -> tuple[int, int, int]:
    shifted = tuple(min(72, max(12, channel + rng.randint(-8, 8))) for channel in ink)
    return shifted  # type: ignore[return-value]


def _paint_text(layer: Image.Image, text: str, font_path: Path, params: FieldJitter) -> int:
    width, height = layer.size
    budget_w = max(1, width - 2)
    budget_h = max(1, height - 2)
    font, lines, tracking_px, line_h, size = _fit(
        text,
        font_path,
        budget_w,
        budget_h,
        params.size_px,
        params.tracking_em,
        params.rotation,
    )
    block_w = max(1, math.ceil(max(_text_width(line, font, tracking_px) for line in lines)))
    block_h = max(1, line_h * len(lines))
    text_image = Image.new("RGBA", (block_w + 2, block_h + 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_image)
    fill = (*params.ink, 255)
    for index, line in enumerate(lines):
        _draw_tracked(draw, line, font, (1, 1 + index * line_h), fill, tracking_px)
    rotated = text_image.rotate(
        params.rotation,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(0, 0, 0, 0),
    )
    origin_x = _clamp_origin(width, rotated.width, (width - rotated.width) // 2 + params.dx)
    origin_y = _clamp_origin(height, rotated.height, (height - rotated.height) // 2 + params.dy)
    layer.paste(rotated, (origin_x, origin_y), rotated)
    return size


def _fit(
    text: str,
    font_path: Path,
    budget_w: int,
    budget_h: int,
    start_px: int,
    tracking_em: float,
    rotation: float,
):
    start = max(6, min(start_px, budget_h))
    for size in range(start, 5, -1):
        font = ImageFont.truetype(str(font_path), size)
        tracking_px = tracking_em * size
        lines = _wrap(text, font, budget_w, tracking_px)
        line_h = max(1, int(math.ceil(size * 1.2)))
        block_w = max(_text_width(line, font, tracking_px) for line in lines)
        block_h = line_h * len(lines)
        rot_w, rot_h = _rotated_size(block_w + 2, block_h + 2, rotation)
        if rot_w <= budget_w and rot_h <= budget_h:
            return font, lines, tracking_px, line_h, size
    font = ImageFont.truetype(str(font_path), 6)
    tracking_px = tracking_em * 6
    return font, _wrap(text, font, budget_w, tracking_px), tracking_px, max(1, int(math.ceil(6 * 1.2))), 6


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: float, tracking_px: float) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if _text_width(trial, font, tracking_px) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _text_width(text: str, font: ImageFont.FreeTypeFont, tracking_px: float) -> float:
    if not text:
        return 0.0
    width = 0.0
    for index, char in enumerate(text):
        width += float(font.getlength(char))
        if index:
            width += tracking_px
    return max(1.0, width)


def _draw_tracked(draw, text: str, font, xy, fill, tracking_px: float) -> None:
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += float(font.getlength(char)) + tracking_px


def _rotated_size(width: float, height: float, degrees: float) -> tuple[float, float]:
    theta = math.radians(abs(degrees))
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    return (
        width * cos_t + height * sin_t,
        width * sin_t + height * cos_t,
    )


def _clamp_origin(host: int, item: int, desired: int) -> int:
    if item >= host:
        return (host - item) // 2
    return max(0, min(desired, host - item))
