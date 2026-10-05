#!/usr/bin/env python3
import csv
import json
import sys
from pathlib import Path

from reportlab.pdfgen import canvas

ROWS = (
    {"full_name": "QXNAME-ALPHA-7741", "city": "QXCITY-ALPHA-2290"},
    {"full_name": "QXNAME-BETA-8832", "city": "QXCITY-BETA-1104"},
)
DECOY = [{"name": "other", "page": 0, "x": 10, "y": 10, "w": 40, "h": 20}]


def main() -> None:
    run = Path(sys.argv[1])
    pdf = canvas.Canvas(str(run / "acro.pdf"), pagesize=(420, 320))
    pdf.setFont("Times-Roman", 11)
    pdf.drawString(36, 280, "Full name")
    pdf.drawString(36, 200, "City")
    for name, y in (("full_name", 230), ("city", 150)):
        pdf.acroForm.textfield(
            name=name,
            x=36,
            y=y,
            width=320,
            height=40,
            borderWidth=1,
            forceBorder=True,
            fontSize=12,
        )
    pdf.save()
    (run / "decoy-boxes.json").write_text(json.dumps(DECOY), encoding="utf-8")
    with (run / "rows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["full_name", "city"])
        writer.writeheader()
        writer.writerows(ROWS)


if __name__ == "__main__":
    main()
