---
change-id: cloud-doc-context-summary
schema-version: 0.1.0
last-changed: 2026-07-09
---

# Implementation Plan: cloud-doc-context-summary

## Objective

Make the one-sentence document-context summary generate + inject on cloud
providers (PANJIT/DeepSeek) — the user's real path — by routing
`_detect_document_context` through a shared, provider-agnostic raw-completion
seam and removing the `_cloud_client is None` block that today skips the summary
on any cloud run. Local-Ollama behavior stays byte-identical; a failed/empty
cloud summary degrades to no preamble and never aborts the job. Satisfies
AC-1..AC-7 (change-classification.md) and BR-109 (business-rules.md).

## Verified Seam Facts (confirmed against live source — read BEFORE editing)

This change is NOT "delete the guard and pass the active client". That alone
would call Ollama-only methods on the cloud client and fail. Confirmed:

- `orchestrator._detect_document_context` (`app/backend/processors/orchestrator.py:321-338`)
  calls `client._build_no_system_payload(prompt)` (L329) and
  `client._call_ollama(payload)` (L331). Both are **Ollama-only**
  (`OllamaClient._build_no_system_payload` L226-227, `._call_ollama` L245-315).
  `OpenAICompatibleClient` implements **neither** (its method set:
  `openai_compatible_client.py:238-263` — has `_post_completion`, `translate_once`,
  `_is_translation_dedicated`, `health`, etc.; no `_call_ollama`, no
  `_build_no_system_payload`).
- The shared `translate_once(text, tgt, src_lang, cancel_event=None, system_context=None)`
  is present on both clients — but it is the **WRONG** seam for a summary: both
  implementations WRAP the argument in "Translate the following text from X to
  Y…" (`OllamaClient.translate_once` L442-489 → `_build_single_translate_payload`;
  `OpenAICompatibleClient.translate_once` L288-318, inline prompt L309-312). Passing
  the summary instruction to `translate_once` makes the model *translate the
  instruction* instead of summarizing the document. Do NOT use `translate_once`.
- The raw-completion paths (no translate framing, no system prompt) are private
  and asymmetric: Ollama = `_call_ollama(_build_no_system_payload(prompt))`;
  cloud = `_post_completion(prompt)` (`openai_compatible_client.py:172-230`,
  returns `(ok, text)`, catches `RequestException` internally so it never raises,
  and is wall-clock bounded by BR-100). **Resolution: add a thin shared PUBLIC
  method `complete(prompt) -> (ok, text)` to BOTH concrete clients** that wraps
  each client's raw-completion path, and call `client.complete(prompt)` from
  `_detect_document_context`. See IP-1/IP-2/IP-3.
- Guard site: `app/backend/processors/orchestrator.py:557-564`. The exclusion is
  L562 (`and _cloud_client is None  # skip when cloud provider is active …`); the
  call at L564 passes `ollama_client` (the always-built local handle), NOT the
  active `client`. The other conditions (`CONTEXT_DETECTION_ENABLED` L558,
  `QWEN_CONTEXT_FLOW_ENABLED` L559, `not client._is_translation_dedicated()` L560,
  `sample` L561) MUST be preserved.
- Injection point (UNCHANGED wiring, reuse verbatim): the `build_strategy` branch
  `orchestrator.py:566-575` (`detected_context=doc_context` L572 →
  `client.system_prompt = decision.system_prompt` L575; "Document context:" is
  emitted inside `translation_strategy.build_strategy` at
  `translation_strategy.py:304`) AND the non-dynamic else branch
  `orchestrator.py:586-589`
  (`client.system_prompt = f"{base_system_prompt}\n\nDocument context: {doc_context}"`).
  Both already consume `doc_context`; no edit here.
- `_detect_document_context` is called exactly once, from `process_files` (L564).
  On a local run `client is ollama_client` (L527), so passing `client` is
  identical to today on the local path (AC-6). On a cloud run `client is
  _cloud_client` (L524), so the summary routes to the cloud client (AC-1).
- Why NOT add `complete` to the base Protocol (`base_llm_client.py`):
  `tests/test_llm_client_protocol.py::TestProtocolDefinition::test_protocol_defines_five_methods`
  asserts the Protocol has EXACTLY 5 methods (and pins the 5 signatures). Adding a
  6th Protocol method breaks that out-of-scope test. Both concrete clients gaining
  `complete` still satisfy every existing conformance test (they only `hasattr`-check
  the 5 Protocol methods; extras are allowed). `base_llm_client.py` is NOT edited.

