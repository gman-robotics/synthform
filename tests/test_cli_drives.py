import json
import os
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "verify-synthform" / "scripts"
TOKENS = ("QXNAME-ALPHA-7741", "QXCITY-ALPHA-2290", "QXNAME-BETA-8832", "QXCITY-BETA-1104")
MISSING_BOXES = "PDF has no AcroForm text fields; pass --boxes"


def _env(hashseed: str = "random") -> dict:
    env = dict(os.environ)
    env.update(
        PYTHONPATH=str(REPO / "src"),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONHASHSEED=hashseed,
    )
    return env


def _build(script: str, directory: Path) -> None:
    subprocess.run(
        [sys.executable, str(SCRIPTS / script), str(directory)],
        check=True,
        capture_output=True,
        env=_env(),
    )


def _fill(args: list[str], hashseed: str = "random") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "synthform", "fill", *args],
        check=False,
        capture_output=True,
        text=True,
        env=_env(hashseed),
    )


def _labels(out: Path) -> list[dict]:
    text = (out / "labels.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def _assert_no_tokens_in_text_layer(out: Path) -> None:
    for pdf in sorted(out.glob("row-*.pdf")):
        extracted = "\n".join((page.extract_text() or "") for page in PdfReader(str(pdf)).pages)
        for token in TOKENS:
            assert token not in extracted


def test_drive_acroform_uses_widget_names(tmp_path: Path):
    _build("make-acroform.py", tmp_path)
    out = tmp_path / "out"
    proc = _fill(
        [
            "--form", str(tmp_path / "acro.pdf"),
            "--data", str(tmp_path / "rows.csv"),
            "--boxes", str(tmp_path / "decoy-boxes.json"),
            "--out", str(out),
            "--dpi", "90",
            "--seed", "3",
        ]
    )
    assert proc.returncode == 0, proc.stderr
    assert {line["field"] for line in _labels(out)} == {"full_name", "city"}
    _assert_no_tokens_in_text_layer(out)


def test_drive_json_and_png_writes_one_pdf(tmp_path: Path):
    _build("make-png-form.py", tmp_path)
    out = tmp_path / "out"
    proc = _fill(
        [
            "--form", str(tmp_path / "blank.png"),
            "--data", str(tmp_path / "rows.json"),
            "--boxes", str(tmp_path / "boxes.json"),
            "--out", str(out),
            "--dpi", "72",
            "--seed", "1",
        ]
    )
    assert proc.returncode == 0, proc.stderr
    assert (out / "row-0001.pdf").is_file()
    assert not (out / "row-0002.pdf").exists()
    assert len(_labels(out)) == 2
    _assert_no_tokens_in_text_layer(out)


def test_two_processes_write_identical_labels(tmp_path: Path):
    _build("make-blank-form.py", tmp_path)
    first = tmp_path / "out-a"
    second = tmp_path / "out-b"
    for out, hashseed in ((first, "1"), (second, "2")):
        proc = _fill(
            [
                "--form", str(tmp_path / "blank.pdf"),
                "--data", str(tmp_path / "rows.csv"),
                "--boxes", str(tmp_path / "boxes.json"),
                "--out", str(out),
                "--dpi", "72",
                "--seed", "7",
            ],
            hashseed,
        )
        assert proc.returncode == 0, proc.stderr
    assert (first / "labels.jsonl").read_bytes() == (second / "labels.jsonl").read_bytes()


def test_missing_boxes_exits_2_and_creates_no_pdf(tmp_path: Path):
    _build("make-blank-form.py", tmp_path)
    out = tmp_path / "out"
    proc = _fill(
        ["--form", str(tmp_path / "blank.pdf"), "--data", str(tmp_path / "rows.csv"), "--out", str(out)]
    )
    assert proc.returncode == 2
    assert MISSING_BOXES in proc.stderr
    assert not out.exists()
