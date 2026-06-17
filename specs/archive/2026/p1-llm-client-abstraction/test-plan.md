---
change-id: p1-llm-client-abstraction
schema-version: 0.1.0
last-changed: 2026-06-17
risk: medium
tier: 3
---

# Test Plan: p1-llm-client-abstraction

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1: base_llm_client.py defines LLMClient Protocol with exactly 6 methods | unit | tests/test_llm_client_protocol.py::test_protocol_defines_six_methods | 0 |
| AC-1: all 6 method signatures match design.md table | contract | tests/test_llm_client_protocol.py::test_protocol_method_signatures | 0 |
| AC-2: OllamaClient is a structural subtype of LLMClient | contract | tests/test_llm_client_protocol.py::test_ollama_client_satisfies_protocol | 0 |
| AC-2: runtime_checkable isinstance check passes | contract | tests/test_llm_client_protocol.py::test_ollama_client_isinstance_llm_client | 0 |
| AC-3: translation_service.py contains zero calls to _build_no_system_payload | unit | tests/test_llm_client_protocol.py::test_translation_service_no_private_payload_call | 0 |
| AC-3: translation_service.py contains zero calls to _call_ollama | unit | tests/test_llm_client_protocol.py::test_translation_service_no_private_ollama_call | 0 |
| AC-4: frozen public OllamaClient methods still present post-refactor | contract | tests/test_llm_client_protocol.py::test_ollama_client_frozen_public_api_intact | 0 |
| AC-4: new Protocol alias methods (health, list_models, unload) delegate correctly | unit | tests/test_llm_client_protocol.py::test_ollama_client_alias_methods_delegate | 0 |
| AC-5: existing dynamic-strategy tests pass unchanged | regression | tests/test_ollama_client_dynamic_strategy.py | 1 |
| AC-5: existing translation-strategy tests pass unchanged | regression | tests/test_translation_strategy.py | 1 |
| AC-5: HY-MT quality-refinement tests pass unchanged (context-detection parity guard) | regression | tests/test_hy_mt_quality_refinement.py | 1 |
| AC-5: existing translation-profiles tests pass unchanged | regression | tests/test_translation_profiles_scenarios.py | 1 |
| AC-5: existing model-router tests pass unchanged | regression | tests/test_model_router.py | 1 |
| AC-5: translation_service uses Protocol surface for context-detection block | integration | tests/test_llm_client_protocol.py::test_context_detection_uses_public_method | 1 |
| AC-6: base_llm_client.py imports only stdlib typing | unit | tests/test_llm_client_protocol.py::test_base_module_stdlib_only | 0 |
| AC-7: no governed contract file is modified | unit | tests/test_llm_client_protocol.py::test_no_governed_contract_modified | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Structural/source-grep assertions (ast or re.search on source file); no network; < 5 s |
| contract | 0 | Protocol conformance via `runtime_checkable` + `inspect.signature`; no mocks |
| regression | 1 | Five existing test files run unmodified; must pass with zero assertion edits |
| integration | 1 | Mock only at HTTP boundary; verify translation_service drives context-detection via Protocol method |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| (none) | — | All five regression files must pass with zero assertion edits per AC-5 |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- E2E tests — no route or schema change
- Stress / soak / monkey — structural refactor, no load surface
- Frontend tests — AC-7 forbids any frontend modification
- Data-boundary tests — no data or env change
- Visual / UI tests — no UI
- Property-based tests for translation helpers — existing suite is behavior-complete for this refactor

## Notes

- `tests/test_llm_client_protocol.py` is the only new test file; all tests in it must fail before implementation and pass after.
- AC-3 source-grep tests open `translation_service.py` as text and use `re.search`; no import of the module is required.
- `test_hy_mt_quality_refinement.py` is the primary regression guard for the deferred-context-detection rewrite risk (design.md Open Risks §1).
- The `_is_translation_dedicated()` removal risk (design.md Open Risks §2) is covered by the existing dynamic-strategy and profiles regression files passing unchanged.
