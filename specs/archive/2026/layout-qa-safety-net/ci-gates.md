# CI/CD Gate Review

Change: `layout-qa-safety-net` (Tier 3, backend-only, additive/default-off
`LAYOUT_QA_ENABLED`). See `change-classification.md` (AC-1..AC-9) and
`design.md` for the plan this review certifies.

## Required Gates for This Change
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| unit-tests | 2+ | yes | PR (`contract-and-fast-tests` job) | `pytest tests/` | junit XML — auto-picks up `tests/test_layout_qa.py`, edited `test_env_contract.py`/`test_orchestrator_judge.py` |
| contract-validate | 2+ | yes | pre-commit/PR | `cdd-kit validate --contracts` | exit 0 — auto-picks up env-contract.md + business-rules.md edits |
| change-gate | 2+ | yes | pre-commit/PR | `cdd-kit gate layout-qa-safety-net` | exit 0 |
| residual-text | 2+ | yes | PR | `pytest tests/test_pdf_layout_refactor.py -k "residual_text" --tb=short -q` | residual source-text count = 0 (unaffected by shim re-host) |
| biou-layout-fidelity | 2+ | no | PR | `pytest tests/test_layout_metrics.py -k "biou" --tb=short -q` | informational, unaffected |
| truncation-rate | 2+ | no | PR | `pytest tests/test_layout_metrics.py -k "truncation_rate" --tb=short -q` | informational, unaffected (BR-104 signal; no new logic here) |
| full-regression | 3 | no | nightly (`full-regression` job) | `pytest tests/ --tb=short -q` | junit XML — confirms flag-off byte-identical path nightly |

## Metric-Core Re-Host: CI-Transparency Verdict (independently verified)
`contracts/ci/ci-gate-contract.md` Gate Inventory rows for `residual-text`,
`biou-layout-fidelity`, `truncation-rate`, `reading-order-edit-distance` all
target **test files** (`tests/test_pdf_layout_refactor.py`,
`tests/test_layout_metrics.py`) — never `tests/metrics/{biou,residual_text,
truncation_rate}.py` module paths in the command column. Confirmed directly
from the contract text itself (not merely relayed from `design.md` Decision
1): the metric-core move into `app/backend/services/layout_qa.py` is
CI-transparent. **No `ci-gate-contract.md` edit required; task 2.6 correctly
stays `skipped`.**
Carry-forward requirement regardless: the re-export shims must keep
`tests.metrics.biou` (`compute_biou`, `_iou`, `BIOU_REGRESSION_BUDGET`),
`tests.metrics.residual_text` (`check_residual_text`), and
`tests.metrics.truncation_rate` (`compute_truncation_rate`) importable with
identical names/signatures, since `test_layout_metrics.py` /
`test_pdf_layout_refactor.py` import from those exact module paths even
though the contract only names the test files. backend-engineer's
import-site grep (design.md Open Risks) is the enforcement point;
qa-reviewer spot-checks it.
Note: `.github/workflows/contract-driven-gates.yml` is outside this agent's
authorized `context-manifest.md` paths (`cdd-kit context check` denied it);
job names above (`contract-and-fast-tests`, `full-regression`) are cited
from upstream task framing, not independently re-read — the verdict itself
rests solely on the authorized `ci-gate-contract.md` text.

## Workflow Changes Applied
None. No new job, trigger, secret, or `.github/workflows/*.yml` edit. The
existing blanket `pytest tests/` job auto-discovers the new test file and
edits; `cdd-kit validate --contracts` auto-discovers the env-contract.md
(0.16.0) and business-rules.md (0.25.0, BR-106) edits. No Makefile targets
affected.

## Artifact Retention
No new artifact type introduced. Existing junit XML / step-log artifacts
from `unit-tests`, `residual-text`, `biou-layout-fidelity`,
`truncation-rate`, `full-regression` are retained under each gate's current
CI setting; `contracts/ci/ci-gate-contract.md` § Artifact Retention Policy
has no repo-wide default yet — out of scope for this change to define.

## Promotion Policy
No tier changes. `biou-layout-fidelity`, `truncation-rate`,
`reading-order-edit-distance` remain informational (Tier 2+, non-blocking)
per the existing Informational Gate Promotion Policy — unaffected; no new
non-determinism introduced. `full-regression` stays Tier 3 nightly
informational (feature is default-off; no real-infra dependency to promote
against).

## Rollback Policy
Set `LAYOUT_QA_ENABLED=false` (already the shipped default) or `git revert`
the change commit. No data migration, no schema change, no API/UI surface.
Reverting also un-hosts the metric-core move; the shims guarantee
`tests.metrics.*` import paths keep working in either direction, so no gate
regresses mid-rollback.

## Merge Eligibility
mergeable — conditional on `unit-tests`, `contract-validate`, `change-gate`,
`residual-text` passing green (including new `tests/test_layout_qa.py` per
test-plan.md's AC-1..AC-4 mapping); `biou-layout-fidelity`/`truncation-rate`
remain informational and do not block.
