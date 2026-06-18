# CI Gates: p2-layout-detection

## Required Gates
| gate | tier | trigger | command / workflow | pass condition | owner |
|---|---:|---|---|---|---|
| contract-validate | 2 | PR / pre-commit | `cdd-kit validate --contracts` | exit 0 | platform-team |
| change-gate | 2 | PR / pre-commit | `cdd-kit gate p2-layout-detection` | exit 0 | platform-team |
| unit-tests | 2 | PR | `pytest tests/` | exit 0; junit XML uploaded | application-team |
| golden-sample-regression | 2 | PR | `pytest tests/test_golden_regression.py --tb=short -q` | all pre-existing IR fields match; reading_order-only diff not a regression | application-team |
| layout-detector-dependency-gate | 2 | PR | `! grep -E "(ultralytics\|onnxruntime-gpu)" app/backend/requirements.txt app/backend/environment.yml` | exit 0 (neither forbidden package present) | platform-team |

## Informational Gates
| gate | trigger | command / workflow | notes | owner |
|---|---|---|---|---|
| hf-download-live | nightly (Tier 3) | `pytest tests/ -k hf_live` | live HuggingFace download; not required at PR; out-of-scope per test-plan.md §Out of Scope | application-team |

## Tier Floor Override

Tier-floor keyword triggers expected on this change: `LAYOUT_DETECTOR_MODEL_PATH`, `model`, `weights`, `offline`, `download`, `integration`.
Override rationale: no DB migration, no auth flow, no cache layer, no external API endpoint — all inference is local and CPU-only at CI time. Override applied to **Tier 2** per `change-classification.md §Tier Floor Override`.

## Promotion Policy

- All Tier 2 required gates must be green before merge.
- A failed `layout-detector-dependency-gate` (ultralytics or onnxruntime-gpu detected) blocks merge with no override path — remove the forbidden package.
- `golden-sample-regression`: a diff limited to the `reading_order` field alone does not block merge; any pre-existing-field diff does (see `contracts/ci/ci-gate-contract.md §golden-sample-regression gate`).
- New Tier 3 nightly gate (`hf-download-live`) promoted to required only if AC-4 coverage gaps are found post-merge.

## Rollback Policy

Revert the PR. The layout detector is on an isolated code path (`parsers/layout_detector.py`) with no schema migration; revert restores the prior heuristic immediately. No DB rollback required.

## Merge Eligibility

mergeable when all five required gates pass and no open AC-8 violation (ultralytics import) is present.
