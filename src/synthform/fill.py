"""Fill every data row and write image-only PDFs plus labels."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from synthform import SYNTHETIC_WARNING, __version__
from synthform.data import load_rows
from synthform.errors import ScanformError
from synthform.fields import resolve_fields
from synthform.fonts import load_font_faces
from synthform.pdfout import write_image_pdf
from synthform.raster import load_form_pages, points_to_pixels
from synthform.render import draw_field
from synthform.rngutil import stable_seed
from synthform.scan import apply_scan, map_box, params_for
from synthform.styles import assign_row_styles


def fill_form(
    form: Path,
    data: Path,
    out: Path,
    boxes: Path | None = None,
    dpi: int = 200,
    seed: int = 0,
    font_dir: Path | None = None,
) -> None:
    if dpi < 36 or dpi > 600:
        raise ScanformError("--dpi must be between 36 and 600")
    rows = load_rows(data)
    pages, page_sizes = load_form_pages(form, dpi)
    fields = resolve_fields(form, boxes)
    _warn_unknown_columns(rows, {field.name for field in fields})
    for field in fields:
        if field.page >= len(pages):
            raise ScanformError(
                f"field {field.name!r} is on page {field.page}, but the form has {len(pages)} page(s)"
            )
    styles = assign_row_styles(len(rows), seed, load_font_faces(font_dir))
    out.mkdir(parents=True, exist_ok=True)
    labels: list[dict[str, object]] = []
    skipped_fields: list[dict[str, str]] = []
    filenames: list[str] = []
    for index, row in enumerate(rows):
        row_number = index + 1
        row_id = f"row-{row_number:04d}"
        style = styles[index]
        working = [page.copy() for page in pages]
        drawn: list[tuple] = []
        for field in fields:
            raw = row.get(field.name, "")
            text = raw.strip()
            if not text:
                continue
            image = working[field.page]
            pixel_box = points_to_pixels(field, page_sizes[field.page], image.size)
            if pixel_box[2] < 2 or pixel_box[3] < 2:
                continue
            jitter = draw_field(image, pixel_box, text, style, seed, field.name, row_number)
            if jitter is None:
                print(f"synthform: {row_id} field {field.name!r}: text does not fit", file=sys.stderr)
                skipped_fields.append({"row_id": row_id, "field": field.name})
                continue
            drawn.append((field, text, pixel_box, jitter))
        final_pages = []
        scan_params = []
        for page_index, image in enumerate(working):
            rng = random.Random(stable_seed(seed, "scan", row_number, page_index))
            params = params_for(rng, dpi)
            final_pages.append(apply_scan(image, params, rng))
            scan_params.append(params)
        filename = f"{row_id}.pdf"
        write_image_pdf(out / filename, final_pages, dpi)
        filenames.append(filename)
        for field, text, pixel_box, jitter in drawn:
            labels.append(
                {
                    "row_id": row_id,
                    "field": field.name,
                    "text": text,
                    "page": field.page,
                    "box": map_box(pixel_box, working[field.page].size, scan_params[field.page]),
                    "font_id": style.font_id,
                    "seed": seed,
                    "style": style.to_json(),
                    "jitter": jitter.to_json(),
                }
            )
    _write_labels(out / "labels.jsonl", labels)
    if not labels:
        print("synthform: no label written", file=sys.stderr)
    manifest = {
        "generator": "synthform",
        "version": __version__,
        "warning": SYNTHETIC_WARNING,
        "synthetic_training_sample": True,
        "not_a_signed_original": True,
        "seed": seed,
        "dpi": dpi,
        "row_count": len(rows),
        "form": form.name,
        "files": filenames,
        "skipped_fields": skipped_fields,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _warn_unknown_columns(rows: list[dict[str, str]], names: set[str]) -> None:
    warned: set[str] = set()
    for row in rows:
        for key in row:
            if key not in names and key not in warned:
                print(f"synthform: no box for field {key!r}", file=sys.stderr)
                warned.add(key)


def _write_labels(path: Path, labels: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for label in labels:
            handle.write(json.dumps(label, ensure_ascii=False))
            handle.write("\n")
