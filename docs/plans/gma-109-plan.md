# GMA-109 plan: prove synthform ink, then make the scan and the hot path honest

Status: revised after review round 1. Base: main at a0e7265462329247d3c6903e0c649211d4f69d34.
Ticket: GMA-109. Every PR body says `Refs GMA-109`. No PR body says Fixes or Closes.

This file holds a plan only. It changes no code. The last section lists what changed in review round 1.

## 1. Rules for this work

1. Validation comes first. No scan change and no speed change starts until a blank image-only PDF fails `drive-fill-boxes` (see section 3).
2. Test data is synthetic. The tests use forms that the tests build with ReportLab. No test uses Form 1583 or any legal, tax, or identity form.
3. The tool does not copy a person's handwriting or signature. The OFL fonts stay. No stroke model.
4. A review loop is at most 2 rounds per slice. No force-push.
5. A process pool across rows is out of scope.
6. Commit and PR text use ASD-STE100 Simplified Technical English. No at-sign in a commit message or a PR body.
7. One PR for each slice. Every PR body says `Refs GMA-109`. No PR body says Fixes or Closes. The check is `grep -n "Refs GMA-109" pr-body.md` (one hit or more) and `! grep -Eni "fixes|closes" pr-body.md`.
8. Push by the GitHub API. Use a role no-reply address as author and committer. The address must not hold a personal login. Add no Co-authored-by line.
9. The author of the work does not merge. The maintainer merges.
10. Start rules:
    - Slice 1 starts without a new question to the maintainer when the plan review clears the plan or lists only NITs.
    - Slice 2 may start while slice 1 is in review. It merges after slice 1.
    - Slice 3 starts only after slices 1 and 2 are both merged by the maintainer.
    - Slice 4 starts only after slice 3 is merged by the maintainer.

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

The reviewer ran the same checks on a second stack (Python 3.12, 14 tests pass in 1.10 s). The numbers agree where both ran.

### Proof that a blank form passes the check today

The ticket says that a blank copy passes `check-fill-boxes.py`. This is true. The proof used a scratch copy of the repo. It changed no repo file.

1. Copy the repo. In the copy, edit `src/synthform/render.py`. In `draw_field`, add `return params` right after the line that calls `field_draw_params`. The generator now paints no ink.
2. Run `skills/verify-synthform/scripts/verify-synthform drive-fill-boxes` (with `SYNTHFORM_PYTHON` and `PYTHONPATH` set to the copy).
3. Result: exit 0 and `pdfs=2 labels=4 ... warning=ok text_layer=no_answer_tokens`. The check passed.
4. Control: the unchanged repo gives the same line. Rasters of the two runs differ in the ink area (the bounding box of the difference is 97,95 to 482,242 pixels on a 585 x 417 page). So the PDFs really differ and the check cannot see it.

## 3. The gate: how a blank page is shown to fail

Slice 1 builds the proof. The order inside slice 1 is fixed. It shows that the check can fail before the check is used as a gate.

What the words mean in this plan:

- **Filled run:** the real CLI on the drive form with the drive words.
- **Twin run:** the real CLI on the same form, same seed, same dpi, same row count, with every value empty. The twin run writes no label line (empty text is skipped before `draw_field`).
- **Blank image-only PDF:** a PDF that the generator wrote, with the right page size and the right scan seed, that has no handwriting in the label boxes. The paint-nothing mutant (M1) makes one.

The proof has three tests. Each one is a different pair. A correct check exits 0 on the first pair and 1 on the other two. No single test is both a correct check and red.

| Test | Input | Expected |
| --- | --- | --- |
| `test_real_fill_passes_against_its_empty_twin` | `verify-synthform drive-fill-boxes` on the unchanged code | exit 0. The control: a check that fails on everything proves nothing |
| `test_paint_nothing_mutant_fails_drive_fill_boxes` (mutant M1) | a temporary copy of the code where `draw_field` returns before it paints; `verify-synthform drive-fill-boxes` runs on the copy | exit 1 and the text `no ink in label box` |
| `test_ink_in_the_page_body_fails_drive_fill_boxes` (mutant M2) | a temporary copy where `draw_field` also paints a 2 x 2 near-black dot in the page body; `drive-fill-boxes` runs on the copy | exit 1, the text `ink outside label box`, and at least one outside pixel above 8 |

The tests build the mutant copy in `tmp_path`. They copy `src/` and `skills/`, patch one function with a string replace, set `PYTHONPATH` and `SYNTHFORM_PYTHON` for the copy, and run the real script with `subprocess`. They never edit a repo file. The tests assert that the string replace changed the file, so a later refactor cannot turn a mutant into a no-op.

Place of the M2 dot: in the page body, outside every box, at 50 % of the page width and 92 % of the page height. Never in a corner. Measured: page rotation with `expand=False` replaces a corner with the cast color. A 2 x 2 dot at pixel (2, 2) gave an outside maximum of 0 to 4 at angles of 1.2 degrees and -1.2 degrees, so the mutant would survive. The same dot gave about 170 at 0.35 degrees. A dot in the page body gave 170 to 186 at all four angles.

