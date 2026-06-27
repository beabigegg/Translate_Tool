---
artifact: visual-review-report
change-id: pdf-layout-refactor
reviewer: visual-reviewer
verdict: APPROVED_WITH_RISK
date: 2026-06-27
---

# Visual Review Report — pdf-layout-refactor

## Verdict: APPROVED_WITH_RISK

No blocking issues. One carry-forward risk (AC-4 per-span renderer gap, tracked below).

## Whitening Coverage: Adequate

`fitz_renderer.py` `_generate_overlay` path correctly implements bbox-exact whitening.
Reads `element.metadata.get("lines", [])` for paragraph-aggregated elements (whitening
each source line individually) and falls back to placement bbox for single-line elements.
`page.search_for` is never called. `graphics=0` flag on `apply_redactions` preserves
table border strokes. Two AC-1 tests assert `search_for` not called and `add_redact_annot`
called.

## Scale-Fit Logic: Correct

`fit_text_cascade` in `text_region_renderer.py` performs a 20-iteration binary search
between `lo=MIN_READABLE_FONT_PT (8pt)` and `hi=initial_size`. Floor is 8pt (cannot
go lower). Truncation step fires only after 8pt is exhausted. `MIN_FONT_SIZE_PT = 8`
alias eliminates the 6pt/4pt/8pt conflict from the design Open Risks. Post-cascade
clamp in `_insert_text_in_rect` (language-specific min, defaulting 4pt) is dominated
by the cascade value and does not weaken the readable floor guarantee.

## Style Fidelity: Gap (Risk — Carry-Forward)

IR side is correct: `StyleInfo.is_underline` added with `False` default; `to_dict`
and `from_dict` are backward-compatible; `color`, `is_bold`, `is_italic` all round-trip.

Renderer side is incomplete: `_insert_text_in_rect` constructs its own `StyleInfo`
(font_size only) and ignores `element.style` — no per-span color/bold/italic/underline
applied to fitz TextWriter output. D-4 ("fitz renderer emits one `insert_text` per span
run") is not present in the implementation.

**Risk level**: Low regression impact. Pre-change state was also unstyled output;
this is not a regression, only a gap relative to the D-4 target. The IR correctly stores
all style fields for future renderer consumption.

**Follow-on**: open a separate tracked change to wire `element.style` consumption into
`_insert_text_in_rect` (per-span color/bold/italic application).

## DPI Reasoning: Sound

`PDF_RENDER_DPI=150` default with `=72` opt-out documented. Matrix scale `150/72 ≈ 2.08`
applied at both rasterize sites in `pdf_parser.py`.

Coordinate mismatch fix is correctly implemented: `LayoutDetector.detect()` accepts
`page_width_pt`/`page_height_pt` parameters; `pdf_parser.py` passes `page.rect.width`
and `page.rect.height` (PDF points, independent of render DPI) so coordinate mapping
is correct at any DPI value. New test `TestDpiCoordinateBackMapping::test_element_type_correct_with_pt_params_at_high_dpi`
verifies behavioral correctness of the fix at 3× DPI.

## Summary

| Check | Result |
|---|---|
| Whitening leaves no ghost text | Pass |
| Scale-fit stays above 8pt floor | Pass |
| IR stores color/bold/italic/underline | Pass |
| Fitz renderer applies per-span style | Gap (follow-on) |
| DPI matrix correctly applied | Pass |
| Coordinate back-mapping correct | Pass (tested) |
| No blocking issues | Pass |
