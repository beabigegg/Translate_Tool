# CI/CD Gate Review

## Change ID
tatr-parse-outputs

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| validate-contracts | 1 | yes | push / pull_request | `cdd-kit validate --contracts` — `contract-driven-gates` / `contract-and-fast-tests` | pass/fail |
| table-recognizer-targeted | 0 | yes | local / push / pull_request | `pytest tests/test_table_recognizer.py -x -q --tb=short` — `contract-driven-gates` / `contract-and-fast-tests` | pass/fail |
| full-suite | 1 | yes | push / pull_request | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` — `contract-driven-gates` / `contract-and-fast-tests` | `test-results/junit.xml` (14-day retention) |

Gates not applicable to this change (no E2E surface, no stress/load path, no schema or env change, no API or OpenAPI edit):
lint (no new linting target), build (no build artefact), integration (no live ONNX session in scope), e2e-critical, visual, resilience, fuzz/monkey, stress, soak, openapi-sync, env-schema-sync.

### Test-plan rows covered by the targeted gate

All rows in `test-plan.md § Acceptance Criteria → Test Mapping` (AC-1 through AC-8, test classes `TestParseOutputsGrid`, `TestParseOutputsDegenerate`, `TestParseOutputsBoxFormat`) are Tier 0 and are exercised by `pytest tests/test_table_recognizer.py`. The existing `contract-and-fast-tests` targeted step (`.github/workflows/contract-driven-gates.yml` lines 105–111) picks them up automatically.

## Workflow Changes Applied

No changes to `.github/workflows/contract-driven-gates.yml` are required.

The existing `contract-and-fast-tests` job already contains all three required steps in the correct order:

1. `cdd-kit validate --contracts` — validates contracts globally before tests run.
2. `pytest tests/test_table_recognizer.py -x -q --tb=short` — targeted fast-fail for all `_parse_outputs` tests.
3. `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` — full suite smoke check.

No new jobs, steps, secrets, caches, or matrix entries are needed.

## Promotion Policy

All new `_parse_outputs` tests must remain Tier 0 (pure numpy mock inputs; no ONNX session, no file I/O, no network). Any test that requires a live ONNX model belongs in a Tier 3 nightly job and must carry an explicit owner and exit date before it is added to any PR-required step.

`TABLE_RECOGNITION_ENABLED` defaults to `false`; no production promotion gate is needed until that flag is enabled in a subsequent change.

## Rollback Policy

Rollback is a plain revert commit (`git revert`). No migration, schema change, or env variable is involved. Because the feature is gated off by default, a bad `_parse_outputs` implementation cannot affect any active translation path; reverting the single source file (`app/backend/parsers/table_recognizer.py`) and its tests is sufficient.

## Merge Eligibility

mergeable when all three required gates pass:
- `validate-contracts` — `cdd-kit validate --contracts` exits 0
- `table-recognizer-targeted` — all AC-1 through AC-8 test cases in `tests/test_table_recognizer.py` green
- `full-suite` — no regression across `tests/` (`pytest` exits 0)