## Execution Scope

### In Scope
- Add public `complete(self, prompt: str) -> Tuple[bool, str]` to `OllamaClient`
  (wrap `_call_ollama(_build_no_system_payload(prompt))`) and to
  `OpenAICompatibleClient` (wrap `_post_completion(prompt)`).
- Rewire `_detect_document_context` to call `client.complete(prompt)` and update
  its `client` param annotation to `LLMClient`.
- Edit the guard/call site: delete the `and _cloud_client is None` line; change
  the argument `ollama_client` → `client`. Preserve every other guard condition.
- Update two existing test doubles (see Required Changes IP-6/IP-7) and add the
  new test file `tests/test_orchestrator_context_detection.py` (test-strategist owns
  the test bodies; backend-engineer implements to make them pass).

### Out of Scope
- JSON structured translation I/O (`{"text":…}`→`{"translation":…}`) — Step 3, a
  separate tracked change. Do NOT touch it.
- Summary-prompt wording: `context_prompts._CONTEXT_DETECTION_PROMPTS`
  (`context_prompts.py:232-245`) and `_get_context_detection_prompt` are UNCHANGED.
- Downstream injection wiring: `build_strategy` and the else-branch
  `client.system_prompt = …"Document context: …"` are UNCHANGED (reuse only).
- Flag rename: `QWEN_CONTEXT_FLOW_ENABLED` keeps its historical name; no new env var,
  no default change.
- `base_llm_client.py` Protocol: NOT edited (would break the exactly-5 assertion).
- `translate_once` / `_post_completion` / `_call_ollama` / `_build_no_system_payload`
  internals: NOT modified. `model_router.py`, `translation_service.py`,
  `translation_strategy.py`, `translation_helpers.py`: NOT modified.
- No opportunistic refactor of `process_files`, the client-resolution block
  (L443-529), or the phase-0/term/judge sections.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | clients/ollama_client.py | Add `def complete(self, prompt: str) -> Tuple[bool, str]: return self._call_ollama(self._build_no_system_payload(prompt))` (place near the Protocol-alias region ~L874-890). Byte-identical to the prior local summary call. | backend-engineer |
