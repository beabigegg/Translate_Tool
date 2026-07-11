# CI/CD Gate Plan

## Change ID
docx-body-textbox-dedup — Tier 2, medium risk, module-level (change-classification.md).
Bug-fix lane. No new CI gate and no CI/CD contract change: tasks 2.6 and 4.4
are `skipped`. This plan records the existing gates that apply; no
workflow-file edit is introduced.

## Required Gates
| gate | tier | required | trigger | command/workflow | artifact |
|---|---:|---:|---|---|---|
| contract-validate | 2+ | yes | PR/push | `cdd-kit validate --contracts` (job `contract-and-fast-tests`) | exit code 0 |
| change-gate | 2+ | yes | pre-commit/PR | `cdd-kit gate docx-body-textbox-dedup` (local/pre-PR, not a workflow step) | exit code 0 |
| new/updated tests — `tests/test_docx_body_textbox_dedup.py`, `tests/test_docx_header_footer.py` | 2+ | yes | PR/push | no dedicated step; swept by blanket `pytest tests/ -x -q` below | junit.xml |
| unit-tests (blanket sweep) | 2+ | yes | PR/push | `pytest tests/ -x -q --tb=short --junitxml=test-results/junit.xml`; also re-runs `tests/test_docx_parser.py`, `tests/test_docx_nested_tables.py` (AC-5) | junit.xml |
| golden-sample-regression | 2+ | yes | PR | `pytest tests/test_golden_regression.py --tb=short -q` — AC-5: textbox-free DOCX output byte-identical, no re-baseline | per-sample diff |
| full-regression | 2+ | yes (informational→escalates) | PR | `pytest tests/ -q --tb=short` | full-regression.xml |
| renderer-equivalence, text-expansion-benchmark, layout-detector-dependency-gate, libreoffice-conversion-gate | 2+ | yes | PR | unchanged — no textbox-strip surface touched | per gate, unchanged |

## New Workflow Changes
**None. `.github/workflows/contract-driven-gates.yml` is byte-for-byte unchanged.**

No dedicated targeted-test step for the new `tests/test_docx_body_textbox_dedup.py`:
the blanket sweep already collects any new `tests/test_*.py` file, and a
dedicated step would repeat the thrice-recurring drift in CLAUDE.md Promoted
Learnings. Fresh drift check performed for this change: `grep -n "cdd-kit
gate" .github/workflows/contract-driven-gates.yml` → zero matches
(change-gate is local-only, confirmed absent); `grep -n "pytest tests/"` →
exactly six lines, all mapping to live required gates (blanket sweep ×2,
golden-sample-regression, text-expansion-benchmark, renderer-equivalence,
libreoffice-conversion-gate) — no stale per-archived-change step, no leftover
`expose-output-mode-ui-gate` job. Prior close-outs' cleanup holds.

No new row in `contracts/ci/ci-gate-contract.md`. No CI/CD contract change
(tasks 2.6/4.4 `skipped`).

`tests/test_docx_header_footer.py::TestTxbxContentStrippedFromHeader::test_body_paragraph_textbox_fold_in_unchanged`
has one assertion intentionally flipped (test-plan.md "bug-pin repurpose"
row): it previously pinned the pre-fix fold-in behavior as "unchanged" —
exactly the bug BR-115's amendment reverses. Deliberate, reviewed update, not
a regression; covered by the same blanket sweep, no separate gate needed.

## Required Check Policy
`contract-validate` and the blanket sweep are Tier-2+ merge-blocking.
`full-regression` is informational-that-escalates. `change-gate` is
local-only, never run in CI (grep-confirmed above).

## Local Pre-PR Command Sequence
```
conda run -n translate-tool cdd-kit test run --phase collect
conda run -n translate-tool pytest tests/test_docx_body_textbox_dedup.py -v
conda run -n translate-tool pytest tests/test_docx_body_textbox_dedup.py tests/test_docx_header_footer.py tests/test_docx_nested_tables.py -v
conda run -n translate-tool cdd-kit validate --contracts
conda run -n translate-tool cdd-kit test run --phase full
cdd-kit gate docx-body-textbox-dedup
```
Full suite requires the `translate-tool` conda env (torch hard-errors
outside it, per CLAUDE.md), even though no test here touches QE/COMET.

## Informational Gate Promotion Policy
No promotion — a pure `python-docx` extractor-threading fix (routing body/cell
paragraph walk through existing `_p_text_no_txbx`) introduces no
non-deterministic field.

## Rollback Policy
No runtime kill-switch (no env var). Rollback is a git revert of the
extractor-threading swap at the four named call sites (collection L427,
SDT-branch/cell-branch/`_scan_our_tail_texts` restore reads) plus the amended
BR-115 scope; additive threading of an existing helper, no migration, no
wire-format break — revert restores byte-for-byte pre-change (body/cell
double-count) behavior.

## Artifact Retention
No new artifact type; existing 14-day retention on `junit.xml`/
`full-regression.xml` unchanged and sufficient.

## Merge Eligibility Decision
mergeable — once the blanket sweep passes with `tests/test_docx_body_textbox_dedup.py`
(new) and the repurposed assertion in `tests/test_docx_header_footer.py`
included, `cdd-kit validate --contracts` passes, `golden-sample-regression`/
`full-regression` show no new failures (AC-5), and `cdd-kit gate
docx-body-textbox-dedup` exits 0 pre-PR.

## Notes
No new CI gate, no CI/CD contract change, no workflow-file edit — relies
entirely on gates already required by `contracts/ci/ci-gate-contract.md`. See
§New Workflow Changes for the fresh drift check; see test-plan.md for the
full AC → test mapping and Test Execution Ladder.
