# CI/CD Gate Review

## Change ID
p2-text-expansion

## Required Gates for This Change
| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| contract-validate | 1 | yes | pre-commit / PR | `cdd-kit validate --contracts` | exit 0 |
| change-gate | 1 | yes | pre-commit / PR | `cdd-kit gate p2-text-expansion` | exit 0 |
| unit-contract-integration | 1 | yes | PR | `pytest tests/ -x -q --tb=short` (job: `contract-and-fast-tests`) | JUnit XML; covers AC-4 AC-5 AC-6 AC-7 AC-8 via test-plan.md rows T-01–T-14 |
| golden-sample-regression | 2 | yes | PR | `pytest tests/test_golden_regression.py --tb=short -q` (job: `golden-sample-regression`) | per-sample pass/fail diff; pre-existing-field diff blocks merge |
| text-expansion-benchmark | 2 | yes | PR | `pytest tests/test_text_expansion_benchmark.py --tb=short -q` (job: `text-expansion-benchmark`) | zero-overflow + zero-tofu assertion log; covers AC-1 AC-2 AC-3 |
| renderer-equivalence | 2 | yes | PR | `pytest tests/test_ir_pipeline_decoupling.py tests/test_renderer_convergence.py -k "equivalence" --tb=short -q` (job: `renderer-equivalence`) | per-element diff log; covers AC-6 |

## Workflow Changes Applied

### New job: `text-expansion-benchmark`
Added to `.github/workflows/contract-driven-gates.yml`. Rationale for a dedicated
job rather than extending `golden-sample-regression`: the benchmark asserts rendered
pixel overflow and tofu absence (visual metric), not field-by-field IR equivalence;
mixing the two assertions in one job obscures failure triage. The job runs on
`pull_request` only, is required for merge, and consumes only pre-committed
fixtures — no network, no GPU.

### Extended job: `renderer-equivalence`
Added `tests/test_renderer_convergence.py` to the pytest invocation so mock-based
per-backend wiring assertions (AC-6) are included once the backend-engineer commits
that file. The `-k "equivalence"` filter picks up the new test class automatically.

## Promotion Policy
All Tier-2 gates in this plan are required (block merge). No informational-only
gates exist for this change. If `text-expansion-benchmark` produces intermittent
failures due to font-rendering non-determinism on different runner images, the
affected sub-check must be quarantined to an informational sub-job per the
ci-gate-contract.md Informational Gate Promotion Policy; the parent job remains
required on deterministic assertions.

## Rollback Policy
This change is purely in-process rendering logic. No datastore migration, no env
change, no schema DDL. Rollback = revert the renderer and font-utils commits.
The additive `render_truncated` IR field is ignored by consumers that do not read
it; no data cleanup is required. The `text-expansion-benchmark` job is removed
from the workflow in the same revert PR.

## Merge Eligibility
Blocked until all six gates pass: `contract-validate`, `change-gate`,
`unit-contract-integration`, `golden-sample-regression`,
`text-expansion-benchmark`, `renderer-equivalence`.
