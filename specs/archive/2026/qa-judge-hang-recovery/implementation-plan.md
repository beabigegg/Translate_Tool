---
change-id: qa-judge-hang-recovery
schema-version: 0.1.0
last-changed: 2026-07-07
risk: high
tier: 1
---

# Implementation Plan: qa-judge-hang-recovery

## Objective

Make a hung QA/LLM-judge cloud call both cancellable and wall-clock-bounded so
this class of incident never again requires killing the backend process. Deliver
two cooperating mechanisms plus their contract/config surface:

1. A wall-clock **total-duration ceiling** on every cloud completion, added in
   `openai_compatible_client._post_completion`, additive on top of the existing
   `(connect, read)` tuple, degrade-not-fail (see design.md D2).
2. A **cancel-aware interruptible post** sharing the ceiling's wait primitive:
   setting `cancel_event` (the judge path passes `job.stop_flag`) aborts an
   in-flight blocked socket read (design.md D1).
3. Cooperative `stop_flag` checks inside `_run_judge_loop_impl` (loop-top +
   before each per-block `evaluate()` + before each per-block re-translate) for
   fast-exit; `cancel_event` threaded through `evaluate()`/`_complete()` and
   through `translation_client.translate_once(...)`.
4. New `judge_status="stopped"` (4th enum value): cancel → `stopped`;
   ceiling-timeout-with-no-cancel → stays `unavailable` (design.md D3).
5. New env var `OPENAI_TOTAL_TIMEOUT_SECONDS` + additive contract edits.

Every change is additive/non-breaking. A cancelled or timed-out judge pass must
still produce a well-defined `JudgeResult` (BR-74 shape), keep BR-73 iteration
accounting intact, and leave the backend alive.

## Execution Scope

### In Scope
- Cloud client ceiling + interruptible post + optional `cancel_event` kwarg
  (`openai_compatible_client.py`).
- `cancel_event` plumbing on `translate_once`/`_post_completion` and the
  `LLMClient` Protocol signature (back-compatible default `None`).
- `OllamaClient` `cancel_event` kwarg for between-block cancellation parity
  (mid-read interrupt is best-effort only — see design Open Risks).
- Judge-loop cancellation: `cancel_event` param on `run_judge_loop` /
  `_run_judge_loop_impl` / `evaluate` / `_complete`; cooperative checks; new
  `stopped` degradation path (`quality_judge.py`).
- Judge call-site wiring in `job_manager.py`: pass `cancel_event=job.stop_flag`
  into `run_judge_loop` and into the sibling's
  `_judge.translation_client.translate_once(...)`.
- New config `OPENAI_TOTAL_TIMEOUT_SECONDS` (`config.py`).
- Additive contract edits: business-rules (BR-99/BR-100 + 2 Table U rows),
  env-contract + `.env.example.template` + `env.schema.json`,
  data-shape-contract.md:567, api-contract.md:51/323 (+ `openapi export`).
- New test file `tests/test_cloud_total_timeout.py` with a dribbling mock-server
  fixture; new test classes in existing files per test-plan.md.

### Out of Scope
- Retry/backoff framework — the ceiling is a bounded cap, not a retry (non-goal).
- Main translation loop's existing `stop_flag` path (`job_manager.py:352`,
  `process_files`) — untouched; it does NOT gain new `cancel_event` wiring
  (main translation gains the ceiling automatically, no cancel wiring).
- Judge scoring/tier logic, JSON/token parsing, `JUDGE_MAX_ITERATIONS` value,
  BR-72/BR-73/BR-75 semantics — only their survival under cancel/timeout.
- `qa-judge-provider-consistency` scope: do NOT touch BR-97's
  `_skip_judge_provider` gate, `_build_cloud_client`, or the
  `translation_client` property itself (that sibling owns them). Consume them.