Order of the work in slice 1:

1. **Commit 1: tests and fixtures only, no check change.** Add the three tests above and the mutant builder. Run them on the old check. The two mutant tests must be RED (the old check exits 0 on a page without ink, proved in section 2). The control test is GREEN. Paste this run in the PR body.
2. **Commit 2: add the paired-seed difference check** (section 4, slice 1, steps 1 to 3). Run the same tests. All three must be GREEN, and the failure text must be the text in the table.
3. **Stop rule.** If one mutant test stays green after commit 2, slice 1 is not done.
4. The PR may hold two commits so that the red run stays in the history. If the maintainer wants one commit, the PR body keeps the red run output instead.
5. **Gate rule.** Slices 3 and 4 start only after slice 1 is merged and its PR body holds the red run (step 1) and the green run (step 2).

What the check does (all numbers are locked, see section 9):

- It reads the label boxes only from the `labels.jsonl` of the filled run. The twin run has no label lines. A check that reads boxes from the twin has zero boxes, and a page without ink would pass.
- A pixel is "outside" only when it lies outside every label box of that page. On a page with two fields, a pixel inside field A is outside field B, but it is not outside.
- It rasterizes the page of each written PDF with pypdfium2 at the manifest dpi. It never uses the generator image.
- The per-pixel difference is the maximum of the red, green, and blue differences. It is not gray. Measured: a 24 x 24 block of (235, 255, 255) on white gave a gray maximum of 8 and a red maximum of 22.
- Outside: no pixel above 8. The limit `OUTSIDE_TOL` is 8. It is never raised. If a test finds an outside pixel above 8, the fix is a wider box pad (slice 2 and slice 3), never a higher limit.
- Inside: for the drive form only (two boxes of 40 pt), at least 1 % of each label box has a difference of 48 or more. The rule is not used for tight text boxes. Measured: with 9 pt boxes at 100 dpi the inside maximum sits near 35 to 47, so the share at 48 or more is 0 for some seeds.
- Tests with other boxes assert the outside rule only.
- The 1 px width gap: at 100 dpi the generator image is 584 px wide, the PDF media box is 420.48 pt wide, and pdfium renders 585 px. At 72, 200, and 300 dpi the sizes match. Compare the two PDF rasters to each other (they have the same size). Do not require the raster to equal the generator image size.

## 4. Slices (pull requests)

| Slice | Name | Starts when | Changes scan strength or speed? |
| --- | --- | --- | --- |
| 1 | Prove ink: paired-seed check, blank gate, four CLI drives, skill text | the plan review clears the plan or lists NITs only | No |
| 2 | Honest inputs and labels: `_fit` skip, widget types, `/Rotate` and CropBox, wider `map_box` pad, `map_box` blur fixture, no-label warning | slice 1 is open | No |
| 3 | Scan: blur in mm, zero-mean grain, cast before JPEG, row in field seed, version 0.2.0 | slices 1 and 2 are merged | Yes |
| 4 | Throughput: `map_box` corners, embed JPEG, one metadata write, font cache | slice 3 is merged | Speed only |

Merge order: 1, 2, 3, 4. The order is strict. Slices 2 and 3 both edit `fill.py` and `render.py`, so slice 3 starts from the merged slice 2.

### Slice 1: prove ink

Steps in order (the gate work in section 3 comes first, as commit 1):

1. Make `check-fill-boxes.py` take an optional third argument, the twin run directory (`check-fill-boxes.py FILLED_OUT EVIDENCE TWIN_OUT`). Put the logic in one function, `check_run(filled_dir, twin_dir) -> list[str]`, that returns failure messages. `main()` prints them and exits 1 if the list is not empty. Keep the old checks (two PDFs, four labels, manifest, warning, no answer token in the text layer).
2. Add the difference check inside `check_run`, with the rules in section 3. Write `diff-row-0001.png` and `diff-summary.txt` to the evidence directory.
3. Change `make-blank-form.py` to also write `rows-twin.csv` (same header, two rows, empty values).
4. Change `verify-synthform`: `drive_fill_boxes` runs the CLI a second time with `rows-twin.csv` into `out-twin`, same seed and dpi. Then it calls the check. The drive must not treat a stderr warning from the twin run as a failure (after slice 2 the twin run prints the no-label warning).
5. Add four drives to `verify-synthform` and to the skill: `drive-fill-acroform`, `drive-fill-json-image`, `drive-seed-repro`, `drive-refuse-missing-boxes`. Each one runs `python -m synthform` in its own process with its own work directory under `SYNTHFORM_VERIFY_WORK`. `drive-seed-repro` starts the two runs with different `PYTHONHASHSEED` values (1 and 2). `drive-refuse-missing-boxes` checks exit code 2, the stderr text, and that the `--out` directory does not exist. Add `drive-all`, which runs the five drives one after the other as separate processes.
6. Add `tests/test_cli_drives.py`. It runs the same four cases with `subprocess.run([sys.executable, "-m", "synthform", ...])`. It never calls `cli.main`.
7. Fix `skills/verify-synthform/SKILL.md`: replace the `RUN_ID` sentence with `SYNTHFORM_VERIFY_WORK`. Update the Evidence list and the feature files (`fill-boxes.md`, `fill-acroform.md`, `fill-json-image.md`, `seed-repro.md`, `refuse-missing-boxes.md`, `README.md`) so they say which drive covers which feature. Remove "Not covered by drive-fill-boxes" where a drive now covers the case.
8. Run the gate steps from section 3 and paste the output.

