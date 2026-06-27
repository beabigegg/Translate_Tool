# CI/CD Gate Review

change-id: table-context-translation

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 1 | yes | push / PR | `cdd-kit validate --contracts` | exit 0 |
| openapi-sync | 1 | yes | push / PR | `cdd-kit openapi export --check --out contracts/api/openapi.yml` | exit 0 (no API change — openapi.yml must be unchanged) |
| table-context-translation-targeted | 1 | yes | push / PR | `pytest tests/test_table_serialization.py tests/test_table_context_translation.py -x -q --tb=short` | exit 0; covers AC-1..AC-8 fast-fail (see test-plan.md rows for all test IDs) |
| unit-tests (full suite) | 1 | yes | push / PR | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` | junit XML; AC-6 non-table regression guard; includes tests/test_translation_service.py paragraphs |
| golden-sample-regression | 2 | yes | PR | `pytest tests/test_golden_regression.py --tb=short -q` | per-sample diff log; confirms IR field stability across DOCX/PPTX/PDF |
| layout-detector-dependency-gate | 2 | yes | PR | `! grep -E "^[^#]*(ultralytics\|onnxruntime-gpu)" app/backend/requirements.txt app/backend/environment.yml` | exit 0 |
| renderer-equivalence | 2 | yes | PR | `pytest tests/test_ir_pipeline_decoupling.py tests/test_renderer_convergence.py -k "equivalence" --tb=short -q` | per-element diff log |
| text-expansion-benchmark | 2 | yes | PR | `pytest tests/test_text_expansion_benchmark.py --tb=short -q` | zero-overflow + zero-tofu log |

## Informational Gates

| gate | tier | trigger | command / workflow | notes |
|---|---:|---|---|---|
| full-regression (PR job) | 2 | PR | `pytest tests/ -q --tb=short` | Failures become required blockers if any table-context test regresses |

## Workflow Changes Applied

Added step `Targeted tests — table_serialization + table_context_translation` to the `contract-and-fast-tests` job in `.github/workflows/contract-driven-gates.yml`. The step runs immediately before the full suite to provide fast-fail on this change's tests (AC-1..AC-8). No new job was added; no `cdd-kit gate <change-id>` step was added (contract validation is covered by the existing `cdd-kit validate --contracts` step).

Updated the archived-changes comment at the top of the workflow to list `table-context-translation` as an active change.

## Promotion Policy

A PR is eligible to merge when all Tier 1 gates in `contract-and-fast-tests` pass on the PR head commit AND all Tier 2 jobs (`golden-sample-regression`, `layout-detector-dependency-gate`, `renderer-equivalence`, `text-expansion-benchmark`) pass. The `openapi-sync` gate verifies no API surface change (AC-7); a non-zero exit there blocks merge unconditionally.

## Rollback Policy

This change modifies three format processors and two clients (no schema migration, no new env vars). Rollback is a revert commit. No data migration or teardown steps are required. The targeted test step added to CI is removed automatically by the revert.

## Merge Eligibility

blocked until all Tier 1 and Tier 2 required gates pass
