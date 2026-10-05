# GMA-109 plan: prove synthform ink, then make the scan and the hot path honest

Status: draft for review. Base: main at a0e7265462329247d3c6903e0c649211d4f69d34.
Ticket: GMA-109. Every PR body says `Refs GMA-109`. No PR body says Fixes or Closes.

This file holds a plan only. It changes no code.

## 1. Rules for this work

1. Validation comes first. No scan change and no speed change starts until a blank image-only PDF fails `drive-fill-boxes` (see section 3).
2. Test data is synthetic. The tests use forms that the tests build with ReportLab. No test uses Form 1583 or any legal, tax, or identity form.
3. The tool does not copy a person's handwriting or signature. The OFL fonts stay. No stroke model.
4. One review loop is at most 2 rounds per PR. No force-push.
5. A process pool across rows is out of scope.
6. Commit and PR text use ASD-STE100 Simplified Technical English.

## 2. Baseline at a0e7265 (measured)

| Item | Result |
| --- | --- |
| Test command | `python -m pytest -q` (config is in `pyproject.toml`: `testpaths = ["tests"]`, `pythonpath = ["src"]`) |
| Existing tests | 14 passed in 1.40 s (cold first run 2.25 s). Files: `test_fill.py` 6, `test_render.py` 4, `test_styles.py` 4 |
| Needed libraries | Python 3.11 or newer, Pillow, pypdf, pypdfium2 (bundles pdfium), ReportLab. Installed with `pip install -e ".[dev]"` in a venv. Poppler is not needed. numpy is not installed and is not needed |
| CI | None. The repo has no `.github` directory. Run the tests by hand and paste the result in each PR |
| `verify-synthform doctor` | exit 0 |
| `verify-synthform drive-fill-boxes` | exit 0, 0.8 s, `pdfs=2 labels=4 ... text_layer=no_answer_tokens` |
| Throughput (30 rows x 12 fields, Letter page, 200 dpi, seed 3) | 64.6 s CPU (best of 3), 169 MB peak memory, 33.1 MB of PDF in total |
| Profile (5 rows, cProfile, share of run time) | `map_box` 37 %; `write_image_pdf` 30 % (ReportLab ASCII85 encoder 24 %); `_sensor_noise` 17 %; `draw_field` 3.5 %; blur 3.5 %; JPEG round-trip 0.9 %; `_stamp_metadata` 0.2 %; `ImageFont.truetype` 0.1 % |

The machine that ran the baseline was busy (load average above 30 on 8 cores). Use CPU seconds, not wall time, for every speed comparison.

### Proof that a blank form passes the check today

The ticket says that a blank copy passes `check-fill-boxes.py`. This is true. The proof used a scratch copy of the repo. It changed no repo file.

1. Copy the repo. In the copy, edit `src/synthform/render.py`. In `draw_field`, add `return params` right after the line that calls `field_draw_params`. The generator now paints no ink.
2. Run `skills/verify-synthform/scripts/verify-synthform drive-fill-boxes` (with `SYNTHFORM_PYTHON` and `PYTHONPATH` set to the copy).
3. Result: exit 0 and `pdfs=2 labels=4 ... warning=ok text_layer=no_answer_tokens`. The check passed.
4. Control: the unchanged repo gives the same line. Rasters of the two runs differ in the ink area (the bounding box of the difference is 97,95 to 482,242 pixels on a 585 x 417 page). So the PDFs really differ and the check cannot see it.

## 3. The gate: how a blank page is shown to fail

Slice 1 builds the proof. The order inside slice 1 is fixed. It shows that the check can fail before it uses the check as a gate.

