#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from PIL import Image

ROW = {"full_name": "QXNAME-ALPHA-7741", "city": "QXCITY-ALPHA-2290"}
BOXES = [
    {"name": "full_name", "page": 0, "x": 20, "y": 150, "w": 220, "h": 36},
    {"name": "city", "page": 0, "x": 20, "y": 80, "w": 220, "h": 36},
]


def main() -> None:
    run = Path(sys.argv[1])
    Image.new("RGB", (360, 240), (255, 255, 255)).save(run / "blank.png")
    (run / "boxes.json").write_text(json.dumps(BOXES), encoding="utf-8")
    (run / "rows.json").write_text(json.dumps([ROW]), encoding="utf-8")


if __name__ == "__main__":
    main()
