#!/usr/bin/env python3
"""Write the verification blank form, boxes, and two-row CSV. Not a user form."""
import csv
import json
import sys
from pathlib import Path

from reportlab.pdfgen import canvas

ROWS = (
    {"full_name": "QXNAME-ALPHA-7741", "city": "QXCITY-ALPHA-2290"},
    {"full_name": "QXNAME-BETA-8832", "city": "QXCITY-BETA-1104"},
)
BOXES = [
    {"name": "full_name", "page": 0, "x": 36, "y": 200, "w": 340, "h": 40},
    {"name": "city", "page": 0, "x": 36, "y": 120, "w": 340, "h": 40},
]


def write_rows(path: Path, rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["full_name", "city"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    run = Path(sys.argv[1])
    form = run / "blank.pdf"
    pdf = canvas.Canvas(str(form), pagesize=(420, 300))
    pdf.setFont("Times-Roman", 11)
    pdf.drawString(36, 250, "Full name")
    pdf.rect(36, 200, 340, 40, stroke=1, fill=0)
    pdf.drawString(36, 170, "City")
    pdf.rect(36, 120, 340, 40, stroke=1, fill=0)
    pdf.save()
    (run / "boxes.json").write_text(json.dumps(BOXES), encoding="utf-8")
    write_rows(run / "rows.csv", ROWS)
    write_rows(run / "rows-twin.csv", [{"full_name": "", "city": ""} for _ in ROWS])


if __name__ == "__main__":
    main()
