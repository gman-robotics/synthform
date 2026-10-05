"""Wrap scanned JPEG pages in a PDF whose metadata says this is a synthetic training sample."""

from __future__ import annotations

import io
from pathlib import Path

from reportlab import rl_config
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from synthform import SYNTHETIC_WARNING, __version__


def write_image_pdf(path: Path, pages: list[bytes], dpi: int) -> None:
    if not pages:
        raise ValueError("write_image_pdf needs at least one page")
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_a85 = rl_config.useA85
    rl_config.useA85 = 0
    try:
        _write(path, pages, dpi)
    finally:
        rl_config.useA85 = previous_a85


def _write(path: Path, pages: list[bytes], dpi: int) -> None:
    canvas = Canvas(str(path), invariant=1)
    canvas.setTitle("Synthetic training sample")
    canvas.setSubject(SYNTHETIC_WARNING)
    canvas.setKeywords("synthetic training sample, not a signed original")
    canvas.setCreator(f"synthform {__version__}")
    canvas.setAuthor("synthform synthetic training generator")
    canvas.setProducer(f"synthform {__version__} synthetic training sample")
    for data in pages:
        image = ImageReader(io.BytesIO(data))
        width_px, height_px = image.getSize()
        width_pt = width_px * 72.0 / dpi
        height_pt = height_px * 72.0 / dpi
        canvas.setPageSize((width_pt, height_pt))
        canvas.drawImage(
            image,
            0,
            0,
            width=width_pt,
            height=height_pt,
            preserveAspectRatio=False,
            anchor="sw",
        )
        _drop_jpeg_handle_cycle(image)
        canvas.showPage()
    canvas.save()


def _drop_jpeg_handle_cycle(image: ImageReader) -> None:
    image.__dict__.pop("jpeg_fh", None)
