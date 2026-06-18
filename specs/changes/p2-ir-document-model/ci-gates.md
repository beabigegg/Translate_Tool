# CI/CD Gate Plan — p2-ir-document-model

## Required Gates for This Change
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | pre-commit / PR | `cdd-kit validate --contracts` | exit code 0 |
| change-gate | 1 | yes | pre-commit / PR | `cdd-kit gate p2-ir-document-model` | exit code 0 |
| unit-tests | 1 | yes | PR | `pytest tests/ -x -q --tb=short` | junit XML |
| golden-sample-regression | 1 | yes | PR | `pytest tests/test_golden_regression.py --tb=short -q` | per-sample diff (step log) |

All four gates must pass before a PR is eligible to merge.
See `contracts/ci/ci-gate-contract.md` §Gate Inventory for the authoritative gate definitions.
See `test-plan.md` §Golden-sample regression for fixture scope and pass/fail criteria.

## Workflow Changes Applied
- Added job `golden-sample-regression` to `.github/workflows/contract-driven-gates.yml`.
- Job runs on `pull_request` only; depends on Python + pip-cached deps; no network or GPU required.
- Fixture files under `tests/fixtures/golden/` are pre-committed binaries; no downloads at CI time.

## Promotion Policy
- `golden-sample-regression` enters as Tier 1 (required, blocks merge) because it guards
  the Round-trip guarantee fields listed in `contracts/data/data-shape-contract.md`.
- A `reading_order`-only diff does not constitute a regression and must not block merge.
- If flakiness is observed (e.g. PyMuPDF table-detection non-determinism across runner
  versions), the affected sample field may be quarantined to an informational sub-job with
  a recorded owner and exit date — do not disable the gate outright.

## Rollback Policy
- Rollback = revert the implementing commit. No data migration required (IR is in-memory
  and job-scoped; no persisted corpus exists). Golden fixtures remain on the branch for
  reference and do not block revert.
- Gate must remain active post-rollback to detect any future regression against the
  pre-change snapshot baseline.

## Merge Eligibility
mergeable when all four required gates are green on the PR head SHA.
