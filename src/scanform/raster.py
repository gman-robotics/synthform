"""Rasterize a blank PDF or load a form image."""

from __future__ import annotations

from PIL import Image
import pypdfium2 as pdfium

from scanform.errors import ScanformError
from scanform.fields import FieldBox


def load_form_pages(
    path,
    dpi: int,
) -> tuple[list[Image.Image], list[tuple[float, float]]]:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg"}:
        with Image.open(path) as source:
            image = _to_rgb(source).copy()
        width_pt = image.width * 72.0 / dpi
        height_pt = image.height * 72.0 / dpi
        return [image], [(width_pt, height_pt)]
    if suffix != ".pdf":
        raise ScanformError("FORM must be a PDF, PNG, or JPEG")
    document = pdfium.PdfDocument(str(path))
    try:
        if len(document) == 0:
            raise ScanformError("PDF has no pages")
        images: list[Image.Image] = []
        sizes: list[tuple[float, float]] = []
        scale = dpi / 72.0
        for page in document:
            width_pt, height_pt = page.get_size()
            rendered = page.render(scale=scale).to_pil()
            images.append(_to_rgb(rendered).copy())
            sizes.append((float(width_pt), float(height_pt)))
        return images, sizes
    finally:
        document.close()


def points_to_pixels(
    field: FieldBox,
    page_size_pt: tuple[float, float],
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Map a bottom-left PDF box onto a top-left pixel box for this raster."""
    page_w, page_h = page_size_pt
    image_w, image_h = image_size
    scale_x = image_w / page_w
    scale_y = image_h / page_h
    x = int(round(field.x * scale_x))
    width = int(round(field.w * scale_x))
    height = int(round(field.h * scale_y))
    y = int(round((page_h - field.y - field.h) * scale_y))
    return clamp_box((x, y, width, height), image_size)


def clamp_box(
    box: tuple[int, int, int, int],
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    x, y, width, height = box
    image_w, image_h = image_size
    x0 = min(image_w, max(0, x))
    y0 = min(image_h, max(0, y))
    x1 = min(image_w, max(0, x + width))
    y1 = min(image_h, max(0, y + height))
    return x0, y0, x1 - x0, y1 - y0


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        return background
    return image.convert("RGB")
