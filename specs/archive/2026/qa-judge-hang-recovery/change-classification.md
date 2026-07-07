# Change Classification

No atomic-split trigger fires (this is one coherent incident fix — cancel +
bound the judge hang — not multiple unrelated features/surfaces; contract
touch is 2-3 of 6, task count is modest).

## Change Types
- primary: bug-fix (QA/judge-phase hang — performance/liveness), business-logic-change (judge cancellation + wall-clock ceiling semantics — promotes the bug-fix so the contract path is forced)
- secondary: env-change (likely new `JUDGE_TOTAL_TIMEOUT_S`-style config), reliability/resilience-hardening (cloud LLM client total-duration guard)

## Lane
- bug-fix

Note on promotion: this is a genuine symptom-driven live incident, so the
bug-fix lane (reproduction, root cause, failing test, regression test) is
retained for its evidence discipline. But because the fix forces contract
changes (business-rules for cancellation/timeout behavior, env-contract for
the ceiling config, possibly data-shape/api for a judge status value), the
contract path is forced via the `business-logic-change`/`env-change` primary
types and a mandatory `contract-reviewer`.

## Bug Symptom Type
- performance (30+ min judge-phase hang / no wall-clock bound / no cancellation — liveness failure)

## Diagnostic Only
- no (root cause already investigated this session with line-level evidence; this is a behavior fix, not instrumentation)

## Bug Evidence
- symptom: job hung 30+ min in the LLM-judge phase; UI Cancel had no effect; recovery required killing the whole backend process
- expected: (a) Cancel from the UI stops a job that has entered the judge phase; (b) a cloud LLM call is bounded by an actual wall-clock ceiling and cannot hang indefinitely
- actual: `run_judge_loop`/`_run_judge_loop_impl` (`quality_judge.py:278-444`) never checks `job.stop_flag`; `requests` `(connect,read)` tuple measures inter-chunk gap, not total duration, so a dribbling/keep-alive stream hangs past the documented "≤7 min" bound
- reproduction status: observed in a live production incident this session (PID 3369, `ss -tnp` showed two ESTABLISHED panjit sockets unchanged 30+ min, backend CPU advanced ~3s over 25 min, `job.status_detail` frozen); needs a deterministic automated repro (simulated trickle/keep-alive socket + a job entering the judge loop)
- hypotheses: (1) read-timeout resets on each received byte so a slow-dribble stream never trips it; (2) no `stop_flag` reach into judge loop means cooperative cancellation cannot fire mid-scoring-call
- root cause pointer: `quality_judge.py:278-444` (no cancellation check) + `openai_compatible_client.py:28-31,112-135` (`timeout=self._timeout` per-chunk only) + `base_llm_client.py` (bare `Protocol`, no shared retry/timeout base despite CLAUDE.md)
- regression evidence required: must not regress BR-73 (iteration cap enforced unconditionally) or BR-74 (graceful degradation → `judge_status="unavailable"`, job still completes); must not weaken the existing `(connect,read)` per-chunk protection

## Risk Level
- high

## Impact Radius
- cross-module (job_manager cancellation path + quality_judge loop + shared cloud LLM client; the client-level total-timeout guard, if chosen, affects ALL cloud calls including main translation)

## Tier
- 1

Rationale: high risk (concurrency/`threading.Event` cancellation correctness
+ network timeout semantics on the shared LLM client used by the whole
translation pipeline; a bad ceiling could abort legitimate long calls, a bad
`stop_flag` path could leave `job.judge` half-written) across module
boundaries, tied to a real production incident. Classified upward per "when
in doubt, classify upward."

## Architecture Review Required
- yes
- reason: three non-obvious design decisions explicitly deferred to
  spec-architect — (1) cancellation granularity mechanism (cooperative check
  inside the blocking call's timeout path vs. total-timeout-as-cancellation
  with `stop_flag` between blocks — a between-iterations-only check would NOT
  have caught this hang, which was inside a single scoring call); (2) whether
  the wall-clock guard lives in `openai_compatible_client.py` (fixes all
  cloud calls, wider blast radius) or is scoped to the judge call path; (3)
  the ceiling's shape/default and whether a new explicit `cancelled` judge
  state is introduced vs. reusing `unavailable`.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

STOP after `implementation-plan.md` this pass — no `bug-fix-engineer`/`backend-engineer` implementation this pass.

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | change-request already documents current behavior with line-level Findings A/B |
| proposal.md | no | product intent unambiguous |
| spec.md | no | no separate user-facing behavior investigation beyond design/impl-plan |
| design.md | yes | Architecture Review Required = yes; spec-architect must decide cancellation mechanism, timeout placement, ceiling shape, and cancelled-state semantics |
| qa-report.md | no | use agent-log/qa-reviewer.yml unless blocking findings |
| regression-report.md | no | regression scope (BR-73/74, per-chunk timeout) captured in test-plan |
| visual-review-report.md | no | no UI/visual change |
| monkey-test-report.md | no | not applicable |
| stress-soak-report.md | no | single hung call, not load-driven; resilience test covers it |