### Slice 2: honest inputs and labels

1. `_fit` (in `render.py`): return a flag that says if the text fits. Today the last lines return the 6 px font with no fit test.
2. `draw_field`: when the text does not fit at 6 px, paint nothing and report "not drawn". `fill.py` then writes no label for that field, prints one line to stderr that holds `text does not fit`, and adds the field to `skipped_fields` in `manifest.json`. The key is new. `manifest.json` has no such key today.
3. Pin the unbreakable token for the tests (section 5, line 3).
4. `fields.py`: keep a widget only when its field type is `/Tx`. Read the type with `_inherited(widget, "/FT")`, as today. Do not read only the widget's own `/FT`: a parent `/Tx` with a kid that has no `/FT` is a text field. A choice widget, a widget with no field type anywhere in its chain, `/Btn`, and `/Sig` are not filled. A form that has only such widgets now needs `--boxes`, and the boxes work.
5. `raster.py`: refuse a PDF page with `/Rotate` other than 0 (after modulo 360) with `ScanformError`, so the CLI exits 2 and writes nothing. Apply the same rule to a page whose `CropBox` differs from its `MediaBox`. Compare the four numbers with a tolerance of 0.01 pt.
6. `scan.py`: widen the `map_box` pad. New pad: `ceil(3 * blur_radius + 1) + 4` pixels. The 4 extra pixels cover the JPEG block leak. Measured with the scan as it is today (a solid near-black fill of the field rectangle with a 2 px inset, the paired difference, max RGB channel, 40 random scan settings for each dpi, box offset varied): the worst outside value without extra pad was 9 to 12 (dpi 100, 200, 300), and with +4 px it was 4. With a 0 px inset it was 13 to 14 without extra pad and 4 to 6 with +4. `map_box` keeps `blur_radius` in pixels.
7. `fill.py`: when the final label list is empty, print one line to stderr that holds `no label written` and exit 0. The exit code does not change.
8. Add the fixtures and tests of section 5. Build every fixture with ReportLab and pypdf in the test. Do not commit binary PDFs.
9. Update `README.md`: text fields only; a skipped field; a rotated or cropped PDF; the no-label warning.

### Slice 3: scan (starts after slices 1 and 2 are merged)

1. **Scan seed.** Keep the scan seed as `stable_seed(seed, "scan", row_number, page_index)`. The seed has no text and no field name. This matters. The filled run and the twin run share the scan seed, so shared grain cancels in the paired difference. Measured: with one shared grain seed the outside maximum was 0. With two grain seeds it was 19, with 1101 pixels above 8. A different scan seed between the two runs would break the proof.
2. **Blur in millimetres.** `params_for(rng, dpi)` draws `blur_sigma_mm` and converts: `blur_radius_px = blur_sigma_mm * dpi / 25.4`. `ScanParams.blur_radius` stays in pixels, because `map_box` computes its pad from it. (A mm value in that field gives a pad of 2 px and the blur leaves the box.) Pillow `GaussianBlur(radius)` takes the standard deviation. `fill.py` passes `dpi`. Range: see section 9, Q6.
3. **Zero-mean grain.** Replace `_sensor_noise`. Build a signed grain layer with mean 0 and add it to the page (`ImageChops.add` with an offset). Do not blend toward gray. Draw the bytes with `rng.randbytes`, so the work stays fast and the seed still repeats the result. Range: see section 9, Q7. Use the same offset on R, G, and B.
4. **Cast before JPEG.** New order: rotate, blur, grain, paper cast, JPEG encode. Nothing touches the pixels after the JPEG encode.
5. **Row number in the field seed.** `field_draw_params(style, seed, field_name, box_w, box_h, row=0)` uses `stable_seed(seed, "field", row, field_name, font_id)`. `fill.py` passes the row number. Default `row=0` keeps old callers valid. The test goes through `fill_form` (section 5).
6. **Pad.** Run the edge-fill sweep (section 5, line 11) with the new blur, grain, and cast order. If an outside pixel is above 8, widen the pad. Do not change `OUTSIDE_TOL`. Do not change the scan seed.
7. **Version.** Change `version` in `pyproject.toml` and `__version__` in `src/synthform/__init__.py` together to 0.2.0. A test compares the two.
8. State in the PR body that every pixel, every `box`, and every `jitter` value changes by design.

