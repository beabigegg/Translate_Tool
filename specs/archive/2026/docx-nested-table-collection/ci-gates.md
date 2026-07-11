# CI/CD Gate Plan

## Change ID
docx-nested-table-collection — Tier 2, medium risk, cross-module
(change-classification.md). No new CI gate and no CI/CD contract change:
tasks 2.6 and 4.4 are `skipped`. This plan records existing gates that apply
plus the one new targeted-test step needed while this change is active.

## Required Gates
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 2+ | yes | PR/push | `cdd-kit validate --contracts` (job `contract-and-fast-tests`) | exit code 0 |
| change-gate | 2+ | yes | pre-commit/PR | `cdd-kit gate docx-nested-table-collection` (local/pre-PR, not a workflow step — see ci-gate-contract.md §Gate Inventory `change-gate` row) | exit code 0 |
| new tests — `tests/test_docx_nested_tables.py` | 2+ | yes | PR/push | no dedicated step; already swept by the blanket `pytest tests/ -x -q` below | junit.xml |
| targeted — table_context_translation (AC-7 regression) | 2+ | yes | PR/push | already swept by the blanket sweep below; no dedicated step needed (file not separately fast-failed today) | junit.xml |
| unit-tests (blanket sweep) | 2+ | yes | PR/push | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml` (job `contract-and-fast-tests`) | junit.xml |
| golden-sample-regression | 2+ | yes | PR | `pytest tests/test_golden_regression.py --tb=short -q` (job `golden-sample-regression`) | per-sample diff |
| full-regression | 2+ | yes (informational→escalates) | PR | `pytest tests/ -q --tb=short` (job `full-regression`) | full-regression.xml |
| renderer-equivalence, text-expansion-benchmark, layout-detector-dependency-gate, libreoffice-conversion-gate | 2+ | yes | PR | unchanged — no DOCX table/collection surface touched by these gates | per gate, unchanged |

## Workflow Changes Applied
**None. `.github/workflows/contract-driven-gates.yml` is byte-for-byte unchanged by this change.**

A dedicated `Targeted tests — docx_nested_tables` fast-fail step was drafted and
then deliberately withdrawn. The blanket sweep on the very next line
(`pytest tests/ -x -q --tb=short`) already collects `tests/test_docx_nested_tables.py`,
so the step bought no coverage — only a marginally earlier failure position in an
already fail-fast run.

Against that near-zero benefit stands a measured cost. `ci-cd-gatekeeper` read the
whole workflow and found **six** targeted-test steps still present whose sole
purpose was fast-failing a change that has since been archived
(`term-extraction-db-first`, `fallback-chain-cloud-providers`, `p3-table-structure`,
`p3-llm-judge`, `pdf-renderer-fallback-warn`, and the whole
`expose-output-mode-ui-gate` job). Two of those are the same instances CLAUDE.md
already records as having drifted undetected three times. The drift exists precisely
because each change adds a step and no change removes one. Adding a seventh to a pile
of six, for no coverage gain, would be indefensible; the drift is carried into
`/cdd-close` as a cleanup item instead.

Not drift, checked and excluded: the three "Env schema sync" grep steps and the
"Dead-import assertion" step name archived change-ids in comments, but they enforce
`contracts/env/env-contract.md` §Deployment Sync Policy permanently and are correctly
retained. Likewise the five gates promoted into `contracts/ci/ci-gate-contract.md`
§Gate Inventory (`golden-sample-regression`, `layout-detector-dependency-gate`,
`renderer-equivalence`, `text-expansion-benchmark`, `libreoffice-conversion-gate`).

No new row in `contracts/ci/ci-gate-contract.md` §Gate Inventory. No CI/CD contract
change (`tasks.yml` 2.6 and 4.4 are `skipped`).

AC-7 regression re-run (`test_table_context_translation.py` plus the other four files
in test-plan.md's "Existing Tests Checked for Breakage") gets no dedicated step
either: none of those five has a fast-fail step today, and the blanket sweep plus
`full-regression` already cover them.

## Required Check Policy
`contract-validate` and the blanket sweep (which collects the new
`tests/test_docx_nested_tables.py`) are Tier-2+ merge-blocking. `full-regression` is
informational-that-escalates (new failures block; pre-existing do not).
`change-gate` runs locally pre-PR only — no change in this repo runs
`cdd-kit gate <id>` inside CI today (verified by grep; see the
archived-change-id drift report delivered separately to the requesting agent).

## Local Pre-PR Command Sequence
```
conda run -n translate-tool cdd-kit test run --phase collect
conda run -n translate-tool cdd-kit test run --phase targeted
conda run -n translate-tool cdd-kit test run --phase changed-area
conda run -n translate-tool cdd-kit validate --contracts
conda run -n translate-tool cdd-kit test run --phase full
cdd-kit gate docx-nested-table-collection
```
The full suite requires the `translate-tool` conda env (torch hard-errors
outside it, per CLAUDE.md Promoted Learnings), even though no test in this
change touches QE/COMET.

## Informational Gate Promotion Policy
No promotion in this change — a pure `python-docx` tree walk introduces no
non-deterministic field, so no quarantine candidate applies.

## Rollback Policy
No runtime kill-switch (no new env var — change-classification.md §Required
Contracts: Env). Rollback is git-revert; the change is additive to the
`<w:tbl>` walk and BR-81 dedup with no migration and no wire-format break
(data-shape 0.18.0's cell-list shape is unchanged), so a revert restores
byte-for-byte pre-change collection behavior.

## Merge Eligibility
mergeable — once the blanket
sweep passes with AC-7's five re-run files included, `cdd-kit validate
--contracts` passes, `golden-sample-regression`/`full-regression` show no new
failures, and `cdd-kit gate docx-nested-table-collection` exits 0 pre-PR.

## Notes
No new CI gate definition, no CI/CD contract change, and no workflow-file edit:
this change relies entirely on gates already required by
`contracts/ci/ci-gate-contract.md`. See §Workflow Changes Applied for why the
drafted targeted-test step was withdrawn. See
test-plan.md for the AC → test mapping and Test Execution Ladder this plan's
local command sequence mirrors.
