# scanform

scanform builds synthetic training samples of filled forms. You give it a blank form and a table of fake field values. It writes one scanned-looking PDF per row, plus labels for training a form reader.

These PDFs are synthetic training samples. They are not signed originals.

Do not use this to fill Form 1583 or any legal, tax, or identity form for submission. Do not present the output as an authentic document. scanform does not copy a real person's signature and does not try to defeat forensic checks.

## What you get

Each row becomes `row-0001.pdf`, `row-0002.pdf`, and so on. The page is a raster image inside a PDF. The answers are not a live text layer. `labels.jsonl` records the text and the pixel box. `manifest.json` records the generator version and the synthetic-sample warning.

PDF metadata says the file is a synthetic training sample and not a signed original.

## Install

Python 3.11 or newer. Install inside the environment where you want the tool, not on a machine that should stay free of these packages.

```bash
cd /home/dev/src
python3 -m pip install --user --break-system-packages -e ".[dev]"
export PATH="$HOME/.local/bin:$PATH"
```

`python3 -m scanform` works without that `PATH` change.

## Fill a form

```bash
scanform fill --form blank.pdf --data rows.csv --out out --seed 7
```

`--form` is a PDF, PNG, or JPEG. `--data` is a CSV with a header row, or a JSON list of objects. Keys are field names.

If the PDF has AcroForm text fields, scanform uses those widget rectangles. A missing `--boxes` file is fine in that case. When AcroForm fields exist, scanform uses them and does not use `--boxes`.

Signature widgets and buttons are skipped. This tool does not draw a signature graphic and has no flag to clone a person's signature.

When the PDF has no AcroForm fields, or the form is an image, pass `--boxes`:

```json
[
  {"name": "full_name", "page": 0, "x": 36, "y": 200, "w": 340, "h": 40}
]
```

`page` is zero-based. `x`, `y`, `w`, and `h` are PDF points. The origin is the bottom-left of the page.

`--dpi` defaults to 200. `--seed` defaults to 0. The seed drives font choice, jitter, and the scan effects. The same seed and the same inputs reproduce the same labels.

`--font-dir` optionally adds `.ttf` or `.otf` files that are already in that directory. It reads only those font files. It does not download fonts or handwriting datasets, and it does not imitate a particular writer.

## Labels

`labels.jsonl` has one JSON object per filled field:

| Key | Meaning |
| --- | --- |
| `row_id` | PDF stem, such as `row-0001` |
| `field` | Field name |
| `text` | Synthetic value drawn for that field |
| `page` | Zero-based page index |
| `box` | `{x, y, w, h}` in pixels of the final scan. Origin is top-left, y grows downward |
| `font_id` | Handwriting font chosen for that row |
| `seed` | The `--seed` value for the run |

`style` is the row's shared jitter: size scale, baseline, rotation, tracking, and ink. `jitter` is the extra per-field shift actually used when drawing. Ink is near-black and is not `#000000`.

The pixel box is the field rectangle after the small scan rotation, expanded so the mild blur stays inside it.

`manifest.json` includes `generator`, `version`, and `warning`.

## How the pages are made

For each row, scanform picks one Open Font License handwriting font and one jitter setting. When the number of rows is small (at most the size of the built-in style list, which is thousands of font and jitter pairs), two rows do not share that same pair.

Each field then gets a little more jitter: size, baseline, a small rotation, tracking, near-black ink, and a slight x/y offset inside the box. Text that does not fit is wrapped or shrunk. Nothing is drawn outside the box.

After the fields are composited, scanform applies a small page rotation, mild blur, sensor noise, JPEG-style compression, and a slight gray paper cast. It then wraps that raster in a PDF. There is no live text layer of the answers.

This first version uses fonts plus jitter so it runs with no handwriting dataset.

## Public handwriting sets

These sets can later train a stroke or style model. This repository does not download them and does not commit their images or strokes. A later hook may read a local directory you already have. This version's `--font-dir` only adds local font files. Do not redistribute a set whose terms forbid it.

- IAM Handwriting Database (Marti and Bunke): English, 657 writers, 1539 pages, line and word labels. Research use, registration required. https://fki.tic.heia-fr.ch/databases/iam-handwriting-database
- IAM-OnDB: online pen strokes, non-commercial research, registration required, do not redistribute. https://fki.tic.heia-fr.ch/databases/download-the-iam-on-line-handwriting-database
- CVL: about 310 writers, English and German, word boxes. The Vienna Computer Vision Lab describes non-commercial research terms; confirm the license before any commercial training. https://cvl.tuwien.ac.at/research/cvl-databases/an-off-line-database-for-writer-retrieval-writer-identification-and-word-spotting/
- RIMES: French mail-like pages. Research agreement, not a casual download.
- GNHK (GoodNotes Handwriting Kollection): in-the-wild English notes, CC-BY-4.0. https://github.com/GoodNotes/GNHK-dataset

Historical HTR sets (Bentham, Washington, Saint Gall) are a different domain. They are not a goal of this project.

## Fonts

The handwriting fonts under `src/scanform/fonts/` are third-party font software under the SIL Open Font License 1.1. Each family directory includes its `OFL.txt` and its copyright notice. The Python code in this repository is MIT. The fonts stay under the OFL and are not relicensed.

Families: Caveat, Patrick Hand, Indie Flower, Shadows Into Light, Kalam, Architects Daughter, Gloria Hallelujah, Cedarville Cursive, Reenie Beanie, Covered By Your Grace, Nothing You Could Do, and La Belle Aurore. Upstream copies live in the [Google Fonts](https://github.com/google/fonts) `ofl/` tree. Caveat is the Regular instance of that OFL family.

Homemade Apple is a similar public handwriting face. The file currently served by fonts.gstatic.com identifies itself as Apache-2.0, so it is not vendored in this OFL set.

No handwriting dataset is vendored.

## Development

```bash
cd /home/dev/src
python3 -m pytest -q
```

## License

MIT. See `LICENSE`. The bundled fonts are SIL Open Font License 1.1. See each `OFL.txt`.