| IP-2 | clients/openai_compatible_client.py | Add `def complete(self, prompt: str) -> Tuple[bool, str]: return self._post_completion(prompt)` (place near `translate_once` ~L288-318). Delivers the summary prompt as the sole user message; no translate framing, no system prompt. | backend-engineer |
| IP-3 | processors/orchestrator.py `_detect_document_context` (L321-338) | Replace the two Ollama-only calls (L329, L331) with a single `ok, result = client.complete(prompt)`. Keep the existing `try/except`, `result.strip()[:200]`, `[CONTEXT] Detected:` log, and `return ""` fallback verbatim. Change the `client` param annotation `OllamaClient` → `LLMClient`. | backend-engineer |
| IP-4 | processors/orchestrator.py import block (~L11-12) | Add `from app.backend.clients.base_llm_client import LLMClient` (stdlib-only module, no import cycle) to support the IP-3 annotation. | backend-engineer |
| IP-5 | processors/orchestrator.py guard/call site (L557-564) | Delete the line `and _cloud_client is None  # skip when cloud provider is active …` (L562); change the call arg `_detect_document_context(ollama_client, …)` → `_detect_document_context(client, …)` (L564). Preserve L558-561 exactly. | backend-engineer |
| IP-6 | tests/test_context_prompt_i18n.py::test_immediate_and_deferred_use_same_template (L74-110) | Update the mocked call target: replace `mock_client._build_no_system_payload`/`._call_ollama` setup + the "`_build_no_system_payload was not called`" assertion with `mock_client.complete.return_value = (True, "detected context")` and assert the helper sentinel reaches `mock_client.complete.call_args`. | backend-engineer |
| IP-7 | tests/test_provider_fallback.py::TestOrchestratorProviderWiring::test_cloud_client_used_when_provider_id_set (L399-404) | Remove the now-stale `patch("…orchestrator.CONTEXT_DETECTION_ENABLED", False)` and its rationale comment (the limitation it cites is exactly the bug this change fixes). Assertions (6-tuple, winning_provider=="panjit", client isinstance OpenAICompatibleClient) are unaffected; the shared `_mock_post` already answers the extra summary POST. Re-run to confirm green. | backend-engineer |
| IP-8 | tests/test_orchestrator_context_detection.py (NEW) | Implement production code so the test-strategist's AC-1..AC-7 rows (test-plan.md §Acceptance Criteria → Test Mapping) pass. Test bodies authored per test-plan; backend-engineer wires production to green. Torch-free. | backend-engineer |
| IP-9 | tests/test_orchestrator_phase0.py::_make_mock_ollama_client (L161-168) | VERIFY-ONLY. Local path: `client is ollama_client` (bare MagicMock); `client.complete(prompt)` returns a MagicMock, unpacking raises inside `_detect_document_context`'s try → returns "" (unchanged from today's `_call_ollama` MagicMock behavior). Optional hardening: add `mock.complete.return_value = (False, "")`. Re-run these tests to confirm still green. | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | Inferred Acceptance Criteria AC-1..AC-7 | scope + verification targets |
| test-plan.md | §Acceptance Criteria → Test Mapping; §Test Update Contract; §Notes (seam risk) | test files to write/update, mock boundaries |
| test-plan.md | §Test Execution Ladder | required phases (collect/targeted/changed-area floor; contract; full) |
| ci-gates.md | §Required Gates for This Change | verification commands (`cdd-kit validate --contracts`, blanket pytest) |
| contracts/business/business-rules.md | BR-109 (cloud-context-detection-parity) | behavior the change must satisfy (already authored; seam-agnostic) |
| contracts/env/env-contract.md | `CONTEXT_DETECTION_ENABLED`, `QWEN_CONTEXT_FLOW_ENABLED` descriptions | contract-reviewer updates (not backend-engineer) |
| change-classification.md | "design.md = no"; Architecture Review = no | no design.md required; proceed |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| app/backend/clients/ollama_client.py | edit (add method) | IP-1: `complete()` wraps `_call_ollama(_build_no_system_payload(prompt))`. Do not alter `_call_ollama`/`_build_no_system_payload`. |
| app/backend/clients/openai_compatible_client.py | edit (add method) | IP-2: `complete()` wraps `_post_completion(prompt)`. Do not alter `_post_completion`. |
| app/backend/processors/orchestrator.py | edit | IP-3 (`_detect_document_context` body + annotation, L321-338), IP-4 (import), IP-5 (guard L562 delete + L564 arg `ollama_client`→`client`). Nothing else in `process_files`. |
| app/backend/clients/base_llm_client.py | DO NOT EDIT | Adding to the Protocol breaks `test_llm_client_protocol.py` exactly-5 assertion (out of scope). |
| app/backend/services/context_prompts.py | DO NOT EDIT | Prompt wording is a non-goal. |
| app/backend/services/translation_strategy.py | DO NOT EDIT | Injection wiring (`Document context:` L304) is reuse-only. |
| app/backend/config.py | DO NOT EDIT | `CONTEXT_DETECTION_ENABLED=True` (L128, code constant), `QWEN_CONTEXT_FLOW_ENABLED` (L160, env). No flag/default change. |
| tests/test_context_prompt_i18n.py | edit | IP-6. |
| tests/test_provider_fallback.py | edit | IP-7. |
| tests/test_orchestrator_context_detection.py | create | IP-8 (bodies per test-plan; backend wires to green). |
| tests/test_orchestrator_phase0.py | verify (optional 1-line harden) | IP-9. |

## Contract Updates

- API: none (no endpoint added/renamed/changed).
- CSS/UI: none.
- Env: `contracts/env/env-contract.md` — descriptions of `CONTEXT_DETECTION_ENABLED`
  and `QWEN_CONTEXT_FLOW_ENABLED` now also gate the cloud path; note
  `QWEN_CONTEXT_FLOW_ENABLED` name is historical/provider-agnostic. Documentation-only;
  no new var, no default/secret change. **Owner: contract-reviewer** (not backend-engineer).
- Data shape: none (JSON I/O is Step 3).
- Business logic: `contracts/business/business-rules.md` BR-109 already encodes this
  behavior and is **seam-agnostic** ("the ACTIVE cloud translation client"), so it is
  consistent with the `complete()` seam — no correction needed. Recommend contract-reviewer
  bump `schema-version` from the LIVE value and optionally add a one-line clarification
  that the summary uses a raw-completion seam (NOT the translate path) to pre-empt Step-3
  confusion. **Owner: contract-reviewer.**
- CI/CD: none (ci-gates.md §Workflow Changes Applied = None).

## Test Execution Plan

