# CI/CD Gate Review

## Change ID
pptx-group-shape-collection (Tier 3, bug-fix lane)

## Required Gates for This Change
| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 2+ | yes | pre-commit / PR | cdd-kit validate --contracts | exit code 0 |
| change-gate | 2+ | yes | pre-commit / PR | cdd-kit gate pptx-group-shape-collection | exit code 0 |
| unit-tests (blanket sweep) | 2+ | yes | PR | pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml (`.github/workflows/contract-driven-gates.yml` job `contract-and-fast-tests`) | junit XML |
| full-regression | 2 | yes (informational, escalates on new failure) | PR | pytest tests/ -q --tb=short (`full-regression` job) | junit XML |
| golden-sample-regression | 2 | yes | PR | pytest tests/test_golden_regression.py --tb=short -q | per-sample diff (step log) |

No other existing gate (`renderer-equivalence`, `text-expansion-benchmark`,
`layout-detector-dependency-gate`, `libreoffice-conversion-gate`,
`frontend-tests`) touches PPTX group-shape collection; none are re-scoped by
this change.

## Workflow Changes Applied
None. No `.github/workflows/*.yml` edit, no `Makefile` target, no new gate.
Per change-classification.md (tasks 2.6/4.4 explicitly skipped) and the
CI/CD Required Contract answer ("no"), this is a backend-only bug fix with a
new test file (`tests/test_pptx_group_shapes.py`, confirmed absent —
see Drift Check below) that is already collected by the existing blanket
sweep `pytest tests/ -x -q` in the `contract-and-fast-tests` job and by the
`full-regression` job's whole-suite `pytest tests/ -q`. Adding a dedicated
targeted-test workflow step for this one file would repeat a drift pattern
already documented and corrected three times (table_recognizer,
quality_judge+co., table_serialization+table_context_translation): a
per-change targeted CI step is stale the moment the change archives, and
nobody remembers to delete it. The test-plan.md "targeted" and "changed-area"
ladder phases (`pytest tests/test_pptx_group_shapes.py -v`,
`pytest tests/test_pptx_parser.py tests/test_table_context_translation.py -k
pptx -v`) are pre-PR/local evidence commands only — not new CI steps.

## Local Pre-PR Command Sequence (conda-scoped)
Run in order; stop and fix on first failure (test-plan.md Stop Rules):
1. `conda run -n translate-tool pytest tests/test_pptx_group_shapes.py -v`
2. `conda run -n translate-tool pytest tests/test_pptx_parser.py tests/test_table_context_translation.py -k pptx -v`
3. `conda run -n translate-tool cdd-kit validate --contracts`
4. `conda run -n translate-tool pytest tests/ -x -q --tb=short`
5. `cdd-kit gate pptx-group-shape-collection --strict`

## AC-5 Regression Note
AC-5 (existing flat-shape PPTX output unchanged) is proven by the new
`TestFlatShapeRegression` class inside `tests/test_pptx_group_shapes.py`
(test-plan.md row AC-5) plus the pre-existing `tests/test_pptx_parser.py`
suite, both of which run unmodified inside the same blanket sweep and
full-regression jobs above — neither file nor any fake/stub in it needs an
update (test-plan.md §Existing-Test Sweep found no `id(shape)`-dependent
mock). A red result in either file blocks the gate identically to any other
regression.

## Promotion Policy
No promotion. This change adds zero new gates and re-scopes zero existing
gates; it rides the current Tier 2 PR-required floor
(`contract-and-fast-tests`, `full-regression`, `golden-sample-regression`)
unchanged. Tier 3/4/5 real-infra, soak, and manual-dispatch gates are not
applicable per change-classification.md (no cross-module, load, or
production-like surface).

## Rollback Policy
Standard PR revert. No workflow file changes ship with this change, so
rollback is a pure application-code revert (`pptx_processor.py` +
`business-rules.md` BR-116) with no CI/CD artifact to unwind.

## Merge Eligibility
mergeable — contingent on: `tests/test_pptx_group_shapes.py` all green,
`tests/test_pptx_parser.py` unchanged and green (AC-5/AC-7), and
`cdd-kit validate --contracts` passing the new BR-116 entry. No workflow or
CI/CD contract file requires modification for this change to be gate-ready.
