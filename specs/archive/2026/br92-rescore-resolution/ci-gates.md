# CI/CD Gate Plan

## Change ID
br92-rescore-resolution

## Required Gates
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---:|---|---|---|
| lint | 1 | yes | pull_request | existing `contract-and-fast-tests` workflow step | pass/fail |
| build | 1 | yes | pull_request | existing build step (no build-affecting change) | pass/fail |
| unit | 1 | yes | pull_request | `pytest tests/ -x -q --tb=short` (existing blanket step, unscoped — auto-discovers test-plan.md's file changes) | pass/fail |
| contract | 1 | yes | pull_request | `cdd-kit validate --contracts` (existing) | pass/fail |
| integration | 1/3 | no | — | not applicable (retire path, no integration surface) | — |
| e2e-critical | 1 | no | — | not applicable | — |
| visual | 2 | no | — | no UI surface | — |
| data-boundary | 1 | no | — | not applicable | — |
| resilience | 1/3 | no | — | not applicable (retire path) | — |
| fuzz/monkey | 1/3 | no | — | not applicable | — |
| stress | 4/5 | no | — | not applicable | — |
| soak | 4/5 | no | — | not applicable | — |

## New Workflow Changes
None. The existing blanket `pytest tests/ -x -q --tb=short` step in
`.github/workflows/contract-driven-gates.yml`'s `contract-and-fast-tests` job
auto-discovers the deleted/inverted test functions in
`tests/test_quality_evaluation.py` and `tests/test_env_contract.py` with zero
workflow edits. `cdd-kit validate --contracts` already checks
`business-rules.md`/`env-contract.md`/`data-shape-contract.md` consistency —
sufficient to catch a partial/incomplete retirement (a dangling verified-by
reference or a stale claim left behind).

## Required Check Policy
`unit` and `contract` gates are PR-required (existing policy, unchanged by
this deletion-only change).

## Informational Gate Promotion Policy
Not applicable — no new informational gate introduced.

## Rollback Policy
Trivial: this is a contract/config/test deletion with no runtime behavior
change (the removed code path never executed). Revert is a straight git
revert with no data-migration or cache-invalidation concern.

## Artifact Retention
Not applicable — no new artifact type produced.

## Merge Eligibility Decision
Standard: existing `unit` + `contract` PR-required gates passing is
sufficient for this change; no additional manual/nightly gate needed.

## Notes
No `ci-cd-gatekeeper` agent was required for this change (change-classifier:
`CI/CD: none`) — this file is populated directly from the existing,
unmodified gate policy per `contracts/ci/ci-gate-contract.md`, confirming
zero workflow edits are needed. See test-plan.md for the exact test node IDs.
