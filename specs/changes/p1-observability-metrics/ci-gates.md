# CI/CD Gate Plan

## Change ID

## Required Gates
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---:|---|---|---|
| lint | 1 | yes | pull_request |  |  |
| build | 1 | yes | pull_request |  |  |
| unit | 1 | yes | pull_request |  |  |
| contract | 1 | conditional | pull_request |  |  |
| integration | 1/3 | conditional | pull_request/nightly |  |  |
| e2e-critical | 1 | conditional | pull_request |  |  |
| visual | 2 | conditional | pull_request |  |  |
| data-boundary | 1 | conditional | pull_request |  |  |
| resilience | 1/3 | conditional | pull_request/nightly |  |  |
| fuzz/monkey | 1/3 | conditional | pull_request/nightly |  |  |
| stress | 4/5 | conditional | weekly/manual |  |  |
| soak | 4/5 | conditional | weekly/manual |  |  |

## New Workflow Changes

## Required Check Policy

## Informational Gate Promotion Policy

## Rollback Policy

## Artifact Retention

## Merge Eligibility Decision

## Notes

Reference test-plan.md rows or gate names instead of duplicating full test strategy.
