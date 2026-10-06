#!/usr/bin/env python3
"""Measure one synthform fill on a synthetic Letter form: CPU seconds, peak memory, and PDF bytes."""
import argparse
import csv
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

BOX_COUNT = 12
BOX_W = 500
BOX_H = 26
WORDS = (
    "amber", "birch", "cedar", "delta", "ember", "fjord", "grove", "harbor", "island", "juniper",
    "kettle", "lantern", "meadow", "north", "orchard", "pebble", "quarry", "river", "summit", "timber",
    "upland", "valley", "willow", "yarrow", "zephyr", "basalt", "canyon", "dune", "estuary", "fern",
)


def build_inputs(directory: Path, rows: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    width, height = letter
    pdf = canvas.Canvas(str(directory / "blank.pdf"), pagesize=letter)
    pdf.setFont("Times-Roman", 9)
    boxes = []
    for index in range(BOX_COUNT):
        y = height - 72 - (index + 1) * 52
        name = f"field_{index + 1:02d}"
        pdf.drawString(56, y + BOX_H + 4, name)
        pdf.rect(56, y, BOX_W, BOX_H, stroke=1, fill=0)
        boxes.append({"name": name, "page": 0, "x": 56, "y": y, "w": BOX_W, "h": BOX_H})
    pdf.save()
    (directory / "boxes.json").write_text(json.dumps(boxes, indent=2) + "\n", encoding="utf-8")
    rng = random.Random(5)
    names = [box["name"] for box in boxes]
    with (directory / "rows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for _ in range(rows):
            writer.writerow({name: " ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 4))) for name in names})



def peak_rss_mb_from_rusage(ru_maxrss: int) -> float:
    if sys.platform == "darwin":
        return ru_maxrss / (1024.0 * 1024.0)
    return ru_maxrss / 1024.0


def run_once(python: str, inputs: Path, out: Path, dpi: int) -> tuple[float, float]:
    if out.exists():
        shutil.rmtree(out)
    command = [
        python, "-m", "synthform", "fill",
        "--form", str(inputs / "blank.pdf"),
        "--data", str(inputs / "rows.csv"),
        "--boxes", str(inputs / "boxes.json"),
        "--out", str(out),
        "--dpi", str(dpi),
        "--seed", "3",
    ]
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    process = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    stderr = process.stderr.read()
    _, status, usage = os.wait4(process.pid, 0)
    process.returncode = os.waitstatus_to_exitcode(status)
    if process.returncode != 0:
        sys.stderr.write(stderr.decode("utf-8", "replace"))
        raise SystemExit(f"fill exited {process.returncode}")
    return usage.ru_utime + usage.ru_stime, peak_rss_mb_from_rusage(usage.ru_maxrss)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("/tmp/synthform-bench"))
    parser.add_argument("--rows", type=int, default=30)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--keep-out", type=Path)
    args = parser.parse_args()
    inputs = args.work / "in"
    out = args.work / "out"
    build_inputs(inputs, args.rows)
    cpu: list[float] = []
    peak = 0.0
    for _ in range(args.runs):
        seconds, rss_mb = run_once(args.python, inputs, out, args.dpi)
        cpu.append(round(seconds, 2))
        peak = max(peak, rss_mb)
    pdf_bytes = sum(path.stat().st_size for path in out.glob("row-*.pdf"))
    if args.keep_out is not None:
        if args.keep_out.exists():
            shutil.rmtree(args.keep_out)
        shutil.copytree(out, args.keep_out)
    result = {
        "rows": args.rows,
        "dpi": args.dpi,
        "cpu_seconds": cpu,
        "best_cpu_seconds": min(cpu),
        "peak_rss_mb": round(peak, 1),
        "pdf_bytes": pdf_bytes,
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
