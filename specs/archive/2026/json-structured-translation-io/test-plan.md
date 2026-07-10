---
change-id: json-structured-translation-io
schema-version: 0.1.0
last-changed: 2026-07-10
risk: high
tier: 1
---

# Test Plan: json-structured-translation-io

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit (serialize) | tests/test_table_serialization.py::TestSerializeContentCellsOnly::test_47_content_cells_against_257_phantom_columns_no_grid_shape | 0 |
| AC-1 | integration | tests/test_table_context_translation.py::TestPhantomColumnRegression::test_xlsx_257_col_sheet_completes_without_fallback | 1 |
| AC-2 | unit (parse) | tests/test_table_serialization.py::TestParseCoordinateRemap::test_valid_reply_restores_translations_by_row_col | 0 |
| AC-2 | integration | tests/test_table_context_translation.py::TestJsonTableRoundTrip::test_row_neighbor_context_delivered_in_outgoing_payload | 1 |
| AC-3 | unit | tests/test_json_translation_body.py::TestBodyEnvelope::test_body_payload_sends_text_key_parses_translation_key | 0 |
| AC-3 | contract | tests/test_json_translation_body.py::TestBodyEnvelope::test_schema_rejects_missing_translation_key | 0 |
| AC-4 (table) | data-boundary | tests/test_table_context_translation.py::TestFallbackBehavior::test_unparseable_json_falls_back_to_per_cell_batch | 1 |
| AC-4 (body) | data-boundary | tests/test_json_translation_body.py::TestBodyFallback::test_unparseable_json_falls_back_to_translate_once | 1 |
| AC-4 (never-fail) | resilience | tests/test_json_translation_body.py::TestBodyFallback::test_job_completes_normally_on_corrupted_json | 1 |
| AC-5 (table) | resilience | tests/test_table_context_translation.py::TestFallbackLogging::test_fallback_emits_info_via_translatetool_logger | 1 |
| AC-5 (body) | resilience | tests/test_json_translation_body.py::TestBodyFallback::test_fallback_emits_info_via_translatetool_logger | 1 |
| AC-6 | unit | tests/test_table_recognizer.py::TestNumericPassthroughWiring (extend, no new test) | 0 |
| AC-6 | unit | tests/test_nontranslatable_segment_guard.py (extend, no new test) | 0 |
| AC-7 | integration | tests/test_table_context_translation.py::TestOneCallPerTableOffice + ::TestPdfTableCellSerialization (extend both) | 1 |
| AC-7 | unit | tests/test_json_translation_prompt.py::TestSharedBuilderConsumers::test_both_prompt_builders_delegate_to_shared_module | 0 |
| AC-8 | contract (non-pytest) | `cdd-kit validate --contracts` | 0 |

## Test Families Required

unit, contract, integration, data-boundary, resilience.
Not applicable: e2e (disproportionate for this fix — see change-classification.md §Required Tests), monkey, stress, soak (call volume explicitly out of scope).

| family | tier | notes |
|---|---|---|
| unit | 0 | serialize/parse coordinate shape, schema validators, shared prompt-builder phrasing pin, BR-82/BR-112 fallback-trigger selection logic in isolation |
| contract | 0 | data-shape wire-format conformance (request/response envelope, round-trip guarantee); body envelope schema; `cdd-kit validate --contracts` realizes AC-8 |
| integration | 1 | xlsx/pptx/docx/pdf-cell-batch → shared seam → parsed translations, asserted on the captured payload boundary passed to the mocked client transport, never on internal attributes |
| data-boundary | 1 | phantom-column shape (47 cells / 257 cols), missing-coordinate reject-whole-reply, extra-coordinate-ignored, corrupted/schema-invalid JSON, echoed-source (whole-grid vs single-cell) |
| resilience | 1 | job never fails on either path; INFO line reaches the `TranslateTool` logger (`record.name` filter) for every fallback trigger |

## New test files proposed
- `tests/test_json_translation_prompt.py` — shared instruction builder (BR-111): contains `Return: {"translation": <your translation>}`; does NOT contain `Reply ONLY with JSON` or `Output a JSON object with a single key`; the built user payload for a table/body call is NOT re-wrapped by `translate_once`'s "Translate the following text… Output only the translation" framing (regression pin for the existing `translation_service.py` L901-906 double-wrap); both `OllamaClient` and `OpenAICompatibleClient` expose the seam with matching signature (the Protocol no longer enforces it); a stub ignoring `response_format` still passes (not relied upon). Matches the contract's recorded pointer for BR-111 — no rename.
- `tests/test_json_translation_body.py` — body envelope (BR-112): `{"text":...}` out / `{"translation":...}` in; fallback on unparseable JSON, empty content, missing/wrong-typed key, `translation == text`; INFO log on fallback; BR-108 meta-refusal guard applied to both happy-path and fallback value. Matches the contract's recorded pointer for BR-112 — no rename.

