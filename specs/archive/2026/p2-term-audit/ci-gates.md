# CI/CD Gate Review

## Change ID

p2-term-audit

## Tier Floor Override

`tier-floor-override: 2`

Rationale: The change-classification and change-request contain "integration" vocabulary that `cdd-kit gate` may misfire on, spuriously elevating the tier floor to 3+. "Integration" in this change refers exclusively to in-process post-translate hook wiring (the `post_translate_hook` seam used by `quality_evaluator.py`) and to integration-level tests that run against real module boundaries — not to cross-system network integration, external auth, DDL migration, or a new HTTP route. There is no new env secret, no `ALTER TABLE`, no new API endpoint, and no cross-service boundary. Tier 2 is correct.

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | push / PR | `cdd-kit validate --contracts` | exit code 0 |
| change-gate | 1 | yes | push / PR | `cdd-kit gate p2-term-audit` | exit code 0 |
| openapi-sync | 1 | yes | push / PR | `cdd-kit openapi export --check --out contracts/api/openapi.yml` | exit code 0 (no drift) |
| unit-tests | 1 | yes | push / PR | `pytest tests/ -x -q --tb=short` | junit XML; covers AC-1 through AC-8 (see test-plan.md) |
| layout-detector-dependency-gate | 2 | yes | PR | `! grep -E "(ultralytics\|onnxruntime-gpu)" app/backend/requirements.txt app/backend/environment.yml` | exit code 0 (no forbidden packages) |

Gates above are all existing gates in `.github/workflows/contract-driven-gates.yml`. No new gate command or workflow job is required for this change; `unit-tests` covers unit, contract, integration, and data-boundary families in a single `pytest tests/` run (see change-classification.md §Required Tests).

## ci-gate-contract.md Changes

None. The existing `contract-validate`, `change-gate`, and `unit-tests` gates cover all required test families (unit, contract, integration, data-boundary) for this change. No new row is added to `contracts/ci/ci-gate-contract.md`.

## Workflow Changes Applied

Updated `.github/workflows/contract-driven-gates.yml`:

1. **Change gate step** (`contract-and-fast-tests` job): `run:` changed from `echo "No active change gates — all changes archived."` to `cdd-kit gate p2-term-audit`.
2. **Header comment**: active change updated from `none (archived: ...)` to `p2-term-audit (archived: ...)`.

No new jobs or steps added.

## Informational / Manual Gates

None. No flaky quarantine, nightly real-infra gate, weekly soak, or manual dispatch gate applies to this change (see change-classification.md §Tasks Not Applicable 6.3, 6.4).

## Promotion Policy

If a required gate produces non-deterministic results across runner versions, the affected sub-check must be quarantined to an informational sub-job per `contracts/ci/ci-gate-contract.md §Informational Gate Promotion Policy`. The parent gate remains required. No such quarantine is anticipated for this change.

## Rollback Policy

This change is additive (new `services/term_audit.py`, new `terminology_audit` field on the qa-report data shape, new business rule). Rollback = revert the PR. No DDL migration, no new env secret, no new HTTP route — no additional rollback procedure required.

## Merge Eligibility

mergeable when all five required gates above pass (contract-validate, change-gate, openapi-sync, unit-tests, layout-detector-dependency-gate).
