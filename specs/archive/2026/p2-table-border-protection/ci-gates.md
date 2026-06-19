---
change-id: p2-table-border-protection
schema-version: 0.1.0
last-changed: 2026-06-19
---

# CI/CD Gate Review

## Required Gates for This Change

| gate | tier | required | trigger | command / workflow | artifact |
|---|---:|:---:|---|---|---|
| contract-validate | 1 | yes | pre-commit / PR | `cdd-kit validate --contracts` | exit code 0 |
| change-gate | 1 | yes | pre-commit / PR | `cdd-kit gate p2-table-border-protection` | exit code 0 |
| unit-tests | 1 | yes | PR | `pytest tests/ -x -q --tb=short` | junit XML (`test-results/junit.xml`) |
| golden-sample-regression | 2 | yes | PR | `pytest tests/test_golden_regression.py --tb=short -q` | per-sample pass/fail diff (step log) |
| renderer-equivalence | 2 | yes | PR | `pytest tests/test_ir_pipeline_decoupling.py tests/test_renderer_convergence.py -k "equivalence" --tb=short -q` | per-element pass/fail diff (step log) |

Gates map to test-plan.md rows as follows:

- `unit-tests` covers AC-1 (`TestBorderAwareRedactRect`), AC-2 (`TestSideBySideSourceMasking`), AC-3 (`TestMaskCoversTextContent`), AC-5 (`TestConfinementNoNewImports`) — all Tier 0 unit classes in `tests/test_table_border_protection.py`.
- `golden-sample-regression` covers AC-4 (`tests/test_golden_regression.py`). Any re-baseline must cite this change-id.
- `renderer-equivalence` provides AC-3/AC-4 defence: confirms the geometry-only change does not break fitz/ReportLab element-level decision parity.
- Integration classes `TestOverlayBorderPreservation` and `TestSideBySideRightPanelMasking` (Tier 3, test-plan.md) run inside the `pytest tests/` sweep and are therefore covered by the `unit-tests` gate; no dedicated CI job is added.

No new CI job is introduced. The existing `contract-and-fast-tests` job covers `contract-validate`, `change-gate`, and `unit-tests`. The existing `golden-sample-regression` and `renderer-equivalence` jobs cover the remaining required gates.

## Workflow Changes Applied

Updated `.github/workflows/contract-driven-gates.yml`:

- **Active-change-gates comment** (line 3): updated from `none (archived: …)` to `p2-table-border-protection (archived: p1-cloud-providers, …)`.
- **Change-gate step** (job `contract-and-fast-tests`): replaced the `echo "No active change gates..."` placeholder with `cdd-kit gate p2-table-border-protection`.

No new jobs, steps, secrets, or caching config were added.

## Required Check Policy

All five gates listed in the table above are required. The PR is blocked until all five report success on the head commit. Branch protection must bind to the job `name:` values: `contract-and-fast-tests`, `golden-sample-regression`, `renderer-equivalence`.

## Informational Gate Promotion Policy

Integration tests (`TestOverlayBorderPreservation`, `TestSideBySideRightPanelMasking`) run inside `pytest tests/` and are covered by the `unit-tests` gate. If PyMuPDF availability is inconsistent across runner images, the affected integration sub-check must be quarantined to an informational sub-job per `contracts/ci/ci-gate-contract.md §Informational Gate Promotion Policy`; the remaining unit assertions stay required.

## Rollback Policy

Rollback trigger: `golden-sample-regression` fails on a pre-existing fixture field after merge, or `renderer-equivalence` reports an inclusion/bucket/text-source divergence attributable to this change.

Rollback action: revert the merge commit to `app/backend/renderers/fitz_renderer.py`. Golden fixture snapshots are pre-committed binaries; no snapshot regeneration is required on rollback. Any re-baseline commits that cited this change-id must also be reverted.

## Artifact Retention

Existing retention settings apply: `test-results` artifacts at 14 days (set in `contract-and-fast-tests` job). No new artifact upload steps are introduced for this change.

## Merge Eligibility

mergeable when all five required gates pass on the PR head commit: `contract-validate`, `change-gate`, `unit-tests` (including all `tests/test_table_border_protection.py` unit classes), `golden-sample-regression`, `renderer-equivalence`.
