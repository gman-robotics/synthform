import csv
import gc
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from PIL.JpegImagePlugin import JpegImageFile
from pypdf import PdfReader
from reportlab import rl_config
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from synthform import SYNTHETIC_WARNING, __version__
from synthform import fill as fill_module
from synthform import pdfout
from synthform.cli import main
from synthform.fill import fill_form

ANSWERS = (
    {"full_name": "QXNAME-ALPHA-7741", "city": "QXCITY-ALPHA-2290"},
    {"full_name": "QXNAME-BETA-8832", "city": "QXCITY-BETA-1104"},
)


def test_fill_two_csv_rows_writes_image_only_pdfs(tmp_path: Path):
    form = tmp_path / "blank.pdf"
    boxes = _write_blank_form(form)
    boxes_path = tmp_path / "boxes.json"
    boxes_path.write_text(json.dumps(boxes), encoding="utf-8")
    data = tmp_path / "rows.csv"
    _write_csv(data, ANSWERS)
    out = tmp_path / "out"

    assert main(
        [
            "fill",
            "--form",
            str(form),
            "--data",
            str(data),
            "--boxes",
            str(boxes_path),
            "--out",
            str(out),
            "--dpi",
            "100",
            "--seed",
            "7",
        ]
    ) == 0

    _assert_run(out, seed=7, dpi=100)


def test_same_seed_repeats_labels(tmp_path: Path):
    form = tmp_path / "blank.pdf"
    boxes = _write_blank_form(form)
    boxes_path = tmp_path / "boxes.json"
    boxes_path.write_text(json.dumps(boxes), encoding="utf-8")
    data = tmp_path / "rows.csv"
    _write_csv(data, ANSWERS)
    first = tmp_path / "a"
    second = tmp_path / "b"
    args = [
        "--form",
        str(form),
        "--data",
        str(data),
        "--boxes",
        str(boxes_path),
        "--dpi",
        "72",
        "--seed",
        "7",
    ]
    assert main(["fill", *args, "--out", str(first)]) == 0
    assert main(["fill", *args, "--out", str(second)]) == 0
    assert (first / "labels.jsonl").read_text(encoding="utf-8") == (
        second / "labels.jsonl"
    ).read_text(encoding="utf-8")


def test_acroform_fields_are_used_when_boxes_are_missing(tmp_path: Path):
    form = tmp_path / "acro.pdf"
    _write_acro_form(form)
    decoy = tmp_path / "boxes.json"
    decoy.write_text(
        json.dumps([{"name": "other", "page": 0, "x": 10, "y": 10, "w": 40, "h": 20}]),
        encoding="utf-8",
    )
    data = tmp_path / "rows.csv"
    _write_csv(data, ANSWERS)
    out = tmp_path / "out"
    assert main(
        [
            "fill",
            "--form",
            str(form),
            "--data",
            str(data),
            "--boxes",
            str(decoy),
            "--out",
            str(out),
            "--dpi",
            "90",
            "--seed",
            "3",
        ]
    ) == 0
    labels = _read_labels(out)
    assert {line["field"] for line in labels} == {"full_name", "city"}
    _assert_answers_are_not_text(out)


def test_json_rows_fill_an_image_form(tmp_path: Path):
    form = tmp_path / "blank.png"
    Image.new("RGB", (360, 240), (255, 255, 255)).save(form)
    boxes = [
        {"name": "full_name", "page": 0, "x": 20, "y": 150, "w": 220, "h": 36},
        {"name": "city", "page": 0, "x": 20, "y": 80, "w": 220, "h": 36},
    ]
    boxes_path = tmp_path / "boxes.json"
    boxes_path.write_text(json.dumps(boxes), encoding="utf-8")
    data = tmp_path / "rows.json"
    data.write_text(json.dumps([ANSWERS[0]]), encoding="utf-8")
    out = tmp_path / "out"
    assert main(
        [
            "fill",
            "--form",
            str(form),
            "--data",
            str(data),
            "--boxes",
            str(boxes_path),
            "--out",
            str(out),
            "--dpi",
            "72",
            "--seed",
            "1",
        ]
    ) == 0
    assert (out / "row-0001.pdf").is_file()
    assert not (out / "row-0002.pdf").exists()
    labels = _read_labels(out)
    assert len(labels) == 2
    _assert_answers_are_not_text(out)


def test_pdf_without_fields_requires_boxes(tmp_path: Path):
    form = tmp_path / "blank.pdf"
    _write_blank_form(form)
    data = tmp_path / "rows.csv"
    _write_csv(data, ANSWERS)
    assert main(
        ["fill", "--form", str(form), "--data", str(data), "--out", str(tmp_path / "out")]
    ) == 2


