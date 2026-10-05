#!/usr/bin/env python3
"""Check a fill-boxes run and write the proof summary. Reads files only."""
import json
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops
from pypdf import PdfReader

ANSWERS = ("QXNAME-ALPHA-7741", "QXCITY-ALPHA-2290", "QXNAME-BETA-8832", "QXCITY-BETA-1104")
OUTSIDE_TOL = 8
INSIDE_LEVEL = 48
INSIDE_MIN_SHARE = 0.01
DIFF_GAIN = 4


def read_labels(out: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (out / "labels.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]


def difference_image(first: Image.Image, second: Image.Image) -> Image.Image:
    diff = ImageChops.difference(first.convert("RGB"), second.convert("RGB"))
    red, green, blue = diff.split()
    return ImageChops.lighter(ImageChops.lighter(red, green), blue)


def clamp_box(box: dict, size: tuple[int, int]) -> tuple[int, int, int, int]:
    left = min(size[0], max(0, box["x"]))
    upper = min(size[1], max(0, box["y"]))
    right = min(size[0], max(0, box["x"] + box["w"]))
    lower = min(size[1], max(0, box["y"] + box["h"]))
    return left, upper, right, lower


def box_union_mask(size: tuple[int, int], boxes: list[dict]) -> Image.Image:
    mask = Image.new("L", size, 0)
    for box in boxes:
        left, upper, right, lower = clamp_box(box, size)
        if right > left and lower > upper:
            mask.paste(255, (left, upper, right, lower))
    return mask


def outside_layer(diff: Image.Image, boxes: list[dict]) -> Image.Image:
    return ImageChops.subtract(diff, box_union_mask(diff.size, boxes))


def outside_max(diff: Image.Image, boxes: list[dict]) -> int:
    return outside_layer(diff, boxes).getextrema()[1]


def inside_share(diff: Image.Image, box: dict, level: int = INSIDE_LEVEL) -> float:
    left, upper, right, lower = clamp_box(box, diff.size)
    area = (right - left) * (lower - upper)
    if area == 0:
        return 0.0
    histogram = diff.crop((left, upper, right, lower)).histogram()
    return sum(histogram[level:]) / area


def render_pages(path: Path, dpi: int) -> list[Image.Image]:
    document = pdfium.PdfDocument(str(path))
    try:
        return [
            page.render(scale=dpi / 72.0).to_pil().convert("RGB") for page in document
        ]
    finally:
        document.close()


def structure_failures(out: Path, evidence: Path | None) -> list[str]:
    failures: list[str] = []
    labels = read_labels(out)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    if len(list(out.glob("row-*.pdf"))) != 2:
        failures.append("expected two PDFs")
    if len(labels) != 4:
        failures.append(f"expected 4 label lines, got {len(labels)}")
    if manifest.get("row_count") != 2:
        failures.append("manifest row_count is not 2")
    warning = str(manifest.get("warning", "")).lower()
    if "synthetic training sample" not in warning or "not a signed original" not in warning:
        failures.append("manifest warning missing")
    text_parts = []
    for pdf in sorted(out.glob("row-*.pdf")):
        reader = PdfReader(str(pdf))
        extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        text_parts.append(f"== {pdf.name} ==\n{extracted}")
        for token in ANSWERS:
            if token in extracted:
                failures.append(f"{token} leaked into the text layer of {pdf.name}")
        meta = reader.metadata
        blob = " ".join(
            str(part)
            for part in (
                meta.title if meta else None,
                meta.subject if meta else None,
                meta.keywords if meta else None,
            )
            if part
        ).lower()
        if "synthetic training sample" not in blob:
            failures.append(f"{pdf.name} metadata missing synthetic warning")
    if evidence is not None:
        (evidence / "text-layer.txt").write_text("\n".join(text_parts), encoding="utf-8")
    return failures


def ink_failures(filled: Path, twin: Path, evidence: Path | None) -> list[str]:
    failures: list[str] = []
    summary = [
        f"outside_tol={OUTSIDE_TOL} inside_level={INSIDE_LEVEL} "
        f"inside_min_share={INSIDE_MIN_SHARE}"
    ]
    dpi = int(json.loads((filled / "manifest.json").read_text(encoding="utf-8"))["dpi"])
    labels = read_labels(filled)
    overall = 0
    unchecked = False
    for pdf in sorted(filled.glob("row-*.pdf")):
        twin_pdf = twin / pdf.name
        if not twin_pdf.is_file():
            failures.append(f"twin run has no {pdf.name}")
            unchecked = True
            continue
        filled_pages = render_pages(pdf, dpi)
        twin_pages = render_pages(twin_pdf, dpi)
        if [page.size for page in filled_pages] != [page.size for page in twin_pages]:
            failures.append(f"{pdf.name} and its twin differ in page count or raster size")
            unchecked = True
            continue
        for page_index, (filled_page, twin_page) in enumerate(zip(filled_pages, twin_pages)):
            diff = difference_image(filled_page, twin_page)
            page_labels = [
                label
                for label in labels
                if label["row_id"] == pdf.stem and label["page"] == page_index
            ]
            boxes = [label["box"] for label in page_labels]
            outside = outside_layer(diff, boxes)
            peak = outside.getextrema()[1]
            overall = max(overall, peak)
            line = f"{pdf.name} page={page_index} outside_max={peak}"
            if peak > OUTSIDE_TOL:
                bbox = outside.point(lambda value: 255 if value > OUTSIDE_TOL else 0).getbbox()
                failures.append(
                    f"ink outside label box: {pdf.name} page {page_index} "
                    f"max {peak} limit {OUTSIDE_TOL} bbox {bbox}"
                )
            for label in page_labels:
                share = inside_share(diff, label["box"])
                line += f" {label['field']}={share:.2%}"
                if share < INSIDE_MIN_SHARE:
                    failures.append(
                        f"no ink in label box: {pdf.name} field {label['field']} "
                        f"share {share:.2%} need {INSIDE_MIN_SHARE:.0%} at {INSIDE_LEVEL} or more"
                    )
            summary.append(line)
            if evidence is not None and page_index == 0:
                gained = diff.point(lambda value: min(255, value * DIFF_GAIN))
                gained.save(evidence / f"diff-{pdf.stem}.png")
    if overall > OUTSIDE_TOL:
        summary.append(f"outside_max={overall}")
    elif unchecked:
        summary.append("outside_max=unchecked")
    else:
        summary.append(f"outside_max<={OUTSIDE_TOL}")
    if evidence is not None:
        (evidence / "diff-summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return failures


def check_run(
    filled_dir: Path,
    twin_dir: Path | None = None,
    evidence: Path | None = None,
) -> list[str]:
    failures = structure_failures(filled_dir, evidence)
    if failures or twin_dir is None:
        return failures
    return ink_failures(filled_dir, twin_dir, evidence)


def summary_line(out: Path, checked_ink: bool) -> str:
    labels = read_labels(out)
    fonts = sorted({line["font_id"] for line in labels})
    line = (
        f"pdfs=2 labels={len(labels)} fonts={fonts} "
        f"seed={labels[0]['seed']} warning=ok text_layer=no_answer_tokens"
    )
    if checked_ink:
        line += " ink=checked"
    return line + "\n"


def main() -> None:
    if len(sys.argv) not in (3, 4):
        raise SystemExit("usage: check-fill-boxes.py FILLED_OUT EVIDENCE [TWIN_OUT]")
    out = Path(sys.argv[1])
    evidence = Path(sys.argv[2])
    twin = Path(sys.argv[3]) if len(sys.argv) == 4 else None
    failures = check_run(out, twin, evidence)
    if failures:
        for message in failures:
            print(message, file=sys.stderr)
        raise SystemExit(1)
    summary = summary_line(out, twin is not None)
    (evidence / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary, end="")


if __name__ == "__main__":
    main()
