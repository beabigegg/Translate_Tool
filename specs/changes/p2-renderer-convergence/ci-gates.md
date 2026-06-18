# CI/CD Gate Plan

## Change ID
p2-renderer-convergence

## Required Gates for This Change
| gate | tier | required | trigger | command / workflow | owner | artifact |
|---|---:|---:|---|---|---|---|
| contract-validate | 2 | yes | pre-commit / PR | `cdd-kit validate --contracts` | platform-team | exit code 0 |
| change-gate | 2 | yes | pre-commit / PR | `cdd-kit gate p2-renderer-convergence` | platform-team | exit code 0 |
| unit-tests | 1 | yes | PR (push to main) | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` | application-team | junit XML (14 days) |
| golden-sample-regression | 2 | yes | PR | `pytest tests/test_golden_regression.py --tb=short -q` | application-team | step log (per-sample diff) |
| layout-detector-dependency-gate | 2 | yes | PR | `! grep -E "(ultralytics\|onnxruntime-gpu)" app/backend/requirements.txt app/backend/environment.yml` | platform-team | exit code 0 |
| renderer-equivalence | 2 | yes | PR | `pytest tests/test_ir_pipeline_decoupling.py -k "equivalence" --tb=short -q` | application-team | junit XML (14 days) |

### Gate Notes

- **unit-tests** covers AC-1 through AC-6 and AC-7 unit/resilience/contract/data-boundary families at Tier 0 (fast).
  See test-plan.md rows: `TestIRBboxReflow`, `TestFitzPrimary`, `TestFitzFallback`, `TestMalformedIRDataBoundary`,
  `TestReadingOrderPreservedBothPaths`, `TestElementTypingPreservedBothPaths`, `TestMalformedIRBothPaths`, `TestFallbackPath`.
- **golden-sample-regression** covers AC-7 regression family (existing golden fixtures must not regress).
  See test-plan.md row: `tests/test_golden_regression.py`.
- **renderer-equivalence** covers AC-4/AC-5 integration and equivalence families.
  See test-plan.md rows: `TestLayoutEquivalence`, `TestEquivalenceGolden`, `TestReadingOrderPreservedBothPaths`,
  `TestElementTypingPreservedBothPaths`. When `tests/test_renderer_convergence.py` is created by the
  backend-engineer, the `-k "equivalence"` filter will automatically pick up `TestLayoutEquivalence` and
  `TestEquivalenceGolden` from that file without a workflow change.
- Stress / soak gates: not applicable — rendering is per-document, not a queue/long-running surface
  (see change-classification.md Tasks Not Applicable).

## Workflow Changes Applied

Added job `renderer-equivalence` to `.github/workflows/contract-driven-gates.yml`.

- Modelled after `golden-sample-regression` job.
- Runs on `pull_request` only.
- Sets up Python 3.10 with pip cache.
- Installs `app/backend/requirements.txt`.
- Runs: `pytest tests/test_ir_pipeline_decoupling.py -k "equivalence" --tb=short -q --junitxml=test-results/renderer-equivalence.xml`
- Uploads junit XML artifact with 14-day retention.
- When `tests/test_renderer_convergence.py` is added by the backend-engineer, the `-k "equivalence"`
  filter extends automatically to that file without modifying this workflow.

## Promotion Policy

- All Tier 0 tests run in the `contract-and-fast-tests` job on every push to `main` and every PR.
- Tier 2 gates (`golden-sample-regression`, `layout-detector-dependency-gate`, `renderer-equivalence`)
  run on PR only (`if: github.event_name == 'pull_request'`).
- A gate may not be demoted below its tier-floor without a `tier-floor-override` entry in the change's
  context-manifest and recorded rationale.
- No stress/soak tier-4 gate is required for this change per change-classification.md.

## Rollback Policy

No schema or data migration is involved. Rollback is code-only.

- Immediate: revert the fitz-primary dispatch in `pdf_processor._translate_pdf_to_pdf`; the
  `PDF_RENDERER_PRIMARY` config switch (default `fitz`) allows operator-level forced-fallback without
  a code deploy.
- Full code rollback: revert the `pdf_generator.py` → `fitz_renderer.py` rename and dispatch wrapper;
  the shared `bbox_reflow.py` module is additive and may remain without breaking previous behavior.
- CI gate rollback: remove the `renderer-equivalence` job from the workflow and the corresponding
  row from `contracts/ci/ci-gate-contract.md` in the same revert PR.
- At change close: remove the `cdd-kit gate p2-renderer-convergence` step from the workflow per
  the CLAUDE.md promoted learning (archived dirs no longer exist under `specs/changes/`).

## Merge Eligibility

blocked until all of the following pass on the PR:
- `contract-and-fast-tests` (contract-validate, change-gate, unit-tests)
- `golden-sample-regression`
- `layout-detector-dependency-gate`
- `renderer-equivalence`

informational-risk: `full-regression` job is informational; new failures escalate to blocker per
existing policy in the workflow.
