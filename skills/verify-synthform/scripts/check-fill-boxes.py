#!/usr/bin/env python3
"""Check a fill-boxes run and write the proof summary. Reads files only."""
import json
import sys
from pathlib import Path

from pypdf import PdfReader

ANSWERS = ("QXNAME-ALPHA-7741", "QXCITY-ALPHA-2290", "QXNAME-BETA-8832", "QXCITY-BETA-1104")


def main() -> None:
    out = Path(sys.argv[1])
    evidence = Path(sys.argv[2])
    labels = [
        json.loads(line)
        for line in (out / "labels.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    if len(list(out.glob("row-*.pdf"))) != 2:
        raise SystemExit("expected two PDFs")
    if len(labels) != 4:
        raise SystemExit(f"expected 4 label lines, got {len(labels)}")
    if manifest.get("row_count") != 2:
        raise SystemExit("manifest row_count is not 2")
    warning = str(manifest.get("warning", "")).lower()
    if "synthetic training sample" not in warning or "not a signed original" not in warning:
        raise SystemExit("manifest warning missing")
    fonts = {line["font_id"] for line in labels}
    text_parts = []
    for pdf in sorted(out.glob("row-*.pdf")):
        reader = PdfReader(str(pdf))
        extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        text_parts.append(f"== {pdf.name} ==\n{extracted}")
        for token in ANSWERS:
            if token in extracted:
                raise SystemExit(f"{token} leaked into the text layer of {pdf.name}")
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
            raise SystemExit(f"{pdf.name} metadata missing synthetic warning")
    (evidence / "text-layer.txt").write_text("\n".join(text_parts), encoding="utf-8")
    summary = (
        f"pdfs=2 labels={len(labels)} fonts={sorted(fonts)} "
        f"seed={labels[0]['seed']} warning=ok text_layer=no_answer_tokens\n"
    )
    (evidence / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary, end="")


if __name__ == "__main__":
    main()