### Slice 4: throughput (starts after slice 3 is merged)

Order, by measured cost. Run the measure plan in section 6 before and after each step. After each step, also run the paired-seed check: outside maximum 8 or below, and the drive inside rule. Do not replace that rule with a new tolerance.

1. `map_box`: transform the four corners, round down the minimum and up the maximum, and add the pad. No page-sized image. The new box must be at least as large as the box that today's mask method gives, on every edge. Measured: over 3000 random boxes, angles, blur values, and page sizes (including boxes cut by the page edge), the corner box was never smaller than the mask box.
2. Embed the JPEG. Slice 3 already removed every pixel step after the JPEG encode, so the encoded bytes go into the PDF as they are. Set `reportlab.rl_config.useA85 = 0`, so ReportLab does not wrap the stream in ASCII85 (the profile shows ASCII85 costs 24 % of the run). Measured: with `useA85 = 0` and `Canvas(..., invariant=1)` the image filter list is `/DCTDecode` only and the raw stream equals the JPEG bytes.
3. Metadata once: use `Canvas(..., invariant=1)` and `canvas.setProducer(...)`. Delete `_stamp_metadata` and the pypdf import. `invariant=1` is needed. Without it ReportLab writes the current time and the PDF bytes differ from run to run (checked). Today the pypdf rewrite drops the date, so the bytes repeat by accident.
4. Font cache: `functools.lru_cache` on a helper `_font(path_str, size)`. The profile shows this saves about 0.1 %. It is a tidy-up. Do it last.

## 5. Done-when lines and their proof

Names below are the planned names. All tests run with `python -m pytest -q` from the repo root.

| # | Done-when line | Proof | Expected |
| --- | --- | --- | --- |
| 1 | A real fill passes `drive-fill-boxes` and its difference image is covered by the label boxes | `tests/test_ink_proof.py::test_real_fill_passes_against_its_empty_twin`; `tests/test_ink_proof.py::test_paired_seed_difference_is_inside_the_label_boxes`; `verify-synthform drive-fill-boxes` | tests pass; command exits 0; `diff-summary.txt` says `outside_max<=8` |
| 2 | A blank image-only PDF fails `drive-fill-boxes` | `tests/test_ink_proof.py::test_paint_nothing_mutant_fails_drive_fill_boxes` (mutant M1) | test passes; the drive on the mutant exits 1 and prints `no ink in label box` |
| 2a | The check is not fooled by ink outside the box | `tests/test_ink_proof.py::test_ink_in_the_page_body_fails_drive_fill_boxes` (mutant M2, dot in the page body) | test passes; the drive exits 1 and prints `ink outside label box` |
| 2b | The check reads boxes from the filled labels only, and "outside" means outside every box | `tests/test_ink_proof.py::test_check_reads_boxes_from_the_filled_labels`; `::test_pixel_inside_another_box_is_not_outside`; `::test_colored_leak_is_measured_in_the_worst_channel` (24 x 24 block of (235, 255, 255): gray reads 8, red reads 22, so the check must fail it) | tests pass |
| 2c | The test reads the written PDF | the tests above rasterize `row-*.pdf` with pypdfium2 and never use the pre-PDF PIL image | review the test source |
| 2d | Edge ink stays in the padded box | `tests/test_render.py::test_edge_fill_stays_inside_the_padded_box` (solid fill, 2 px inset, dpi 100, 200, 300, outside maximum 8 or below) | passes |
| 3 | An unbreakable token that does not fit at 6 px makes no label that claims the full string | `tests/test_render.py::test_unbreakable_token_that_cannot_fit_is_not_drawn`; `tests/test_render.py::test_unbreakable_token_that_fits_when_shrunk_keeps_its_label`; `tests/test_fill.py::test_unfit_token_gets_no_label_a_stderr_line_and_a_skipped_field` | tests pass |
| 4 | The four CLI drives pass in separate processes | `tests/test_cli_drives.py::test_drive_acroform_uses_widget_names`; `::test_drive_json_and_png_writes_one_pdf`; `::test_two_processes_write_identical_labels`; `::test_missing_boxes_exits_2_and_creates_no_pdf`; `verify-synthform drive-all` | tests pass; command exits 0 |
| 5 | SKILL.md names `SYNTHFORM_VERIFY_WORK` | `! grep -n RUN_ID skills/verify-synthform/SKILL.md` | no output, exit 0 |
| 6 | `map_box` fixture with a real blur | `tests/test_render.py::test_mapped_box_covers_blurred_rotated_rectangle` (blur 0.6, 2.0, 4.0 px; angle -1.2, 1.2) | passes |
| 7 | `/Rotate 90` and a CropBox that differs are refused | `tests/test_raster.py::test_rotated_pdf_is_refused`; `::test_cropbox_pdf_is_refused` (`python -m synthform`, exit 2, no `--out` directory) | passes |
| 8 | Only `/Tx` fields are filled | `tests/test_fields.py::test_only_text_widgets_are_filled` (one `/Tx` plus `/Sig`, `/Btn`, `/Ch`, and a widget with no `/FT`; the labels name only the `/Tx` field); `::test_text_field_type_is_inherited_from_the_parent`; `::test_choice_only_pdf_uses_boxes` | passes |
| 8a | No label written gives a warning, exit 0 | `tests/test_fill.py::test_no_label_written_warns_and_exits_0` (all values empty; also a data column with no box) asserts exit 0, `no label written` on stderr, and zero lines in `labels.jsonl` | passes |
| 9 | Blur scales with dpi | `tests/test_scan.py::test_blur_radius_scales_with_dpi` (same seed at 100 and 200 dpi, ratio 2.0) | passes |
| 10 | Noise is zero-mean | `tests/test_scan.py::test_grain_is_zero_mean_on_white_black_and_gray` | passes |
| 11 | Cast is applied before JPEG | `tests/test_scan.py::test_cast_is_applied_before_jpeg` (the JPEG encoder gets the tinted page; output equals the decoded JPEG) | passes |
| 12 | Field jitter differs by row | `tests/test_fill.py::test_field_jitter_differs_by_row_through_fill_form`; `tests/test_styles.py::test_field_jitter_repeats_for_the_same_row` | passes |
| 13 | `map_box` allocates no page-sized image | `tests/test_render.py::test_map_box_allocates_no_page_sized_image`; `::test_map_box_is_at_least_as_large_as_the_mask_box` | passes |
| 14 | PDF metadata is written once | `tests/test_fill.py::test_pdf_metadata_is_written_once` (the module has no `PdfWriter`; `/Producer`, `/Title`, `/Subject`, `/Keywords`, `/Creator`, `/Author` are right; two runs give the same bytes) | passes |
| 15 | Fonts are cached | `tests/test_render.py::test_font_is_loaded_once_per_size` (`cache_info().hits` rises on the second `_fit`) | passes |
| 16 | JPEG is not round-tripped and Flate-compressed | `tests/test_fill.py::test_pdf_embeds_the_jpeg_as_is` | passes |
| 17 | Version is 0.2.0 in both places | `tests/test_scan.py::test_pyproject_and_package_versions_match` | passes |
| 18 | PR body says `Refs GMA-109` and not Fixes or Closes | `grep -n "Refs GMA-109" pr-body.md` and `! grep -Eni "fixes|closes" pr-body.md` | one hit or more; no hit |
| 19 | Existing tests stay green | `python -m pytest -q` | at least 14 passed, plus the new tests, 0 failed |

