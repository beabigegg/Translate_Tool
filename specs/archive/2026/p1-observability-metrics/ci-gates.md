---
change-id: p1-observability-metrics
schema-version: 0.1.0
last-changed: 2026-06-17
tier: 2
---

# CI/CD Gate Plan: p1-observability-metrics

## Required Gates (block merge)

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| contract-validate | 1 | yes | push, pull_request | `cdd-kit validate --contracts` in `contract-and-fast-tests` job | none |
| openapi-sync | 1 | yes | push, pull_request | `cdd-kit openapi export --check --out contracts/api/openapi.yml` in `contract-and-fast-tests` job | none |
| secret-scan | 1 | yes | push, pull_request | grep pattern in `contract-and-fast-tests` job | none |
| unit + contract + integration tests | 1 | yes | push, pull_request | `pytest tests/ -x -q` in `contract-and-fast-tests` job; covers test-plan.md rows AC-1..AC-7 | `test-results/junit.xml` (14 days) |

## Informational Gates (PR, non-blocking)

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| full-regression | 2 | no (escalates if new failures) | pull_request | `pytest tests/ -q` in `full-regression` job | `test-results/full-regression.xml` (14 days) |
| env-template-check | 2 | no | pull_request | grep in `full-regression` job | none |

## Nightly / Weekly / Manual Gates

None required. Per change-classification.md: no external store, no live provider, no threading, no E2E surface. Stress/soak explicitly deferred (see `change-classification.md` Tasks Not Applicable 3.5).

## Workflow Changes Applied

None. The existing `contract-and-fast-tests` job in `.github/workflows/contract-driven-gates.yml` already runs all four required gates above on every push and pull_request. The `full-regression` job already provides informational Tier 2 coverage on PRs.

A new `cdd-kit gate p1-observability-metrics` entry is NOT added to the workflow. Rationale: `cdd-kit gate <id>` validates per-change artifact completeness, not functional correctness. All functional coverage for this change is provided by `cdd-kit validate --contracts` (contract drift) and `pytest tests/` (AC-1..AC-7 per test-plan.md). Adding a redundant change-gate step would duplicate signals without reducing risk.

## OpenAPI Regeneration Requirement

After editing `contracts/api/api-contract.md`, run:

```
cdd-kit openapi export --out contracts/api/openapi.yml
```

Commit the updated `contracts/api/openapi.yml` in the same PR. The `openapi-sync` gate (`cdd-kit openapi export --check`) will fail the `contract-and-fast-tests` job if `openapi.yml` is stale. This is the highest-likelihood failure mode for this change.

## Promotion Policy

This change clears gate when, on the PR:
1. `contract-and-fast-tests` passes (all four required gates green).
2. `full-regression` passes or any new failures are triaged and recorded in `agent-log/qa-reviewer.yml` with owner and exit date.

## Rollback Policy

Additive change only (new endpoint, new module, increment hooks). Rollback is a revert of the PR. No migration, no external state, no persistence — counters are in-process and disappear on process restart. No rollback script required.

## Merge Eligibility

mergeable when `contract-and-fast-tests` is green and `openapi.yml` is committed and in-sync.
