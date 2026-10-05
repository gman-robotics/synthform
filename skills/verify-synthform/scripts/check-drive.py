#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from pypdf import PdfReader

ANSWERS = ("QXNAME-ALPHA-7741", "QXCITY-ALPHA-2290", "QXNAME-BETA-8832", "QXCITY-BETA-1104")


def fail(message: str) -> None:
    raise SystemExit(message)


def text_layer_is_clean(out: Path) -> str:
    parts = []
    for pdf in sorted(out.glob("row-*.pdf")):
        reader = PdfReader(str(pdf))
        extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        for token in ANSWERS:
            if token in extracted:
                fail(f"{token} leaked into the text layer of {pdf.name}")
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
            fail(f"{pdf.name} metadata missing synthetic warning")
        parts.append(f"== {pdf.name} ==\n{extracted}")
    return "\n".join(parts)


def read_labels(out: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (out / "labels.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]


def main() -> None:
    kind = sys.argv[1]
    out = Path(sys.argv[2])
    evidence = Path(sys.argv[3])
    labels = read_labels(out)
    pdfs = sorted(path.name for path in out.glob("row-*.pdf"))
    if kind == "acroform":
        fields = {line["field"] for line in labels}
        if fields != {"full_name", "city"}:
            fail(f"label fields are {sorted(fields)}, expected the widget names")
        if pdfs != ["row-0001.pdf", "row-0002.pdf"] or len(labels) != 4:
            fail(f"expected two PDFs and four labels, got {pdfs} and {len(labels)}")
    elif kind == "json-image":
        if pdfs != ["row-0001.pdf"] or len(labels) != 2:
            fail(f"expected one PDF and two labels, got {pdfs} and {len(labels)}")
    else:
        fail(f"unknown kind {kind}")
    (evidence / "text-layer.txt").write_text(text_layer_is_clean(out), encoding="utf-8")
    summary = f"kind={kind} pdfs={len(pdfs)} labels={len(labels)} text_layer=no_answer_tokens\n"
    (evidence / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary, end="")


if __name__ == "__main__":
    main()
