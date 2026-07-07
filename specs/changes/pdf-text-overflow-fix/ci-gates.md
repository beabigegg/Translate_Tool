# CI/CD Gate Plan

## Change ID
pdf-text-overflow-fix

## Required Gates
| gate | tier | required | trigger | command/workflow | expected artifact |
|---|---:|---:|---|---|---|
| lint | 1 | yes | pull_request | existing `contract-and-fast-tests` workflow step | pass/fail |
| build | 1 | yes | pull_request | existing build step | pass/fail |
| unit | 1 | yes | pull_request | `pytest tests/ -x -q --tb=short` (existing blanket step — auto-discovers `test_text_region_renderer.py`, `test_pdf_parser.py`, `test_pdf_layout_table_fixes.py` extensions) | pass/fail |
| contract | 1 | yes | pull_request | `cdd-kit validate --contracts` (existing; checks amended BR-40 + new BR-98/99 + data-shape invariant) | pass/fail |
| integration | 1/3 | yes | pull_request | covered by the same blanket step (`test_coordinate_renderer.py`) | pass/fail |
| e2e-critical | 1 | no | — | not applicable this pass (full PDF-job E2E deferred to implementation session per change-classification.md) | — |
| visual | 2 | yes (implementation session only) | pull_request | rendered-PDF overlap/legibility verification via `visual-reviewer` — NOT this planning pass | pass/fail |
| data-boundary | 1 | yes | pull_request | BR-98 false-positive sanity-gate-discard case, covered by the same blanket step | pass/fail |
| resilience | 1/3 | yes | pull_request | `test_pdf_render_warnings.py::TestFitzFallbackWarning` extension, covered by the same blanket step | pass/fail |
| fuzz/monkey | 1/3 | no | — | not applicable | — |
| stress | 4/5 | no | — | not applicable | — |
| soak | 4/5 | no | — | not applicable | — |

## New Workflow Changes
None. The existing blanket `pytest tests/ -x -q --tb=short` step covers all
new/extended test files with zero workflow edits. `cdd-kit validate
--contracts` already checks `business-rules.md`/`data-shape-contract.md`
structure — sufficient to catch a partial/incomplete BR-40 amendment or a
missing BR-98/99 Decision Table row.

## Required Check Policy
`unit`, `integration`, `contract`, `data-boundary`, and `resilience` gates
are PR-required — resilience/data-boundary promoted to required (not the
usual nightly default) since this change's purpose IS fixing a rendering
defect; shipping without those regression tests running on every PR would
defeat the point. `visual` becomes PR-required only once the implementation
session lands (no rendered output exists yet in this planning pass).

## Informational Gate Promotion Policy
Not applicable this pass — visual gate promotion happens at implementation
time, not staged through an informational period.

## Rollback Policy
Medium risk: BR-40's amendment widens where the shared cascade is called
from (fitz path untouched) and the table-detection fallback is additive-only
(never overrides a successful strict-mode detection) — both are designed to
be safe to roll forward. Revert plan: reverting removes the wrap-fallback
and bbox-correction, restoring today's overflow behavior on side-by-side/
fallback and unreliable table-cell bboxes — i.e. reverting re-introduces the
exact reported defect, so this should be treated as roll-forward-preferred.

## Artifact Retention
Not applicable — no new artifact type produced (contract/prose + renderer
code changes only).

## Merge Eligibility Decision
No hard dependency on other in-flight changes — this change's file surface
(PDF renderers/parser) does not overlap with any of the QA-pipeline changes
planned earlier this session. Standard `unit`/`integration`/`contract`/
`data-boundary`/`resilience` PR-required gates sufficient once implemented.
Note: at actual contract-edit time, re-check `business-rules.md`'s
last-used BR number in case the unrelated `qa-judge-provider-consistency`/
`qa-judge-hang-recovery` changes (which independently also claim BR-98/99)
landed first — renumber this change's BR-98/BR-99 if so.

## Notes
No `ci-cd-gatekeeper` agent was required for this change (change-classifier
deferred it, along with backend-engineer/visual-reviewer/e2e-resilience-engineer/
qa-reviewer, to the later implementation session) — populated directly from
the existing, unmodified gate policy. See test-plan.md for exact test node
IDs and the flagged AC-3 (render_truncated on new paths) plumbing
dependency.