- BR-92 rescore resolution, three-mechanism docs, UI Cancel button (reused).

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | cloud client | Add wall-clock ceiling + cancel-aware interruptible post in `_post_completion`; thread optional `cancel_event=None` through `translate_once`. On ceiling expiry OR `cancel_event.set()`, close session to abort in-flight read and raise a `requests`-compatible timeout so the existing `except RequestException` path degrades. Never weaken the `(connect, read)` tuple. | backend-engineer |
| IP-2 | config | Add `OPENAI_TOTAL_TIMEOUT_SECONDS: float = float(os.environ.get("OPENAI_TOTAL_TIMEOUT_SECONDS", "480"))` following the `CRITIQUE_TIMEOUT_SECONDS` (config.py:141) pattern; positive-float. | backend-engineer |
| IP-3 | client protocol | Add optional `cancel_event=None` kwarg to `LLMClient.translate_once` (base_llm_client.py:22) — back-compatible, keeps structural-subtype conformance. | backend-engineer |
| IP-4 | local client | Add `cancel_event=None` kwarg to `OllamaClient.translate_once` (ollama_client.py:442); observe between-block cancellation; mid-read abort best-effort only (no dribble ceiling needed locally). | backend-engineer |
| IP-5 | judge loop | Add `cancel_event: Optional[threading.Event] = None` param AFTER the sibling's `snapshot_cb=None` on `run_judge_loop`/`_run_judge_loop_impl`; thread into `evaluate()`→`_complete()`→client call; add cooperative checks (loop-top, before each per-block `evaluate`, before each per-block re-translate); on set flag return a well-defined `JudgeResult(judge_status="stopped", attempts=<current>)`. | bug-fix-engineer |
| IP-6 | judge call-site | In `job_manager.py` judge hook (L480-518): pass `cancel_event=job.stop_flag` into `run_judge_loop` (L512) and into `_judge.translation_client.translate_once(...)` inside the (sibling-rewritten) `_translate_fn`. Do not re-touch `_skip_judge_provider` (L477) or `cancel_job` (L561). | bug-fix-engineer |
| IP-7 | contracts | Add BR-99 (judge-loop cancellation) + BR-100 (cloud-LLM total-duration ceiling) after sibling's BR-98; 2 Table U rows; env-contract + template + schema row; `judge_status` `stopped` at data-shape:567 and api-contract:51/323; re-run `cdd-kit openapi export --out contracts/api/openapi.yml`. | contract-reviewer |
| IP-8 | tests | Create `tests/test_cloud_total_timeout.py` with dribbling mock-server fixture; add the test classes named in test-plan.md across `test_quality_judge.py`, `test_openai_compatible_client.py`, `test_orchestrator_judge.py`, `test_env_contract.py`. | e2e-resilience-engineer + bug-fix-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| design.md | D1 (two-layer cancellation) | mechanism for AC-1/AC-2 |
| design.md | D2 (ceiling in `_post_completion`, `OPENAI_TOTAL_TIMEOUT_SECONDS`) | IP-1/IP-2 constraint |
| design.md | D3 (`stopped` vs `unavailable`) | IP-5/IP-7 status mapping |
| design.md | "Edit-ordering with siblings" | param order + landing order |
| design.md | Open Risks | Ollama best-effort, session-leak, ceiling calibration |
| docs/adr/0011 | Decision + Consequences | do-not-silently-revert; degrade-not-fail |
| test-plan.md | AC→test mapping table | Test Execution Plan targets |
| test-plan.md | Notes: test-infra gap | new dribbling mock-server fixture |
| test-plan.md | Test Update Contract | no existing enum-list assertion to change |
| change-classification.md | Inferred Acceptance Criteria AC-1..AC-8 | acceptance mapping |
| ci-gates.md | Required Gates table | verification gates (lint/build/unit/contract/resilience) |
| business-rules.md | BR-73, BR-74 | invariants the fix must not break |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `app/backend/clients/openai_compatible_client.py` | edit `_post_completion` (112-156) | wrap blocking `session.post` (121-126) in supervised interruptible wait; add total ceiling from `OPENAI_TOTAL_TIMEOUT_SECONDS`; watch `cancel_event`; on ceiling/cancel close `self._session` and raise a `requests.exceptions.Timeout` so lines 127-131 degrade cleanly. Do not change the `timeout=self._timeout` tuple. Add `cancel_event=None` param. |
| `app/backend/clients/openai_compatible_client.py` | edit `translate_once` (214-230) | add `cancel_event=None` kwarg; forward to `_post_completion`. |
| `app/backend/clients/base_llm_client.py` | edit `translate_once` (22-28) | add `cancel_event: Optional[threading.Event] = None` to Protocol signature; import `threading`. |
| `app/backend/clients/ollama_client.py` | edit `translate_once` (442-470) | add `cancel_event=None` kwarg; best-effort between-block observance; no ceiling. |
| `app/backend/config.py` | add after line 141 region | `OPENAI_TOTAL_TIMEOUT_SECONDS` float env (default 480), commented like `CRITIQUE_TIMEOUT_SECONDS`. |
| `app/backend/services/quality_judge.py` | edit `run_judge_loop` (278-317) | append `cancel_event=None` param AFTER sibling `snapshot_cb`; forward to `_run_judge_loop_impl`; keep never-raise wrapper. |
| `app/backend/services/quality_judge.py` | edit `_run_judge_loop_impl` (319-462) | append `cancel_event=None`; check at loop-top (355), before per-block `evaluate` (359-362), before per-block re-translate (425-438); on set → return `JudgeResult(judge_status="stopped", attempts=attempts, model=self.model, ...)`. |
| `app/backend/services/quality_judge.py` | edit `evaluate` (235-276) + `_complete` (116-121) | thread `cancel_event` into the client `_post_completion`/`_call_ollama` call so an in-flight scoring read is cancellable (AC-1). |
| `app/backend/services/job_manager.py` | edit judge hook (480-518) | pass `cancel_event=job.stop_flag` to `run_judge_loop` (512) and to `translation_client.translate_once(...)` inside `_translate_fn`. Consumes sibling's `translation_client` property; imports `OllamaClient`/`DEFAULT_MODEL` stay (used at 338/617/628). |
| `contracts/business/business-rules.md` | add | BR-99, BR-100 after sibling BR-98; 2 Table U rows (cancel→stopped; ceiling-timeout→unavailable). |
| `contracts/env/env-contract.md` | add row | `OPENAI_TOTAL_TIMEOUT_SECONDS` (backend, application-team, positive float, degrade-not-fail). |
| `contracts/env/.env.example.template` | add row | same var + default. |
| `contracts/env/env.schema.json` | add property | positive-float validator (no existing float precedent — author fresh, per contract-reviewer note). |
| `contracts/data/data-shape-contract.md` | edit line 567 | `judge_status` enum → add `stopped`. |
| `contracts/api/api-contract.md` | edit lines 51, 323 | add `stopped` to judge_status enum; then `cdd-kit openapi export --out contracts/api/openapi.yml`. |
| `tests/test_cloud_total_timeout.py` | create | dribbling/keep-alive mock HTTP server fixture; resilience tests (AC-1/AC-2/AC-8). |
| `tests/test_quality_judge.py` | add classes | `TestCancelDuringInFlightScoring`, `TestCancellationDegradation`, `TestIterationCapUnaffectedByCancellation`. |
| `tests/test_openai_compatible_client.py` | add classes | `TestTotalTimeoutCeilingAdditive`, `TestTotalTimeoutConfig`. |
| `tests/test_orchestrator_judge.py` | add test | `test_cancel_during_judge_phase_reaches_terminal_state`. |
| `tests/test_env_contract.py` | add test | `test_openai_total_timeout_seconds_declared`. |

