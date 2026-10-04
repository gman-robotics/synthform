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

## Companions

| Skill | Role here |
|---|---|
| `maintain-verification-skill` | Upkeep of this map after the CLI changes |

The surface is a short-lived CLI. There is no server, port, or shared session. Each drive uses its own work directory under `/tmp`. Two drives can run at once if they use different `RUN_ID` values.

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

That command creates a disposable blank PDF, a two-row CSV, and a boxes file, then runs the real CLI. See `features/fill-boxes.md` for the user-facing recipe. Other features in the map are not covered by that one command.

## Evidence

Proof for `drive-fill-boxes` is written to `/tmp/synthform-verify-evidence/fill-boxes/` and is not deleted by cleanup.

Required files:

- `command.txt` — the exact `python3 -m synthform fill` invocation
- `stdout.txt` and `stderr.txt`
- `exit_code.txt`
- `labels.jsonl` and `manifest.json` copied from the run
- `text-layer.txt` — `pypdf` extract of both PDFs, which must not contain the synthetic answer tokens
- `summary.txt` — row count, font ids, and the metadata warning check

A passing proof shows the action (the CLI command and exit code 0) and the resulting state (two PDFs, four label lines, warning in metadata, answer tokens absent from the text layer). Do not treat a dry name as proof. This CLI has no dry-run flag. The fill command always writes files in `--out`.

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
| same | `skills/verify-synthform/scripts/verify-synthform cleanup` |

Run them from the repo root. They are executable. `drive-fill-boxes` is more than one command, so it is a script, not prose.