1. **Commit 1: tests and fixtures only, no check change.** Add `tests/test_ink_proof.py` and the blank fixture. The fixture writes a "blank" run: the real CLI, same form, same seed, same row count, but every value empty. The labels come from the filled run. Add the test `test_blank_pdf_fails_the_ink_check`. The test runs `python check-fill-boxes.py FILLED_OUT EVIDENCE BLANK_OUT` in a subprocess and expects exit 1. The old script ignores the third argument and exits 0, so the test is RED. The old check passes the blank run. Paste this red output in the PR body. This shows that the test can detect the fault.
2. **Commit 2: add the paired-seed difference check** to `check-fill-boxes.py` and to the driver. Run the same test. It must be GREEN, and the failure message must say that a label box holds no ink.
3. **Positive control.** The same code, form, and seed with real values must pass. A check that fails on everything proves nothing.
4. **Mutant control (run by hand, paste in the PR body).** Make two mutants in a scratch copy. Mutant M1: `draw_field` paints nothing. Mutant M2: `draw_field` paints one extra dot outside the box. Run `drive-fill-boxes` on each. M1 must exit non-zero with "no ink in label box". M2 must exit non-zero with "ink outside label box". The unchanged repo must exit 0.
5. **Gate rule.** Slices 3 and 4 start only after slice 1 is merged and its PR body holds the red run (step 1), the green run (step 2), and both mutant runs (step 4). Slice 2 changes no scan and no speed. It may start while slice 1 is in review. It merges after slice 1.

What "blank image-only PDF" means in this plan: a PDF that the generator wrote, with the right page size and the right scan seed, that has no handwriting in the label boxes.

## 4. Slices (pull requests)

| Slice | Name | Starts when | Changes scan strength or speed? |
| --- | --- | --- | --- |
| 1 | Prove ink: paired-seed check, blank gate, four CLI drives, skill text | now | No |
| 2 | Honest inputs and labels: `_fit` clipping, widget types, `/Rotate`, `map_box` blur fixture | slice 1 is open | No |
| 3 | Scan: blur in mm, zero-mean grain, cast before JPEG, row in field seed | slice 1 is merged | Yes |
| 4 | Throughput: `map_box` corners, embed JPEG, one metadata write, font cache | slice 3 is merged | Speed only |

Merge order: 1, 2, 3, 4. Each slice has its own `Refs GMA-109` PR body.

### Slice 1: prove ink

Steps in order:

1. Make `check-fill-boxes.py` take an optional third argument, the blank run directory (`check-fill-boxes.py FILLED_OUT EVIDENCE BLANK_OUT`). Put the logic in one function, `check_run(filled_dir, blank_dir) -> list[str]`, that returns failure messages. `main()` prints them and exits 1 if the list is not empty. Keep the old checks (two PDFs, four labels, manifest, warning, no answer token in the text layer).
2. Add the difference check inside `check_run`:
   - Rasterize page 1 of each filled PDF and its blank twin with pypdfium2 at the manifest dpi.
   - Subtract with `PIL.ImageChops.difference` and convert to gray. No numpy.
   - Outside every label box of that page: no pixel above `OUTSIDE_TOL` (default 8 gray levels).
   - Inside each label box: at least `MIN_INK_FRACTION` (default 1 %) of the box area has a difference of 48 or more.
   - Write `diff-row-0001.png` and `diff-summary.txt` to the evidence directory.
3. Change `make-blank-form.py` to also write `rows-blank.csv` (same header, two rows, empty values).
4. Change `verify-synthform`: `drive_fill_boxes` runs the CLI a second time with `rows-blank.csv` into `out-blank`, same seed and dpi. Then it calls the check.
5. Add four drives to `verify-synthform` and to the skill: `drive-fill-acroform`, `drive-fill-json-image`, `drive-seed-repro`, `drive-refuse-missing-boxes`. Each one runs `python -m synthform` in its own process with its own work directory under `SYNTHFORM_VERIFY_WORK`. `drive-seed-repro` starts the two runs with different `PYTHONHASHSEED` values (1 and 2). `drive-refuse-missing-boxes` checks exit code 2, the stderr text, and that the `--out` directory does not exist. Add `drive-all`, which runs the five drives one after the other as separate processes.
6. Add `tests/test_cli_drives.py`. It runs the same four cases with `subprocess.run([sys.executable, "-m", "synthform", ...])`. It never calls `cli.main`.
7. Fix `skills/verify-synthform/SKILL.md`: replace the `RUN_ID` sentence with `SYNTHFORM_VERIFY_WORK`. Update the Evidence list and the feature files (`fill-boxes.md`, `fill-acroform.md`, `fill-json-image.md`, `seed-repro.md`, `refuse-missing-boxes.md`, `README.md`) so they say which drive covers which feature. Remove "Not covered by drive-fill-boxes" where a drive now covers the case.
8. Run the gate steps from section 3 and paste the output.