## Required Contracts
- API: likely none new — flag for contract-reviewer only IF spec-architect introduces a new `judge_status` enum value (e.g. `cancelled`)
- CSS/UI: none (existing Cancel button reused)
- Env: likely yes — a wall-clock ceiling config (e.g. `JUDGE_TOTAL_TIMEOUT_S`) following the repo's `os.environ.get(...)` pattern (exact form deferred to spec-architect)
- Data shape: possible — if a new explicit `cancelled` state is added to `JudgeResult`/`job.judge` (deferred to design)
- Business logic: yes — extend/clarify BR-74 (graceful degradation must cover cancellation and total-timeout) and add a rule for the wall-clock ceiling + judge-loop cancellation guarantees, without weakening BR-73
- CI/CD: none new

## Required Tests
- unit: `stop_flag` cooperative check inside `run_judge_loop`/`_run_judge_loop_impl` stops promptly and returns a well-defined `JudgeResult`; wall-clock guard fires against a mocked slow/dribbling response
- contract: BR-73/BR-74 conformance; env var presence/validation; data/api judge-status shape if a new state is added
- integration: `job_manager.cancel_job()` → job in judge phase exits cleanly with well-defined `job.judge`, no unhandled exception, backend stays alive
- E2E: optional, covered by integration + resilience
- resilience: inject a hanging/keep-alive-trickle socket (never fully silent) and assert the wall-clock ceiling aborts and BR-74 degradation holds; assert Cancel interrupts an in-flight judge call, not just between iterations
- data-boundary: none (unless a new judge_status value is added)
- visual/fuzz/stress: none
- soak: consideration — a lightweight duration assertion may fold into the resilience test rather than a separate soak suite

## Required Agents
This pass (plan-only, STOP after implementation-plan.md):
- spec-architect — writes `design.md`; resolves the three deferred design decisions; coordinates edit-region ordering with the depends-on sibling
- contract-reviewer — reviews business-rules (BR-73/74), env-contract, and any data/api judge-status change
- test-strategist — writes `test-plan.md`, maps ACs → tests, ensures a failing repro test precedes the fix
- implementation-planner — turns design + contracts + tests into `implementation-plan.md`; this is the stop point
- qa-reviewer — release-readiness / evidence sign-off

Required for the eventual implementation pass (NOT invoked this pass):
`bug-fix-engineer`, `backend-engineer`, `e2e-resilience-engineer`, `stress-soak-engineer`.

## Inferred Acceptance Criteria
- AC-1: Setting `job.stop_flag` (UI Cancel) while a job is in the judge phase causes `run_judge_loop`/`_run_judge_loop_impl` to stop promptly — including interrupting an in-flight scoring call, not only between judge iterations.
- AC-2: A cloud LLM call that dribbles keep-alive/partial bytes (never fully silent) is bounded by a wall-clock total-duration ceiling and aborts instead of hanging indefinitely.
- AC-3: The wall-clock ceiling is additive on top of the existing `(connect_timeout, read_timeout)` tuple and does not weaken the per-chunk protection.
- AC-4: On cancellation or total-timeout mid-judge, BR-74 graceful degradation holds — the job completes with a well-defined `job.judge` state (`unavailable` or an explicit `cancelled`), never a half-written result or unhandled exception, and the backend process stays alive.
- AC-5: BR-73 iteration cap (`JUDGE_MAX_ITERATIONS`) remains enforced unconditionally; cancellation/timeout does not bypass or corrupt iteration accounting.
- AC-6: A hung judge-phase job is fully recoverable in-app via the existing Cancel button, with no need to kill the backend process.
- AC-7: The timeout ceiling is configurable following the repo's `os.environ.get(...)` pattern with a sane default, documented in the env contract, `.env.example.template`, and `env.schema.json`.
- AC-8: A deterministic automated reproduction (simulated trickle/keep-alive socket + a job entering the judge loop) exists and fails before the fix, passes after.

## Tasks Not Applicable
- not-applicable: 1.4, 2.2, 2.6, 3.4, 4.2, 4.4, 5.1, 5.2

(2.2 CSS/UI + 2.6 CI/CD contract: no UI/pipeline contract change. 3.4
data-boundary/monkey: no import/export boundary. 4.2 Frontend: existing
Cancel button reused, no FE change. 4.4 CI/CD workflows: env-var validation
covered by existing gates. 5.1 UI/UX + 5.2 Visual review: no UI surface.
Task 1.3 REMAINS applicable.)

## Clarifications or Assumptions
- Wall-clock ceiling likely belongs at the client level (`openai_compatible_client.py`) for the broader benefit, but flagged as a spec-architect decision to avoid unexpectedly expanding into `qa-judge-provider-consistency`/`batch-critique-qe-scoring` territory. Confirm before implementation.
- Data-shape and API changes are conditional on whether a new explicit `cancelled` judge state is introduced — spec-architect to decide `cancelled` vs. reusing `unavailable`.
- `depends-on: qa-judge-provider-consistency` is an edit-ordering/rebase dependency, not a classification blocker — land/rebase this change after it.
- CER-001/CER-002 requested reads of sibling changes' planning artifacts
  (`qa-judge-provider-consistency`, `translation-progress-detail-ui`) — per
  `.cdd/context-policy.json`'s hard `forbiddenPaths` baseline
  (`specs/changes/*`), cross-change reads are NEVER approvable regardless of
  CER status. Main Claude will brief spec-architect/implementation-planner
  directly with the relevant sibling decisions instead of granting these
  reads (see context-manifest.md).
