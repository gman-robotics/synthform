---
name: verify-synthform
description: >-
  Drive the synthform CLI the way a user does: fill a blank form from a
  table and prove the image-only PDF, labels, and synthetic warning.
  Use when checking synthform fill, labels, or scan output.
version: 1.0.0
---

# verify-synthform

**Purpose**
Prove synthform by running the real CLI, not by calling internal setters.

**Trigger**
Use when a change touches fill, boxes, AcroForm, labels, or scan output, or when someone asks to prove synthform works.

**Do not use for**
- Filling Form 1583 or any legal, tax, or identity form for submission
- Cloning a person's handwriting or signature

## Requirements

Python 3.12/3.13 only, no CI. The repo has no CI configuration, so run the proofs by hand on a machine with Python 3.12 or 3.13.

## Companions

| Skill | Role here |
|---|---|
| `maintain-verification-skill` | Upkeep of this map after the CLI changes |

The surface is a short-lived CLI. There is no server, port, or shared session. Each drive uses its own work directory under `/tmp`. Two runs of the same drive can run at once if they use different `SYNTHFORM_VERIFY_WORK` and `SYNTHFORM_VERIFY_EVIDENCE` values.

Repo root on this Mac's experiment sandbox is `/home/dev/src` inside `exp-scanform`. On a normal checkout, the root is the clone of https://github.com/gman-robotics/synthform. The helpers take that root as the working directory.

## Launch

There is no process to keep alive. Launch means the package imports and the CLI answers.

```bash
cd /home/dev/src
skills/verify-synthform/scripts/verify-synthform doctor
```

Ready when that command exits 0. Teardown is `skills/verify-synthform/scripts/verify-synthform cleanup`. Cleanup does not stop a long-running process, because none was started.

## Doctor

Read-only. Run this first when anything looks off.

```bash
skills/verify-synthform/scripts/verify-synthform doctor
```

It checks that `python3 -m synthform` imports, prints a version, and that `fill --help` contains `Synthetic training sample`, `Not a signed original`, and `Form 1583`. It does not write a PDF.

## Drive

The harness is the synthform CLI plus the helper scripts in this skill. Do not call `synthform.cli.main` from a proof. The user path is `python3 -m synthform fill`.

Drive one feature with:

```bash
skills/verify-synthform/scripts/verify-synthform drive-fill-boxes
```

That command creates a disposable blank PDF, a two-row CSV, an empty twin CSV, and a boxes file. It runs the real CLI twice with the same seed and dpi: once with the values (the filled run) and once with every value empty (the twin run). The check rasterizes the PDFs, subtracts the twin from the filled run, and fails when a label box has no ink or when ink appears outside every label box. See `features/fill-boxes.md` for the user-facing recipe.

Four more drives cover the other features. Each one runs `python3 -m synthform fill` in its own process, in its own work directory under `SYNTHFORM_VERIFY_WORK`:

```bash
skills/verify-synthform/scripts/verify-synthform drive-fill-acroform
skills/verify-synthform/scripts/verify-synthform drive-fill-json-image
skills/verify-synthform/scripts/verify-synthform drive-seed-repro
skills/verify-synthform/scripts/verify-synthform drive-refuse-missing-boxes
```

`drive-all` runs the five drives one after the other, each as a separate process. A feature that no drive covers is not verified. Report it as not verified.

## Evidence

Proof for each drive is written to `/tmp/synthform-verify-evidence/<drive name>/` (`fill-boxes`, `fill-acroform`, `fill-json-image`, `seed-repro`, `refuse-missing-boxes`) and is not deleted by cleanup. A drive removes the old evidence of its own name when it starts.

Required files for `drive-fill-boxes`:

- `command.txt` — the exact `python3 -m synthform fill` invocation
- `stdout.txt` and `stderr.txt`
- `exit_code.txt`
- `labels.jsonl` and `manifest.json` copied from the run
- `text-layer.txt` — `pypdf` extract of both PDFs, which must not contain the synthetic answer tokens
- `summary.txt` — row count, font ids, and the metadata warning check
- `command-twin.txt`, `stdout-twin.txt`, `stderr-twin.txt`, and `exit_code-twin.txt` — the twin run
- `diff-summary.txt` — the largest difference outside the label boxes and the share of each box where the largest of the red, green, and blue differences is 48 or more. The last line is `outside_max<=8` when the check passes, `outside_max=N` when ink is outside the boxes, and `outside_max=unchecked` when a twin PDF is missing or its raster size differs
- `diff-row-0001.png` and `diff-row-0002.png` — the difference image of page 1 of each row, made four times brighter

The other drives write `command.txt`, `stdout.txt`, `stderr.txt`, `exit_code.txt`, and the files that their check reads. `drive-seed-repro` writes `command-a.txt`, `command-b.txt`, `labels-a.jsonl`, and `labels-b.jsonl`.

A passing proof shows the action (the CLI command and exit code 0) and the resulting state (two PDFs, four label lines, warning in metadata, answer tokens absent from the text layer, and ink in the label boxes only). Do not treat a dry name as proof. This CLI has no dry-run flag. The fill command always writes files in `--out`.

## Cleanup

```bash
skills/verify-synthform/scripts/verify-synthform cleanup
```

Removes `/tmp/synthform-verify-work` only. It does not delete `/tmp/synthform-verify-evidence`. It does not kill by process name.

## Helpers

| Script | Invocation |
|---|---|
| `scripts/verify-synthform` | `skills/verify-synthform/scripts/verify-synthform doctor` |
| same | `skills/verify-synthform/scripts/verify-synthform drive-fill-boxes` |
| same | `skills/verify-synthform/scripts/verify-synthform drive-fill-acroform` |
| same | `skills/verify-synthform/scripts/verify-synthform drive-fill-json-image` |
| same | `skills/verify-synthform/scripts/verify-synthform drive-seed-repro` |
| same | `skills/verify-synthform/scripts/verify-synthform drive-refuse-missing-boxes` |
| same | `skills/verify-synthform/scripts/verify-synthform drive-all` |
| same | `skills/verify-synthform/scripts/verify-synthform cleanup` |
| `scripts/check-fill-boxes.py` | `check-fill-boxes.py FILLED_OUT EVIDENCE [TWIN_OUT]` (the drive calls it) |

Run them from the repo root. They are executable. Each drive is more than one command, so it is a script, not prose.
