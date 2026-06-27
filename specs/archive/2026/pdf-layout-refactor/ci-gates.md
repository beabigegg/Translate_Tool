---
change-id: pdf-layout-refactor
schema-version: 0.1.0
last-changed: 2026-06-27
tier: 1
---

# CI/CD Gate Plan: pdf-layout-refactor

## Required Gates

| gate | tier | trigger | required | command / workflow | owner | pass criterion |
|---|---:|---|---|---|---|---|
| residual-text | 1 | PR | yes | `pytest tests/test_pdf_layout_refactor.py -k "residual_text" -x -q --tb=short` | application-team | exit 0; residual source-text count = 0 (AC-1) |
| ocr-absent-gate | 1 | PR | yes | `pytest tests/test_pdf_layout_refactor.py -k "ocr_absent" -x -q --tb=short` | application-team | exit 0; OCR_ENABLED=False path never crashes (AC-7, AC-8) |
| full-regression | 1 | PR | yes | `pytest tests/ -x -q --tb=short` (existing `contract-and-fast-tests` job) | application-team | exit 0; full suite green; covers AC-2..AC-8 |
| biou-layout-fidelity | 1 | PR | no (informational) | `pytest tests/test_layout_metrics.py -k "biou" -x -q --tb=short` | application-team | BIoU >= pre-change baseline (AC-2) |
| truncation-rate | 1 | PR | no (informational) | `pytest tests/test_layout_metrics.py -k "truncation_rate" -x -q --tb=short` | application-team | truncation rate <= pre-change baseline (AC-3) |
| reading-order-edit-distance | 1 | PR | no (informational) | `pytest tests/test_layout_metrics.py -k "reading_order" -x -q --tb=short` | application-team | normalized edit distance falls vs. x-gap baseline (AC-5) |

See test-plan.md AC-1..AC-8 for the full acceptance-criteria-to-test mapping.

## Workflow Changes Applied

`contract-and-fast-tests` job in `.github/workflows/contract-driven-gates.yml`:

1. Active change gates comment updated to include `pdf-layout-refactor`.
2. Targeted step added before the full `pytest tests/` step:

   ```yaml
   - name: pdf-layout-refactor targeted tests
     run: |
       pytest tests/test_pdf_layout_refactor.py -x -q --tb=short
   ```

   Running the full new test file fast-fails on all AC-1..AC-8 tests (including both required
   gates `residual-text` and `ocr-absent-gate`) before the broader suite.

Informational gates (`biou-layout-fidelity`, `truncation-rate`, `reading-order-edit-distance`)
exercise metrics already covered by the existing full-suite step via `tests/test_layout_metrics.py`.
They are not added as separate required steps; promote via the Informational Gate Promotion Policy.

## Promotion Policy

Promote an informational gate to required when: (a) owner assigned and (b) exit date within
2 sprints is set here. Steps: change `no (informational)` to `yes` in the gate table and add a
targeted step to `.github/workflows/contract-driven-gates.yml`.

## Rollback Policy

Items 3.1-3.7 are isolated seam changes revertable independently. `PDF_RENDER_DPI=72` and
`OCR_ENABLED=False` (the defaults) reproduce today's behavior. Gate rollback: remove the
`pdf-layout-refactor targeted tests` step from the workflow and revert the active-gates comment.

## Merge Eligibility

mergeable — `contract-and-fast-tests` (including `pdf-layout-refactor targeted tests`) must pass.
Informational gates (`biou-layout-fidelity`, `truncation-rate`, `reading-order-edit-distance`)
must be reported but do not block merge.

## Notes

- Tier-floor watch: if `cdd-kit gate` tier-floors on "OCR" or "integration" vocabulary, apply
  `tier-floor-override` with rationale: "OCR_ENABLED is a lazy feature flag, not an auth/cache/
  migration concern; genuine tier is 1."
- At `/cdd-close`: remove the `cdd-kit gate pdf-layout-refactor` line from the workflow and
  archive this change.
