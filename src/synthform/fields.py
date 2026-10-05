"""Field rectangles in PDF points, origin at the bottom-left of the page."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import IndirectObject

from synthform.errors import ScanformError

_FILLED_FIELD_TYPE = "/Tx"


@dataclass(frozen=True)
class FieldBox:
    name: str
    page: int
    x: float
    y: float
    w: float
    h: float


def resolve_fields(form: Path, boxes_path: Path | None) -> list[FieldBox]:
    suffix = form.suffix.lower()
    if suffix == ".pdf":
        acroform = extract_acroform_boxes(form)
        if acroform:
            return acroform
        if boxes_path is None:
            raise ScanformError("PDF has no AcroForm text fields; pass --boxes")
        return load_boxes(boxes_path)
    if suffix in {".png", ".jpg", ".jpeg"}:
        if boxes_path is None:
            raise ScanformError("image forms need --boxes")
        return load_boxes(boxes_path)
    raise ScanformError("FORM must be a PDF, PNG, or JPEG")


def load_boxes(path: Path) -> list[FieldBox]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScanformError(f"--boxes is not valid JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise ScanformError("--boxes must be a JSON list")
    boxes: list[FieldBox] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ScanformError(f"--boxes[{index}] must be an object")
        try:
            name = str(item["name"]).strip()
            page = int(item["page"])
            x = float(item["x"])
            y = float(item["y"])
            width = float(item["w"])
            height = float(item["h"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ScanformError(
                f"--boxes[{index}] needs name, page, x, y, w, h"
            ) from exc
        if not name:
            raise ScanformError(f"--boxes[{index}] has an empty name")
        if page < 0 or width <= 0 or height <= 0:
            raise ScanformError(f"--boxes[{index}] has an invalid page or size")
        boxes.append(FieldBox(name, page, x, y, width, height))
    if not boxes:
        raise ScanformError("--boxes is empty")
    return boxes


def extract_acroform_boxes(path: Path) -> list[FieldBox]:
    reader = PdfReader(str(path))
    boxes: list[FieldBox] = []
    for page_index, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        for annot in annots:
            widget = annot.get_object()
            if str(widget.get("/Subtype", "")) != "/Widget":
                continue
            field_type = _inherited(widget, "/FT")
            if field_type is None or str(field_type) != _FILLED_FIELD_TYPE:
                continue
            rect = widget.get("/Rect")
            name = _qualified_name(widget)
            if rect is None or not name:
                continue
            llx, lly, urx, ury = (float(value) for value in rect)
            boxes.append(
                FieldBox(
                    name=name,
                    page=page_index,
                    x=min(llx, urx),
                    y=min(lly, ury),
                    w=abs(urx - llx),
                    h=abs(ury - lly),
                )
            )
    return boxes


def _qualified_name(widget) -> str:
    parts: list[str] = []
    current = widget
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        token = current.get("/T")
        if token is not None:
            parts.append(str(token))
        parent = current.get("/Parent")
        if parent is None:
            break
        current = parent.get_object() if isinstance(parent, IndirectObject) else parent
    parts.reverse()
    return ".".join(part for part in parts if part)


def _inherited(widget, key: str):
    current = widget
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if key in current:
            return current.get(key)
        parent = current.get("/Parent")
        if parent is None:
            return None
        current = parent.get_object() if isinstance(parent, IndirectObject) else parent
    return None
