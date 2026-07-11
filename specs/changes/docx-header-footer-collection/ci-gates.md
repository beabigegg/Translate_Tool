# CI/CD Gate Plan

## Change ID
docx-header-footer-collection — Tier 2, medium risk, cross-module
(change-classification.md). No new CI gate and no CI/CD contract change:
tasks 2.6 and 4.4 are `skipped`. This plan records the existing gates that
apply; no workflow-file edit is introduced.

## Required Gates
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 2+ | yes | PR/push | `cdd-kit validate --contracts` (job `contract-and-fast-tests`) | exit code 0 |
| change-gate | 2+ | yes | pre-commit/PR | `cdd-kit gate docx-header-footer-collection` (local/pre-PR, not a workflow step — see ci-gate-contract.md §Gate Inventory `change-gate` row) | exit code 0 |
| new tests — `tests/test_docx_header_footer.py` | 2+ | yes | PR/push | no dedicated step; already swept by the blanket `pytest tests/ -x -q` below | junit.xml |
| unit-tests (blanket sweep) | 2+ | yes | PR/push | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` (job `contract-and-fast-tests`); also re-runs `tests/test_docx_nested_tables.py` and `tests/test_docx_parser.py` (AC-2, AC-4, AC-5) | junit.xml |
| golden-sample-regression | 2+ | yes | PR | `pytest tests/test_golden_regression.py --tb=short -q` (job `golden-sample-regression`) — AC-6: body/table output must stay byte-stable | per-sample diff |
| full-regression | 2+ | yes (informational→escalates) | PR | `pytest tests/ -q --tb=short` (job `full-regression`) | full-regression.xml |
| renderer-equivalence, text-expansion-benchmark, layout-detector-dependency-gate, libreoffice-conversion-gate | 2+ | yes | PR | unchanged — no header/footer collection surface touched by these gates | per gate, unchanged |

## New Workflow Changes
**None. `.github/workflows/contract-driven-gates.yml` is byte-for-byte unchanged.**

No dedicated targeted-test step is added for `tests/test_docx_header_footer.py`:
the blanket sweep at line ~104 (`pytest tests/ -x -q --tb=short`) already
collects any new `tests/test_*.py` file, so a dedicated step buys no coverage.
This mirrors the immediately-prior `docx-nested-table-collection` close-out,
which withdrew the same kind of step and removed six stale per-archived-change
targeted-test steps (the last, `expose-output-mode-ui-gate`, generalized into
`frontend-tests`). Fresh drift check on the live workflow for this change:
zero `cdd-kit gate <id>` invocations exist anywhere in it (change-gate is
local-only), and no stale targeted-test step or `expose-output-mode-ui-gate`
job remains — the prior cleanup holds.

No new row in `contracts/ci/ci-gate-contract.md` §Gate Inventory. No CI/CD
contract change (`tasks.yml` 2.6 and 4.4 are `skipped`).

AC-6 (body/table output unchanged) is covered by `golden-sample-regression`
and `full-regression` with no dedicated step: `test_golden_regression.py`
diffs pre-existing IR fields, and header/footer collection runs strictly
after the body walk (design.md Q3), so body-segment-index drift would surface
there. AC-3 (COM shapes pass unchanged) has no Windows CI runner in this
pipeline; verified by source inspection (design.md Q1, ADR-0019) and the new
unit test file, not by a CI gate.

## Required Check Policy
`contract-validate` and the blanket sweep are Tier-2+ merge-blocking.
`full-regression` is informational-that-escalates (new failures block;
pre-existing do not). `change-gate` is local-only, never run in CI (grep-confirmed).

## Local Pre-PR Command Sequence
```
conda run -n translate-tool cdd-kit test run --phase collect
conda run -n translate-tool cdd-kit test run --phase targeted
conda run -n translate-tool cdd-kit test run --phase changed-area
conda run -n translate-tool cdd-kit validate --contracts
conda run -n translate-tool cdd-kit test run --phase full
cdd-kit gate docx-header-footer-collection
```
The full suite requires the `translate-tool` conda env (torch hard-errors
outside it, per CLAUDE.md Promoted Learnings), even though no test in this
change touches QE/COMET.

## Informational Gate Promotion Policy
No promotion — a pure `python-docx` header/footer tree walk (reusing the
existing `_process_container_content` walker) introduces no non-deterministic
field, so no quarantine candidate applies.

## Rollback Policy
No runtime kill-switch (no new env var — change-classification.md §Required
Contracts: Env; design.md §Migration/Rollback rejects a default-off flag, since
it would ship the fix dormant and preserve the silent-drop bug being fixed).
Rollback is a git revert of the new collection/restore helper and its one call
site after the body walk; additive to the walker plus element-identity dedup
(mirroring BR-81/BR-113), no migration, no wire-format break — a revert
restores byte-for-byte pre-change (headers/footers silently dropped) behavior.

## Artifact Retention
No new artifact type; existing 14-day retention on `junit.xml`/
`full-regression.xml` (set in the live workflow) is unchanged and sufficient.

## Merge Eligibility Decision
mergeable — once the blanket sweep passes with the new
`tests/test_docx_header_footer.py` included, `cdd-kit validate --contracts`
passes, `golden-sample-regression`/`full-regression` show no new failures
(AC-6), and `cdd-kit gate docx-header-footer-collection` exits 0 pre-PR.

## Notes
No new CI gate, no CI/CD contract change, no workflow-file edit — relies
entirely on gates already required by `contracts/ci/ci-gate-contract.md`. See
§New Workflow Changes for the fresh drift check confirming the prior
close-out's cleanup still holds; see test-plan.md for the AC → test mapping.
