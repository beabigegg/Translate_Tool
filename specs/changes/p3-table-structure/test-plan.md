---
change-id: p3-table-structure
schema-version: 0.1.0
last-changed: 2026-06-22
risk: medium
tier: 2
---

# Test Plan: p3-table-structure

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_table_recognizer.py::TestTableStructureIRShape | 0 |
| AC-1 | contract | tests/test_table_recognizer.py::TestTableStructureRoundTrip | 0 |
| AC-2 | integration | tests/test_table_recognizer.py::TestCellGranularityTranslation | 1 |
| AC-3 | unit | tests/test_table_recognizer.py::TestNumericPassthrough | 0 |
| AC-3 | integration | tests/test_table_recognizer.py::TestNumericPassthroughWiring | 1 |
| AC-4 | integration | tests/test_table_recognizer.py::TestSameTableCellBatching | 1 |
| AC-5 | data-boundary | tests/test_table_recognizer.py::TestModelUnavailableFallback | 1 |
| AC-6 | data-boundary | tests/test_table_recognizer.py::TestDegenerateTableHandling | 1 |

## Test Names (one per line)

**File: `tests/test_table_recognizer.py`** (new file — must be created before implementation)

### Unit: TableStructure IR shape (AC-1)
- `TestTableStructureIRShape::test_table_cell_id_format`
- `TestTableStructureIRShape::test_table_structure_fields_present`
- `TestTableStructureIRShape::test_table_structure_attached_in_metadata`
- `TestTableStructureIRShape::test_table_element_without_structure_is_plain_region`

### Unit: is_numeric_cell predicate (AC-3)
- `TestNumericPassthrough::test_numeric_predicate_boundaries`
- `TestNumericPassthrough::test_digit_only_cell_is_numeric`
- `TestNumericPassthrough::test_text_cell_is_not_numeric`
- `TestNumericPassthrough::test_mixed_digit_separator_cell_is_numeric`
- `TestNumericPassthrough::test_empty_cell_is_not_numeric`

### Contract: TableStructure IR round-trip (AC-1)
- `TestTableStructureRoundTrip::test_table_structure_round_trip`
- `TestTableStructureRoundTrip::test_old_format_ir_no_table_structure`

### Integration: cell-batch wiring — WHICH cells enter the batch (AC-4)
- `TestSameTableCellBatching::test_single_batch_per_table`
- `TestSameTableCellBatching::test_separate_batches_for_separate_tables`
- `TestSameTableCellBatching::test_batch_payload_contains_text_cells_not_numeric`

### Integration: no flattened translation when structure available (AC-2)
- `TestCellGranularityTranslation::test_no_flattened_translation_when_structure_available`
- `TestCellGranularityTranslation::test_cell_batch_failure_applies_placeholder`

### Integration: numeric passthrough wiring — identity check (AC-3)
- `TestNumericPassthroughWiring::test_numeric_cell_not_sent_to_llm`
- `TestNumericPassthroughWiring::test_numeric_cell_content_identical_pre_post_translation`

### Data-boundary: model unavailable (AC-5)
- `TestModelUnavailableFallback::test_table_recognizer_unavailable_falls_back`
- `TestModelUnavailableFallback::test_table_recognizer_load_error_falls_back`

### Data-boundary: degenerate tables (AC-6)
- `TestDegenerateTableHandling::test_all_numeric_table_no_llm_call`
- `TestDegenerateTableHandling::test_all_empty_cells_no_llm_call`
- `TestDegenerateTableHandling::test_merged_cells_treated_as_single_cell`

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | `is_numeric_cell` predicate, `TableStructure` / `TableCell` field shape, metadata attachment |
| contract | 0 | `TableStructure` to_dict/from_dict round-trip; old-format IR backward-compat |
| integration | 1 | cell-batch wiring: WHICH cells sent, WHICH excluded; no-flatten invariant; placeholder on batch failure |
| data-boundary | 1 | model absent/load-error fallback (mirrors layout_detector); all-numeric / all-empty / merged-cell degenerate tables |

## Anti-Tautology Rules

**AC-3 (numeric passthrough):** Tests MUST assert that the LLM call was NOT made AND that `translated_content == content` exactly. A count-only assertion (`assert mock.call_count == 0`) is insufficient — also assert the specific cell's `translated_content` value. Use `patch.object` on a collection-time module reference for the LLM client, not on the translation_service wrapper, to avoid wrong-entry-point tautology.

**AC-4 (cell batching):** Tests MUST assert WHICH cells are in the batch payload (the actual `content` strings of the text cells), not just that one call was made. Tests MUST separately assert that numeric cells are absent from the payload by inspecting the call arguments. Use `patch.object` targeting `translation_service` at the LLM-client boundary, capturing the call arguments for inspection.

**AC-2 (no flattened translation):** Test must call through the cell-batch seam directly (not through `translate_document()` which may not be wired) and assert that the `table` element's `TranslatableElement.translated_content` is populated from cell-level results, not from a flattened single call.

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_translatable_document.py | extend | Add `test_table_structure_round_trip` and `test_old_format_ir_no_table_structure` if not placed in test_table_recognizer.py |

## Out of Scope

- DOCX/PPTX native table translation (CER-001 deferred; PDF-only in p3)
- UI/rendering of recognized table cells (no UI surface touched)
- QE scoring of individual cells (parent `table` element is the QE surface)
- Stress/soak tests (cell-batch coalesces to single LLM call per table; reduces load)
- E2E tests against a live ML model (model is mocked at the ONNX/weights boundary)

## Notes

- All LLM calls mocked at the `onnxruntime.InferenceSession` or translation-client boundary using `patch.object` with collection-time module reference (see CLAUDE.md promoted learnings on mock.patch target binding).
- Model unavailable tests mirror `TestMissingModelFallsBackToHeuristic` in `tests/test_layout_detector.py` — assert WARNING logged AND fallback behavior (no `TableStructure` attached).
- `test_old_format_ir_no_table_structure` must assert `from_dict()` does not raise when `metadata["table_structure"]` is absent.
- All new tests must be RED before `table_recognizer.py` is implemented.
