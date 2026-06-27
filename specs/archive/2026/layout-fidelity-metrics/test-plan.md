---
change-id: layout-fidelity-metrics
schema-version: 0.1.0
last-changed: 2026-06-27
risk: low
tier: 0
---

# Test Plan: layout-fidelity-metrics

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_layout_metrics.py::TestBIoU::test_identical_bboxes_return_1 | 0 |
| AC-1 | unit | tests/test_layout_metrics.py::TestBIoU::test_disjoint_bboxes_return_0 | 0 |
| AC-1 | unit | tests/test_layout_metrics.py::TestBIoU::test_partial_overlap_value_and_matched_pair | 0 |
| AC-1 | unit | tests/test_layout_metrics.py::TestBIoU::test_return_type_is_float_in_unit_interval | 0 |
| AC-2 | data-boundary | tests/test_layout_metrics.py::TestBIoUDegenerate::test_empty_source_list | 0 |
| AC-2 | data-boundary | tests/test_layout_metrics.py::TestBIoUDegenerate::test_empty_rendered_list | 0 |
| AC-2 | data-boundary | tests/test_layout_metrics.py::TestBIoUDegenerate::test_zero_area_source_box | 0 |
| AC-2 | data-boundary | tests/test_layout_metrics.py::TestBIoUDegenerate::test_zero_area_rendered_box | 0 |
| AC-3 | unit | tests/test_layout_metrics.py::TestResidualText::test_clean_page_returns_empty_list | 0 |
| AC-3 | unit | tests/test_layout_metrics.py::TestResidualText::test_leaking_text_flagged_with_region_record | 0 |
| AC-3 | unit | tests/test_layout_metrics.py::TestResidualText::test_record_contains_bbox_and_text_fields | 0 |
| AC-4 | unit | tests/test_layout_metrics.py::TestTruncationRate::test_all_truncated_ratio_is_1 | 0 |
| AC-4 | unit | tests/test_layout_metrics.py::TestTruncationRate::test_none_truncated_ratio_is_0 | 0 |
| AC-4 | unit | tests/test_layout_metrics.py::TestTruncationRate::test_partial_truncated_ratio_and_overflow_area | 0 |
| AC-4 | data-boundary | tests/test_layout_metrics.py::TestTruncationRate::test_elements_with_none_bbox_excluded_from_overflow | 0 |
| AC-5 | unit | tests/test_layout_metrics.py::TestGoldenFixture::test_fixture_file_exists_and_is_valid_pdf | 0 |
| AC-5 | unit | tests/test_layout_metrics.py::TestGoldenFixture::test_fixture_is_exactly_one_page | 0 |
| AC-6 | unit | tests/test_layout_metrics.py::TestBIoU::test_partial_overlap_value_and_matched_pair | 0 |
| AC-7 | unit | tests/test_layout_metrics.py::TestModuleImports::test_biou_importable_from_tests_metrics | 0 |
| AC-7 | unit | tests/test_layout_metrics.py::TestModuleImports::test_residual_text_importable_from_tests_metrics | 0 |
| AC-7 | unit | tests/test_layout_metrics.py::TestModuleImports::test_truncation_rate_importable_from_tests_metrics | 0 |
| AC-7 | unit | tests/test_layout_metrics.py::TestModuleImports::test_no_app_backend_files_modified | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Direct calls to `compute_biou`, `check_residual_text`, `compute_truncation_rate` with known numeric inputs and verified outputs |
| data-boundary | 0 | Empty lists, zero-area boxes, `None` bbox on elements — each must return a defined value with no exception raised |

## Anti-Tautology Note (AC-6)

`test_partial_overlap_value_and_matched_pair` must assert the **identity** of which source index matched which rendered index, not only the scalar mean. Asserting only the float output is a selection-tautology — the same value can be produced by mismatched pairs.

## Fixture Path Convention (AC-5, AC-7)

All test code that resolves `tests/fixtures/golden/simple_test.pdf` must derive the repo root via `Path(__file__).parent.parent`, never a hardcoded absolute path.

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| full | final/CI | pytest | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| (none) | — | No existing tests modified; all are new |

## Out of Scope

- Integration with live orchestrator / processor pipeline
- PyMuPDF real-PDF I/O in unit tests (stub the `page` argument)
- Performance or stress testing of metric functions
- Frontend changes
- Any `app/backend/` or `app/frontend/` modification

## Notes

- `tests/metrics/__init__.py` must exist for import assertions (AC-7) to pass.
- `simple_test.pdf` must be a **committed binary** — not generated at test runtime — so its hash is stable across CI runners.
- Bounded run command: `pytest tests/test_layout_metrics.py` (Tier 0, target < 30 s).