## Extended (not new) test files
- `tests/test_table_serialization.py` — replace grid-shape assertions with coordinate-cell-list assertions (serialize: content-only cells, explicit row/col; parse: coordinate remap, reject-missing, ignore-extra, echoed-source-whole-grid).
- `tests/test_table_context_translation.py` — extend `TestFallbackBehavior`, `TestPromptBuilder`, `TestOneCallPerTableOffice`, `TestPdfTableCellSerialization`; add the phantom-column regression case (47 cells vs 257 reported columns) and fallback-logging assertions filtered on `record.name == "TranslateTool"`. All four office/PDF call sites are exercised via the existing in-memory helpers (`_make_docx_with_table`, `_make_xlsx_with_cells`, `_make_pptx_with_table`, direct `TableCell`/`TableStructure` construction) — no new binary fixture needed.
- `tests/test_nontranslatable_segment_guard.py` — add the BR-108-widened meta-refusal-inside-valid-JSON case: `{"translation": "I need more context to translate this"}` is schema-valid, non-echoed, and still must be caught.
- `tests/test_pdf_layout_table_fixes.py` — `_StubTableClient` (and `_FailingClient`) must gain the new seam method or the two PDF-path tests that reach it will break; fixture update only, no new test class.
- `tests/test_llm_client_protocol.py` — unmodified; `test_protocol_defines_five_methods` stays green.
- `tests/test_env_contract.py` — extend with `JSON_STRUCTURED_TRANSLATION_ENABLED` default-true row and flag-off legacy-byte-for-byte case, only if implementation-plan confirms the flag lands.

## Table call-site testability (AC-7)
All four office/PDF call sites are testable WITHOUT a real `.docx`/`.pptx`/`.pdf`/`.xlsx` file: `tests/test_table_context_translation.py` builds in-memory fixtures and constructs `TableCell`/`TableStructure` IR objects directly. `docs/TEST_DOC/*.docx` (untracked) is evidence for the separate nested-table follow-up only — do not wire it into pytest here.

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | `pytest --collect-only tests/test_table_serialization.py tests/test_json_translation_prompt.py tests/test_json_translation_body.py tests/test_nontranslatable_segment_guard.py` | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | `pytest tests/test_table_serialization.py tests/test_table_context_translation.py tests/test_json_translation_prompt.py tests/test_json_translation_body.py tests/test_nontranslatable_segment_guard.py tests/test_pdf_layout_table_fixes.py::TestFallbackBehavior tests/test_llm_client_protocol.py::TestProtocolDefinition::test_protocol_defines_five_methods` | 1 | test-evidence.yml |
| changed-area | yes | targeted set plus `tests/test_openai_compatible_client.py tests/test_ollama_client_dynamic_strategy.py tests/test_context_window_segments.py` (system-channel merge order must stay intact) | 1 | test-evidence.yml |
| contract | yes | `cdd-kit validate --contracts` | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | `pytest tests/` (project root, per CLAUDE.md) — run once at gate time | 1 | test-evidence.yml |

Never widen any phase to a `test_pdf_*` glob or QE/COMET files — both hard-error outside the `translate-tool` conda env / on an onnxruntime import-ordering quirk unrelated to this change; scope by explicit node-id only.

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_table_serialization.py (all `TestSerializeStructure`/parse-shape cases) | RETAIN + extend | Resolution A: the legacy pipe-grid `serialize()`/`parse()` are frozen, not deleted — they remain reachable when `JSON_STRUCTURED_TRANSLATION_ENABLED=0`, so their existing cases stay green unmodified. ADD coordinate-JSON cases for the new `serialize_json()`/`parse_json()`. Do NOT replace. |
| tests/test_env_contract.py | no behavior test | This file only asserts a variable is DECLARED in `env-contract.md`; it contains no `importlib.reload` and tests no runtime behavior (verified: `grep -c importlib.reload` returns 0). The flag's declaration test goes here; the flag's BEHAVIOR test (flag-OFF routes to the legacy path) belongs in `test_table_context_translation.py` / `test_json_translation_body.py` via `monkeypatch.setattr(config, "JSON_STRUCTURED_TRANSLATION_ENABLED", False)`. Consumers must therefore read `config.JSON_STRUCTURED_TRANSLATION_ENABLED` by attribute, never `from ... import` (which freezes the value at first import, as `translation_service.py:10` does for `CRITIQUE_LOOP_ENABLED`). |
| tests/test_table_context_translation.py::TestPromptBuilder, TestFallbackBehavior, TestPdfTableCellSerialization | update | prompt builder and fallback trigger now operate on JSON envelopes and the BR-111 seam, not the pipe-grid + `translate_once` framing |
| tests/test_pdf_layout_table_fixes.py::_StubTableClient / _FailingClient | update | must expose the new BR-111 seam method or PDF-path integration tests reaching it will break (design.md §Migration/Rollback) |
| tests/test_nontranslatable_segment_guard.py (BR-108 cases) | update | guard now also applies to the BR-112 JSON-parsed `translation` value, not only the plain-text reply |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope
- Critique-loop call volume (recorded scope decision, change-request §Non-goals).
- Residual double LibreOffice `.xls` conversion (carried over from doc-context-sampling-fix).
- Body-envelope batching / N-segment index batching (rejected alternative; change-request §Recorded scope decision).
- Nested-table collection in DOCX (tracked as the next change; orthogonal — JSON changes how cells are sent, not which are collected).
- No visual, monkey, fuzz, or stress/soak families — no UI surface, no call-volume concern in scope here.

## Notes
Every fallback/log assertion MUST filter `record.name == "TranslateTool"` (caplog attaches to root; a bare `caplog.at_level` check is a documented false-green tautology in this repo). Every payload assertion MUST read the mocked transport's captured request body, never `client.system_prompt` or another internal attribute. BR-82's echoed-source test MUST assert WHICH condition fired (whole-grid-unchanged vs single-cell-unchanged), never a changed-cell count.
