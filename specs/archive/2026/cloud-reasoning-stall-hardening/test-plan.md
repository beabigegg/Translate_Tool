---
change-id: cloud-reasoning-stall-hardening
schema-version: 0.1.0
last-changed: 2026-07-11
risk: high
tier: 1
---

# Test Plan: cloud-reasoning-stall-hardening

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 (BR-118) | unit/contract | tests/test_openai_compatible_client.py::TestReasoningDirectiveComposition::test_translate_once_system_message_exact_equals_directive_plus_base_prompt_plus_neighbor_context | 1 |
| AC-1 (BR-118) | unit/contract | tests/test_openai_compatible_client.py::TestReasoningDirectiveComposition::test_reasoning_directive_absent_from_every_user_message | 1 |
| AC-1 (BR-118) | unit/contract | tests/test_openai_compatible_client.py::TestReasoningDirectiveComposition::test_translate_json_system_message_carries_directive_ahead_of_base_prompt_and_neighbor_context | 1 |
| AC-1 (BR-118) | unit/contract | tests/test_openai_compatible_client.py::TestReasoningDirectiveComposition::test_directive_value_sourced_from_openai_translation_reasoning_config_constant | 1 |
| AC-1 (BR-118) | contract | tests/test_context_prefix_bleed.py (extended) — reasoning directive substring absent from every echoed user `text` | 1 |
| AC-2 (BR-118 exemption) | unit | tests/test_openai_compatible_client.py::TestOutlineReasoningExemption::test_complete_passes_reasoning_none_no_directive_in_system_message | 1 |
| AC-2 (BR-118 exemption) | integration | tests/test_orchestrator_context_detection.py::test_detect_document_context_returns_nonempty_summary_when_translation_calls_suppress_reasoning | 1 |
| AC-3 (BR-100 default) | unit (existing, update) | tests/test_openai_compatible_client.py::TestTotalTimeoutConfig::test_env_var_parses_positive_float_default | 0 |
| AC-3 (BR-100 ceiling) | resilience | tests/test_cloud_total_timeout.py::test_stalled_dribble_aborts_within_120s_ceiling_not_480s | 1 |
| AC-4 (BR-100 embed routing) | unit | tests/test_openai_compatible_client.py::TestEmbedBounded::test_embed_invokes_run_bounded_post_wrapper_not_raw_session_post | 1 |
| AC-4 (BR-100 embed resilience) | resilience | tests/test_cloud_total_timeout.py::test_embed_stalled_post_aborts_within_ceiling_degrades_to_empty_list | 1 |
| AC-5 (BR-119 default-off parity) | unit | tests/test_critique_loop_batching.py::test_critique_skip_cached_segments_default_false_every_segment_still_enters_pending_keys | 0 |
| AC-5 (BR-119 opt-in selection) | unit | tests/test_critique_loop_batching.py::test_critique_skip_cached_segments_true_excludes_phase1_cache_hit_keys_from_pending_keys | 0 |
| AC-5 (BR-119 no-drop) | unit | tests/test_critique_loop_batching.py::test_critique_skip_cached_segments_true_keeps_excluded_segments_draft_present_in_tmap | 0 |
| AC-5 (BR-119 gate unaffected) | unit | tests/test_critique_gate.py::test_critique_skip_cached_flag_does_not_alter_max_iterations_timeout_or_gate_for_segments_still_in_loop | 0 |

## Test Families Required

Mark all that apply: **unit**, **contract**, **integration**, **resilience**.
| family | tier | notes |
|---|---|---|
| unit | 0/1 | config constants Tier 0 (<30s); payload-composition + critique pre-filter selection tests mock at the `requests.Session.post` / `LLMClient` boundary, Tier 1 (PR-required — BR-118/BR-119 are the core of this change) |
| contract | 1 | ADR-0016/ADR-0021 no-leak invariant (`test_context_prefix_bleed.py`, `test_openai_compatible_client.py`) — captured-payload exact-equality |
| integration | 1 | `test_orchestrator_context_detection.py` — cloud path with reasoning suppressed still yields a valid document-context summary |
| resilience | 1 | `test_cloud_total_timeout.py` — real local dribble socket, no client-internals mocking; owned by e2e-resilience-engineer; PR-required (this is the regression the change targets, not deferred to nightly) |

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
| tests/test_openai_compatible_client.py::TestTotalTimeoutConfig::test_env_var_parses_positive_float_default | update | literal `480.0` → `120.0`; BR-100 default lowered |
| tests/test_openai_compatible_client.py::TestTotalTimeoutCeilingAdditive (both tests, `patch("app.backend.config.OPENAI_TOTAL_TIMEOUT_SECONDS", 480.0)` ~L760/766/772/780/795) | update | same literal must change to 120.0 (or any value ≠ read-timeout) to stay a valid additive-ceiling probe |
| tests/test_context_prefix_bleed.py (`_FakeEchoClient`-based no-leak assertions) | update | extend to also assert BR-118 directive absent from echoed user `text`, alongside existing neighbor-context no-leak check |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope
- Live PANJIT E2E probe (manual/authorized only, never a gated test — change-request.md item 1 verification note).
- Any test reading `docs/TEST_DOC/` (forbidden path, context-manifest.md).
- UI / frontend tests (no UI surface).
- The local Ollama translate path (not used for translation — change-request.md Non-goals).

## Anti-Tautology Notes
AC-1/AC-2: assert on the captured OUTGOING payload (`session.post` `json=` / fake client's recorded `system_context`/`text`), never `client.system_prompt` (assignment-without-delivery); assert directive absence from `user_content` explicitly, not just relative ordering (order-without-location). AC-4: assert `_run_bounded_post`/its worker is actually exercised by `embed()`, not that a kwarg is merely accepted while `self._session.post` is still called directly. AC-5: assert the SET of `(tgt, text)` keys entering `_pending_keys` (selection-not-count), plus that an excluded segment's `tmap` entry stays non-empty (no silent drop). Any log assertion must filter `record.name == "TranslateTool"` (caplog root-logger bleed). Grep `tests/` for `_post_completion`/`translate_once`/`embed` fakes with fixed signatures before landing — a fake accepting a new kwarg without recording it stays green even if delivery is deleted.

## Notes
`_post_completion(reasoning="low")` literal is already in the working tree (design.md); tests must pin the config-sourced `OPENAI_TRANSLATION_REASONING` value, not the literal, so a future default change stays test-visible. `embed()` routing and the BR-119 flag are net-new wiring — the tests above are written to fail (RED) against current code.
