# CI/CD Gate Plan

## Change ID
download-url-in-jobstatus

## Required Gates
| gate name | tier | required | trigger | command / workflow | artifact |
|---|---:|---|---|---|---|
| contract-validation | 1 | required | pull_request, push | `cdd-kit validate --contracts` | pass/fail (stdout) |
| openapi-sync | 1 | required | pull_request, push | `cdd-kit openapi export --check --out contracts/api/openapi.yml` | pass/fail (stdout) |
| targeted-unit-tests | 1 | required | pull_request, push | `pytest tests/test_jobstatus_download_url.py -x -q --tb=short` | junit XML (14 days) |
| full-test-suite | 1 | required | pull_request, push | `cdd-kit gate download-url-in-jobstatus` (local pre-PR) / `.github/workflows/contract-driven-gates.yml` job `contract-and-fast-tests` | junit XML (14 days) |
| secret-scan | 1 | required | pull_request, push | grep pattern in `contract-driven-gates.yml` step "Secret scan" | pass/fail |
| full-regression | 2 | informational | pull_request | `.github/workflows/contract-driven-gates.yml` job `full-regression` | junit XML (14 days) |

## Workflow Changes Applied
No changes to `.github/workflows/contract-driven-gates.yml` are required for this change.

Rationale: This is a Tier 3 (module-level, low-risk) bug fix. The existing `contract-and-fast-tests` job already runs `cdd-kit validate --contracts`, the OpenAPI sync check (`cdd-kit openapi export --check`), and `pytest tests/ -x -q`. The new test file `tests/test_jobstatus_download_url.py` is automatically picked up by `pytest tests/`. No new change-gate row is added to `contract-driven-gates.yml` (Tier 3 policy: no change-gate row required).

Post-implementation prerequisite (not a workflow change — developer action):
After `schemas.py` and `routes.py` are updated, run:
```
cdd-kit openapi export --out contracts/api/openapi.yml
```
and commit the regenerated file. The CI `openapi-sync` gate will fail on a stale `openapi.yml` (see CLAUDE.md promoted lesson and `implementation-plan.md` post-implementation step).

## Promotion Policy
- All Tier 1 required gates must be green before merge.
- The `full-regression` (Tier 2) job is informational; a new failure introduced by this change escalates it to a merge blocker.
- No Tier 3 nightly gate is configured for this change (low-risk, module-level scope).
- No `contract-driven-gates.yml` change-gate row is added (Tier 3 policy).

## Rollback Policy
- Revert `app/backend/api/schemas.py` and `app/backend/api/routes.py` to their pre-change state.
- Regenerate `contracts/api/openapi.yml` (`cdd-kit openapi export --out contracts/api/openapi.yml`) and commit.
- No migration, infrastructure state, or external system is affected; revert is zero-risk.

## Merge Eligibility
mergeable when:
1. `contract-and-fast-tests` (contract-validation + openapi-sync + targeted-unit-tests + full-test-suite + secret-scan) is green.
2. `contracts/api/openapi.yml` reflects schema-version 0.6.0 (regenerated post-implementation).
3. AC-1 through AC-7 (change-classification.md) are covered by passing tests.
4. No pre-existing test regressions introduced (full-regression informational job stays green or is explained in qa-report.md).

## Artifact Retention
- `test-results/junit.xml` — 14 days (matches existing workflow policy in `contract-driven-gates.yml`).
- `test-results/full-regression.xml` — 14 days.

## Notes
- Gate table references test-plan.md acceptance-criteria rows AC-1..AC-7 for test coverage mapping; do not duplicate strategy here.
- The `openapi-sync` gate is the single enforcement point for `openapi.yml` freshness; the developer must run `cdd-kit openapi export` locally before pushing (see implementation-plan.md §Post-implementation step).
- CER-001 (`tests/contract/response-samples.json`) is still pending; if approved and a JobStatus sample exists, update that sample before pushing or the contract-validation gate may flag drift.
