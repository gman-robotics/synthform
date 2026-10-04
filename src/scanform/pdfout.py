"""Wrap rasters in a PDF whose metadata says this is a synthetic training sample."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from scanform import SYNTHETIC_WARNING, __version__


def write_image_pdf(path: Path, images: list[Image.Image], dpi: int) -> None:
    if not images:
        raise ValueError("write_image_pdf needs at least one page")
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(path))
    canvas.setTitle("Synthetic training sample")
    canvas.setSubject(SYNTHETIC_WARNING)
    canvas.setKeywords("synthetic training sample, not a signed original")
    canvas.setCreator(f"scanform {__version__}")
    canvas.setAuthor("scanform synthetic training generator")
    for image in images:
        width_pt = image.width * 72.0 / dpi
        height_pt = image.height * 72.0 / dpi
        canvas.setPageSize((width_pt, height_pt))
        canvas.drawImage(
            ImageReader(image),
            0,
            0,
            width=width_pt,
            height=height_pt,
            preserveAspectRatio=False,
            anchor="sw",
            mask="auto",
        )
        canvas.showPage()
    canvas.save()
    _stamp_metadata(path)


def _stamp_metadata(path: Path) -> None:
    reader = PdfReader(str(path))
    writer = PdfWriter()
    writer.append(reader)
    writer.add_metadata(
        {
            "/Title": "Synthetic training sample",
            "/Subject": SYNTHETIC_WARNING,
            "/Keywords": "synthetic training sample, not a signed original",
            "/Creator": f"scanform {__version__}",
            "/Author": "scanform synthetic training generator",
            "/Producer": f"scanform {__version__} synthetic training sample",
        }
    )
    with path.open("wb") as handle:
        writer.write(handle)
