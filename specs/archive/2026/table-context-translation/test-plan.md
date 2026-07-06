---
change-id: table-context-translation
schema-version: 0.1.0
last-changed: 2026-06-27
risk: medium
tier: 2
---

# Test Plan: table-context-translation

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 (one LLM call per table — DOCX) | unit | tests/test_table_context_translation.py::test_single_llm_call_per_table_docx | 0 |
| AC-1 (one LLM call per table — XLSX) | unit | tests/test_table_context_translation.py::test_single_llm_call_per_table_xlsx | 0 |
| AC-1 (one LLM call per table — PPTX) | unit | tests/test_table_context_translation.py::test_single_llm_call_per_table_pptx | 0 |
| AC-1 (all-numeric table — zero calls) | unit | tests/test_table_context_translation.py::test_all_numeric_table_makes_no_llm_call | 0 |
| AC-2 (instruction before serialized grid) | unit | tests/test_table_context_translation.py::test_instruction_precedes_serialized_grid_in_prompt | 0 |
| AC-3 (same text, different col → separate translations) | unit | tests/test_table_context_translation.py::test_same_text_different_cols_get_separate_translations | 0 |
| AC-3 (non-table segments use col=None key) | unit | tests/test_table_context_translation.py::test_non_table_segments_use_col_none_dedup_key | 0 |
| AC-4 (header row/col inline with body in grid) | unit | tests/test_table_serialization.py::test_serialized_grid_row0_and_col0_inline_with_body | 0 |
| AC-5 (PDF TableCell row/col drives serialization) | integration | tests/test_table_context_translation.py::test_pdf_tablecell_row_col_drives_serialization | 1 |
| AC-6 (non-table paragraph path unaffected) | unit | tests/test_translation_service.py::test_non_table_paragraph_translation_unaffected | 0 |
| AC-6 (paragraph tmap key unchanged — col=None) | unit | tests/test_translation_service.py::test_paragraph_tmap_key_col_none | 0 |
| AC-7 (no API surface change) | contract | contracts/api/api-contract.md — enforced by cdd-kit validate gate | 0 |
| AC-8 (row-count mismatch → None / fallback) | resilience | tests/test_table_serialization.py::test_parse_returns_none_on_row_count_mismatch | 0 |
| AC-8 (col-count mismatch → None / fallback) | resilience | tests/test_table_serialization.py::test_parse_returns_none_on_col_count_mismatch | 0 |
| AC-8 (no pipe delimiters → None / fallback) | resilience | tests/test_table_serialization.py::test_parse_returns_none_when_no_pipe_delimiters | 0 |
| AC-8 (fallback restores full per-cell mapping) | resilience | tests/test_table_context_translation.py::test_fallback_per_cell_batch_preserves_all_cell_mapping | 0 |
| BR-68/BR-69 (numeric passthrough + batch coalescing) | contract | tests/test_table_context_translation.py::test_numeric_cells_excluded_from_batch_and_passthrough | 0 |
| data-boundary round-trip | data-boundary | tests/test_table_serialization.py::test_serialize_parse_round_trip_preserves_row_col_positions | 0 |
| serializer pipe-escape + newline sanitization | unit | tests/test_table_serialization.py::test_serialize_escapes_pipe_chars_and_collapses_newlines | 0 |
| serializer drops markdown separator line | unit | tests/test_table_serialization.py::test_parse_drops_markdown_separator_line | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Serializer pure functions; dedup-key differentiation; prompt-builder instruction ordering; per-format processor grouping; all mocked at LLM boundary |
| data-boundary | 0 | `serialize()` → mock-translate → `parse()` round-trip; (row,col) positions survive intact for every cell |
| resilience | 0 | `parse()` returns `None` on each shape-mismatch variant; caller falls back to per-cell SEG batch without cell corruption |
| integration | 1 | PDF `translation_service` cell-batch path wired to shared serializer using real `TableCell` IR fields |
| contract | 0 | BR-68/BR-69 numeric passthrough + batch coalescing; AC-7 enforced by `cdd-kit validate --contracts` gate |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_table_recognizer.py | extend (do not duplicate) | BR-68/BR-69 batch-coalescing tests already cover numeric passthrough at cell level; new tests cover the serializer path layered on top |

## Out of Scope

- AC-7 API drift: covered by `cdd-kit validate --contracts` gate; no test function required.
- Visual or rendered table output correctness: existing renderer tests unchanged.
- DOCX/XLSX/PPTX native table parsing accuracy: upstream parser; not changed by this track.
- `output_mode` (replace/append) interaction with table cells: Track F (Wave 3).
- LLM translation quality or semantic correctness of table output.

## Notes

AC-4 is provably satisfied by whole-table serialization: row 0 and col 0 co-occur inline with every body cell in the same Markdown string; the unit test on `test_table_serialization.py` verifies structure, not LLM semantics.
AC-7 requires no test function — the `cdd-kit validate --contracts` Tier 0 gate checks for undeclared endpoint changes mechanically.
All mocks must target LLM client boundary (`ollama_client` / `openai_compatible_client`) using collection-time `patch.object` per CLAUDE.md tautology prevention rule.
`tests/test_translation_service.py` is a new file; it proves non-regression by calling the non-table path directly (not via `translate_document()`) to avoid wrong-entry-point tautology.
