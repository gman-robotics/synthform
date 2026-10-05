# Refuse a PDF with no boxes

Refuse a PDF with no boxes lets a user see a clear failure instead of a blank scan when a fieldless PDF is passed without `--boxes`.

## Sub-features

- `refuse-exit-2` exits 2.
- `refuse-no-pdf` does not write `row-0001.pdf`.

## How to get to it (user POV)

- Run `python3 -m synthform fill --form blank.pdf --data rows.csv --out out` on a PDF that has no AcroForm fields and omit `--boxes`.

## Driving it with verify-synthform

Preconditions:

- Doctor has passed.
- `skills/verify-synthform/scripts/verify-synthform drive-refuse-missing-boxes` covers this entry point. `drive-fill-boxes` does not.

- **Fill.** The drive runs the command above on the blank form of the boxes drive. Exit code is 2. `stderr.txt` holds `PDF has no AcroForm text fields; pass --boxes`.
- **Proof.** The `--out` directory does not exist, so `out/row-0001.pdf` does not exist. Evidence is in `/tmp/synthform-verify-evidence/refuse-missing-boxes/`.

## Gotchas

- Exit 2 is the expected result. Do not treat it as a broken install.
- An AcroForm PDF does not need `--boxes`. This feature is only for a fieldless PDF.
