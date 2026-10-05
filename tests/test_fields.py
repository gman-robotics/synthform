import json
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject
from reportlab.pdfgen import canvas

from synthform.errors import ScanformError
from synthform.fields import extract_acroform_boxes, resolve_fields

KINDS = ("direct", "parent", "sig", "btn", "ch", "none")


def _build(path: Path, kinds: tuple[str, ...]) -> None:
    source = path.with_name("source.pdf")
    pdf = canvas.Canvas(str(source), pagesize=(420, 400))
    for index, kind in enumerate(kinds):
        pdf.acroForm.textfield(
            name=kind,
            x=30,
            y=340 - index * 50,
            width=300,
            height=30,
            borderWidth=1,
            forceBorder=True,
        )
    pdf.save()
    writer = PdfWriter(clone_from=PdfReader(str(source)))
    by_name = {}
    for annot in writer.pages[0]["/Annots"]:
        widget = annot.get_object()
        by_name[str(widget["/T"])] = widget
    for kind, field_type in (("sig", "/Sig"), ("btn", "/Btn"), ("ch", "/Ch")):
        if kind in by_name:
            by_name[kind][NameObject("/FT")] = NameObject(field_type)
    if "none" in by_name:
        del by_name["none"]["/FT"]
    if "parent" in by_name:
        widget = by_name["parent"]
        del widget["/FT"]
        group = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("group"),
                NameObject("/FT"): NameObject("/Tx"),
            }
        )
        group_ref = writer._add_object(group)
        group[NameObject("/Kids")] = ArrayObject([widget.indirect_reference])
        widget[NameObject("/Parent")] = group_ref
    with path.open("wb") as handle:
        writer.write(handle)


def test_only_text_widgets_are_filled(tmp_path: Path):
    form = tmp_path / "mixed.pdf"
    _build(form, KINDS)
    names = {box.name for box in extract_acroform_boxes(form)}
    assert names == {"direct", "group.parent"}


def test_text_field_type_is_inherited_from_the_parent(tmp_path: Path):
    form = tmp_path / "parent.pdf"
    _build(form, ("parent",))
    assert [box.name for box in extract_acroform_boxes(form)] == ["group.parent"]


@pytest.mark.parametrize("kind", ["sig", "btn", "ch", "none"])
def test_choice_only_pdf_uses_boxes(tmp_path: Path, kind: str):
    form = tmp_path / "only.pdf"
    _build(form, (kind,))
    assert extract_acroform_boxes(form) == []
    with pytest.raises(ScanformError, match="--boxes"):
        resolve_fields(form, None)
    boxes_path = tmp_path / "boxes.json"
    boxes_path.write_text(
        json.dumps([{"name": "city", "page": 0, "x": 10, "y": 10, "w": 100, "h": 20}]),
        encoding="utf-8",
    )
    assert [box.name for box in resolve_fields(form, boxes_path)] == ["city"]
