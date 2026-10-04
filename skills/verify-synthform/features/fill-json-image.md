# Fill an image from JSON

Fill an image from JSON lets a user pass a PNG or JPEG plus a boxes file and a JSON list of one or more objects.

## Sub-features

- `image-one-row` writes only `row-0001.pdf` when the JSON list has one object.
- `image-boxes-required` needs `--boxes`. An image has no AcroForm.

## How to get to it (user POV)

- Run `python3 -m synthform fill --form blank.png --data rows.json --boxes boxes.json --out out --dpi 72 --seed 1`.

## Driving it with verify-synthform

Preconditions:

- Doctor has passed.
- Not covered by `drive-fill-boxes`.

- **Fill.** Create a white PNG, a one-object JSON file, and boxes in PDF points. Run the CLI. Exit code 0. `row-0002.pdf` is absent. `labels.jsonl` has two lines.
- **Proof.** The PDF text layer does not contain the JSON values.

## Gotchas

- Box coordinates for an image are still PDF points. The page size is `pixels * 72 / dpi`. Pixel coordinates copied from a screenshot will land in the wrong place.