### Slice 2: honest inputs and labels

1. `_fit` (in `render.py`): return a flag that says if the text fits. Today it returns the 6 px font even when the text still clips. The fallback at the end of `_fit` is the place.
2. `draw_field`: when the text does not fit at 6 px, paint nothing and report "not drawn". `fill.py` then writes no label for that field, prints one line to stderr (`synthform: skipped field ... text does not fit`), and adds the field to `skipped_fields` in `manifest.json` (see question Q2).
3. Add the tests for an unbreakable token (see section 5).
4. `fields.py`: change the keep-set from "not `/Btn` or `/Sig`" to "field type is `/Tx`". A choice widget and a widget with no field type are no longer drawn. A form that has only such widgets now needs `--boxes` and the boxes work (see question Q5).
5. `raster.py`: refuse a PDF page with `/Rotate` other than 0 (after modulo 360) with `ScanformError`, so the CLI exits 2 and writes nothing (see question Q3). Apply the same rule to a page whose `CropBox` differs from its `MediaBox` (see question Q4).
6. Add the fixtures: `map_box` with a real blur radius; signature, button, and choice widgets; a `/Rotate 90` PDF. Build every fixture with ReportLab and pypdf in the test. Do not commit binary PDFs.
7. Update `README.md`: text fields only; a skipped field; a rotated PDF.

### Slice 3: scan (starts after the gate)

1. **Blur in millimetres.** `params_for(rng, dpi)` draws `blur_sigma_mm` and converts: `blur_radius_px = blur_sigma_mm * dpi / 25.4`. Pillow `GaussianBlur(radius)` takes the standard deviation, so the unit is a sigma. Default range: 0.10 to 0.22 mm (see question Q6). `map_box` pad stays `ceil(3 * blur_radius_px + 1)`, so the label box grows with the blur.
2. **Zero-mean grain.** Replace `_sensor_noise`. Build a signed grain layer with mean 0 and add it to the page (`ImageChops.add` with offset). Do not blend toward gray. Draw the bytes with `rng.randbytes` so the work stays fast and the seed still repeats the result. Default: grain standard deviation 2 to 5 gray levels, same offset on R, G, and B (see question Q7). Today the effective grain is only 0.24 to 1.1 levels (sigma 6 to 14 times alpha 0.04 to 0.08), and the blend also darkens white paper by 5 to 10 levels.
3. **Cast before JPEG.** New order: rotate, blur, grain, paper cast, JPEG encode. Nothing touches the pixels after the JPEG encode.
4. **Row number in the field seed.** `field_draw_params(style, seed, field_name, box_w, box_h, row=0)` uses `stable_seed(seed, "field", row, field_name, font_id)`. `fill.py` passes the row number. Default `row=0` keeps old callers valid.
5. Re-run the paired-seed check and the tight-box experiment (section 6). If the outside-box difference passes `OUTSIDE_TOL`, widen the `map_box` pad by the JPEG block size or raise the tolerance. Record which one in the PR.
6. State in the PR body that every pixel and every `jitter` value changes by design.

### Slice 4: throughput (starts after slice 3 is merged)

Order, by measured cost. Run the measure plan in section 6 before and after each step.

1. `map_box`: transform the four corners and pad them. No page-sized image.
2. Embed the JPEG (see question Q8). Slice 3 already removed every pixel step after the JPEG encode, so the encoded bytes can go into the PDF as they are. Also set `reportlab.rl_config.useA85 = 0`, so ReportLab does not wrap the stream in ASCII85 (the profile shows ASCII85 costs 24 % of the run).
3. Metadata once: use `Canvas(..., invariant=1)` and `canvas.setProducer(...)`. Delete `_stamp_metadata` and the pypdf import. `invariant=1` is needed. Without it ReportLab writes the current time and the PDF bytes differ from run to run (checked). Today the pypdf rewrite drops the date, so the bytes repeat by accident.
4. Font cache: `functools.lru_cache` on a helper `_font(path_str, size)`. The profile shows this saves about 0.1 %. It is a tidy-up. Do it last.

## 5. Done-when lines and their proof

Names below are the planned names. All tests run with `python -m pytest -q` from the repo root.

