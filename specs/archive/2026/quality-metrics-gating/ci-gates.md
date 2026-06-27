# CI/CD Gate Plan

## Change ID
quality-metrics-gating

## Required Gates

| gate | tier | trigger | command / workflow | expected artifact |
|---|---:|---|---|---|
| validate-contracts | 1 | push/PR | `cdd-kit validate --contracts` | 0 errors |
| env-schema-sync | 1 | push/PR | `grep -q "QE_RESCORE_THRESHOLD" contracts/env/.env.example.template && grep -q "QE_RESCORE_THRESHOLD" contracts/env/env.schema.json` | both deployment sync artefacts contain QE_RESCORE_THRESHOLD |
| targeted-quality-gating | 1 | push/PR | `pytest tests/test_quality_evaluation.py tests/test_quality_judge.py tests/test_critique_gate.py tests/test_translate_document_parity.py tests/test_env_contract.py -x -q --tb=short` | 0 failures |
| full-test-suite | 1 | push/PR | `pytest tests/ -x -q --tb=short` | 0 failures, no regressions |

## New Workflow Changes
- Add `targeted-quality-gating` step to `contract-and-fast-tests` job in `.github/workflows/contract-driven-gates.yml`
- Add `env-schema-sync` step for QE_RESCORE_THRESHOLD (same pattern as the existing JUDGE_MODEL sync step)
- Remove both steps at `/cdd-close` per CLAUDE.md learnings

## Required Check Policy
All Tier 1 gates must pass before merge. No waivers.

## Informational Gate Promotion Policy
- Stress/soak results from stress-soak-engineer are informational (Tier 2) — QE latency/VRAM regression exceeding approved threshold escalates to blocker via qa-reviewer.
- OpenAPI sync (cdd-kit openapi export --check) is conditional: only required if contract-reviewer approves CER-001 (per-segment scores extend API response schema).

## Rollback Policy
`QE_ENABLED` and `CRITIQUE_LOOP_ENABLED` are env flags — revert defaults to `false` within 1 commit if QE latency causes production issues. No migration required.

## Merge Eligibility Decision
PR merge requires: all 4 Tier 1 gates green + contract-reviewer approval + qa-reviewer approval (including approved-with-risk documentation for QE_ENABLED default flip).

## Notes
- `env-schema-sync` follows the existing JUDGE_ENABLED/JUDGE_MODEL gate pattern in the CI workflow.
- ci-gates.md per-row command/workflow column heading contains the literal "workflow" per CLAUDE.md gate-table rule.
- tier-floor false-positive risk: vocabulary in this change (`threshold`, `cache`, `endpoint`, `integration`) can trigger false Tier 0 — apply `tier-floor-override` with written rationale if needed.
