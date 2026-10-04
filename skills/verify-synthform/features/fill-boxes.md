# Fill with boxes

Fill with boxes lets a user turn a blank PDF and a CSV into one scanned-looking PDF per row, using a boxes file for the field rectangles.

## Sub-features

- `fill-boxes-run` writes `row-0001.pdf` and `row-0002.pdf`.
- `fill-boxes-labels` writes four label lines and a manifest.
- `fill-boxes-text-layer` keeps the answer tokens out of the PDF text layer.
- `fill-boxes-warning` puts the synthetic-sample warning in PDF metadata and `manifest.json`.

## How to get to it (user POV)

- Run `python3 -m synthform fill --form blank.pdf --data rows.csv --boxes boxes.json --out out --dpi 100 --seed 7`.

## Driving it with verify-synthform

Preconditions:

- `skills/verify-synthform/scripts/verify-synthform doctor` exits 0.
- `/tmp/synthform-verify-work` is free to delete.

- **Build the blank form.** The helper writes a 420 by 300 point PDF, `boxes.json`, and a two-row CSV. Run `skills/verify-synthform/scripts/verify-synthform drive-fill-boxes`. The work directory contains `blank.pdf`, `boxes.json`, and `rows.csv` before the CLI runs.
- **Fill.** The same command runs `python3 -m synthform fill` with `--dpi 100 --seed 7`. Exit code is 0.
- **Proof.** After the command, `/tmp/synthform-verify-evidence/fill-boxes/summary.txt` reports two PDFs, four labels, and `text_layer=no_answer_tokens`. `exit_code.txt` is `0`. `text-layer.txt` does not contain `QXNAME-ALPHA-7741`.

## Gotchas

- A PDF with no AcroForm and no `--boxes` exits 2. That is a different feature.
- The label `box` is the field rectangle after scan rotation, not a tight ink box.
- Answer tokens in a rendered image are expected. They must not appear in `extract_text()`.
