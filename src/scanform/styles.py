"""One font-and-jitter tuple per row. Small batches do not reuse a tuple."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from scanform.errors import ScanformError
from scanform.fonts import FontFace

_SIZE_SCALES = (0.58, 0.72, 0.86)
_ROTATIONS = (-2.2, -0.7, 0.8, 2.1)
_TRACKING = (-0.02, 0.03, 0.08)
_BASELINES = (-0.05, 0.02, 0.09)
_INKS = (
    (28, 26, 24),
    (20, 24, 36),
    (36, 30, 26),
    (18, 20, 22),
    (30, 34, 28),
)


@dataclass(frozen=True)
class RowStyle:
    font_id: str
    font_path: Path
    size_scale: float
    rotation: float
    tracking: float
    baseline: float
    ink: tuple[int, int, int]

    def key(self) -> tuple:
        return (
            self.font_id,
            self.size_scale,
            self.rotation,
            self.tracking,
            self.baseline,
            self.ink,
        )

    def to_json(self) -> dict[str, object]:
        return {
            "size_scale": self.size_scale,
            "rotation": self.rotation,
            "tracking": self.tracking,
            "baseline": self.baseline,
            "ink": list(self.ink),
        }


def assign_row_styles(count: int, seed: int, fonts: list[FontFace]) -> list[RowStyle]:
    if count < 1:
        return []
    if not fonts:
        raise ScanformError("no handwriting fonts found")
    palette = _palette(fonts)
    order = random.Random(seed)
    order.shuffle(palette)
    if count <= len(palette):
        return palette[:count]
    chosen: list[RowStyle] = []
    for index in range(count):
        base = palette[index % len(palette)]
        cycle = index // len(palette)
        if cycle == 0:
            chosen.append(base)
            continue
        chosen.append(
            RowStyle(
                font_id=base.font_id,
                font_path=base.font_path,
                size_scale=round(base.size_scale - 0.01 * cycle, 4),
                rotation=base.rotation,
                tracking=base.tracking,
                baseline=base.baseline,
                ink=base.ink,
            )
        )
    return chosen


def _palette(fonts: list[FontFace]) -> list[RowStyle]:
    styles: list[RowStyle] = []
    for face in fonts:
        for size_scale in _SIZE_SCALES:
            for rotation in _ROTATIONS:
                for tracking in _TRACKING:
                    for baseline in _BASELINES:
                        for ink in _INKS:
                            if ink == (0, 0, 0) or min(ink) < 8:
                                continue
                            styles.append(
                                RowStyle(
                                    font_id=face.font_id,
                                    font_path=face.path,
                                    size_scale=size_scale,
                                    rotation=rotation,
                                    tracking=tracking,
                                    baseline=baseline,
                                    ink=ink,
                                )
                            )
    return styles