| # | Done-when line | Proof | Expected |
| --- | --- | --- | --- |
| 1 | A blank image-only PDF fails `drive-fill-boxes` | `tests/test_ink_proof.py::test_blank_pdf_fails_the_ink_check`; by hand: mutant M1, then `skills/verify-synthform/scripts/verify-synthform drive-fill-boxes` | test passes; command exits 1 and prints "no ink in label box" |
| 2 | A real fill passes; the difference image is covered by the label box | `tests/test_ink_proof.py::test_paired_seed_difference_is_inside_the_label_boxes`; `tests/test_ink_proof.py::test_tight_boxes_stay_inside_the_tolerance`; `verify-synthform drive-fill-boxes` | tests pass; command exits 0; `diff-summary.txt` says `outside_max<=8` |
| 2a | The check is not fooled by ink outside the box | `tests/test_ink_proof.py::test_ink_outside_the_label_box_fails_the_check`; mutant M2 | test passes; command exits 1 and prints "ink outside label box" |
| 2b | The test reads the written PDF | same tests; they rasterize `row-*.pdf` with pypdfium2 and never use the pre-PDF PIL image | review the test source |
| 3 | An unbreakable token that does not fit at 6 px makes no label that claims the full string | `tests/test_render.py::test_unbreakable_token_that_cannot_fit_is_not_drawn`; `tests/test_render.py::test_unbreakable_token_that_fits_when_shrunk_keeps_its_label`; `tests/test_fill.py::test_unfit_token_gets_no_label_and_a_manifest_entry` | tests pass |
| 4 | The four CLI drives pass in separate processes | `tests/test_cli_drives.py::test_drive_acroform_uses_widget_names`; `::test_drive_json_and_png_writes_one_pdf`; `::test_two_processes_write_identical_labels`; `::test_missing_boxes_exits_2_and_creates_no_pdf`; `verify-synthform drive-all` | tests pass; command exits 0 |
| 5 | SKILL.md names `SYNTHFORM_VERIFY_WORK` | `! grep -n RUN_ID skills/verify-synthform/SKILL.md` | no output, exit 0 |
| 6 | `map_box` fixture with a real blur | `tests/test_render.py::test_mapped_box_covers_blurred_rotated_rectangle` (blur 0.6, 2.0, 4.0 px; angle -1.2, 1.2) | passes |
| 7 | `/Rotate 90` refused | `tests/test_raster.py::test_rotated_pdf_is_refused` (`python -m synthform`, exit 2, no `--out` directory) | passes |
| 8 | Signature, button, and choice widgets stay out; a choice-only form can use `--boxes` | `tests/test_fields.py::test_signature_button_and_choice_widgets_are_not_filled`; `::test_choice_only_pdf_uses_boxes`; `::test_widget_without_field_type_is_skipped` | passes |
| 9 | Blur scales with dpi | `tests/test_scan.py::test_blur_radius_scales_with_dpi` (same seed at 100 and 200 dpi, ratio 2.0) | passes |
| 10 | Noise is zero-mean | `tests/test_scan.py::test_grain_is_zero_mean` (flat gray page, mean shift under 0.25 level, standard deviation inside the set range); `::test_grain_does_not_lift_black` | passes |
| 11 | Cast is applied before JPEG | `tests/test_scan.py::test_cast_is_applied_before_jpeg` (the JPEG encoder gets the tinted page; output equals the decoded JPEG) | passes |
| 12 | Field jitter differs by row | `tests/test_styles.py::test_same_style_on_two_rows_gets_different_field_jitter`; `::test_field_jitter_repeats_for_the_same_row` | passes |
| 13 | `map_box` allocates no page-sized image | `tests/test_render.py::test_map_box_allocates_no_page_sized_image` (6000 x 8000 page, `tracemalloc` peak under 1 MB); `::test_map_box_matches_the_mask_reference` (within 2 px per edge, and covers the rotated rectangle) | passes |
| 14 | PDF metadata is written once | `tests/test_fill.py::test_pdf_metadata_is_written_once` (the module has no `PdfWriter`; `/Producer`, `/Title`, `/Subject`, `/Keywords`, `/Creator`, `/Author` are right; two runs give the same bytes) | passes |
| 15 | Fonts are cached | `tests/test_render.py::test_font_is_loaded_once_per_size` (`cache_info().hits` rises on the second `_fit`) | passes |
| 16 | JPEG is not round-tripped and Flate-compressed | `tests/test_fill.py::test_pdf_embeds_the_jpeg_as_is` (image filter is `/DCTDecode` only; the stream starts with `FFD8`; no `/FlateDecode`; the scan path never opens a JPEG) | passes |
| 17 | PR body says `Refs GMA-109` | `grep -n "Refs GMA-109" pr-body.md` and `! grep -Eni "fixes|closes|resolves" pr-body.md` | one hit; no hit |
| 18 | Existing tests stay green | `python -m pytest -q` | at least 14 passed, plus the new tests, 0 failed |

