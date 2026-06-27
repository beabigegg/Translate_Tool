# CI/CD Gate Plan

## Change ID
layout-fidelity-metrics

## Required Gates
| gate | tier | required | trigger | command / workflow | expected artifact |
|---|---:|---:|---|---|---|
| unit | 1 | yes | pull_request | `pytest tests/test_layout_metrics.py -v` | test pass |
| full-suite | 1 | yes | pull_request | `pytest` | no regression |

## New Workflow Changes
None. This change adds test infrastructure only; no new CI workflow YAML is authored. Track G will register BIoU/residual-text/truncation-rate as required metric gates in `.github/workflows/contract-driven-gates.yml` as a separate change.

## Required Check Policy
See `ci/required-check-policy.md`. The `pytest` full-suite run is already a required check; no new required checks are added here.

## Informational Gate Promotion Policy
n/a — no informational gates introduced.

## Rollback Policy
Pure additive change. Rollback = revert PR. No data migration, no deployed artifact, no env change needed.

## Artifact Retention
Test output (pytest stdout) retained by default CI artifact policy. No additional retention configuration needed.

## Merge Eligibility Decision
Gate must be green (all pytest tests pass, including tests/test_layout_metrics.py) before merge.

## Notes
Reference `test-plan.md` for the full test family mapping. The ci-gates.md is intentionally minimal for this Tier 4 infrastructure addition.
