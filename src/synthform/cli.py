"""Command line for synthform fill."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from synthform import SYNTHETIC_WARNING, __version__
from synthform.errors import ScanformError
from synthform.fill import fill_form

_DESCRIPTION = (
    "Generate synthetic scanned-form training samples. "
    + SYNTHETIC_WARNING
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="synthform", description=_DESCRIPTION)
    parser.add_argument("--version", action="version", version=f"synthform {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    fill = commands.add_parser("fill", help="Fill a blank form from a table of synthetic values", description=_DESCRIPTION)
    fill.add_argument("--form", required=True, type=Path, help="Blank PDF, PNG, or JPEG")
    fill.add_argument("--data", required=True, type=Path, help="CSV or JSON list of objects")
    fill.add_argument("--out", required=True, type=Path, help="Directory for PDFs, labels, and manifest")
    fill.add_argument("--boxes", type=Path, default=None, help="JSON field boxes when the form has no AcroForm")
    fill.add_argument("--dpi", type=int, default=200, help="Raster resolution (default 200)")
    fill.add_argument("--seed", type=int, default=0, help="Seed for font, jitter, and scan effects")
    fill.add_argument(
        "--font-dir",
        type=Path,
        default=None,
        help="Optional directory of local .ttf/.otf files already on disk. Does not download anything.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "fill":
            fill_form(
                form=args.form,
                data=args.data,
                out=args.out,
                boxes=args.boxes,
                dpi=args.dpi,
                seed=args.seed,
                font_dir=args.font_dir,
            )
    except ScanformError as exc:
        print(f"synthform: {exc}", file=sys.stderr)
        return 2
    return 0
