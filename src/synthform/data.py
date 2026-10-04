"""Load a CSV or a JSON list of field rows."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from synthform.errors import ScanformError


def load_rows(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _load_csv(path)
    if suffix == ".json":
        return _load_json(path)
    raise ScanformError("DATA must be a .csv or a .json list of objects")


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ScanformError("CSV has no header row")
        rows = [_stringify(raw) for raw in reader]
    if not rows:
        raise ScanformError("DATA has no rows")
    return rows


def _load_json(path: Path) -> list[dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScanformError(f"DATA is not valid JSON: {exc}") from exc
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ScanformError("JSON DATA must be a list of objects")
    if not payload:
        raise ScanformError("DATA has no rows")
    return [_stringify(item) for item in payload]


def _stringify(raw: dict) -> dict[str, str]:
    row: dict[str, str] = {}
    for key, value in raw.items():
        if key is None:
            continue
        row[str(key)] = "" if value is None else str(value)
    return row
