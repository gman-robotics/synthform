"""Vendored Open Font License handwriting faces, plus an optional local directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import ImageFont

from scanform.errors import ScanformError

FONT_DIR = Path(__file__).resolve().parent / "fonts"
_FONT_SUFFIXES = {".ttf", ".otf"}


@dataclass(frozen=True)
class FontFace:
    font_id: str
    path: Path


def load_font_faces(extra_dir: Path | None = None) -> list[FontFace]:
    paths = sorted(
        path
        for path in FONT_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in _FONT_SUFFIXES
    )
    if extra_dir is not None:
        if not extra_dir.is_dir():
            raise ScanformError(f"--font-dir is not a directory: {extra_dir}")
        paths.extend(
            sorted(
                path
                for path in extra_dir.iterdir()
                if path.is_file() and path.suffix.lower() in _FONT_SUFFIXES
            )
        )
    faces: list[FontFace] = []
    seen: set[str] = set()
    for path in paths:
        face = _load_face(path, seen)
        if face is not None:
            faces.append(face)
    if not faces:
        raise ScanformError("no handwriting fonts found")
    return faces


def _load_face(path: Path, seen: set[str]) -> FontFace | None:
    try:
        ImageFont.truetype(str(path), 16)
    except OSError:
        return None
    font_id = path.stem
    suffix = 2
    while font_id in seen:
        font_id = f"{path.stem}-{suffix}"
        suffix += 1
    seen.add(font_id)
    return FontFace(font_id, path)
