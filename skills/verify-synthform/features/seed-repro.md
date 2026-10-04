# Repeat a seed

Repeat a seed lets a user run the same form, table, boxes, dpi, and seed twice and get the same `labels.jsonl`.

## Sub-features

- `seed-same-labels` byte-matches the two label files.
- `seed-different-out` still writes two separate output directories.

## How to get to it (user POV)

- Run the same `python3 -m synthform fill` command twice with different `--out` directories and the same `--seed`.

## Driving it with verify-synthform

Preconditions:

- Doctor has passed.
- Not covered by `drive-fill-boxes`.

- **Fill twice.** Use `--seed 7` and `--dpi 72` into `out-a` and `out-b`. Both exit 0.
- **Proof.** `out-a/labels.jsonl` and `out-b/labels.jsonl` are identical.

## Gotchas

- Changing `--dpi` or `--font-dir` changes the labels even when the seed is the same.
- PDF bytes may still differ if a compressor embeds a timestamp. Compare labels, not file hashes, unless you have checked the bytes.
