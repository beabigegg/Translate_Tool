# CI/CD Gate Plan

## Change ID
p1-contract-baseline

Tier 4, contracts-only documentation change. No production code, no new test
code, no new CI workflows. The only required gate is contract conformance.

## Required Gates
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---:|---|---|---|
| contract | 4 | yes | pull_request | cdd-kit validate --contracts | test-evidence.yml |
| change gate | 4 | yes | pre-merge | cdd-kit gate p1-contract-baseline | gate report |
| lint | — | n/a | — | no code changed | — |
| build | — | n/a | — | no code changed | — |
| unit | — | n/a | — | no code/tests added | — |
| integration | — | n/a | — | no runtime change | — |
| e2e-critical | — | n/a | — | no user-facing flow change | — |
| visual | — | n/a | — | no UI surface | — |
| data-boundary | — | n/a | — | no runtime data path change | — |
| resilience | — | n/a | — | no failure surface change | — |
| fuzz/monkey | — | n/a | — | no interactive surface | — |
| stress | — | n/a | — | no load surface | — |
| soak | — | n/a | — | no long-running surface | — |

## New Workflow Changes
None. No CI workflow files are added or modified.

## Required Check Policy
`cdd-kit validate --contracts` must pass (exit 0) before merge. `cdd-kit gate
p1-contract-baseline` confirms only `contracts/*.md` are modified (AC-8).

## Informational Gate Promotion Policy
N/A — no new gates introduced.

## Rollback Policy
Revert is trivial: edits are isolated to five Markdown contract files; reverting
the commit restores the prior shells with no runtime impact.

## Artifact Retention
Standard CDD `test-evidence.yml` retention; no additional artifacts produced.

## Merge Eligibility Decision
Eligible when `cdd-kit validate --contracts` passes and the gate confirms scope
is limited to the five contract files.

## Notes
`.cdd/conformance.json` is `enabled:false`; this change does not flip it.
See test-plan.md for the AC -> verification mapping.
