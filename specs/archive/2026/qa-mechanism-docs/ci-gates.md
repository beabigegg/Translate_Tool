# CI/CD Gate Plan

## Change ID
qa-mechanism-docs

## Required Gates
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---:|---|---|---|
| lint | 1 | yes | pull_request | existing `contract-and-fast-tests` workflow step | pass/fail |
| build | 1 | yes | pull_request | existing build step (no build-affecting change) | pass/fail |
| unit | 1 | no | — | no code surface | — |
| contract | 4 | yes | pull_request | `cdd-kit validate --contracts` (existing) — checks Table Y + BR-id references, `quality_score_avg`/`JobQualityRecord` prose consistency | pass/fail |
| integration | 1/3 | no | — | not applicable | — |
| e2e-critical | 1 | no | — | not applicable | — |
| visual | 2 | no | — | no UI surface | — |
| data-boundary | 1 | no | — | not applicable | — |
| resilience | 1/3 | no | — | not applicable | — |
| fuzz/monkey | 1/3 | no | — | not applicable | — |
| stress | 4/5 | no | — | not applicable | — |
| soak | 4/5 | no | — | not applicable | — |

## New Workflow Changes
None. `cdd-kit validate --contracts` (existing) and `cdd-kit openapi export
--check` (existing, already wired) fully cover this change — the latter
catches a stale `openapi.yml`/`openapi.json` if `quality_score_avg`'s notes
edit isn't followed by a re-export, per implementation-plan.md's IP-6.

## Required Check Policy
`contract` gate is PR-required (existing policy). `openapi export --check`
is PR-required (existing, unchanged).

## Informational Gate Promotion Policy
Not applicable — no new informational gate introduced.

## Rollback Policy
Trivial: prose-only contract edits, no schema/behavior change. A revert is a
straight git revert with no data-migration or cache-invalidation concern.

## Artifact Retention
Not applicable.

## Merge Eligibility Decision
This change should merge LAST among the four QA-pipeline changes — it
`depends-on` `br92-rescore-resolution`, `qa-judge-provider-consistency`, and
`qa-judge-hang-recovery` (see `tasks.yml` frontmatter) so its cross-references
describe final, landed behavior (BR-92 deleted, BR-98/99/100 present) rather
than dangling references to not-yet-existing rules.

## Notes
No `ci-cd-gatekeeper` agent was required (change-classifier: `CI/CD: none`)
— populated directly from the existing, unmodified gate policy. See
test-plan.md for the verification-only test approach (no pytest ladder,
`test-evidence-not-applicable` set in `tasks.yml` frontmatter).
