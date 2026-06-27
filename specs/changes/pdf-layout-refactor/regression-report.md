---
artifact: regression-report
change-id: pdf-layout-refactor
date: 2026-06-27
---

# Regression Report — pdf-layout-refactor

## Purpose

Durable before/after evidence for the high-risk PDF layout behavior changes (BR-84..88).

## Test Suite Baseline

| Phase | Result | Run |
|---|---|---|
| collect | passed | 20260627-190446 |
| targeted (29 new tests) | passed | 20260627-190446 |
| changed-area | passed | 20260627-190446 |
| contract | passed | 20260627-190446 |
| full | passed (990 passed, 4 skipped, 0 failures) | 20260627-190446 |

No pre-existing failures on `main`. The 4 skipped tests are pre-existing
fixture-availability skips (DOCX/PPTX golden, TABLE region emission, table-border
vector drawings) — confirmed present on `main` branch before this change.

## Metric Gates Status

| Gate | Type | Status |
|---|---|---|
| residual-text | required | pass — `test_pdf_layout_refactor.py -k residual_text` green |
| ocr-absent-gate | required | pass — `test_pdf_layout_refactor.py -k ocr_absent` green |
| biou-layout-fidelity | informational | deferred — no committed golden metric baseline yet |
| truncation-rate | informational | deferred — no committed golden metric baseline yet |
| reading-order-edit-distance | informational | deferred — no committed golden metric baseline yet |

The three informational gates are tracked in `ci-gate-contract.md` §Informational Gate
Promotion Policy. They require committed golden PDF fixtures with `.ir.json` snapshots
as baselines. The fixture-less informational gates are intended to be promoted to
required when fixture-based metric deltas are available as follow-on work (see AC-2,
AC-5, AC-6 metric claims in `change-classification.md`).

## DPI Coordinate Regression

One regression was found and fixed during this change: `LayoutDetector.detect()` was
using pixmap pixel dimensions to denormalize region bboxes, which was correct at the
prior 72 DPI setting (1px ≈ 1pt) but broke at the new 150 DPI default. Fix: added
`page_width_pt`/`page_height_pt` parameters to `detect()` and updated `pdf_parser.py`
to pass `page.rect.width`/`page.rect.height`. Regression test added:
`TestDpiCoordinateBackMapping::test_element_type_correct_with_pt_params_at_high_dpi`
in `tests/test_layout_detector.py`.

## Style Fidelity Gap (Known, Non-Regression)

`_insert_text_in_rect` does not consume `element.style` (color/bold/italic). This was
also true pre-change — no visual style regression is introduced. The IR stores all
style fields correctly for future renderer wiring. Tracked as a follow-on in
`visual-review-report.md`.
