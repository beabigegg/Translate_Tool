---
change-id: qa-judge-hang-recovery
schema-version: 0.1.0
last-changed: 2026-07-07
risk: high
tier: 1
---

# Test Plan: qa-judge-hang-recovery

Designed against the depends-on sibling's finalized shape: `_translate_fn` →
`_judge.translation_client.translate_once(...)`, `QualityJudge.translation_client`
property. `run_judge_loop`/`_run_judge_loop_impl` also carries `snapshot_cb=None`
(translation-progress-detail-ui); this change appends `cancel_event=None` after it.

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | resilience | tests/test_cloud_total_timeout.py::test_cancel_event_aborts_blocked_post_mid_read | 1 |
| AC-1 | unit | tests/test_quality_judge.py::TestCancelDuringInFlightScoring::test_stop_flag_set_mid_evaluate_exits_promptly | 0 |
| AC-2 | resilience | tests/test_cloud_total_timeout.py::test_ceiling_fires_on_dribbling_never_silent_response | 1 |
| AC-3 | unit | tests/test_openai_compatible_client.py::TestTotalTimeoutCeilingAdditive::test_wellbehaved_call_still_bounded_by_connect_read_tuple | 0 |
| AC-3 | unit | tests/test_openai_compatible_client.py::TestTotalTimeoutCeilingAdditive::test_ceiling_absent_from_per_chunk_timeout_tuple | 0 |
| AC-4 | contract | tests/test_quality_judge.py::TestCancellationDegradation::test_cancel_mid_loop_yields_judge_status_stopped | 1 |
| AC-4 | contract | tests/test_quality_judge.py::TestCancellationDegradation::test_ceiling_timeout_yields_judge_status_unavailable_not_stopped | 1 |
| AC-5 | contract | tests/test_quality_judge.py::TestIterationCapUnaffectedByCancellation::test_max_iterations_cap_enforced_when_cancel_event_none | 1 |
| AC-5 | contract | tests/test_quality_judge.py::TestIterationCapUnaffectedByCancellation::test_attempts_count_not_corrupted_by_mid_loop_cancel | 1 |
| AC-6 | integration | tests/test_orchestrator_judge.py::test_cancel_during_judge_phase_reaches_terminal_state | 1 |
| AC-7 | unit | tests/test_openai_compatible_client.py::TestTotalTimeoutConfig::test_env_var_parses_positive_float_default | 0 |
| AC-7 | contract | tests/test_env_contract.py::TestEnvContractDeclared::test_openai_total_timeout_seconds_declared | 1 |
| AC-8 | resilience | tests/test_cloud_total_timeout.py::test_dribbling_socket_regression_repro_matches_live_incident | 1 |

## Test Families Required

Mark all that apply: unit / contract / integration / **resilience**

| family | tier | notes |
|---|---|---|
| unit | 0 | interruptible-wait/ceiling primitive in isolation; config float parsing; Protocol `cancel_event=None` back-compat kwarg on `translate_once`/`_post_completion` |
| contract | 1 | BR-73/BR-74 + new BR-99/BR-100 Table U rows; env-contract/.env.example.template/env.schema.json row; data-shape-contract.md + api-contract.md `judge_status` enum gains `stopped` (additive; grepped existing tests, none assert an exhaustive enum list, so no update needed there) |
| integration | 1 | `job_manager.cancel_job()` (real `threading.Event` + real worker thread, mirrors `test_orchestrator_judge.py`'s `_wait_for_job` pattern) drives a job through the judge phase to a terminal `status` with well-defined `job.judge`; asserts no unhandled exception surfaces |
| resilience | 1 (required-gate, bug-fix lane) | local dribbling test server / cancel-mid-read interrupt; this IS the incident regression proof so it stays in the PR-required Tier 1 lane, not nightly; ceiling/dribble-interval values monkeypatched small (ceiling≈0.5s, chunk every ≈0.1s) to stay inside the 10 min budget |

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
| (none identified) | — | `judge_status` gains `stopped` additively; no existing test asserts an exhaustive enum list (verified by grep), so no existing assertion needs to change |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- Judge scoring/tier semantics, JSON/token parsing (D6) — unchanged; covered by existing `tests/test_quality_judge.py` rows for BR-72/BR-75.
- `JUDGE_MAX_ITERATIONS` value/BR-73 cap semantics themselves — only its survival under cancel/timeout is in scope.
- Main translation loop's own `stop_flag` path (`job_manager.py:352`) — already correct, not touched.
- `OllamaClient` in-flight socket interrupt — best-effort per design's Open Risks; only its between-block `stop_flag` observance is asserted (folded into `TestCancelDuringInFlightScoring`), not a dribble-ceiling (none needed locally).
- Retry/backoff framework, BR-92 rescore resolution, three-mechanism docs — separate sibling changes.
- UI Cancel button — reused as-is, no frontend test.

## Notes

- **Test-infra gap:** no existing mock-server/socket-timing harness — `tests/test_openai_compatible_client.py` only patches `requests.Session.post` with an instant `MagicMock`, which cannot represent a dribbling/chunked transfer or a genuinely blocked read. AC-2/AC-3/AC-8 need a **new fixture**: a local HTTP server (background thread) sending periodic small chunks past the ceiling but never silent long enough to trip `read_timeout`. Add it inside the new `tests/test_cloud_total_timeout.py`.
- **Context-manifest gap:** `tests/test_quality_judge.py` and `tests/test_env_contract.py` are the established homes for BR-72..77 / env-var tests per `business-rules.md` but are not in this change's Allowed Paths — flag before the implementation pass extends them.
- Mock boundary: unit/contract tests mock `requests.Session.post`/`get`; resilience tests use a real local socket (network boundary), never mock `OpenAICompatibleClient`/`QualityJudge` internals (tautology risk).
- `evaluate()`/`_complete()` swallow exceptions into `judge_status="unavailable"` (D5) — cancel-vs-timeout tests must assert the *distinguishing* signal reaches `_run_judge_loop_impl`, not just "some" exception.