Note: `tests/test_quality_judge.py` and `tests/test_env_contract.py` are in
Allowed Paths for this change (context-manifest §Required Tests / §Allowed
Paths) — no expansion needed despite test-plan's earlier "context-manifest gap"
note; confirm at implementation time.

## Contract Updates

- API: additive — `stopped` added to `GET /jobs/{id}/judge` `judge_status` enum
  (api-contract.md:51, :323). Re-run `cdd-kit openapi export`.
- CSS/UI: none (Cancel button reused; frontend positive-matches `available`, so
  unknown `stopped` fails safe as not-available — no FE change).
- Env: new `OPENAI_TOTAL_TIMEOUT_SECONDS` (positive float, ~480s default,
  degrade-not-fail) in env-contract.md, `.env.example.template`, `env.schema.json`.
- Data shape: `judge_status` enum gains `stopped` (data-shape-contract.md:567).
- Business logic: BR-99 (judge-loop cancellation reaches in-flight scoring call;
  degrades to `stopped`; BR-73 cap + BR-74 shape preserved), BR-100 (cloud-LLM
  total-duration ceiling additive on `(connect, read)`, degrade-not-fail) +
  2 Table U rows. Numbering assumes sibling lands BR-98 first.
- CI/CD: none new.

## Test Execution Plan