## 6. Measure plan for slice 3 and slice 4

Inputs (kept outside the repo, or under `skills/verify-synthform/scripts/bench-fill.py` if the maintainer agrees):

- A Letter-size form with 12 text boxes (500 x 26 pt each), built with ReportLab.
- 30 rows of synthetic words, built with `random.Random(5)`.
- Command: `python -m synthform fill --form in/blank.pdf --data in/rows.csv --boxes in/boxes.json --out OUT --dpi 200 --seed 3`.
- Run with `PYTHONHASHSEED=0`.

Timing:

1. Run 3 times. Keep the lowest CPU time (user plus system, from `resource.getrusage(RUSAGE_CHILDREN)`). Keep the peak memory and the total PDF bytes. The shared box is busy, so wall time is not reliable.
2. Baseline at a0e7265: 64.6 s CPU, 169 MB, 33.1 MB of PDF.
3. Record a baseline again at the start of slice 4 (slice 3 changes the work).
4. Run the same command after each step of slice 4. Put one row per step in the PR body: CPU seconds, peak memory, PDF bytes.
5. Optional profile: `cProfile` on 5 rows. Compare the top 10 lines.

Output equality, per step. Make the reference run with the code before the step. Make the second run with the code after the step.

| Step | PDF bytes | Raster of each page (pdfium) | `labels.jsonl` |
| --- | --- | --- | --- |
| `map_box` corners | identical | identical | only `box` changes. Each edge moves by 2 px or less. The new box covers the rotated rectangle |
| Embed JPEG (and no ASCII85) | change on purpose; file is smaller | within a small tolerance set after the first measure (expected: a few gray levels, because the decoders differ) | identical |
| Metadata once | change (file layout) | identical | identical. `pypdf` metadata equal. Two runs give identical bytes |
| Font cache | identical | identical | identical |

Slice 3 is not a speed change. Every pixel and every `jitter` value changes by design, so a before and after comparison is not an equality check there. For slice 3 the checks are the tests in section 5 and the paired-seed check at dpi 100, 200, and 300.

Paired-seed tolerance data (measured at a0e7265, white form, scan as it is today):

- Standard form, dpi 72, 100, 200, 300, seeds 7 and 8: no pixel outside the label boxes differs, except 7 pixels that differ by 1 level (dpi 300, seed 8).
- Tight boxes (11 pt and 9 pt high), dpi 100, 200, 300, six seeds: the largest difference outside the box is 5 levels. JPEG blocks cause it. No pixel differs by 8 or more.
- Ink inside the box (difference of 48 or more): 5 % to 11 % of the box area for the two 17-character test words, at 72, 100, and 200 dpi.

## 7. Claims in the ticket checked against a0e7265

