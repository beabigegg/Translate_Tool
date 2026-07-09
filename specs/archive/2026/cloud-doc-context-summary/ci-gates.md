# CI/CD Gate Plan

## Change ID
cloud-doc-context-summary

## Required Gates for This Change
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contracts-validate | 1 | yes | pull_request | `cdd-kit validate --contracts` (contract-and-fast-tests job, `.github/workflows/contract-driven-gates.yml`) | job pass/fail |
| unit+integration+resilience (blanket) | 1 | yes | pull_request | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` (contract-and-fast-tests job — auto-covers new `tests/test_orchestrator_context_detection.py`, all test-plan.md rows AC-1..AC-7) | test-results/junit.xml (14d) |
| full-regression | 2 | informational | pull_request | `pytest tests/ -q --tb=short --junitxml=test-results/full-regression.xml` (full-regression job) | full-regression.xml (14d) |
| e2e (real-PANJIT 8D-PDF) | manual | no (not automated) | manual re-run | see change-request.md "Observable success criterion" | log line review |

No Tier 0/3/4/5 gates apply: no local-only fast gate is defined separately from
the PR gate, no nightly real-infra dependency (mocked LLM clients only, no
torch/COMET per test-plan.md Notes), no weekly soak (one extra summary call is
not a load profile per change-classification.md), no manual production-like
dispatch beyond the existing `workflow_dispatch`/`schedule` triggers already on
the workflow.

## Workflow Changes Applied
None. No `.github/workflows/*` file is added or edited, and no new job/step is
added to `contract-driven-gates.yml`. Rationale:
- The change is backend-only, adds no dependency, lockfile, DB migration, API
  endpoint, or secret (change-classification.md Risk/Impact/Required Contracts).
- The new test file `tests/test_orchestrator_context_detection.py` is picked up
  automatically by the existing catch-all `pytest tests/ -x -q ...` step in the
  `contract-and-fast-tests` job (line ~134) and by `full-regression`'s
  `pytest tests/ -q ...` — no new targeted-test step is needed because all new
  tests use mocked LLM clients / `requests.Session.post`, require no torch/COMET,
  and are not flaky, slow, or credential-gated enough to warrant isolation.
- `cdd-kit validate --contracts` (already required) picks up the business-rules
  (0.27.0) and env-contract (0.17.0) bumps for this change with no config change.
- No new env var, secret, or Deployment Sync Policy entry is introduced (the env
  touch is descriptive text on two existing vars), so the existing env-sync grep
  steps for other changes are untouched and none is added for this one.

## Promotion Policy
Stays at Tier 1/2 as scoped; no promotion criteria pending. If a future change
adds a JSON I/O step (Step 3) or a new provider-specific network fixture, that
change's ci-gates.md decides whether a dedicated targeted-test step is warranted
then — not retroactively here.

## Rollback Policy
`git revert` of the merge commit. Safe because behavior is fully flag-gated by
`CONTEXT_DETECTION_ENABLED` and `QWEN_CONTEXT_FLOW_ENABLED` (both existing,
default unchanged) and degrades gracefully on cloud-summary failure/empty
(AC-5) — no migration, no schema, no irreversible state to unwind. No feature
flag needs manual disable post-revert.

## Merge Eligibility
mergeable — contingent on `contract-and-fast-tests` passing (includes the
blanket pytest run covering the new test file) and `cdd-kit validate --contracts`
passing against the bumped business-rules/env contracts. `full-regression` is
informational only per existing tier-2 policy and does not block merge.
