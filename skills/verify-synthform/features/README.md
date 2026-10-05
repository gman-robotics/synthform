# synthform verification map

This directory is the maintained source for verifying synthform. Read the index, then use the matching feature file. The harness is the CLI, driven by `skills/verify-synthform/scripts/verify-synthform`.

## Baseline preconditions

- Work from the repo root. On the experiment sandbox that is `/home/dev/src`.
- `python3 -m synthform` imports. Run `skills/verify-synthform/scripts/verify-synthform doctor` first.
- Each drive uses its own directory under `/tmp/synthform-verify-work`. Set `SYNTHFORM_VERIFY_WORK` if two runs must not share that directory.
- Proof goes to `/tmp/synthform-verify-evidence`. Cleanup must not delete it.
- Do not point `--form` at Form 1583 or any legal, tax, or identity form.

## Driving conventions

- The user path is `python3 -m synthform fill`. Do not call `synthform.cli.main` for a proof.
- Treat every command in a feature file as literal.
- Start from doctor unless the feature says otherwise.

## Proof and skip reporting

- Capture the command, exit code, stdout, stderr, and the files the command wrote.
- A PDF that exists is not enough. Check the text layer and the metadata warning.
- Report an unrun entry point as not verified. Do not claim AcroForm was proved by the boxes drive. Use the drive of that feature. `verify-synthform drive-all` runs the five drives.

## Feature entry contract

Each feature file has an H1, one paragraph, then four H2s: `Sub-features`, `How to get to it (user POV)`, `Driving it with verify-synthform`, and `Gotchas`.

## Features

- [Fill with boxes](./fill-boxes.md) is the proved path (`drive-fill-boxes`). Blank PDF, CSV, `--boxes`, and the ink proof against an empty twin.
- [Fill an AcroForm](./fill-acroform.md) uses widget rectangles and ignores `--boxes` (`drive-fill-acroform`).
- [Fill an image from JSON](./fill-json-image.md) is one JSON row and a PNG (`drive-fill-json-image`).
- [Repeat a seed](./seed-repro.md) writes the same labels twice (`drive-seed-repro`).
- [Refuse a PDF with no boxes](./refuse-missing-boxes.md) exits 2 when a fieldless PDF has no `--boxes` (`drive-refuse-missing-boxes`).