| Ticket claim | Result |
| --- | --- |
| `check-fill-boxes.py` only requires answer tokens to be absent from `extract_text()`; a blank copy passes | True. Proved in section 2. Note: the check also needs 4 label lines, so a blank PDF passes only when the labels come from the generator |
| The scan seed in `fill.py` does not depend on the text | True. `stable_seed(seed, "scan", row_number, page_index)`. Measured: filled and blank runs match outside the label boxes |
| `_fit` gives up at 6 px and still clips | True. The last line of `_fit` returns the 6 px font with no fit test. `_paint_text` then pastes a layer that is larger than the box, cropped at the box edge |
| `test_long_text_stays_inside_the_box` uses a spaced string | True. The string is 6 copies of a word with spaces, so it wraps |
| The skill names four cases and does not run them | True. The feature files say "Not covered by drive-fill-boxes". All four pass today with `python -m synthform` (checked by hand) |
| `SKILL.md` says `RUN_ID` | True. One line (line 28). The script and `features/README.md` use `SYNTHFORM_VERIFY_WORK` |
| `test_mapped_box_covers_rotated_rectangle` sets `blur_radius=0` | True |
| `raster.py` uses `page.get_size()`, `fields.py` copies the raw `/Rect`, neither reads `/Rotate` | True. Checked: for `/Rotate 90`, pdfium returns 300 x 420 for a 420 x 300 page, while the widget `/Rect` stays unrotated. The same fault happens when the CropBox is not the MediaBox (not in the ticket) |
| The keep-set is "not `/Btn` or `/Sig`", so `/Ch` and widgets with no `/FT` stay; one kept choice field makes `--boxes` unreachable | True. Checked: a form with one choice widget and `--boxes` gives exit 0, zero labels, a blank PDF, and the warning "no box for field" |
| Blur is 0.4 to 0.85 px | True. It is the sigma of `GaussianBlur`. That is 0.05 to 0.11 mm at 200 dpi |
| Noise blends toward mid-gray | True. `Image.blend(image, gray, alpha)` with alpha 0.04 to 0.08. The effective grain is only 0.24 to 1.1 levels. The blend lowers white paper by 5 to 10 levels |
| The cast is painted after compression | True. The cast blend is the last line of `apply_scan`. The rotation fill also uses the cast color before the blur |
| Same font and field name share one jitter on every row | Mostly true. The random draws repeat for rows that use the same font. The row style (size scale, rotation, tracking, baseline, ink) still differs from row to row |
| `map_box` allocates a full-page mask once per field | True. One call per drawn field |
| `write_image_pdf` rewrites the file with pypdf to set `/Producer` | True. The ticket does not say that the rewrite also makes the bytes repeat. Slice 4 keeps this with `invariant=1` |
| `_fit` calls `ImageFont.truetype` on every size step | True, but small: 476 calls, 0.1 % of the run time |
| The JPEG is decoded, then Flate-compressed in the PDF | True. The ticket omits that ReportLab also wraps the stream in ASCII85 (the filters are `ASCII85Decode` and `FlateDecode`). That is 24 % of the run time |
| The blank raster is loaded once | True |

Metadata once and font cache are real but small in time. The ticket order for the speed work is not the order by cost. Section 4 uses the order by cost.

## 8. Risks

1. **Tolerance.** Exact zero outside the box is not possible with JPEG. The plan uses 8 levels. Slice 3 changes blur, grain, and cast. The tolerance must be measured again there.
2. **False pass.** A very short value (one character) has little ink. The default `MIN_INK_FRACTION` is for the long test words of the drive. Tests with short words use a count of at least 20 pixels.
3. **Skipped fields reduce the corpus.** Q2 sets how a user sees them.
4. **Choice and rotate changes are behavior changes.** A form that worked before may now exit 2 (rotated) or may lose a choice label. Say so in the README and the PR body.
5. **Seed change.** Slice 3 changes every output for a given seed. Bump `__version__` to 0.2.0 in slice 3 (see question Q9). Old corpora cannot be rebuilt from the new version.
6. **`rl_config.useA85` is a global setting in ReportLab.** Set it in `pdfout.py` once. Test that it does not change other PDFs in the same process.
7. **Environment.** The ReportLab C accelerator is not present in the venv used for the baseline, so the pure-Python ASCII85 encoder ran. A machine with the accelerator will show a smaller ASCII85 share.
8. **Unrelated finding (not in this ticket).** `fill` exits 0 and writes blank PDFs when no field gets a label (for example a choice-only form with `--boxes`). Slice 2 removes the case that was found. A general "no label written" warning is a separate decision (Q10).
9. **Page size.** `write_image_pdf` sets the page to `pixels * 72 / dpi` points. A 420 pt page becomes 420.48 pt at 100 dpi. This is a half-pixel scale difference. It is not in the ticket and the plan does not change it.

## 9. Questions for the maintainer

Each question has a recommended default. The plan uses the default until the maintainer answers.

