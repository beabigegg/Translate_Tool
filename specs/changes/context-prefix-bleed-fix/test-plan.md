---
change-id: context-prefix-bleed-fix
schema-version: 0.1.0
last-changed: 2026-07-08
risk: medium
tier: 2
---

# Test Plan: context-prefix-bleed-fix

Reference: `specs/changes/context-prefix-bleed-fix/change-classification.md` (AC-1..AC-7),
`design.md` (Decision (b), the `translate_once(system_context=...)` seam, "Test doubles
to update" section). This plan does not restate those; it maps ACs to test files/names.

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_context_prefix_bleed.py::test_build_context_prefix_returns_system_channel_block_no_user_glue | 0 |
| AC-1 | unit | tests/test_context_prefix_bleed.py::test_translate_merged_paragraphs_user_payload_excludes_neighbor_segments | 0 |
| AC-2 | integration | tests/test_context_prefix_bleed.py::test_fake_client_no_bleed_returns_only_target_segment_8d_fixture | 1 |
| AC-3 | integration | tests/test_context_prefix_bleed.py::test_fake_client_no_bleed_returns_only_target_segment_8d_fixture (RED pre-fix / GREEN post-fix; same node per bug-fix-lane repro/regression rule) | 1 |
| AC-4 | integration | tests/test_context_prefix_bleed.py::test_neighbor_text_appears_only_in_system_context_never_in_translated_output | 1 |
| AC-4 | contract | tests/test_openai_compatible_client.py::TestSystemContextChannel::test_system_context_prepended_as_leading_system_message (new) | 1 |
| AC-4 | contract | tests/test_ollama_client_dynamic_strategy.py::test_system_context_merged_into_system_field (new) | 1 |
| AC-5 | contract | tests/test_context_prefix_bleed.py::test_br78_context_delivered_out_of_band_not_in_translatable_payload | 1 |
| AC-6 | unit | tests/test_context_prefix_bleed.py::test_context_window_segments_and_max_chars_constants_unchanged | 0 |
| AC-7 | contract | tests/test_llm_client_protocol.py::TestProtocolDefinition::test_protocol_method_signatures (updated: append `system_context` to expected params list) | 0 |
| AC-7 | regression | tests/test_context_window_segments.py (updated: `test_prompt_payload_contains_neighbor_text_at_call_boundary`, `test_context_prefix_header_not_present_in_translated_output` move payload assertions from `prompt` to `system`) | 0 |
| AC-7 | regression | tests/test_context_prompt_i18n.py, tests/test_fewshot_glossary.py, tests/test_openai_compatible_client.py (existing classes), tests/test_ollama_client_dynamic_strategy.py (existing 3 tests) stay green unmodified | 0 |

## Test Families Required

Mark all that apply: unit / contract / integration

| family | tier | notes |
|---|---|---|
| unit | 0 | `build_context_prefix` (pure, no app.backend imports) and `translate_merged_paragraphs` assembly with a stub `LLMClient`; assert the exact string handed to `translate_once` as `text=` excludes verbatim neighbor segments — selection assertion (WHICH text), not a length/count check. |
| integration | 1 | fake `LLMClient.translate_once(self, text, tgt, src_lang, cancel_event=None, system_context=None)` that transforms/echoes exactly the `text` it receives and separately records `system_context`; driven through `translate_merged_paragraphs` with the real 8D 3-point fixture strings from change-request.md. Mock boundary = the `LLMClient` Protocol seam (not HTTP) — the bug is prompt-assembly, not transport; the fake stands in for PANJIT/DeepSeek's "translate literally what's in the user message" behavior. |
| contract | 0/1 | `LLMClient` Protocol signature gains `system_context` (Tier 0, source-only) + per-client wire-format placement: OpenAI leading `role:"system"` message, Ollama merged `system` field (Tier 1, mocks each client's own HTTP boundary — `requests.post` / `_call_ollama` — never an internal method). |

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
| tests/test_llm_client_protocol.py::TestProtocolDefinition::test_protocol_method_signatures | update | `translate_once` gains additive `system_context` kwarg (design.md Decision (b)); hard-asserted exact params list must include it (AC-7). |
| tests/test_context_window_segments.py::test_prompt_payload_contains_neighbor_text_at_call_boundary | update | context is no longer glued into the `prompt` field; assertion moves to the `system` payload field (AC-1, AC-4). |
| tests/test_context_window_segments.py::test_context_prefix_header_not_present_in_translated_output | update | same relocation — header now lives in `system`, never concatenated into the translatable text (AC-1, AC-4). |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope
- Office (docx/pptx/xlsx) output-mode tests, judge, QE/COMET, layout-detection tests — untouched by this change.
- `_detect_document_context` cloud doc-summary enablement and JSON structured `{"text":…}`→`{"translation":…}` I/O — steps 2/3 of the realignment, separate changes.
- `pdf_processor`'s direct `translate_once` call sites (CER-001, still pending/out of scope) — `tests/test_pdf_layout_table_fixes.py`'s fake stays untouched per design.md.
- Live-LLM E2E against real PANJIT/DeepSeek endpoints — the fake-client integration test is the load-bearing no-bleed proof; no network test needed.

## Notes
- New file `tests/test_context_prefix_bleed.py` is torch-free; run standalone (base interpreter) for the RED/GREEN repro. Full ladder (incl. any QE-adjacent collection) runs under `conda run -n translate-tool` per CLAUDE.md.
- Anti-tautology: the integration test asserts WHICH text is in the user payload vs the `system_context` capture — asserting only "translation succeeded" or counting segments would pass even with the bug present.
- `test_llm_client_protocol.py::test_protocol_method_signatures` currently hard-asserts the exact 5-param list; updating it in this change is required (additive-kwarg break, CLAUDE.md promoted learning), not optional cleanup.
