---
change-id: p2-table-border-protection
schema-version: 0.1.0
last-changed: 2026-06-19
risk: medium
tier: 3
---

# Test Plan: p2-table-border-protection

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_table_border_protection.py::TestBorderAwareRedactRect | 0 |
| AC-1 | integration | tests/test_table_border_protection.py::TestOverlayBorderPreservation | 3 |
| AC-2 | unit | tests/test_table_border_protection.py::TestSideBySideSourceMasking | 0 |
| AC-2 | integration | tests/test_table_border_protection.py::TestSideBySideRightPanelMasking | 3 |
| AC-3 | unit | tests/test_table_border_protection.py::TestMaskCoversTextContent | 0 |
| AC-3 | integration | tests/test_table_border_protection.py::TestOverlayBorderPreservation | 3 |
| AC-4 | golden-regression | tests/test_golden_regression.py | 3 |
| AC-5 | unit | tests/test_table_border_protection.py::TestConfinementNoNewImports | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Masking-geometry helpers and redact-rect shrink logic; mock PyMuPDF page objects where a real PDF is not needed |
| integration | 3 | End-to-end overlay and side-by-side render of `tests/fixtures/test.pdf`; assert via `page.get_drawings()` and `page.get_text()` |
| golden-regression | 3 | Existing `tests/test_golden_regression.py`; any re-baseline commit must cite this change-id and state the reason |

## New Test File: tests/test_table_border_protection.py

### TestBorderAwareRedactRect (unit, Tier 0)
- `test_redact_rect_shrinks_by_margin` — matched-quad redact_rect is inset by `PDF_MASK_MARGIN_PT` on all four sides
- `test_redact_rect_fallback_uses_double_margin` — fallback (no matching quad) uses `PDF_MASK_MARGIN_PT * 2`
- `test_redact_rect_skipped_when_too_small` — width < 1 or height < 1 → element not added to redaction_items
- `test_text_rect_from_placement_not_quad` — text-insertion rect always uses `placement.x0/y0/x1/y1`, never quad coordinates

### TestMaskCoversTextContent (unit, Tier 0)
- `test_redact_rect_interior_to_text_bbox` — for a standard element, redact_rect lies entirely within the element bbox
- `test_margin_zero_redact_rect_equals_quad_rect` — with `PDF_MASK_MARGIN_PT = 0`, redact_rect == matched quad rect

### TestSideBySideSourceMasking (unit, Tier 0)
- `test_right_panel_source_text_masked_before_overlay` — `_generate_side_by_side` applies a white mask over source text regions on the right-panel copy before the translated overlay is placed; assert via mock call-order on the fitz page
- `test_right_panel_mask_covers_all_elements` — for a page with N elements, N corresponding mask rects are drawn on the right panel

### TestConfinementNoNewImports (unit, Tier 0)
- `test_no_new_top_level_imports_in_fitz_renderer` — parse the import block of `app/backend/renderers/fitz_renderer.py`; assert no new top-level package imports were added by this change

### TestOverlayBorderPreservation (integration, Tier 3)
- `test_overlay_table_borders_survive_redaction` — render `tests/fixtures/test.pdf` overlay mode; assert `page.get_drawings()` is non-empty (vector strokes present after redaction)
- `test_overlay_source_text_not_visible` — render overlay mode; assert original source text string absent from `page.get_text()` of output (redaction applied)

### TestSideBySideRightPanelMasking (integration, Tier 3)
- `test_sbs_right_panel_no_source_text` — render side-by-side; clip to right-half rect; assert source text strings absent from right-panel text extraction
- `test_sbs_right_panel_translated_text_present` — render side-by-side with known translations; assert translated string present in right-half text extraction

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_golden_regression.py (snapshot .ir.json files) | re-baseline if masking geometry shifts element extraction | AC-4; any re-baseline must be committed with explicit justification |

## Out of Scope

- Visual diff of rendered PDFs (owned by visual-reviewer agent; visual-review-report.md)
- Font cache, text-fitting, font-fallback logic (covered by existing TestFontBufferCache)
- DOCX / PPTX renderers
- API, env, data-shape contracts (AC-5: no changes)
- Performance / stress testing

## Notes

- Unit tests mock `fitz.Page` methods (`add_redact_annot`, `apply_redactions`, `draw_rect`) to run without a real PDF.
- Integration tests guard with `@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")`.
- `PDF_MASK_MARGIN_PT` must be imported from `app.backend.config` in tests, never hardcoded.
- Bug-fix-engineer writes failing tests first; backend-engineer makes them pass — this file is their shared contract.
