---
change-id: pdf-layout-refactor
schema-version: 0.1.0
last-changed: 2026-06-27
risk: high
tier: 1
---

# Test Plan: pdf-layout-refactor

## Acceptance Criteria → Test Mapping

| AC | criterion summary | test family | test file | test name(s) | tier |
|---|---|---|---|---|---|
| AC-1 | bbox-exact whitening; residual text = 0 | unit | tests/test_pdf_layout_refactor.py | test_bbox_whitening_uses_draw_rect; test_whitening_non_latin_no_bleed | 1 |
| AC-2 | paragraph aggregation; BIoU improves, truncation falls | integration | tests/test_pdf_layout_refactor.py | test_paragraph_aggregation_reduces_element_count | 1 |
| AC-3 | iterative scale-fit; min font ≥ 8pt; truncation → 0 | unit | tests/test_pdf_layout_refactor.py | test_scale_fit_stays_above_readable_floor; test_scale_fit_truncated_only_at_8pt_overflow | 1 |
| AC-4 | per-span StyleInfo (color/bold/italic/underline) re-applied | unit | tests/test_pdf_layout_refactor.py | test_span_color_preserved; test_span_bold_preserved; test_is_underline_backward_compat | 1 |
| AC-5 | column-aware reading-order model; edit distance ↓ | integration | tests/test_pdf_layout_refactor.py | test_reading_order_column_assignment_two_column | 1 |
| AC-6 | DPI 72→150 via PDF_RENDER_DPI; mAP improves | unit | tests/test_pdf_layout_refactor.py | test_pdf_render_dpi_matrix_scaling; test_high_dpi_pixel_dimensions | 1 |
| AC-7 | FORMULA pass-through untranslated; scanned→OCR routing | unit, resilience, data-boundary | tests/test_pdf_layout_refactor.py | test_formula_pass_through; test_formula_only_page_no_translation; test_scanned_ocr_routing_when_enabled; test_ocr_absent_no_crash | 1 |
| AC-8 | TATR unaffected; fitz→ReportLab fallback converges; CI without OCR library | resilience | tests/test_pdf_layout_refactor.py; tests/test_renderer_convergence.py | test_table_recognition_disabled_unaffected; test_fitz_reportlab_fallback_converges (existing, extend) | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 1 | pure-function seam tests; no real PDF I/O required for whitening, fit, style, DPI, formula |
| integration | 1 | tests/fixtures/test.pdf end-to-end: paragraph aggregation element count, two-column reading order |
| resilience | 1 | OCR library absent (lazy-import disabled), detector unavailable, fitz→ReportLab fallback |
| data-boundary | 1 | formula-only page, scanned/empty page text, high-DPI matrix dimension assertions |
| e2e | 1 | golden fixture regression; extend tests/test_golden_regression.py for AC-2/AC-4/AC-5 |

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | `pytest tests/test_pdf_layout_refactor.py tests/test_renderer_convergence.py tests/test_pdf_render_warnings.py tests/test_pdf_parser.py tests/test_layout_detector.py tests/test_layout_metrics.py -x -q --tb=short` | 1 | test-evidence.yml |
| contract | yes | cdd-kit validate --contracts | 1 | test-evidence.yml |
| full | final/CI | pytest -x -q --tb=short | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_layout_metrics.py — residual-text budget | extend | AC-1 must register 0 residual after whitening fix; re-baseline BIOU_REGRESSION_BUDGET |
| tests/test_layout_metrics.py — truncation-rate budget | extend | AC-3 drives truncation rate to 0; tighten budget floor |
| tests/test_golden_regression.py | extend | add before/after golden fixture entries for AC-2/AC-4/AC-5 render changes |
| tests/test_renderer_convergence.py | extend | add AC-8 TATR-disabled assertion; existing fallback coverage re-verified |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- TATR / table structure recognition (p3-table-structure, shipped; TABLE_RECOGNITION_ENABLED=false verified only).
- XLSX/DOCX/PPTX processor changes.
- LLM critique loop.
- Full visual golden-PDF pixel comparison (durable evidence in visual-review-report.md, not unit tests).

## Notes

- tests/test_pdf_layout_refactor.py is NEW; all AC-1..AC-8 new tests live exclusively in this file.
- AC-7 OCR tests must pass without the OCR library installed (OCR_ENABLED=False is the default; lazy-import seam).
- test_is_underline_backward_compat: StyleInfo.from_dict on a dict missing "is_underline" must default to False.
- DPI matrix unit test must mock fitz.Matrix; does not require a real PDF on disk.
- AC-8 fitz→ReportLab convergence is already in tests/test_renderer_convergence.py — extend, do not duplicate.
