# Fill an AcroForm

Fill an AcroForm lets a user omit a correct boxes file. synthform reads the PDF widget rectangles and does not use `--boxes` when those fields exist.

## Sub-features

- `acro-uses-widgets` labels `full_name` and `city` from the form, not from a decoy boxes file.
- `acro-skips-signature` does not draw signature or button widgets.

## How to get to it (user POV)

- Run `python3 -m synthform fill --form acro.pdf --data rows.csv --out out --seed 3`.
- A `--boxes` file may be present. It is ignored when AcroForm text fields exist.

## Driving it with verify-synthform

Preconditions:

- Doctor has passed.
- `skills/verify-synthform/scripts/verify-synthform drive-fill-acroform` covers this entry point. `drive-fill-boxes` does not.
- `acro-skips-signature` is not covered by a drive. Report it as not verified.

- **Fill.** The drive builds an AcroForm PDF with text fields named `full_name` and `city` and a decoy boxes file. It runs the CLI with `--dpi 90 --seed 3`. Exit code 0. `labels.jsonl` field names are `full_name` and `city`.
- **Proof.** `extract_text()` does not contain the CSV values. Metadata contains `synthetic training sample`. Evidence is in `/tmp/synthform-verify-evidence/fill-acroform/`.

## Gotchas

- Signature and button widgets are skipped. A missing signature graphic is not a failure.
- Passing a decoy `--boxes` must not change the field names. If the labels say `other`, AcroForm was not used.
