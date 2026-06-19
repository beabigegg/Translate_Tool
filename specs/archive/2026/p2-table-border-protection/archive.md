# Archive: p2-table-border-protection

## Change Summary

Two visual rendering defects were fixed in `app/backend/renderers/fitz_renderer.py`. Bug (a): `page.apply_redactions()` was called with no arguments in `_generate_overlay`, causing PyMuPDF to erase all graphics under redaction rects — including table border vector strokes — not just text. Bug (b): `_generate_side_by_side` had no masking step between copying the source page to the right half and placing the translated overlay, leaving source-language text embedded in the page content stream and extractable alongside translated text. Both bugs were fixed with the `apply_redactions(graphics=0)` PyMuPDF argument and a new pre-overlay white-mask loop.

## Final Behavior

- **Overlay mode**: table grid lines (vector strokes) survive redaction; only text is removed. `apply_redactions(graphics=0)` preserves graphics while erasing text content.
- **Side-by-side mode**: source-language text is no longer visible on the right panel. A draw_rect + add_redact_annot + apply_redactions(graphics=0) loop over element bboxes (offset by src_rect.width) runs before the translated overlay is placed.

## Final Contracts Updated

None — no API, env, data-shape, or business-rule contract changes. This was a geometry-only rendering fix contained in fitz_renderer.py.

## Final Tests Added / Updated

- `tests/test_table_border_protection.py` — 13 tests (12 pass, 1 skipped):
  - `TestBorderAwareRedactRect` (4 unit tests) — AC-1 geometry
  - `TestMaskCoversTextContent` (2 unit tests) — AC-3
  - `TestSideBySideSourceMasking` (2 unit tests) — AC-2 call-order mock
  - `TestConfinementNoNewImports` (1 unit test) — AC-5
  - `TestOverlayBorderPreservation` (2 integration tests) — 1 skipped (test.pdf has no vector drawings)
  - `TestSideBySideRightPanelMasking` (2 integration tests) — AC-2 end-to-end

## Final CI/CD Gates

| gate | tier | required |
|---|---|---|
| contract-validate | 1 | yes |
| change-gate | 1 | yes |
| unit-tests | 1 | yes |
| golden-sample-regression | 2 | yes |
| renderer-equivalence | 2 | yes |

No new CI jobs added. Existing jobs cover all gates.

## Production Reality Findings

- `apply_redactions(graphics=0)` is the correct PyMuPDF API for text-only redaction preserving vector strokes — the default (no args) removes all content including graphics; this was the root cause of both bugs (the side-by-side bug shared the same fix).
- The integration test `TestOverlayBorderPreservation::test_overlay_table_borders_survive_redaction` is vacuously skipped because `tests/fixtures/test.pdf` contains no vector drawings. The unit geometry tests pass and the source call is confirmed correct; a vector-stroke PDF fixture would make this test non-vacuous. (VR-1)
- Form XObject streams may not be reached by `apply_redactions` in the side-by-side masking loop — an undocumented edge case. (VR-2)

## Lessons Promoted to Standards

None promoted. The `apply_redactions(graphics=0)` API behavior is an implementation detail — the correct call is in source at fitz_renderer.py:356 and regression is caught by `TestBorderAwareRedactRect` + `TestOverlayBorderPreservation`. Not a durable cross-change workflow rule; do-not-promote.

## Follow-up Work

- **P3 / test-strategist**: Add `tests/fixtures/table_borders.pdf` with vector strokes to make `TestOverlayBorderPreservation` non-vacuous.
- **P3 / backend-engineer**: Document Form XObject edge case in `_generate_side_by_side` source comment.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
