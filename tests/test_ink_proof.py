import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from synthform.fill import fill_form

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "verify-synthform" / "scripts"
DRIVE_LIMIT_SECONDS = 300


def _load_check():
    spec = importlib.util.spec_from_file_location("check_fill_boxes", SCRIPTS / "check-fill-boxes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_repo(destination: Path, replacement: tuple[str, str] | None) -> Path:
    root = destination / "copy"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(REPO / "src", root / "src", ignore=ignore)
    shutil.copytree(REPO / "skills", root / "skills", ignore=ignore)
    if replacement is not None:
        target = root / "src" / "synthform" / "render.py"
        before = target.read_text(encoding="utf-8")
        old, new = replacement
        after = before.replace(old, new)
        assert after != before
        target.write_text(after, encoding="utf-8")
    return root


def _drive_fill_boxes(root: Path, work: Path) -> tuple[subprocess.CompletedProcess, Path]:
    evidence = work / "evidence"
    env = dict(os.environ)
    env.update(
        PYTHONPATH=str(root / "src"),
        PYTHONDONTWRITEBYTECODE="1",
        SYNTHFORM_PYTHON=sys.executable,
        SYNTHFORM_VERIFY_WORK=str(work / "work"),
        SYNTHFORM_VERIFY_EVIDENCE=str(evidence),
    )
    proc = subprocess.run(
        [str(root / "skills" / "verify-synthform" / "scripts" / "verify-synthform"), "drive-fill-boxes"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=DRIVE_LIMIT_SECONDS,
        check=False,
    )
    return proc, evidence / "fill-boxes"


PAINT_NOTHING = (
    "    fitted = params.size_px\n    if width >= 2 and height >= 2 and text.strip():",
    "    return params\n    fitted = params.size_px\n    if width >= 2 and height >= 2 and text.strip():",
)
PAINT_IN_PAGE_BODY = (
    "    if fitted == params.size_px:\n        return params\n",
    "    body_x = page.width // 2\n"
    "    body_y = int(page.height * 0.92)\n"
    "    page.paste((0, 0, 0), (body_x, body_y, body_x + 2, body_y + 2))\n"
    "    if fitted == params.size_px:\n        return params\n",
)


def test_real_fill_passes_against_its_empty_twin(tmp_path: Path):
    proc, _ = _drive_fill_boxes(_copy_repo(tmp_path, None), tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_passing_drive_writes_the_diff_evidence(tmp_path: Path):
    proc, evidence = _drive_fill_boxes(_copy_repo(tmp_path, None), tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    summary = (evidence / "diff-summary.txt").read_text(encoding="utf-8")
    assert summary.splitlines()[-1] == "outside_max<=8"
    assert (evidence / "diff-row-0001.png").is_file()


def test_paint_nothing_mutant_fails_drive_fill_boxes(tmp_path: Path):
    proc, _ = _drive_fill_boxes(_copy_repo(tmp_path, PAINT_NOTHING), tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "no ink in label box" in proc.stderr


def test_ink_in_the_page_body_fails_drive_fill_boxes(tmp_path: Path):
    proc, evidence = _drive_fill_boxes(_copy_repo(tmp_path, PAINT_IN_PAGE_BODY), tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "ink outside label box" in proc.stderr
    assert "no ink in label box" not in proc.stderr
    last = (evidence / "diff-summary.txt").read_text(encoding="utf-8").splitlines()[-1]
    assert last.startswith("outside_max=")
    assert int(last.split("=")[1]) > 8


def _write_run(directory: Path, page: Image.Image, labels: list[dict]) -> None:
    directory.mkdir(parents=True)
    page.convert("P").save(directory / "row-0001.pdf", "PDF", resolution=72.0)
    (directory / "manifest.json").write_text(json.dumps({"dpi": 72}), encoding="utf-8")
    lines = [json.dumps(label) for label in labels]
    (directory / "labels.jsonl").write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def _label(field: str, x: int) -> dict:
    return {
        "row_id": "row-0001",
        "field": field,
        "page": 0,
        "box": {"x": x, "y": 10, "w": 40, "h": 30},
    }


def _inked_page(*columns: int) -> Image.Image:
    page = Image.new("RGB", (120, 100), (255, 255, 255))
    for x in columns:
        page.paste((0, 0, 0), (x + 5, 15, x + 35, 35))
    return page


def test_check_reads_boxes_from_the_filled_labels(tmp_path: Path):
    check = _load_check()
    blank = Image.new("RGB", (120, 100), (255, 255, 255))
    boxes = [_label("a", 10), _label("b", 70)]
    _write_run(tmp_path / "filled", _inked_page(10, 70), boxes)
    _write_run(tmp_path / "twin", blank, [])
    assert check.ink_failures(tmp_path / "filled", tmp_path / "twin", None) == []

    _write_run(tmp_path / "filled2", _inked_page(10, 70), [])
    _write_run(tmp_path / "twin2", blank, boxes)
    failures = check.ink_failures(tmp_path / "filled2", tmp_path / "twin2", None)
    assert any(message.startswith("ink outside label box") for message in failures)


def test_raster_size_mismatch_fails_and_the_summary_does_not_claim_a_pass(tmp_path: Path):
    check = _load_check()
    boxes = [_label("a", 10)]
    _write_run(tmp_path / "filled", _inked_page(10), boxes)
    _write_run(tmp_path / "twin", Image.new("RGB", (140, 100), (255, 255, 255)), [])
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    failures = check.ink_failures(tmp_path / "filled", tmp_path / "twin", evidence)
    assert any("differ in page count or raster size" in message for message in failures)
    last = (evidence / "diff-summary.txt").read_text(encoding="utf-8").splitlines()[-1]
    assert last == "outside_max=unchecked"
    assert "<=" not in last


def test_missing_twin_pdf_fails_and_the_summary_does_not_claim_a_pass(tmp_path: Path):
    check = _load_check()
    _write_run(tmp_path / "filled", _inked_page(10), [_label("a", 10)])
    (tmp_path / "twin").mkdir()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    failures = check.ink_failures(tmp_path / "filled", tmp_path / "twin", evidence)
    assert failures == ["twin run has no row-0001.pdf"]
    last = (evidence / "diff-summary.txt").read_text(encoding="utf-8").splitlines()[-1]
    assert last == "outside_max=unchecked"


def test_pixel_inside_another_box_is_not_outside(tmp_path: Path):
    check = _load_check()
    blank = Image.new("RGB", (120, 100), (255, 255, 255))
    boxes = [_label("a", 10), _label("b", 70)]
    _write_run(tmp_path / "filled", _inked_page(10), boxes)
    _write_run(tmp_path / "twin", blank, [])
    failures = check.ink_failures(tmp_path / "filled", tmp_path / "twin", None)
    assert [message for message in failures if message.startswith("ink outside")] == []
    assert [message for message in failures if message.startswith("no ink in label box")] != []


def test_colored_leak_is_measured_in_the_worst_channel():
    check = _load_check()
    twin = Image.new("RGB", (100, 100), (255, 255, 255))
    filled = twin.copy()
    filled.paste((235, 255, 255), (30, 30, 54, 54))
    boxes = [{"x": 70, "y": 70, "w": 20, "h": 20}]
    gray_peak = ImageChops.difference(filled.convert("L"), twin.convert("L")).getextrema()[1]
    assert gray_peak == 6
    diff = check.difference_image(filled, twin)
    assert check.outside_max(diff, boxes) == 20
    assert check.outside_max(diff, boxes) > check.OUTSIDE_TOL


def test_locked_limits_have_their_planned_values():
    check = _load_check()
    assert check.OUTSIDE_TOL == 8
    assert check.INSIDE_LEVEL == 48
    assert check.INSIDE_MIN_SHARE == 0.01


def _run_inputs(directory: Path, script: str) -> None:
    subprocess.run(
        [sys.executable, str(SCRIPTS / script), str(directory)],
        check=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def _fill_pair(directory: Path, dpi: int, seed: int) -> tuple[Path, Path]:
    filled = directory / f"filled-{dpi}-{seed}"
    twin = directory / f"twin-{dpi}-{seed}"
    for data, out in (("rows.csv", filled), ("rows-twin.csv", twin)):
        fill_form(
            form=directory / "blank.pdf",
            data=directory / data,
            out=out,
            boxes=directory / "boxes.json",
            dpi=dpi,
            seed=seed,
        )
    return filled, twin


@pytest.mark.parametrize("dpi", [72, 100, 200, 300])
def test_paired_seed_difference_is_inside_the_label_boxes(tmp_path: Path, dpi: int):
    check = _load_check()
    _run_inputs(tmp_path, "make-blank-form.py")
    for seed in (7, 8):
        filled, twin = _fill_pair(tmp_path, dpi, seed)
        assert check.check_run(filled, twin, None) == []


@pytest.mark.parametrize("dpi", [100, 200, 300])
def test_paired_seed_outside_difference_stays_low_for_tight_boxes(tmp_path: Path, dpi: int):
    check = _load_check()
    _run_inputs(tmp_path, "make-blank-form.py")
    tight = [
        {"name": "full_name", "page": 0, "x": 36, "y": 200, "w": 200, "h": 11},
        {"name": "city", "page": 0, "x": 36, "y": 120, "w": 200, "h": 9},
    ]
    (tmp_path / "boxes.json").write_text(json.dumps(tight), encoding="utf-8")
    for seed in (1, 2):
        filled, twin = _fill_pair(tmp_path, dpi, seed)
        labels = check.read_labels(filled)
        for pdf in sorted(filled.glob("row-*.pdf")):
            diff = check.difference_image(
                check.render_pages(pdf, dpi)[0], check.render_pages(twin / pdf.name, dpi)[0]
            )
            boxes = [label["box"] for label in labels if label["row_id"] == pdf.stem]
            assert boxes
            assert check.outside_max(diff, boxes) <= check.OUTSIDE_TOL
