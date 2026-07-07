# CI/CD Gate Plan

## Change ID
qa-judge-hang-recovery

## Required Gates
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---:|---|---|---|
| lint | 1 | yes | pull_request | existing `contract-and-fast-tests` workflow step | pass/fail |
| build | 1 | yes | pull_request | existing build step | pass/fail |
| unit | 1 | yes | pull_request | `pytest tests/ -x -q --tb=short` (existing blanket step — auto-discovers `tests/test_quality_judge.py`, `tests/test_openai_compatible_client.py`, `tests/test_env_contract.py` extensions) | pass/fail |
| contract | 1 | yes | pull_request | `cdd-kit validate --contracts` (existing; checks new BR-99/BR-100 + Table U rows, new env var docs) | pass/fail |
| integration | 1/3 | yes | pull_request | covered by the same blanket step (`tests/test_orchestrator_judge.py`) | pass/fail |
| e2e-critical | 1 | no | — | not applicable, backend-only, existing Cancel button reused | — |
| visual | 2 | no | — | no UI surface | — |
| data-boundary | 1 | no | — | not applicable (no exhaustive enum assertion exists) | — |
| resilience | 1/3 | yes | pull_request | NEW `tests/test_cloud_total_timeout.py` (dribbling mock-server fixture) — same blanket pytest step covers it, zero workflow edits needed | pass/fail |
| fuzz/monkey | 1/3 | no | — | not applicable | — |
| stress | 4/5 | no | — | folded into the resilience test above, no separate soak suite | — |
| soak | 4/5 | no | — | folded into the resilience test above | — |

## New Workflow Changes
None. The existing blanket `pytest tests/ -x -q --tb=short` step in
`contract-and-fast-tests` auto-discovers the new `tests/test_cloud_total_timeout.py`
file with zero workflow edits — it is unscoped (runs the whole `tests/`
directory), so a brand-new test module needs no CI registration.
`cdd-kit validate --contracts` already validates business-rules.md/
env-contract.md/data-shape-contract.md/api-contract.md structure, catching
BR-99/BR-100 and the new `judge_status="stopped"` enum value's contract
consistency automatically. `openapi export --check` (already wired) will
catch a stale `openapi.yml`/`openapi.json` if the `GET /jobs/{id}/judge`
schema edit is made without regenerating the export.

## Required Check Policy
`unit`, `integration`, `contract`, and `resilience` gates are PR-required for
this change — resilience is promoted to required (not the usual
nightly/informational default) because this change's entire purpose is
fixing a resilience defect (the live incident); shipping without the
regression test running on every PR would defeat the change's own point.

## Informational Gate Promotion Policy
Not applicable — resilience is promoted directly to PR-required (see above),
not staged through an informational period.

## Rollback Policy
Medium risk (per change-classification's Tier 1 / high risk rating): the
total-timeout ceiling change affects the shared `openai_compatible_client.py`
used by ALL cloud calls, not just judge. Revert plan: the new
`OPENAI_TOTAL_TIMEOUT_SECONDS` env var is additive with a safe default (~480s,
above the existing 420s connect+read worst case) — reverting removes the
ceiling entirely, restoring the pre-fix (unbounded-if-dribbling) behavior,
which is the exact regression being fixed. This should be treated as a
roll-forward-preferred change, not casually reverted.

## Artifact Retention
Not applicable — no new artifact type produced.

## Merge Eligibility Decision
This change must merge AFTER `qa-judge-provider-consistency` (both touch
`job_manager.py`'s judge call site and `quality_judge.py:run_judge_loop`) —
see both changes' Known Risks sections. Standard `unit`/`integration`/
`contract`/`resilience` PR-required gates otherwise sufficient.

## Notes
No `ci-cd-gatekeeper` agent was required for this change per the classifier
(`CI/CD: none` — no workflow file edits needed), but `resilience` is
elevated to PR-required given the bug-fix lane's regression-test
discipline. See test-plan.md for exact test node IDs and the flagged new
test-infrastructure piece (dribbling mock-server fixture, no prior
precedent in this repo).
