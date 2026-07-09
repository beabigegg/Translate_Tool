---
change-id: cloud-base-system-prompt-drop
schema-version: 0.1.0
last-changed: 2026-07-09
risk: medium
tier: 2
---

# Test Plan: cloud-base-system-prompt-drop

Fix exercised through the real production seam: `process_files()` →
`build_strategy()` → `client.translate_once()`. Reasons: (1) it is the actual
regression that shipped — a hand-built prompt would not prove the orchestrator
wiring; (2) it is the only design that lets the AC-7 RED fail on a **payload
assertion** against unfixed source rather than a `TypeError` — `process_files`
already accepts `system_prompt=`/`profile_id=`/`provider_id=` today, so the RED
test collects and runs cleanly pre-fix and only the assertion on the outgoing
system message goes red. A second, lower-level unit test in
`test_openai_compatible_client.py` exercises the new
`OpenAICompatibleClient(system_prompt=...)` kwarg directly once it exists; it
is a **post-fix-only** regression companion, never the AC-7 RED, since calling
it pre-fix raises `TypeError` (a forbidden RED shape).

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | integration | tests/test_orchestrator_context_detection.py::test_cloud_client_delivers_profile_base_system_prompt_semiconductor | 1 |
| AC-2 | integration | tests/test_orchestrator_context_detection.py::test_cloud_client_delivers_profile_base_system_prompt_semiconductor | 1 |
| AC-3 | contract | tests/test_orchestrator_context_detection.py::test_base_prompt_precedes_document_context_preamble_in_composition | 1 |
| AC-4 | unit | tests/test_ollama_client_dynamic_strategy.py::test_ollama_outgoing_payload_base_system_prompt_unchanged | 0 |
| AC-5 | integration | tests/test_orchestrator_context_detection.py::test_fallback_chain_client_delivers_profile_base_system_prompt | 1 |
| AC-6 | unit | tests/test_openai_compatible_client.py::test_default_construction_without_system_prompt_stays_empty | 0 |
| AC-7 | integration | tests/test_orchestrator_context_detection.py::test_cloud_client_delivers_profile_base_system_prompt_semiconductor | 1 |
| AC-8 | contract | covered by `cdd-kit validate --contracts` (BR-110 + CHANGELOG bump); no test file | n/a |

## Test Families Required

unit, contract, integration

| family | tier | notes |
|---|---|---|
| unit | 0 | `OpenAICompatibleClient.__init__(system_prompt=...)` delivers to the outgoing payload (`test_openai_compatible_client.py::test_constructor_system_prompt_kwarg_delivered_to_outgoing_payload`, new — post-fix companion, not the AC-7 RED); default-omitted construction still yields `""` (AC-6 anti-vacuity guard, not silence). |
| unit | 0 | Ollama payload-boundary regression (AC-4): capture the `requests.Session.post` json kwarg reached via `_call_ollama`'s caller, assert `payload["system"]` unchanged from before this change. |
| integration | 1 | `process_files()` end-to-end through `build_strategy` on the PANJIT mock config (`_PANJIT_CFG`, existing fixture in `test_orchestrator_context_detection.py`), asserting only on the captured outgoing `json=` payload — never `client.system_prompt` (AC-1/AC-2/AC-7). |
| contract | 1 | BR-109/BR-110 composition-order conformance: base-prompt string index < scenario-appendix index < few-shot-block index < `Document context:` index, all within the same system-message string (AC-3). |
| integration | 1 | Fallback-chain construction site (`orchestrator.py` L560) also delivers the base prompt when it becomes the winning client (AC-5) — primary provider forced to fail its health probe so the fallback provider wins. |
| regression (existing suites, unmodified) | 1 | Full collection of `test_provider_fallback.py`, `test_cloud_total_timeout.py`, `test_term_extractor.py`, `test_term_extractor_resilience.py`, `test_llm_client_protocol.py` (39 constructions across six files) stays green untouched — an additive optional kwarg with an `""`-equivalent default means no test double needs code changes; AC-6 is proven non-vacuous by the explicit default-omitted assertion above, not by silence. `test_llm_client_protocol.py::test_protocol_defines_five_methods` is unaffected (`__init__` is not part of the Protocol's method surface). |

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | `cdd-kit test select` over `tests/test_openai_compatible_client.py tests/test_orchestrator_context_detection.py tests/test_ollama_client_dynamic_strategy.py tests/test_provider_fallback.py tests/test_cloud_total_timeout.py tests/test_term_extractor.py tests/test_term_extractor_resilience.py tests/test_llm_client_protocol.py` | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | `cdd-kit test select` over the 6 bare node IDs in the mapping table (run via `conda run -n translate-tool cdd-kit test run --phase targeted` — torch import path) | 1 | test-evidence.yml |
| changed-area | yes | `cdd-kit test select` over `tests/test_openai_compatible_client.py tests/test_orchestrator_context_detection.py tests/test_ollama_client_dynamic_strategy.py` | 1 | test-evidence.yml |
| contract | if affected | `cdd-kit validate --contracts` (BR-110 + CHANGELOG bump) | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | `cdd-kit test run --phase full` | 1 | test-evidence.yml |

Never scope any phase to whole `test_pdf_*` or QE/COMET files — pre-existing
env artifacts (onnxruntime/torch) unrelated to this change; see Promoted
Learnings.

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| (none) | — | additive optional kwarg with an unchanged-default value requires no existing test to be edited or deleted; the 39 constructor call sites across six files are a regression net, not an update target. |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- xlsx phantom-column defect (`table_serializer.parse()`) — no test planned (BR-82 fallback already covers correctness; separate change).
- Critique-loop call volume (1 translate + 3 critique calls/segment) — observed, not tested here.
- `app/backend/api/routes.py` (L977/L1068/L1181) and `app/backend/services/quality_judge.py` (L111) construction sites — outside this change's read scope; their existing (unenumerated) suites are the regression net via the full-suite gate, not a new named test here.
- `app/backend/services/model_router.py` — confirmed no reference to `OpenAICompatibleClient`; no test needed.
- No new E2E, visual, fuzz/monkey, stress, or soak surface (payload interception at the client/orchestrator boundary is sufficient per change-classification.md).

## Notes

- Anti-tautology: every assertion above inspects the captured `json=` kwarg of the mocked `requests.Session.post` (or the Ollama `_call_ollama` caller's payload dict) — never `client.system_prompt` — per AC-2/BR-110.
- AC-3 asserts ordering via string index, not mere membership, ruling out the preamble replacing the base.
- Semiconductor role-declaration substring under test: `"You are a professional semiconductor translator for IC design, packaging, and test content."` (`app/backend/translation_profiles.py`).
