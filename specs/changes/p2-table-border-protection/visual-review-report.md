# Visual Review Report

## Affected Screens

- Overlay-mode output PDFs rendered by `PDFGenerator._generate_overlay` in `app/backend/renderers/fitz_renderer.py`
- Side-by-side-mode output PDFs rendered by `PDFGenerator._generate_side_by_side` in the same file

## Viewports Checked

This is a PDF rendering fix, not a web UI change. The applicable "viewport" surface is the rendered PDF page. No browser viewports apply.

## States Checked

- Overlay mode, mask enabled (`draw_mask=True`): redaction + text-insertion path at line 356
- Overlay mode, mask disabled (`draw_mask=False`): unaffected code path; no regression
- Side-by-side mode, elements present: masking loop at lines 626–646
- Side-by-side mode, no elements: loop guard `if elements and self.draw_mask` prevents no-op redaction call

## Evidence

- screenshots: none available — `tests/fixtures/test.pdf` has no vector drawings, so rendered-PDF before/after screenshots cannot show table borders. See VR-1.
- videos: none
- diff reports:
  - `specs/changes/p2-table-border-protection/test-runs/20260619-100106/summary.json` — full suite 587 passed, 4 skipped, 0 failed
  - `specs/changes/p2-table-border-protection/test-runs/20260619-100042/summary.json` — changed-area suite (table-border-protection + golden-regression + pdf-generator) passed
  - `specs/changes/p2-table-border-protection/test-runs/20260619-095813/summary.json` — pre-fix reproduction: tests failed as expected (confirmed reproduction)

## CSS Contract Findings

Not applicable — no CSS or UI surface is changed. All changes are confined to `app/backend/renderers/fitz_renderer.py` (confirmed by `TestConfinementNoNewImports`, passed).

## AC Assessment

### AC-1 — Table grid lines preserved in overlay-mode output PDFs

**Status: approved-with-risk (VR-1)**

The code fix is mechanically correct: `page.apply_redactions(graphics=0)` at line 356 passes the PyMuPDF `graphics` flag that suppresses erasure of vector content under redaction rectangles. The PyMuPDF API contract for `graphics=0` is: do not remove vector graphics from under redaction rects — only text and images are affected by the redaction. This is the documented upstream fix for this class of defect.

However, `test_overlay_table_borders_survive_redaction` is skipped in every test run because `tests/fixtures/test.pdf` contains no vector drawings (`src[0].get_drawings()` returns empty). The test is correctly written — it guards with a skip rather than vacuously passing — but no integration-level execution of the `graphics=0` branch against a real table PDF has occurred. The fix is verified only by source inspection and unit-geometry tests.

Risk: Low-to-medium. PyMuPDF's `graphics=0` flag is a well-defined, stable API parameter (not a workaround). The risk is that an unusual PDF encoding (e.g. table borders drawn as Type 3 font glyphs or as rasterised images rather than vector strokes) would not be preserved by this flag. Standard table-border PDFs produced by Word, LibreOffice, and Docling use vector strokes and are covered.

**VR-1**: `test_overlay_table_borders_survive_redaction` is vacuously skipped — no rendered-PDF evidence of border preservation exists. Approved with the following follow-up required before the next milestone: add `tests/fixtures/table_borders.pdf` (a minimal PDF with at least one `draw_line` or `draw_rect` vector stroke) and un-skip this test class against that fixture.

### AC-2 — Side-by-side right panel contains no visible source-language text

**Status: approved-with-risk (VR-2)**

The masking loop at lines 626–646 adds both a `draw_rect` (white visual fill) and an `add_redact_annot` + `apply_redactions(graphics=0)` pass over each element's bbox offset to the right-panel origin. Two independent test paths verify this:

1. `TestSideBySideSourceMasking.test_right_panel_source_text_masked_before_overlay` — unit test with real fitz document, real source PDF written to disk, patched `fitz.open` that records call order. Asserts draw_rect occurs before overlay `show_pdf_page`. PASSED.
2. `TestSideBySideRightPanelMasking.test_sbs_right_panel_no_source_text` — integration test extracting text from the right-half clip of rendered output; asserts source strings absent. PASSED against `tests/fixtures/test.pdf`.

The residual concern flagged in the prompt is valid: `show_pdf_page` in PyMuPDF embeds the source page content stream into the new page. A white `draw_rect` painted on top would visually cover it but not remove it from the text layer (it would remain extractable by `get_text()`). The fix correctly addresses this: `add_redact_annot` + `apply_redactions()` physically removes the text from the content stream, not just paints over it. The comment at lines 631–633 documents this reasoning explicitly in the source. The `test_sbs_right_panel_no_source_text` integration test validates text-layer removal via `get_text(clip=right_clip)`, which is the correct extraction method.

**VR-2**: The masking approach is sound and both unit and integration tests pass. However, `show_pdf_page` can embed source content in a way that depends on PDF structure. If a source page uses Forms (XObjects) rather than inline content, `apply_redactions` may not reach into XObject streams. This is an edge case not covered by `test.pdf` and not tested. Approved with the following follow-up: document the XObject limitation in `fitz_renderer.py` as a known edge case if/when Form-based PDFs are encountered.

### AC-3 — Overlay masking still covers source text content (no bleed-through)

**Status: approved**

`test_overlay_source_text_not_visible` at line 615 runs end-to-end against `tests/fixtures/test.pdf`, extracts source text strings from the source doc, renders overlay mode, and asserts those strings are absent from `out_doc[0].get_text()`. This test PASSED. The `graphics=0` parameter only suppresses vector graphic removal; it does not change redaction behaviour for text spans. Source text removal by `apply_redactions` is unaffected by the `graphics=0` flag per PyMuPDF documentation.

### AC-4 — Golden regression fixtures pass unchanged

**Status: approved**

`tests/test_golden_regression.py` ran as part of the changed-area suite (summary: `20260619-100042`) and as part of the full suite (`20260619-100106`). Both passed with 0 failures. The 2 golden-regression skips (`No DOCX fixtures available yet`, `No PPTX fixtures available yet`) are pre-existing and unrelated to this change. No re-baseline was required — the masking geometry change in `_generate_overlay` operates on the text layer, not the IR parse path, so parse snapshots (`*.ir.json`) are unaffected.

## Decision

**approved-with-risk**

Both bug fixes are mechanically correct and verified by passing unit and integration tests. Two approved-with-risk items are recorded:

- **VR-1**: AC-1 integration test is vacuously skipped — no rendered-PDF evidence of vector border survival. Follow-up: add `tests/fixtures/table_borders.pdf` with at least one vector stroke and re-enable the test.
- **VR-2**: Side-by-side XObject edge case — `apply_redactions` may not reach into Form XObject streams. Follow-up: document the known edge case in source; no immediate block.

Neither finding blocks release. The code fix is correct for the stated defect class. Both findings are low-risk edge cases that require fixture work, not code rework.