def test_unfit_token_gets_no_label_a_stderr_line_and_a_skipped_field(tmp_path: Path, capsys):
    form = tmp_path / "blank.pdf"
    pdf = canvas.Canvas(str(form), pagesize=(300, 200))
    pdf.rect(20, 100, 110, 42, stroke=1, fill=0)
    pdf.save()
    boxes_path = tmp_path / "boxes.json"
    boxes_path.write_text(
        json.dumps(
            [
                {"name": "notes", "page": 0, "x": 20, "y": 100, "w": 110, "h": 42},
                {"name": "full_name", "page": 0, "x": 20, "y": 30, "w": 200, "h": 40},
            ]
        ),
        encoding="utf-8",
    )
    token = "SUPERCALIFRAGILISTIC-VALUE-998877" * 2
    data = tmp_path / "rows.csv"
    with data.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["notes", "full_name"])
        writer.writeheader()
        writer.writerow({"notes": token, "full_name": "Ada Lovelace"})
        writer.writerow({"notes": "Ada", "full_name": "Grace Hopper"})
    out = tmp_path / "out"

    assert main(
        [
            "fill",
            "--form", str(form),
            "--data", str(data),
            "--boxes", str(boxes_path),
            "--out", str(out),
            "--dpi", "72",
            "--seed", "4",
        ]
    ) == 0

    labels = _read_labels(out)
    assert [(line["row_id"], line["field"]) for line in labels] == [
        ("row-0001", "full_name"),
        ("row-0002", "notes"),
        ("row-0002", "full_name"),
    ]
    assert token not in {line["text"] for line in labels}
    stderr_lines = capsys.readouterr().err.splitlines()
    assert [line for line in stderr_lines if "text does not fit" in line] == [
        "synthform: row-0001 field 'notes': text does not fit"
    ]
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["skipped_fields"] == [{"row_id": "row-0001", "field": "notes"}]


@pytest.mark.parametrize("columns", ["empty", "unboxed"])
def test_no_label_written_warns_and_exits_0(tmp_path: Path, capsys, columns: str):
    form = tmp_path / "blank.pdf"
    boxes = _write_blank_form(form)
    boxes_path = tmp_path / "boxes.json"
    boxes_path.write_text(json.dumps(boxes), encoding="utf-8")
    data = tmp_path / "rows.csv"
    with data.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["full_name", "city", "extra"])
        writer.writeheader()
        extra = "no box for this" if columns == "unboxed" else ""
        writer.writerow({"full_name": "", "city": "", "extra": extra})
    out = tmp_path / "out"

    assert main(
        [
            "fill",
            "--form", str(form),
            "--data", str(data),
            "--boxes", str(boxes_path),
            "--out", str(out),
            "--dpi", "72",
            "--seed", "2",
        ]
    ) == 0

    assert "no label written" in capsys.readouterr().err
    assert (out / "labels.jsonl").read_text(encoding="utf-8") == ""
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8"))["skipped_fields"] == []


def test_a_run_with_labels_does_not_warn_about_missing_labels(tmp_path: Path, capsys):
    form = tmp_path / "blank.pdf"
    boxes = _write_blank_form(form)
    boxes_path = tmp_path / "boxes.json"
    boxes_path.write_text(json.dumps(boxes), encoding="utf-8")
    data = tmp_path / "rows.csv"
    _write_csv(data, ANSWERS)
    assert main(
        ["fill", "--form", str(form), "--data", str(data), "--boxes", str(boxes_path),
         "--out", str(tmp_path / "out"), "--dpi", "72", "--seed", "2"]
    ) == 0
    err = capsys.readouterr().err
    assert "no label written" not in err
    assert "text does not fit" not in err


def test_field_jitter_differs_by_row_through_fill_form(tmp_path: Path):
    form = tmp_path / "blank.pdf"
    boxes = _write_blank_form(form)
    boxes_path = tmp_path / "boxes.json"
    boxes_path.write_text(json.dumps(boxes), encoding="utf-8")
    data = tmp_path / "rows.csv"
    _write_csv(data, [{"full_name": f"Name {index}", "city": f"City {index}"} for index in range(30)])
    out = tmp_path / "out"
    fill_form(form=form, data=data, out=out, boxes=boxes_path, dpi=72, seed=3)

    groups: dict[tuple[str, str], list[tuple]] = {}
    for line in _read_labels(out):
        jitter = line["jitter"]
        style = line["style"]
        residual = (
            jitter["dx"],
            round(jitter["rotation"] - style["rotation"], 3),
            round(jitter["tracking_em"] - style["tracking"], 4),
            tuple(a - b for a, b in zip(jitter["ink"], style["ink"])),
        )
        groups.setdefault((line["font_id"], line["field"]), []).append(residual)
    repeated = [residuals for residuals in groups.values() if len(residuals) >= 2]
    assert repeated
    for residuals in repeated:
        assert len(set(residuals)) == len(residuals)


