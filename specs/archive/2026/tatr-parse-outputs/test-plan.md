---
change-id: tatr-parse-outputs
schema-version: 0.1.0
last-changed: 2026-06-27
risk: low
tier: 3
---

# Test Plan: tatr-parse-outputs

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 (row ordering by y-center) | unit | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_row_ordering_top_row_is_index_zero` | 0 |
| AC-1 (num_rows matches grid) | unit | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_num_rows_and_num_cols_match_grid` | 0 |
| AC-1,AC-2,AC-3 (2×3 happy path) | unit | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_2x3_grid_returns_six_cells` | 0 |
| AC-2 (col ordering by x-center) | unit | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_col_ordering_leftmost_col_is_index_zero` | 0 |
| AC-3 (cell assigned by overlap) | unit | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_cell_assigned_correct_row_col_by_overlap` | 0 |
| AC-4 (content="" on all cells) | unit | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_all_cells_have_empty_content` | 0 |
| AC-5 (CXCYWH → pixel conversion) | unit | `tests/test_table_recognizer.py::TestParseOutputsBoxFormat::test_cxcywh_normalized_converts_to_pixel_coords` | 0 |
| AC-5 (row sort uses pixel y-center) | unit | `tests/test_table_recognizer.py::TestParseOutputsBoxFormat::test_row_sort_uses_pixel_y_center` | 0 |
| AC-6 (no detections → empty safe) | data-boundary | `tests/test_table_recognizer.py::TestParseOutputsDegenerate::test_no_detections_above_threshold_returns_empty` | 0 |
| AC-6 (only cols, no rows → safe) | data-boundary | `tests/test_table_recognizer.py::TestParseOutputsDegenerate::test_zero_rows_only_cols_returns_empty` | 0 |
| AC-6 (only rows, no cols → safe) | data-boundary | `tests/test_table_recognizer.py::TestParseOutputsDegenerate::test_zero_cols_only_rows_returns_empty` | 0 |
| AC-6 (overlapping boxes → no crash) | data-boundary | `tests/test_table_recognizer.py::TestParseOutputsDegenerate::test_overlapping_bboxes_no_crash` | 0 |
| AC-7 (feature flag unchanged) | unit | existing `tests/test_table_recognizer.py::TestModelUnavailableFallback` — no new test needed | 0 |
| AC-8 (cell_id format, direct call) | unit | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_cell_id_format_includes_row_col` | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | All `_parse_outputs` tests; no ONNX session required |
| data-boundary | 0 | Degenerate numpy inputs; folded into same test file as unit tests |

## Entry-Point Enforcement Rule

Every test in `TestParseOutputsGrid`, `TestParseOutputsDegenerate`, and `TestParseOutputsBoxFormat` must call `recognizer._parse_outputs(mock_outputs, element_id)` directly on a bare `TableRecognizer()` instance. Calling `recognize()` or `_run_recognition()` is forbidden — those paths require a live ONNX session and constitute a wrong-entry-point tautology per CLAUDE.md.

## TATR Mock Output Shape

`mock_outputs` is `[logits, boxes]`: `logits` shape `(1, N, 7)` and `boxes` shape `(1, N, 4)` in normalized CXCYWH (0-1 range, relative to 768×768). Class indices: 1=column, 2=row, 5=spanning cell, 6=no-object. Filter: argmax ∈ {1, 2, 5} and score > 0.5.

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| None | — | No existing `_parse_outputs` tests exist; all rows above are new additions |

## Out of Scope

- `recognize()` / `_run_recognition()` paths (require real ONNX weights)
- Text extraction into cell content (separate pdf_parser concern)
- Translation of recognized cells (covered by existing `TestSameTableCellBatching`)
- Spanning-cell row/col-span assignment (no AC covers it; post-MVP)
- `TABLE_RECOGNITION_ENABLED` flag value (covered by existing `TestModelUnavailableFallback`)

## Notes

- All new tests extend `tests/test_table_recognizer.py`; do not create a separate file.
- Tests must be RED before implementation: the current stub always returns a hardcoded 1×1 cell, so any selection assertion (specific `row`/`col` on a 2×3 grid) fails immediately.
- `TestParseOutputsGrid` uses a canonical 2-row × 3-column layout with non-overlapping CXCYWH boxes at known positions so sort order is unambiguous.
- `TestParseOutputsBoxFormat` verifies pixel conversion independently with a 1-row × 1-column case using a known CXCYWH value.
