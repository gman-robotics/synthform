import os
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject, RectangleObject
from reportlab.pdfgen import canvas

from synthform.errors import ScanformError
from synthform.raster import load_form_pages

SRC = Path(__file__).resolve().parents[1] / "src"
ROWS = "full_name,city\nAda Lovelace,London\n"
BOXES = '[{"name": "full_name", "page": 0, "x": 36, "y": 200, "w": 340, "h": 40}]'


def _blank(path: Path, rotate: int | None = None, cropbox: tuple[float, ...] | None = None) -> None:
    source = path.with_name("source.pdf")
    pdf = canvas.Canvas(str(source), pagesize=(420, 300))
    pdf.rect(36, 200, 340, 40, stroke=1, fill=0)
    pdf.save()
    writer = PdfWriter(clone_from=PdfReader(str(source)))
    page = writer.pages[0]
    if rotate is not None:
        page[NameObject("/Rotate")] = NumberObject(rotate)
    if cropbox is not None:
        page.cropbox = RectangleObject(cropbox)
    with path.open("wb") as handle:
        writer.write(handle)


def _run_cli(directory: Path) -> subprocess.CompletedProcess:
    (directory / "rows.csv").write_text(ROWS, encoding="utf-8")
    (directory / "boxes.json").write_text(BOXES, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(SRC), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [
            sys.executable, "-m", "synthform", "fill",
            "--form", str(directory / "blank.pdf"),
            "--data", str(directory / "rows.csv"),
            "--boxes", str(directory / "boxes.json"),
            "--out", str(directory / "out"),
            "--dpi", "72",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.parametrize("rotate", [90, 180, 270, -90])
def test_rotated_pdf_is_refused(tmp_path: Path, rotate: int):
    _blank(tmp_path / "blank.pdf", rotate=rotate)
    proc = _run_cli(tmp_path)
    assert proc.returncode == 2
    assert "/Rotate" in proc.stderr
    assert not (tmp_path / "out").exists()


def test_cropbox_pdf_is_refused(tmp_path: Path):
    _blank(tmp_path / "blank.pdf", cropbox=(10, 10, 400, 280))
    proc = _run_cli(tmp_path)
    assert proc.returncode == 2
    assert "CropBox" in proc.stderr
    assert not (tmp_path / "out").exists()


def test_rotate_360_and_a_cropbox_within_tolerance_are_accepted(tmp_path: Path):
    _blank(tmp_path / "blank.pdf", rotate=360, cropbox=(0.005, 0, 420, 299.995))
    pages, sizes = load_form_pages(tmp_path / "blank.pdf", 72)
    assert len(pages) == 1
    assert sizes[0] == pytest.approx((420.0, 300.0), abs=0.01)


def test_cropbox_beyond_tolerance_is_refused_without_the_cli(tmp_path: Path):
    _blank(tmp_path / "blank.pdf", cropbox=(0.5, 0, 420, 300))
    with pytest.raises(ScanformError, match="CropBox"):
        load_form_pages(tmp_path / "blank.pdf", 72)