def test_help_states_the_synthetic_limit():
    proc = subprocess.run(
        [sys.executable, "-m", "synthform", "fill", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "--form" in proc.stdout
    assert "Form 1583" in proc.stdout
    assert "synthetic training sample" in proc.stdout.lower()


def _assert_run(out: Path, seed: int, dpi: int) -> None:
    assert (out / "row-0001.pdf").is_file()
    assert (out / "row-0002.pdf").is_file()
    labels = _read_labels(out)
    assert len(labels) == 4
    assert sorted(line["text"] for line in labels) == sorted(
        value for row in ANSWERS for value in row.values()
    )
    by_row: dict[str, list[dict]] = {}
    for line in labels:
        assert {"row_id", "field", "text", "page", "box", "font_id", "seed"} <= line.keys()
        assert line["page"] == 0
        assert line["seed"] == seed
        assert line["font_id"]
        assert line["style"]["ink"] != [0, 0, 0]
        assert line["jitter"]["ink"] != [0, 0, 0]
        box = line["box"]
        assert set(box) == {"x", "y", "w", "h"}
        for key in ("x", "y", "w", "h"):
            assert isinstance(box[key], int)
            assert box[key] >= 0
        by_row.setdefault(line["row_id"], []).append(line)
    assert set(by_row) == {"row-0001", "row-0002"}
    row_keys = set()
    for row_id, lines in by_row.items():
        assert len(lines) == 2
        styles = {json.dumps(line["style"], sort_keys=True) for line in lines}
        fonts = {line["font_id"] for line in lines}
        assert len(styles) == 1
        assert len(fonts) == 1
        assert lines[0]["jitter"] != lines[1]["jitter"]
        row_keys.add((next(iter(fonts)), next(iter(styles))))
    assert len(row_keys) == 2
    _assert_answers_are_not_text(out)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["generator"] == "synthform"
    assert manifest["version"] == __version__
    assert manifest["warning"] == SYNTHETIC_WARNING
    assert "synthetic training sample" in manifest["warning"].lower()
    assert manifest["seed"] == seed
    assert manifest["dpi"] == dpi
    assert manifest["row_count"] == 2
    for pdf in (out / "row-0001.pdf", out / "row-0002.pdf"):
        _assert_boxes_fit_page(pdf, [line for line in labels if line["row_id"] == pdf.stem], dpi)


def _assert_answers_are_not_text(out: Path) -> None:
    for pdf in sorted(out.glob("row-*.pdf")):
        reader = PdfReader(str(pdf))
        extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        for row in ANSWERS:
            for value in row.values():
                assert value not in extracted
        meta = reader.metadata
        assert meta is not None
        blob = " ".join(
            str(part)
            for part in (
                meta.title,
                meta.subject,
                meta.keywords,
                meta.creator,
                meta.producer,
                meta.author,
            )
            if part
        ).lower()
        assert "synthetic training sample" in blob
        assert "not a signed original" in blob
        assert pdf.read_bytes().startswith(b"%PDF")


def _assert_boxes_fit_page(pdf: Path, lines: list[dict], dpi: int) -> None:
    reader = PdfReader(str(pdf))
    page = reader.pages[0]
    width_px = int(round(float(page.mediabox.width) * dpi / 72))
    height_px = int(round(float(page.mediabox.height) * dpi / 72))
    for line in lines:
        box = line["box"]
        assert box["x"] + box["w"] <= width_px
        assert box["y"] + box["h"] <= height_px


def _read_labels(out: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (out / "labels.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]


def _write_csv(path: Path, rows: tuple[dict[str, str], ...] | list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["full_name", "city"])
        writer.writeheader()
        writer.writerows(rows)


def _write_blank_form(path: Path) -> list[dict[str, object]]:
    pdf = canvas.Canvas(str(path), pagesize=(420, 300))
    pdf.setFont("Times-Roman", 11)
    pdf.drawString(36, 250, "Full name")
    pdf.rect(36, 200, 340, 40, stroke=1, fill=0)
    pdf.drawString(36, 170, "City")
    pdf.rect(36, 120, 340, 40, stroke=1, fill=0)
    pdf.save()
    return [
        {"name": "full_name", "page": 0, "x": 36, "y": 200, "w": 340, "h": 40},
        {"name": "city", "page": 0, "x": 36, "y": 120, "w": 340, "h": 40},
    ]


def _write_acro_form(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=(420, 320))
    pdf.setFont("Times-Roman", 11)
    pdf.drawString(36, 280, "Full name")
    pdf.drawString(36, 200, "City")
    pdf.acroForm.textfield(
        name="full_name",
        x=36,
        y=230,
        width=320,
        height=40,
        borderWidth=1,
        forceBorder=True,
        fontSize=12,
    )
    pdf.acroForm.textfield(
        name="city",
        x=36,
        y=150,
        width=320,
        height=40,
        borderWidth=1,
        forceBorder=True,
        fontSize=12,
    )
    pdf.save()


def _fill_two_rows(tmp_path: Path, out_name: str = "out", dpi: int = 100) -> Path:
    form = tmp_path / "blank.pdf"
    boxes_path = tmp_path / "boxes.json"
    if not form.exists():
        boxes_path.write_text(json.dumps(_write_blank_form(form)), encoding="utf-8")
        _write_csv(tmp_path / "rows.csv", ANSWERS)
    out = tmp_path / out_name
    fill_form(form=form, data=tmp_path / "rows.csv", out=out, boxes=boxes_path, dpi=dpi, seed=7)
    return out


def _image_streams(pdf: Path) -> list:
    reader = PdfReader(str(pdf))
    streams = []
    for page in reader.pages:
        xobjects = page["/Resources"]["/XObject"]
        for name in xobjects:
            obj = xobjects[name].get_object()
            if obj["/Subtype"] == "/Image":
                streams.append(obj)
    return streams


def _filters(stream) -> list[str]:
    value = stream.get("/Filter")
    if value is None:
        return []
    if isinstance(value, str):
        return [str(value)]
    return [str(item) for item in value]


def test_pdf_embeds_the_jpeg_as_is(tmp_path: Path, monkeypatch):
    loads: list[int] = []
    real_load = JpegImageFile.load

    def counting_load(self, *args, **kwargs):
        loads.append(1)
        return real_load(self, *args, **kwargs)

    monkeypatch.setattr(JpegImageFile, "load", counting_load)
    written: list[tuple[Path, list, int]] = []
    real_write = fill_module.write_image_pdf

    def spy(path: Path, pages: list, dpi: int) -> None:
        written.append((path, list(pages), len(loads)))
        real_write(path, pages, dpi)
        loads.clear()

    monkeypatch.setattr(fill_module, "write_image_pdf", spy)
    _fill_two_rows(tmp_path)

    assert len(written) == 2
    for path, pages, loads_before_write in written:
        assert loads_before_write == 0
        assert all(isinstance(page, bytes) for page in pages)
        streams = _image_streams(path)
        assert len(streams) == len(pages) == 1
        for stream, page in zip(streams, pages):
            assert _filters(stream) == ["/DCTDecode"]
            assert stream._data == page


def test_pdf_metadata_is_written_once(tmp_path: Path):
    assert not hasattr(pdfout, "PdfWriter")
    assert not hasattr(pdfout, "_stamp_metadata")
    source = Path(pdfout.__file__).read_text(encoding="utf-8")
    assert "pypdf" not in source
    first = _fill_two_rows(tmp_path, "a")
    second = _fill_two_rows(tmp_path, "b")
    for name in ("row-0001.pdf", "row-0002.pdf"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
        meta = PdfReader(str(first / name)).metadata
        assert meta.title == "Synthetic training sample"
        assert meta.subject == SYNTHETIC_WARNING
        assert meta.keywords == "synthetic training sample, not a signed original"
        assert meta.creator == f"synthform {__version__}"
        assert meta.author == "synthform synthetic training generator"
        assert meta.producer == f"synthform {__version__} synthetic training sample"


def test_pdf_writer_leaves_the_reportlab_ascii85_setting_alone(tmp_path: Path):
    before = rl_config.useA85
    _fill_two_rows(tmp_path)
    assert rl_config.useA85 == before
    other = tmp_path / "other.pdf"
    pdf = canvas.Canvas(str(other), pagesize=(200, 200))
    pdf.drawImage(_small_png(tmp_path), 10, 10, width=50, height=50)
    pdf.save()
    filters = _filters(_image_streams(other)[0])
    assert ("/ASCII85Decode" in filters) == bool(before)


def _small_png(tmp_path: Path) -> str:
    path = tmp_path / "small.png"
    Image.new("RGB", (8, 8), (200, 10, 10)).save(path)
    return str(path)


def test_pdf_writer_frees_each_page_reader_without_gc(tmp_path: Path):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (240, 240, 236)).save(buffer, format="JPEG", quality=80)
    gc.collect()
    gc.disable()
    try:
        pdfout.write_image_pdf(tmp_path / "one.pdf", [buffer.getvalue(), buffer.getvalue()], 72)
        alive = [item for item in gc.get_objects() if isinstance(item, ImageReader)]
    finally:
        gc.enable()
    assert alive == []
