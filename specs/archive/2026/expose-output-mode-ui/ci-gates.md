---
change-id: expose-output-mode-ui
schema-version: 0.1.0
last-changed: 2026-06-27
tier: 3
---

# CI/CD Gate Review: expose-output-mode-ui

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|---:|---|---|---|
| cdd-kit-gate | 1 | yes | PR / push | `cdd-kit gate expose-output-mode-ui` | exit code 0 |
| backend-tests | 1 | yes | PR / push | `pytest tests/ -x -q --tb=short` | junit XML; `tests/test_output_mode_api.py` guards AC-5 |
| frontend-output-mode-test | 1 | yes | PR | `cd app/frontend && npm test` | exit code 0; covers test-plan.md AC-1 AC-2 AC-3 |

## Workflow Changes Applied

- `.github/workflows/contract-driven-gates.yml` line 3 comment: added `expose-output-mode-ui` to active change list.
- `.github/workflows/contract-driven-gates.yml` step "Change gate" in `contract-and-fast-tests` job: replaced `echo "No active change gates."` with `cdd-kit gate expose-output-mode-ui`.
- `.github/workflows/contract-driven-gates.yml`: added new job `expose-output-mode-ui-gate` (PR-triggered, Tier 1) running two steps:
  1. `cdd-kit gate expose-output-mode-ui` — validates ci-gates.md format, contract conformance, task completion.
  2. `cd app/frontend && npm test` — component tests for selector labels, default value, and payload wiring (test-plan.md AC-1 AC-2 AC-3). Blocks merge until test-strategist adds vitest + `@testing-library/react` and the test file.

## Promotion Policy

All three Tier 1 gates must pass before a PR is eligible to merge:

1. `cdd-kit gate expose-output-mode-ui` — change-state and contract conformance.
2. `pytest tests/` — full backend suite green; `tests/test_output_mode_api.py` confirms no backend regressions (AC-5).
3. `cd app/frontend && npm test` — frontend component assertions for selector rendering, default, and payload wiring (AC-1 AC-2 AC-3).

Existing Tier 2 informational gates (full-regression, golden-sample-regression, text-expansion-benchmark, renderer-equivalence, layout-detector-dependency-gate) run unchanged on all PRs.

No Tier 3/4/5 gates are introduced; this change carries no real-infrastructure, soak, or stress scope.

## Rollback Policy

Frontend-only change (no backend, no database, no env var additions). Rollback is a single-commit revert of `app/frontend/src/pages/TranslatePage.jsx` and the API client payload update. No data repair or migration step required. Safe to revert at any point before or after deploy.

## Merge Eligibility

blocked until all three Tier 1 gates pass: `cdd-kit-gate`, `backend-tests`, `frontend-output-mode-test`.