Required phases (floor): collect, targeted, changed-area; contract applies
(contracts touched); resilience applies (bug-fix lane, PR-required Tier 1);
full at CI. Evidence via `cdd-kit test run`; gate validates `test-evidence.yml`.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_cloud_total_timeout.py::test_cancel_event_aborts_blocked_post_mid_read | set `cancel_event` aborts a blocked read promptly, raises timeout-compatible error |
| AC-1 | tests/test_quality_judge.py::TestCancelDuringInFlightScoring::test_stop_flag_set_mid_evaluate_exits_promptly | loop exits without starting new per-block work |
| AC-2 | tests/test_cloud_total_timeout.py::test_ceiling_fires_on_dribbling_never_silent_response | dribbling response aborts at ceiling, not indefinitely |
| AC-3 | tests/test_openai_compatible_client.py::TestTotalTimeoutCeilingAdditive::test_wellbehaved_call_still_bounded_by_connect_read_tuple | per-chunk tuple still enforced |
| AC-3 | tests/test_openai_compatible_client.py::TestTotalTimeoutCeilingAdditive::test_ceiling_absent_from_per_chunk_timeout_tuple | ceiling is additive, not folded into the tuple |
| AC-4 | tests/test_quality_judge.py::TestCancellationDegradation::test_cancel_mid_loop_yields_judge_status_stopped | cancel → `stopped`, well-defined JudgeResult |
| AC-4 | tests/test_quality_judge.py::TestCancellationDegradation::test_ceiling_timeout_yields_judge_status_unavailable_not_stopped | timeout-no-cancel → `unavailable` |
| AC-5 | tests/test_quality_judge.py::TestIterationCapUnaffectedByCancellation::test_max_iterations_cap_enforced_when_cancel_event_none | BR-73 cap intact |
| AC-5 | tests/test_quality_judge.py::TestIterationCapUnaffectedByCancellation::test_attempts_count_not_corrupted_by_mid_loop_cancel | attempts accounting intact |
| AC-6 | tests/test_orchestrator_judge.py::test_cancel_during_judge_phase_reaches_terminal_state | job reaches terminal state, backend alive, no unhandled exception |
| AC-7 | tests/test_openai_compatible_client.py::TestTotalTimeoutConfig::test_env_var_parses_positive_float_default | env parses to positive-float default |
| AC-7 | tests/test_env_contract.py::TestEnvContractDeclared::test_openai_total_timeout_seconds_declared | env var declared in contract |
| AC-8 | tests/test_cloud_total_timeout.py::test_dribbling_socket_regression_repro_matches_live_incident | fails pre-fix, passes post-fix |

Mock boundary: unit/contract tests mock `requests.Session.post`/`get`;
resilience tests use a real local socket (never mock `OpenAICompatibleClient`/
`QualityJudge` internals — tautology risk per test-plan Notes). Cancel-vs-timeout
tests must assert the *distinguishing* signal reaches `_run_judge_loop_impl`.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Do NOT read sibling change dirs (`qa-judge-provider-consistency`,
  `translation-progress-detail-ui`) — hard-forbidden (CER-001/CER-002 rejected).
  Rely on the sibling shape stated here.

## Known Risks

- **Landing order (hard):** `qa-judge-provider-consistency` must land FIRST,
  then this change. Both touch `job_manager.py`'s judge call-site (`_translate_fn`
  ~L493-510) and `quality_judge.py:run_judge_loop`. This plan is written against
  the sibling's finalized shape: `_translate_fn` →
  `_judge.translation_client.translate_once(...)`, cached `translation_client`
  property on `QualityJudge`, and the removed `last_client`/`OllamaClient(
  DEFAULT_MODEL)` fallback (imports themselves stay, used at job_manager L338/
  617/628). Rebase after the sibling before implementing IP-6.
- **`snapshot_cb` composition:** `translation-progress-detail-ui` added an
  additive optional `snapshot_cb=None` to `run_judge_loop`/`_run_judge_loop_impl`
  for observability. This change's `cancel_event=None` is a different, additive
  param appended AFTER it. They should not conflict, but the exact sibling diff
  is unverifiable from here (forbidden read) — confirm param ordering and that
  both keyword-only defaults coexist at actual implementation time.
- **Ceiling calibration:** ~480s default is an unvalidated placeholder; too tight
  aborts legitimate long `stream=False` generations (indistinguishable from a
  dribble hang). Calibrate against the longest legit panjit/DeepSeek call; it is
  env-tunable and documented as such.
- **Session/thread lifecycle:** the interruptible post uses a worker thread +
  session close to abort a read. Must not leak `requests.Session` objects; an
  abandoned daemon worker lingering to socket close is acceptable. Verify session
  lifecycle in review.
- **Ollama parity:** local mid-read interrupt is best-effort only; between-block
  `stop_flag` observance is the asserted guarantee (test-plan Out of Scope).
- **`stopped` fail-safe:** frontend positive-matches `available`; the additive
  `stopped` enum value must not break any exhaustive enum assertion — test-plan
  confirmed none exists (grep-verified), but re-confirm after contract edit.
- **ADR 0011 do-not-revert:** removing the worker-thread wrapper or ceiling "to
  simplify" reintroduces the exact unbounded-hang incident.