Phases per test-plan.md §Test Execution Ladder — floor: collect, targeted,
changed-area; plus contract (business-rules affected) and full (CI). Evidence via
`cdd-kit test run`; do not restate the ladder here. All targets torch-free (mocked
clients / `requests.Session.post`), run under base `pytest`.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_orchestrator_context_detection.py::test_cloud_active_client_used_for_summary_not_local_ollama | cloud client's `complete` used; local Ollama not called |
| AC-1 | tests/test_orchestrator_context_detection.py::test_cloud_summary_generated_without_local_ollama_present | summary produced via cloud path, no Ollama dependency |
| AC-2 | tests/test_orchestrator_context_detection.py::test_cloud_summary_injected_as_document_context_in_system_prompt | "Document context: <summary>" reaches system prompt |
| AC-3 | tests/test_orchestrator_context_detection.py::test_context_detection_disabled_skips_cloud_summary | no summary when CONTEXT_DETECTION_ENABLED off |
| AC-3 | tests/test_orchestrator_context_detection.py::test_qwen_context_flow_disabled_skips_cloud_summary | no summary when QWEN_CONTEXT_FLOW_ENABLED off |
| AC-4 | tests/test_orchestrator_context_detection.py::test_translation_dedicated_cloud_client_skips_summary | dedicated cloud client → summary skipped |
| AC-5 | tests/test_orchestrator_context_detection.py::test_detect_document_context_returns_empty_on_cloud_call_exception | exception/empty → returns "", no raise |
| AC-5 | tests/test_orchestrator_context_detection.py::test_job_continues_with_no_preamble_when_cloud_summary_empty | job completes (stopped=False), no preamble |
| AC-6 | tests/test_orchestrator_context_detection.py::test_local_ollama_context_detection_unchanged | local path summary generated/injected as before |
| AC-7 | tests/test_orchestrator_context_detection.py::test_no_scope_creep_into_injection_wiring_or_json_io | injection wiring + JSON I/O untouched |
| AC-7 (regression) | tests/test_translation_strategy.py | stays green (unmodified) |
| AC-7 (regression) | tests/test_context_prompt_i18n.py | green after IP-6 update |
| IP-6/IP-7/IP-9 (doubles) | tests/test_provider_fallback.py::TestOrchestratorProviderWiring | green after IP-7; client-dispatch assertions intact |
| Protocol guard | tests/test_llm_client_protocol.py | stays green (base Protocol NOT edited; exactly-5 holds) |

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Graceful degradation is mandatory: a cloud summary failure/empty MUST return ""
  (no preamble) and MUST NOT abort the job (AC-5, BR-109). Do not add re-raise or
  hard-fail paths in `complete()` or `_detect_document_context`.
- Local-Ollama path MUST be byte-identical at the HTTP boundary
  (`_call_ollama(_build_no_system_payload(prompt))` unchanged; only wrapped by
  `complete()`).
- Do NOT use `translate_once` for the summary (it translate-wraps the prompt) and do
  NOT add `complete` to `base_llm_client.py`.

## Known Risks

- **Wrong-seam temptation (highest):** a follow-on agent may "simplify" the summary
  onto `translate_once` because both clients share it — that silently corrupts the
  summary (model translates the instruction). The `complete()` seam + this note guard
  against it; test AC-1/AC-6 assert the correct call target.
- **Protocol test coupling:** `tests/test_llm_client_protocol.py` pins the Protocol to
  exactly 5 methods. Keep `complete` OFF `base_llm_client.py`.
- **Bare-MagicMock fakes:** `_make_mock_ollama_client` and the i18n mock auto-create any
  attribute, so `hasattr`-style dispatch would silently mis-branch. The plan avoids
  capability sniffing (explicit `complete()` call) — fakes must set `complete` returns
  explicitly (IP-6 required; IP-9 optional). Grep of `tests/` for `_detect_document_context`,
  `_call_ollama`, `_build_no_system_payload`, `_post_completion` found no OTHER doubles that
  reproduce this seam (judge/critique/term-extractor fakes use their own paths, unaffected).
- **Latency/cost:** each cloud document now makes ONE extra completion call for the summary
  (bounded by BR-100 `OPENAI_TOTAL_TIMEOUT_SECONDS`, default 480s). Not a soak profile
  (change-classification.md); acceptable, disclosed here per that artifact's note.
- **Code-map freshness:** `.cdd/code-map.yml` header digest matches the read source; line
  numbers above are current as of that generation. If files drift before implementation,
  re-anchor by symbol name, not raw line number.