| # | Question | Recommended default |
| --- | --- | --- |
| Q1 | What is the tolerance for "the difference is inside the label box"? | Outside the box: no pixel above 8 gray levels. Inside each box: at least 1 % of the area at 48 levels or more (drive words), at least 20 pixels (short words) |
| Q2 | `_fit` gives up at 6 px: skip the field, or keep it with a `clipped` flag and the text drawn? | Skip. Write no label, print one stderr line, and list it in `manifest.json` as `skipped_fields`. Reason: the text actually drawn is not defined for rotated, cropped lines |
| Q3 | A PDF with `/Rotate` other than 0: refuse, or transform both the raster and the widget rectangles? | Refuse with exit 2 and a clear message. A transform is a later ticket |
| Q4 | A PDF whose CropBox differs from its MediaBox (same fault, not in the ticket): refuse too? | Refuse too, in the same check |
| Q5 | Choice fields (`/Ch`) and widgets with no `/FT`: skip? | Fill only `/Tx` text fields. Skip all other types. Update the README sentence |
| Q6 | Unit and range of blur | Millimetres. Sigma 0.10 to 0.22 mm. At 200 dpi that is 0.8 to 1.7 px; at 100 dpi, 0.4 to 0.9 px (like today at 100 dpi) |
| Q7 | Zero-mean grain: amplitude and shape | Standard deviation 2 to 5 gray levels, per pixel, same offset on R, G, and B, any zero-mean shape. Independent of dpi |
| Q8 | Embed the JPEG, or skip the round-trip? | Embed the JPEG. It keeps the compression artifacts and makes the files much smaller. Skipping the round-trip would keep the Flate and the large files |
| Q9 | Version bump for the scan change? | Yes. 0.2.0 in slice 3, with a note that outputs changed |
| Q10 | Should `fill` exit non-zero or warn when no label is written at all? | Warn on stderr only. Do not change the exit code in this ticket |
| Q11 | May a benchmark script go into `skills/verify-synthform/scripts/`? | Yes, as `bench-fill.py`. It has no data and no network use |
| Q12 | Is the 2-round review cap counted per slice? | Per slice |

## 10. Files expected to change, and the test command, per slice

Test command for every slice: `python -m pytest -q` from the repo root (venv with `pip install -e ".[dev]"`). Slice 1 also runs `skills/verify-synthform/scripts/verify-synthform drive-all`.

**Slice 1**
- `skills/verify-synthform/scripts/check-fill-boxes.py` (changed)
- `skills/verify-synthform/scripts/make-blank-form.py` (changed)
- `skills/verify-synthform/scripts/verify-synthform` (changed)
- `skills/verify-synthform/scripts/make-acroform.py` (new), `make-png-form.py` (new)
- `skills/verify-synthform/SKILL.md`, `skills/verify-synthform/features/*.md` (changed)
- `tests/test_ink_proof.py` (new), `tests/test_cli_drives.py` (new)
- `docs/plans/gma-109-plan.md` (this file)

**Slice 2**
- `src/synthform/render.py`, `src/synthform/fill.py`, `src/synthform/fields.py`, `src/synthform/raster.py`, `README.md`
- `tests/test_render.py`, `tests/test_fill.py`, `tests/test_fields.py` (new), `tests/test_raster.py` (new)

**Slice 3**
- `src/synthform/scan.py`, `src/synthform/render.py`, `src/synthform/fill.py`, `src/synthform/__init__.py` (version), `README.md`
- `tests/test_scan.py` (new), `tests/test_styles.py`, `tests/test_render.py`, `tests/test_ink_proof.py`

**Slice 4**
- `src/synthform/scan.py` (`map_box`, return the JPEG bytes), `src/synthform/pdfout.py`, `src/synthform/render.py` (font cache), `src/synthform/fill.py`
- `skills/verify-synthform/scripts/bench-fill.py` (new, if Q11 is yes)
- `tests/test_render.py`, `tests/test_fill.py`, `tests/test_scan.py`

## 11. Out of scope

- Form 1583 and any legal, tax, or identity form for submission.
- Cloning a person's handwriting or signature.
- A pen-stroke or handwriting-dataset model. The OFL fonts stay.
- A process pool across rows.
