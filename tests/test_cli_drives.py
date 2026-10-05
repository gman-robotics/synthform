import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
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


SHELL_DRIVES = (
    "drive-fill-acroform",
    "drive-fill-json-image",
    "drive-seed-repro",
    "drive-refuse-missing-boxes",
    "drive-all",
)
DRIVE_TOOLS = ("bash", "grep", "cmp", "cp")
DRIVE_LIMIT_SECONDS = 600


def _run_shell_drive(drive: str, tmp_path: Path) -> tuple[subprocess.CompletedProcess, Path]:
    for tool in DRIVE_TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f"{tool} is not installed, so the shell drive cannot run")
    evidence = tmp_path / "evidence"
    env = _env()
    env.update(
        SYNTHFORM_PYTHON=sys.executable,
        SYNTHFORM_VERIFY_WORK=str(tmp_path / "work"),
        SYNTHFORM_VERIFY_EVIDENCE=str(evidence),
    )
    proc = subprocess.run(
        [str(SCRIPTS / "verify-synthform"), drive],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=DRIVE_LIMIT_SECONDS,
        check=False,
    )
    return proc, evidence


@pytest.mark.parametrize("drive", SHELL_DRIVES)
def test_shell_drive_exits_0_and_writes_evidence(tmp_path: Path, drive: str):
    proc, evidence = _run_shell_drive(drive, tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip().splitlines()[-1].startswith(f"{drive} ok")
    folders = sorted(path.name for path in evidence.iterdir())
    if drive == "drive-all":
        assert folders == ["fill-acroform", "fill-boxes", "fill-json-image", "refuse-missing-boxes", "seed-repro"]
    else:
        assert folders == [drive.removeprefix("drive-")]
    for folder in evidence.iterdir():
        assert (folder / "exit_code.txt").is_file() or (folder / "exit_code-a.txt").is_file(), folder


def test_unknown_shell_drive_name_exits_2(tmp_path: Path):
    proc, _ = _run_shell_drive("drive-nothing", tmp_path)
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_bench_script_measures_a_small_run(tmp_path: Path):
    work = tmp_path / "bench"
    keep = tmp_path / "kept"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "bench-fill.py"),
            "--work", str(work),
            "--rows", "2",
            "--runs", "2",
            "--dpi", "72",
            "--keep-out", str(keep),
        ],
        cwd=REPO,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["rows"] == 2
    assert result["dpi"] == 72
    assert len(result["cpu_seconds"]) == 2
    assert result["best_cpu_seconds"] == min(result["cpu_seconds"])
    assert result["peak_rss_mb"] > 0
    assert result["pdf_bytes"] == sum(path.stat().st_size for path in keep.glob("row-*.pdf"))
    assert sorted(path.name for path in keep.glob("row-*.pdf")) == ["row-0001.pdf", "row-0002.pdf"]
    assert len((keep / "labels.jsonl").read_text(encoding="utf-8").splitlines()) == 24
