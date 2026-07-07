# CI/CD Gate Plan

## Change ID
qa-judge-provider-consistency

## Required Gates
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---:|---|---|---|
| lint | 1 | yes | pull_request | existing `contract-and-fast-tests` workflow step | pass/fail |
| build | 1 | yes | pull_request | existing build step | pass/fail |
| unit | 1 | yes | pull_request | `pytest tests/ -x -q --tb=short` (existing blanket step — auto-discovers `tests/test_quality_judge.py`/`tests/test_orchestrator_judge.py` extensions) | pass/fail |
| contract | 1 | yes | pull_request | `cdd-kit validate --contracts` (existing; checks new BR-98 + Table U row) | pass/fail |
| integration | 1/3 | yes | pull_request | covered by the same blanket pytest step (`test_orchestrator_judge.py`) | pass/fail |
| e2e-critical | 1 | no | — | not applicable, backend-only | — |
| visual | 2 | no | — | no UI surface | — |
| data-boundary | 1 | no | — | not applicable | — |
| resilience | 1/3 | no | — | not applicable to this change (resilience is the sibling `qa-judge-hang-recovery`'s scope) | — |
| fuzz/monkey | 1/3 | no | — | not applicable | — |
| stress | 4/5 | no | — | not applicable | — |
| soak | 4/5 | no | — | not applicable | — |

## New Workflow Changes
None. Existing blanket `pytest tests/ -x -q --tb=short` step covers all new/
extended test files with zero workflow edits. `cdd-kit validate --contracts`
already validates `business-rules.md` structure, so BR-98's addition is
caught automatically. `openapi export --check` is not implicated (no API
schema change).

## Required Check Policy
`unit`, `integration`, and `contract` gates are PR-required (existing
policy, unchanged).

## Informational Gate Promotion Policy
Not applicable — no new informational gate introduced.

## Rollback Policy
Low risk: additive client-construction change with no schema/API surface. A
revert restores the previous (buggy) `last_client` fallback behavior with no
data-migration concern.

## Artifact Retention
Not applicable.

## Merge Eligibility Decision
Standard: existing `unit`/`integration`/`contract` PR-required gates passing
is sufficient; sequence this change's merge BEFORE `qa-judge-hang-recovery`'s
per both changes' Known Risks sections.

## Notes
No `ci-cd-gatekeeper` agent was required for this change (change-classifier:
`CI/CD: none`) — populated directly from the existing, unmodified gate
policy. See test-plan.md for exact test node IDs.