Details that the test names hide:

1. **Zero-mean test (line 10).** Build the grain with a fixed standard deviation of 5. Run the grain stage on a white page, a black page, and a gray 128 page. White: the mean shift is between -2.25 and 0. Black: between 0 and 2.25. Gray: within 0.25. The bound 2.25 is the clip bias (0.399 times the deviation is 2.0) plus a small margin. Measured: the grain layer has mean 0.001 and standard deviation 5.02. The shift is -2.05 on white, +2.05 on black, 0.00 on gray. The gray test alone is not enough: today's blend gives -0.43 on gray 128 and passes it. Today's blend gives -5.6 to -10.6 on white and +4.8 to +9.8 on black, so the white and black tests fail it. In the first commit of slice 3, point the test at `_sensor_noise` to show the red run.
2. **Row jitter test (line 12).** Run `fill_form` with 30 rows and 2 fields. Group the labels by (font_id, field). Use groups with 2 or more rows. For each label compute the residual: `dx`, `rotation - style.rotation`, `tracking_em - style.tracking`, and `ink - style.ink`. Assert that the residuals in a group are all different. Assert that at least one group exists. Do not compare whole `jitter` objects: they differ today because the row style differs. Measured on the current code for the first three parts of the residual (`dx`, rotation, tracking): 18 groups, and in all 18 the residual is identical. So the test is red today and green after the row enters the seed.
3. **Unbreakable token (line 3).** Token: `SUPERCALIFRAGILISTIC-VALUE-998877` written twice with no space between (66 characters). Box: 110 px wide, 42 px high. The test measures the token at 6 px for every vendored face with the lowest tracking in play (-0.035 em). Measured: the narrowest face (CoveredByYourGrace) gives 149.8 px, so the token is wider than the 108 px budget in all 12 faces. The test asserts this for every face, so a new face cannot make the test pass by accident. The 33-character token is not enough: it measures 75 to 119 px and fits the narrow faces. The fill-level test asserts three things: `labels.jsonl` has no line for the field, stderr holds one `text does not fit` line, and `manifest.json` `skipped_fields` lists the row and the field. The fits-when-shrunk test uses a token that fits at 8 px and asserts that the label keeps the full string.
4. **Memory test (line 13).** `tracemalloc` does not see Pillow image memory (measured: peak 0.0 MB for the old `map_box` on a 6000 x 8000 page, where one `L` mask is 48 MB). So the test spies on `PIL.Image.new`, `Image.Image.rotate`, `Image.Image.point`, and `Image.Image.copy` while `map_box` runs. It asserts that no image has more than 1 % of the page pixels. The old code fails (it makes three page-sized images). The test traces `map_box` only.
5. **Box size test (line 13).** The reference is today's mask method, kept inside the test. For 500 random boxes, angles, blur values, and page sizes, the new box must contain the reference box. The reference function is copied into the test because slice 4 deletes the old code.
6. **JPEG test (line 16).** Read the image XObject with pypdf. Assert that its filter list is `/DCTDecode` only. Assert that the raw stream equals the JPEG bytes that the scan returned. Assert that nothing decodes the buffer between the scan and `write_image_pdf`: count calls of `JpegImageFile.load` and read the count when `write_image_pdf` starts; it must be 0. ReportLab itself calls `load` once for the header (measured), so the count inside the writer is not 0. The raw byte equality is the proof that nothing re-encoded the data. Do not assert that the scan never opens a JPEG: the encoder does.
7. **Edge fill sweep (line 2d).** A near-black solid fill of the field rectangle, inset 2 px (the text budget inset is 2 px), on a white page. Compare `apply_scan` of the filled page with `apply_scan` of a white page, same scan seed. Use the max RGB channel. Vary the scan settings (40 draws for each dpi) and the box offset. Assert the outside maximum is 8 or below at dpi 100, 200, and 300. Measured today: 9 to 12 without the extra pad, 4 with it.
8. **Widget fixture (line 8).** Build with pypdf. Fields: one `/Tx` (direct type), one `/Tx` whose type comes from the parent (the kid has no `/FT`), one `/Sig`, one `/Btn`, one `/Ch`, and one widget with no `/FT` anywhere. ReportLab 5.0.1 `acroForm.choice(..., forceBorder=True)` fails with `UnboundLocalError`, so do not build the choice widget with it.
9. **Version test (line 17).** The test reads `version` from `pyproject.toml` and `__version__` and asserts both are `0.2.0`. It runs from slice 3.
10. **Check unit tests (line 2b).** They build small rasters in memory and call `check_run`-level helpers. They need no CLI.
11. **Mutant builder.** A function in `tests/` that copies `src/` and `skills/` to a temporary directory, applies one string replace, and fails if the replace changed nothing.

