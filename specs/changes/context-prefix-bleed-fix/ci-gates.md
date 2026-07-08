# CI/CD Gate Plan

## Change ID
context-prefix-bleed-fix

## Required Gates
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---:|---|---|---|
| lint | 1 | yes | pull_request | existing `contract-and-fast-tests` workflow (unchanged) | pass/fail |
| build | 1 | yes | pull_request | existing `contract-and-fast-tests` workflow (unchanged) | pass/fail |
| unit | 1 | yes | pull_request | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` (existing blanket step in job `contract-and-fast-tests`; auto-discovers new `tests/test_context_prefix_bleed.py` + edited `tests/test_context_window_segments.py`/client tests) | junit XML |
| contract | 1 | yes | pull_request | `cdd-kit validate --contracts` (existing step in `contract-and-fast-tests`; validates BR-78 edit, business-rules.md 0.25.0→0.25.1) | exit code 0 |
| integration | 1 | yes | pull_request | same blanket pytest step in `contract-and-fast-tests` — fake-client `translate_merged_paragraphs`/`translate_blocks_batch` integration test (AC-2, AC-3) is collected automatically | pass/fail |
| e2e-critical | 1 | no | — | not applicable, backend prompt-assembly only, no UI/API surface | — |
| visual | 2 | no | — | no UI surface | — |
| data-boundary | 1 | no | — | not applicable (change-classification.md Tasks Not Applicable 3.4) | — |
| resilience | 1/3 | no | — | not applicable (change-classification.md Tasks Not Applicable 3.3) | — |
| fuzz/monkey | 1/3 | no | — | not applicable | — |
| stress | 4/5 | no | — | not applicable | — |
| soak | 4/5 | no | — | not applicable | — |
| full-regression | 2 | informational | pull_request | existing job `full-regression` (`pytest tests/ -q --tb=short --junitxml=test-results/full-regression.xml`) | junit XML |

## New Workflow Changes
None. `.github/workflows/contract-driven-gates.yml` job `contract-and-fast-tests`
already runs `cdd-kit validate --contracts` and the blanket `pytest tests/ -x -q
--tb=short` step, which auto-collects the new reproduction test
(`tests/test_context_prefix_bleed.py`) and the edited assertions in
`tests/test_context_window_segments.py`/client tests with zero workflow edits.
`full-regression` (Tier 2, informational, PR-triggered) covers the same suite
non-blocking. No new job, secret, or `ci-gate-contract.md` gate-inventory row is
needed — task 2.6 stays skipped per change-classification.md.

## Required Check Policy
`contract-and-fast-tests` (job name, PR-required) is the binding check for this
change; `full-regression` (job name) remains informational per existing policy.
No policy change.

## Informational Gate Promotion Policy
Not applicable — no new informational gate introduced; `full-regression` keeps
its existing informational status.

## Rollback Policy
Behavior-only bug-fix, no persisted state/schema/API surface. `system_context`
is an additive optional kwarg (`=None` default) on `translate_once` across all
three LLM clients, so a single `git revert` of the diff fully restores prior
behavior with no data-migration or client-compat concern. An operational
kill-switch already exists independent of this change: `CONTEXT_WINDOW_SEGMENTS=0`
disables context injection with no code change (design.md Migration/Rollback).

## Artifact Retention
No new artifacts. Existing `test-results/junit.xml` / `full-regression.xml`
retention (14 days, set in workflow) is unchanged.

## Merge Eligibility Decision
mergeable — the existing PR-required `contract-and-fast-tests` job (includes
`cdd-kit validate --contracts` for the BR-78 edit and the blanket pytest run for
the reproduction + integration tests) is sufficient. No new gate, workflow file,
or `contracts/ci/ci-gate-contract.md` edit is required for this change.

## Notes
Test node IDs and the AC → test mapping live in test-plan.md (AC-1..AC-7); this
file tracks gate policy only. Any `translate_once` test double reached via the
paragraph path must be updated in the same change per design.md "Test doubles
to update" — an implementation/test-strategist concern, not a gate.
