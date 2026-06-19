# CI/CD Gate Plan — p2-comet-qe

## tier-floor-override
- override: 2
- rationale: Additive read-only endpoint (GET /jobs/{id}/quality); no schema migration, no auth
  change, no payment surface. Vocabulary in contracts ("endpoint", "integration") would otherwise
  trigger a false Tier 0/2 escalation per CLAUDE.md tier-floor note.

## Required Gates
| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | pre-commit / PR | `cdd-kit validate --contracts` | exit code 0 |
| change-gate | 1 | yes | pre-commit / PR | `cdd-kit gate p2-comet-qe` | exit code 0 |
| openapi-sync | 1 | yes | PR | `cdd-kit openapi export --check --out contracts/api/openapi.yml` | exit code 0 |
| unit-tests | 1 | yes | PR | `pytest tests/` picks up tests/test_quality_evaluation.py (AC-1 AC-2 AC-3 AC-6 AC-7 AC-8) | junit XML |
| layout-detector-dependency-gate | 2 | yes | PR | `! grep -E "(ultralytics\|onnxruntime-gpu)" app/backend/requirements.txt app/backend/environment.yml` | exit code 0 |

## Informational Gates
None for Tier 2. Full-regression job in contract-driven-gates.yml runs as informational on PR.

## Nightly / Weekly / Manual Gates
Not applicable (Tier 2; per change-classification.md §Tasks Not Applicable 6.4).

## Workflow Changes Applied
- `.github/workflows/contract-driven-gates.yml` — `Change gate` step `run:` updated from echo
  placeholder to `cdd-kit gate p2-comet-qe`. Comment on line 3 updated to list p2-comet-qe as
  active. No new CI jobs added.

## Dependency Gate Note — unbabel-comet transitive deps
`unbabel-comet` may transitively depend on `onnxruntime-gpu`. If `pip install unbabel-comet`
pulls in `onnxruntime-gpu`, the layout-detector-dependency-gate will fail. The backend-engineer
must pin CPU-only ONNX dependencies in `app/backend/requirements.txt` (e.g.,
`onnxruntime>=1.20.0` without the `-gpu` suffix and without pulling in the GPU variant
transitively). Verify with `pip show onnxruntime-gpu` after install; add exclusion pins as
needed before committing requirements.txt.

## OpenAPI Sync Dependency
Before raising the PR, the backend-engineer must run:
  `cdd-kit openapi export --out contracts/api/openapi.yml`
and commit the result. The openapi-sync gate (CI step "OpenAPI sync gate") will fail if
`contracts/api/openapi.yml` does not reflect the new GET /jobs/{id}/quality endpoint declared in
`contracts/api/api-contract.md`.

## Promotion Policy
All Tier 1 gates must pass before merge. No gate promotions introduced by this change.

## Rollback Policy
Change is additive (new endpoint, new pip package, new env vars with default disabled). Rollback
is a revert commit; no migration to undo. If `unbabel-comet` causes environment instability,
remove the package pin and set QE_ENABLED=false (default) — the endpoint degrades safely per
AC-7 and BR-57.

## Merge Eligibility
Blocked until all Tier 1 required gates pass: contract-validate, change-gate, openapi-sync,
unit-tests, layout-detector-dependency-gate.
