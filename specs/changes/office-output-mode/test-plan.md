---
change-id: office-output-mode
schema-version: 0.1.0
last-changed: 2026-06-27
risk: medium
tier: 1
---

# Test Plan: office-output-mode

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 (schema enum) | unit | tests/test_output_mode_api.py::test_output_mode_enum_accepts_bilingual | 1 |
| AC-1 (API form field) | contract | tests/test_output_mode_api.py::test_post_jobs_accepts_output_mode_bilingual | 1 |
| AC-1 (openapi) | contract | tests/test_output_mode_api.py::test_openapi_bilingual_in_output_mode_enum | 1 |
| AC-2 (DOCX bilingual table structure) | unit | tests/test_output_mode_processors.py::test_bilingual_docx_produces_two_column_table | 1 |
| AC-2 (DOCX bilingual cell placement) | unit | tests/test_output_mode_processors.py::test_bilingual_docx_source_col_a_translation_col_b_not_same_run | 1 |
| AC-2 (data-boundary: empty para) | data-boundary | tests/test_output_mode_processors.py::test_bilingual_docx_empty_paragraph_passthrough | 1 |
| AC-3 (XLSX adjacent) | unit + data-boundary | tests/test_output_mode_processors.py::test_xlsx_adjacent_translation_at_shifted_column_source_unchanged_no_wrap | 1 |
| AC-4 (XLSX annotation: comment + idempotent) | unit + data-boundary | tests/test_output_mode_processors.py::test_xlsx_annotation_attaches_comment_source_unchanged | 1 |
| AC-4 (pre-existing comment preserved) | data-boundary | tests/test_output_mode_processors.py::test_xlsx_annotation_idempotent_existing_comment_preserved | 1 |
| AC-5 (XLSX replace: no stack, no wrap) | unit + data-boundary | tests/test_output_mode_processors.py::test_xlsx_replace_overwrites_no_stack_no_wrap_text | 1 |
| AC-6 (DOCX SDT replace) | unit | tests/test_output_mode_processors.py::test_docx_sdt_replace_overwrites_source | 1 |
| AC-6 (DOCX para-in-cell replace) | unit | tests/test_output_mode_processors.py::test_docx_para_in_cell_replace_overwrites_source | 1 |
| AC-6 (DOCX text-box replace) | unit | tests/test_output_mode_processors.py::test_docx_textbox_replace_overwrites_source | 1 |
| AC-7 (PPTX SmartArt replace) | unit | tests/test_output_mode_processors.py::test_pptx_smartart_replace_text_not_appended | 1 |
| AC-8 (regression) | regression | tests/test_output_mode_processors.py (existing tests) | 1 |
| integration: XLSX output_mode routing | integration | tests/test_output_mode_orchestrator.py::test_orchestrator_threads_output_mode_to_translate_xlsx | 1 |
| integration: bilingual degrade + warning | integration | tests/test_output_mode_orchestrator.py::test_orchestrator_degrades_bilingual_to_append_for_non_docx_with_warning | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 1 | Call processors directly (`translate_xlsx_xls`, `_update_smartart_texts`, `translate_docx` write-back); assert structure (column index, cell value, table column count) — not just presence counts |
| data-boundary | 1 | Empty source para (bilingual passthrough), pre-existing user comment (annotation idempotency), no `wrap_text` on XLSX replace/adjacent |
| contract | 1 | `OutputMode` enum accepts `bilingual`; HTTP 422 on unknown value; `openapi.yml` enum list contains `bilingual`; collection-time module capture per CLAUDE.md |
| integration | 1 | Call `process_files()` directly (not `translate_document()`); mock at `orchestrator.translate_xlsx_xls` (consumer-bound); assert `call_args.kwargs["output_mode"]` value and `warnings` list |
| regression | 1 | All pre-existing tests in the three test files must pass unchanged |

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_output_mode_api.py::test_post_jobs_rejects_invalid_output_mode_422 | extend | confirm `bilingual` is NOT treated as invalid (it is now valid) |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope
- E2E with live LLM calls
- PDF output mode (no change in this track)
- XLS-to-XLSX LibreOffice/COM conversion path (unchanged)
- Frontend / UI changes
- DOCX header/footer COM path (Windows-only, not in scope)
- Stress, soak, fuzz tests

## Notes
- AC-2: assert `len(table.columns) == 2` and source text in `cells[0]`, translation in `cells[1]`; prove they are NOT concatenated in the same run (anti-tautology).
- AC-3/4/5: call `translate_xlsx_xls()` directly; mock `app.backend.processors.xlsx_processor.translate_texts`; assert column index, `cell.comment`, and `cell.alignment.wrap_text` respectively.
- AC-6: build DOCX fixtures with SDT / table-cell / text-box programmatically; assert the specific XML node's text equals translation and source is absent from that node.
- AC-7: call `_update_smartart_texts()` directly; assert `<a:t>` text equals translation only — no `\n(...)` appended suffix.
- Integration: assert `call_args.kwargs["output_mode"] == "append"` for XLSX/PPTX when input is `"bilingual"`; assert `warnings` list is non-empty for the degradation case.
