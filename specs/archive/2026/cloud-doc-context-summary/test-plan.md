---
change-id: cloud-doc-context-summary
schema-version: 0.1.0
last-changed: 2026-07-09
risk: medium
tier: 2
---

# Test Plan: cloud-doc-context-summary

Reference: `specs/changes/cloud-doc-context-summary/change-classification.md` (AC-1..AC-7),
`change-request.md` (guard/seam location), `contracts/business/business-rules.md` BR-109.
This plan does not restate those; it maps ACs to test files/names.

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_orchestrator_context_detection.py::test_cloud_active_client_used_for_summary_not_local_ollama | 0 |
| AC-1 | integration | tests/test_orchestrator_context_detection.py::test_cloud_summary_generated_without_local_ollama_present | 1 |
| AC-2 | integration | tests/test_orchestrator_context_detection.py::test_cloud_summary_injected_as_document_context_in_system_prompt | 1 |
| AC-3 | unit | tests/test_orchestrator_context_detection.py::test_context_detection_disabled_skips_cloud_summary | 0 |
| AC-3 | unit | tests/test_orchestrator_context_detection.py::test_qwen_context_flow_disabled_skips_cloud_summary | 0 |
| AC-4 | unit | tests/test_orchestrator_context_detection.py::test_translation_dedicated_cloud_client_skips_summary | 0 |
| AC-5 | unit | tests/test_orchestrator_context_detection.py::test_detect_document_context_returns_empty_on_cloud_call_exception | 0 |
| AC-5 | resilience | tests/test_orchestrator_context_detection.py::test_job_continues_with_no_preamble_when_cloud_summary_empty | 1 |
| AC-6 | integration | tests/test_orchestrator_context_detection.py::test_local_ollama_context_detection_unchanged | 1 |
| AC-7 | contract | tests/test_orchestrator_context_detection.py::test_no_scope_creep_into_injection_wiring_or_json_io | 1 |
| AC-7 | regression | tests/test_translation_strategy.py (unmodified, must stay green) | 0 |
| AC-7 | regression | tests/test_context_prompt_i18n.py (unmodified except its own Test Update Contract entry below) | 0 |

## Test Families Required

Mark all that apply: unit / contract / integration / resilience / e2e (manual)

| family | tier | notes |
|---|---|---|
| unit | 0 | Guard/flag logic and `_detect_document_context` called directly against a fake cloud-client double (full protocol shape, no network, no torch). |
| integration | 1 | `process_files()` end-to-end; cloud client resolved via mocked `load_providers_config`; LLM call mocked at `requests.Session.post` (client/network boundary, not an internal method) — mirrors `tests/test_provider_fallback.py::TestOrchestratorProviderWiring`. |
| contract | 1 | AC-3/AC-4/AC-5/AC-7 unit assertions together encode BR-109's decision table (both flags AND-gated, dedicated-client skip, graceful failure, unchanged injection wiring); no separate contract-only file. |
| resilience | 1 | Cloud summary call raises/returns empty → job completes normally (`stopped=False`), no preamble, no exception escapes `process_files`. |
| e2e | manual | Real-PANJIT 8D-PDF re-run (change-request "Observable success criterion") — not an automated gate. |

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
| tests/test_context_prompt_i18n.py::test_immediate_and_deferred_use_same_template | update | Mocks Ollama-only `_build_no_system_payload`/`_call_ollama` directly on a bare `MagicMock()` client; `_detect_document_context` must route the summary call through a method BOTH `OllamaClient` and `OpenAICompatibleClient` implement (BR-109) — update the mocked call target to match. |
| tests/test_provider_fallback.py::TestOrchestratorProviderWiring::test_cloud_client_used_when_provider_id_set | update | Currently force-patches `CONTEXT_DETECTION_ENABLED=False` specifically because context detection "calls OllamaClient internals not available on cloud clients" — that rationale is the bug this change fixes; revisit whether the isolation patch stays (scope) or the test must account for the new extra `requests.Session.post` call the cloud client makes for the summary. |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope
- JSON structured translation I/O (Step 3 of the realignment) — no coverage here.
- Re-testing `build_strategy`'s "Document context:" injection logic itself — already unit-tested in `tests/test_translation_strategy.py`; this plan only proves the cloud path *feeds* that existing wiring.
- DeepSeek-specific network fixtures — one representative cloud provider config ("panjit") suffices; provider selection/fallback is `test_provider_fallback.py`'s scope, unchanged here.
- Load/soak/stress — one extra summary call per document is not a soak profile (change-classification).

## Notes
- Mock boundary: `requests.Session.post` for integration/AC-1/AC-2/AC-6 (network); `app.backend.processors.orchestrator._detect_document_context` (same-module attribute — call site is unqualified) for AC-3/AC-4/AC-5 unit guard tests, with call-count assertions, not just happy path.
- Seam risk: `_detect_document_context` today calls Ollama-only private methods not implemented by `OpenAICompatibleClient` — removing the guard alone is insufficient; verify the real shared call path against live source before wiring fakes (do not assume `translate_once` without checking).
- `tests/test_orchestrator_phase0.py::_make_mock_ollama_client` exercises only the local-Ollama path (`provider_id` unset) — lower risk, but re-verify after the guard/call-site edit since it shares the same call site.
- No torch/COMET dependency anywhere in this plan — all clients are mocked/faked; runs under base `pytest`.
