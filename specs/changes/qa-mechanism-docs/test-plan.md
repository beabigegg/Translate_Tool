---
change-id: qa-mechanism-docs
schema-version: 0.1.0
last-changed: 2026-07-07
risk: low
tier: 4
---

# Test Plan: qa-mechanism-docs

Documentation-only change. No code, schema, or behavior change — see
change-classification.md's `Required Tests: none new`.

## Acceptance Criteria → Test Mapping

| criterion id | test family | verification method | tier |
|---|---|---|---|
| AC-1..AC-4, AC-7 | contract | `cdd-kit validate --contracts` (Table Y present, BR-id references valid) | 4 |
| AC-5 | contract | `cdd-kit openapi export --check` stays green after the `quality_score_avg` notes-cell edit | 4 |
| AC-6 | contract | `cdd-kit validate --contracts` (data-shape-contract.md structure check) | 4 |

## Test Families Required

contract only. No unit / integration / e2e / data-boundary / resilience /
monkey / stress / soak coverage applies — no code surface exists.

## Test Execution Ladder

Not applicable — `tasks.yml` frontmatter carries
`test-evidence-not-applicable` per change-classifier (no testable code
surface). The `contract` phase (`cdd-kit validate`) and `openapi export
--check` are verification steps, not a pytest ladder.

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| (none) | — | no existing test asserts BR-92, quality_score_avg's exact note text, or JobQualityRecord's exact prose — nothing to update |

## Stop Rules

Not applicable (no pytest phases run for this change).

## Out of Scope

- Any unit/integration/e2e test authoring — no code surface.
- Verifying the sibling changes' (`br92-rescore-resolution`,
  `qa-judge-provider-consistency`, `qa-judge-hang-recovery`) own test
  coverage — each owns its own test-plan.md.

## Notes

Verification for this change is entirely contract-validator + openapi
export-check, both already wired in CI with zero new gate configuration.