## 6. Measure plan for slice 3 and slice 4

Inputs (kept outside the repo, or in `skills/verify-synthform/scripts/bench-fill.py`, see Q11):

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

Output equality, per step of slice 4. Make the reference run with the code before the step. Make the second run with the code after the step. After every step also run the paired-seed check on the drive form and on the tight-box form: outside maximum 8 or below (max RGB channel), and the drive inside rule.

| Step | PDF bytes | Raster of each page (pdfium) | `labels.jsonl` |
| --- | --- | --- | --- |
| `map_box` corners | identical | identical | only `box` changes, and each new box contains the old box |
| Embed JPEG (and no ASCII85) | change on purpose; file is smaller | may change by a few gray levels, because the decoders differ. Report the maximum in the PR body. It is information, not a gate. The gate is the paired-seed rule | identical |
| Metadata once | change (file layout) | identical | identical. `pypdf` metadata equal. Two runs give identical bytes |
| Font cache | identical | identical | identical |

Slice 3 is not a speed change. Every pixel, every `box`, and every `jitter` value changes by design, so a before and after comparison is not an equality check there. For slice 3 the checks are the tests in section 5 and the paired-seed check at dpi 100, 200, and 300.

Paired-seed data (measured at a0e7265, white form, scan as it is today; the reviewer's own run agrees):

- Standard form (340 x 40 pt boxes), dpi 72, 100, 200, 300, seeds 7 and 8: no pixel outside the label boxes differs, except 7 pixels that differ by 1 level (dpi 300, seed 8).
- Tight text boxes (11 pt and 9 pt high), six seeds, dpi 100, 200, 300: the outside maximum is 0 to 5 in the two runs. JPEG blocks cause it. No pixel differs by 8 or more.
- Ink inside the box (difference of 48 or more): 5.2 % to 11.5 % of the box area for the two 17-character test words at 72, 100, and 200 dpi (the reviewer measured 6.7 % to 11.5 %). This is stable for the 40 pt drive boxes only.


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
| Same font and field name share one jitter on every row | Mostly true. The random draws repeat for rows that use the same font. Checked with 30 rows and 2 fields: 18 groups of (font, field) hold 2 or more rows, and in all 18 the random part is identical. The whole `jitter` object is never equal, because the row style differs. So a test must compare the jitter minus the style (the residual), not the whole object |
| `map_box` allocates a full-page mask once per field | True. One call per drawn field |
| `write_image_pdf` rewrites the file with pypdf to set `/Producer` | True. The ticket does not say that the rewrite also makes the bytes repeat. Slice 4 keeps this with `invariant=1` |
| `_fit` calls `ImageFont.truetype` on every size step | True, but small: 476 calls, 0.1 % of the run time |
| The JPEG is decoded, then Flate-compressed in the PDF | True. The ticket omits that ReportLab also wraps the stream in ASCII85 (the filters are `ASCII85Decode` and `FlateDecode`). That is 24 % of the run time |
| The blank raster is loaded once | True |

Metadata once and font cache are real but small in time. The ticket order for the speed work is not the order by cost. Section 4 uses the order by cost.

## 8. Risks

1. **Tolerance.** Exact zero outside the box is not possible with JPEG. `OUTSIDE_TOL` is 8 and is locked. Slice 3 changes blur, grain, and cast. Measure the edge fill again there. If an outside pixel is above 8, widen the pad only.
2. **False pass.** A very short value (one character) has little ink. The inside rule (1 % at 48 levels) applies to the 40 pt drive boxes and the drive words only. Other tests assert the outside rule only.
3. **Skipped fields reduce the corpus.** The user sees one stderr line for each skipped field and the list in `manifest.json`.
4. **Behavior changes.** A form that worked before may now exit 2 (rotated or cropped page), or may lose a choice label. The no-label warning is new output on stderr. Say so in the README and in the PR body.
5. **Seed change.** Slice 3 changes every output for a given seed. Version 0.2.0 marks this. Old corpora cannot be rebuilt from the new version.
6. **Label boxes grow.** The extra pad of 4 px makes each `box` larger. A label box is not a tight ink box (the README says so). Slice 2 states the new rule in the README.
7. **`rl_config.useA85` is a global setting in ReportLab.** Set it in `pdfout.py` once. Test that it does not change other PDFs in the same process.
8. **Environment.** The ReportLab C accelerator is not present in the venv used for the baseline, so the pure-Python ASCII85 encoder ran. A machine with the accelerator will show a smaller ASCII85 share.
9. **Page size.** `write_image_pdf` sets the page to `pixels * 72 / dpi` points. A 420 pt page becomes 420.48 pt at 100 dpi, and pdfium renders 585 px where the generator image has 584 px. At 72, 200, and 300 dpi the sizes match. The plan does not change this. Every check compares PDF rasters to each other.
10. **Memory test.** `tracemalloc` cannot see Pillow image memory. The memory test spies on image creation instead (section 5, detail 4).
11. **Mutant tests copy the code.** They run a second Python process on a copy of `src/` and `skills/`. They are slower than unit tests. Each costs about 2 seconds (one drive run).

## 9. Locked answers

The maintainer accepted every recommended default. These answers are final. The plan has no open question.

| # | Question | Locked answer |
| --- | --- | --- |
| Q1 | Tolerance for "the difference is inside the label box" | Outside: no pixel above 8 gray levels, measured as the maximum of the red, green, and blue differences. The limit is never raised. Inside: at least 1 % of each label box has a difference of 48 or more. The inside rule applies to the 40 pt drive boxes only. There is no minimum pixel count rule |
| Q2 | `_fit` gives up at 6 px | Skip the field. Write no label. Print one stderr line that holds `text does not fit`. List the field in `skipped_fields` in `manifest.json` |
| Q3 | A PDF page with `/Rotate` other than 0 | Refuse. Exit 2. Write nothing |
| Q4 | A PDF page whose CropBox differs from its MediaBox | Refuse. Same check as Q3 |
| Q5 | Which widget types are filled | Only `/Tx` text fields. The type may come from a parent |
| Q6 | Blur unit and range | Millimetres. Sigma 0.10 to 0.22 mm. Pixels = mm x dpi / 25.4. At 200 dpi that is 0.79 to 1.73 px. At 100 dpi it is 0.39 to 0.87 px (about today's pixel blur) |
| Q7 | Grain amplitude and shape | Standard deviation 2 to 5 gray levels, per pixel, mean 0, the same offset on R, G, and B, independent of dpi |
| Q8 | Embed the JPEG or skip the round-trip | Embed the JPEG, with ASCII85 off |
| Q9 | Version bump | 0.2.0 in slice 3. Change `pyproject.toml` and `__version__` together |
| Q10 | No label written at all | Warn on stderr only. Exit 0. A test covers it (section 5, line 8a) |
| Q11 | A benchmark script in the skill | Yes. `skills/verify-synthform/scripts/bench-fill.py`. It has no data and no network use |
| Q12 | Review cap | 2 rounds for each slice |

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
- `src/synthform/render.py`, `src/synthform/fill.py`, `src/synthform/fields.py`, `src/synthform/raster.py`, `src/synthform/scan.py` (pad only), `README.md`
- `tests/test_render.py`, `tests/test_fill.py`, `tests/test_fields.py` (new), `tests/test_raster.py` (new)

**Slice 3**
- `src/synthform/scan.py`, `src/synthform/render.py`, `src/synthform/fill.py`, `src/synthform/__init__.py` (version), `pyproject.toml` (version), `README.md`
- `tests/test_scan.py` (new), `tests/test_styles.py`, `tests/test_fill.py`, `tests/test_ink_proof.py`

**Slice 4**
- `src/synthform/scan.py` (`map_box`, return the JPEG bytes), `src/synthform/pdfout.py`, `src/synthform/render.py` (font cache), `src/synthform/fill.py`
- `skills/verify-synthform/scripts/bench-fill.py` (new)
- `tests/test_render.py`, `tests/test_fill.py`, `tests/test_scan.py`

## 11. Out of scope

- Form 1583 and any legal, tax, or identity form for submission.
- Cloning a person's handwriting or signature.
- A pen-stroke or handwriting-dataset model. The OFL fonts stay.
- A process pool across rows.
- A change to the locked limits (8 levels outside, 1 % at 48 levels inside).

## 12. Review round 1 changes

Source: the plan review of the first head (8ed32151), round 1 of 2. Each row is one finding.

| Finding | What changed | Where |
| --- | --- | --- |
| 1 BLOCKER. The blank test ran the passing pair | Split into three tests: a control (real fill against its twin, exit 0), an automated paint-nothing mutant M1 through `drive-fill-boxes` (exit 1, `no ink in label box`), and mutant M2 | Section 3; section 5 lines 1, 2, 2a |
| 2. Which pixels are outside | Boxes come only from the filled `labels.jsonl`. A pixel is outside only if it is outside every box. Tests added | Section 3; section 5 line 2b |
| 3. M2 dot in a corner can vanish | The dot goes in the page body (50 % width, 92 % height). Measured: a corner dot gave 0 to 4 at plus or minus 1.2 degrees; a body dot gave 170 to 186 | Section 3 |
| 4. Edge ink and short boxes | `map_box` pad gets +4 px (slice 2). The 1 % at 48 rule applies to the 40 pt drive boxes only. The tight-box test asserts the outside rule only. New edge-fill test | Section 3; slice 2 step 6; section 5 line 2d and detail 7 |
| 5. Gray hides a colored leak | The difference is the maximum of R, G, B. A test uses the 24 x 24 block | Section 3; section 5 line 2b |
| 6. Scan seed and tolerance | One scan seed with no text and no field name. `OUTSIDE_TOL` stays 8 and is never raised. The "raise tolerance" text is removed. If an outside pixel is above 8, widen the pad only | Slice 3 steps 1 and 6; section 3; section 9 Q1 |
| 7. Zero-mean test passes the old blend | The test runs on a white, a black, and a gray page with bounds from the clip bias. First commit of slice 3 shows it red on `_sensor_noise`. The lift-black test is merged into it | Section 5 line 10 and detail 1 |
| 8. Pin the unbreakable token | A 66-character token, a 110 px box, a test over every vendored face. The fill test asserts stderr and `skipped_fields` | Section 5 line 3 and detail 3 |
| 9. Row jitter and `/FT` | The row test goes through `fill_form` and compares residuals, not whole objects. `_inherited` stays. The widget fixture holds all six widget kinds | Section 5 lines 8 and 12; details 2 and 8; slice 2 step 4 |
| 10. Slice order and slice 4 | Slice 3 starts after slices 1 and 2 are merged. The paired-seed check runs after each slice-4 step. The new `map_box` contains the old box. The JPEG raster tolerance is removed | Section 1 rule 10; section 4; section 6; slice 4 |
| 11. Locks, Q10, version | New "Locked answers" section. The 20-pixel rule and the option to raise the tolerance are gone. Q10 has a step and a test. The version change covers `pyproject.toml` and `__version__` | Section 9; slice 2 step 7; slice 3 step 7; section 5 lines 8a and 17 |
| 12. JPEG test and memory test | The JPEG test compares raw DCT bytes and the `/DCTDecode`-only filter. The memory test traces `map_box` only. Disagreement: `tracemalloc` cannot see Pillow memory, so the test spies on image creation | Section 5 details 4 and 6; section 8 risk 10 |
| 13. Scope drift | The 20-pixel rule and the tolerance rise are removed. Q10 is added. `drive-all` and the diff files stay. The PR-body grep covers Fixes and Closes only | Section 1 rule 7; section 3; section 9 |
| 14. NIT. Author address | The push rule asks for a role no-reply address with no personal login | Section 1 rule 8 |
| 15. NIT. dpi 100 raster is 1 px wider | Recorded. Checks compare PDF rasters to each other | Section 3; section 8 risk 9 |
