# CI/CD Gate Plan

## Change ID
office-output-mode

## Required Gates

| gate | tier | trigger | command / workflow | expected artifact |
|---|---:|---|---|---|
| validate-contracts | 1 | push/PR | `cdd-kit validate --contracts` | 0 errors |
| openapi-sync | 1 | push/PR | `cdd-kit openapi export --check --out contracts/api/openapi.yml` | openapi.yml not stale after bilingual enum added |
| targeted-output-mode | 1 | push/PR | `pytest tests/test_output_mode_processors.py tests/test_output_mode_orchestrator.py tests/test_output_mode_api.py -x -q --tb=short` | 0 failures |
| full-test-suite | 1 | push/PR | `pytest tests/ -x -q --tb=short` | 0 failures, no regressions |

## New Workflow Changes
- Add `targeted-output-mode` step to `contract-and-fast-tests` job in `.github/workflows/contract-driven-gates.yml` (before the full suite step)
- Remove this step at `/cdd-close` per CLAUDE.md learnings

## Required Check Policy
All Tier 1 gates must pass before merge. No waivers.

## Informational Gate Promotion Policy
No informational gates defined for this change. The OpenAPI sync check is already a hard Tier 1 gate in the base workflow.

## Rollback Policy
`output_mode` is a per-request field; no migration required. Revert to `append` default in orchestrator within 1 commit if bilingual DOCX output quality is unacceptable.

## Merge Eligibility Decision
PR merge requires: all 4 Tier 1 gates green + contract-reviewer approval + qa-reviewer approval.

## Notes
- `openapi-sync` is a pre-existing gate; it will fail automatically if `openapi.yml` is stale after the `bilingual` enum addition — no special gate needed.
- ci-gates.md per-row command/workflow column heading contains the literal "workflow" per CLAUDE.md gate-table rule.
