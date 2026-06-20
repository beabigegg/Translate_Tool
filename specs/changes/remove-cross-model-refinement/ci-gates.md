# CI/CD Gate Review

## Change ID: remove-cross-model-refinement

Tier 2 — dead-code removal. No API surface change. No env-contract change.
`contracts/business/business-rules.md` updated (schema-version 0.12.1, BR-41/BR-44
test-pointer retargeted away from deleted `tests/test_hy_mt_quality_refinement.py`).

## Required Gates for This Change

| gate name | tier | required | trigger | command / workflow | artifact |
|---|---:|---|---|---|---|
| contract-validation | 1 | required | push / pull_request | `cdd-kit validate --contracts` | pass/fail in CI log |
| dead-reference-grep | 1 | required | push / pull_request | `grep -rn 'refine_translation\|refine_client\|refine_model\|CROSS_MODEL_REFINEMENT\|HY-MT\|TranslateGemma' app/` | zero-hit exit 0 |
| changed-area-tests | 1 | required | push / pull_request | `pytest tests/test_model_router.py tests/test_translation_strategy.py tests/test_env_contract.py tests/test_llm_client_protocol.py tests/test_sentence_mode_consistency.py tests/test_term_audit.py -x -q --tb=short` | JUnit XML |
| full-test-suite | 1 | required | push / pull_request | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` | test-results/junit.xml |
| change-gate | 1 | required | pre-PR local / push | `cdd-kit gate remove-cross-model-refinement` | pass/fail |
| openapi-sync | 1 | required | push / pull_request | `cdd-kit openapi export --check --out contracts/api/openapi.yml` | pass/fail |
| secret-scan | 1 | required | push / pull_request | `! grep -rn -E "(PANJIT_API\|DEEPSEEK_API)\s*[:=]\s*[A-Za-z0-9+/]{20,}" --include="*.py" --include="*.yml" .` | zero-match exit 0 |
| business-rules-orphan-check | 2 | informational | pull_request | `grep -n 'test_hy_mt_quality_refinement' contracts/business/business-rules.md` | zero-hit exit 0 (confirms IP-11 cleared) |

Gates not applicable to this change (no API endpoint add/remove, no env-contract row
change, no UI, no data migration, no stress/soak target): e2e-critical, visual,
data-boundary, resilience, fuzz/monkey, stress, soak.

## Workflow Changes Applied

Added `cdd-kit gate remove-cross-model-refinement` to the existing
`Change gate (Tier 1 — blocks merge)` step in
`.github/workflows/contract-driven-gates.yml`.

The `dead-reference-grep` and `business-rules-orphan-check` gates are expressed as
inline shell steps within the existing `contract-and-fast-tests` job rather than new
jobs, keeping the runner count unchanged. The `changed-area-tests` run is subsumed by
the existing `full-test-suite` step (`pytest tests/ -x -q`) which already blocks merge;
no separate CI job is needed — run changed-area tests locally (Tier 0) before push.

## Promotion Policy

- All Tier 1 gates must be green before the PR is opened.
- `business-rules-orphan-check` (Tier 2 informational) must resolve to zero hits before
  the PR is merged; a non-zero hit means IP-11 (contract-reviewer repointing BR-41/BR-44)
  is incomplete and the PR is blocked regardless of tier label.
- `cdd-kit gate remove-cross-model-refinement` must pass locally before push (Tier 0
  pre-flight) and again in CI as the `Change gate` step (Tier 1 blocker).

## Rollback Policy

This change is a pure deletion with no data migration and no schema change. Rollback is
a `git revert` of the change commit. No database state or persisted env var is affected.
If the revert is needed post-merge, revert and re-run the full gate before re-merging.

## Merge Eligibility

blocked until:
1. `cdd-kit validate --contracts` green (confirms BR-41/BR-44 proof pointers retargeted).
2. `dead-reference-grep` returns zero hits in `app/` and `tests/`.
3. `business-rules-orphan-check` returns zero hits in `contracts/business/business-rules.md`.
4. `pytest tests/ -x -q` green (all surviving tests pass; deleted test file absent from collection).
5. `cdd-kit gate remove-cross-model-refinement` passes.
