# Change Classification

No atomic-split trigger fires (checked all 4: cross-feature, cross-surface,
contract-heavy, task-heavy — none met). Bug A (side-by-side/fallback has no
word-wrap) and Bug B (table-cell bbox detection unreliable) are coupled by
design, not merely by symptom: Bug B is the shared upstream defect feeding
the identical `bbox_reflow` IR both PDF modes consume, and the Open Questions
explicitly tie the two decisions together (how much correction each layer
owns). Splitting would fracture one spec-architect design decision across
two artificially-dependent changes. Kept as ONE change.

## Change Types
- primary: business-logic-change, feature-enhancement
- secondary: bug-fix (symptom origin), refactor (renderer wrap-path reuse)

## Lane
- feature

Lane is `feature`, not `bug-fix`, despite the symptom-driven origin: the fix
is impossible without amending BR-40 (a business-rules contract that
currently forbids side-by-side/fallback wrap logic) — per the mixed-cases
rule, a fix that needs a contract change is promoted out of the pure
bug-fix lane to force the contract path.

## Risk Level
- medium

## Impact Radius
- cross-module (PDF renderer — side-by-side/fallback wrap gap; PDF parser —
  table-cell bbox detection; shared `bbox_reflow` IR; business-rules
  contract BR-40)

## Tier
- 2

## Architecture Review Required
- yes
- reason: BR-40 currently forbids the fix (cascade logic confined to fitz +
  `bbox_reflow.py`); must be explicitly amended or a deliberately-equivalent
  wrap pass designed for side-by-side/fallback — a non-obvious
  contract/design decision. Spans a module boundary (parser → shared IR →
  renderer) and alters data-flow of table-cell bboxes. Detection-strategy
  fallback (regression risk to already-working `find_tables()` cases) is an
  operational-risk trade-off requiring design review, not implementation-time
  inference.

## Required Artifacts
Always required: change-request.md, change-classification.md, implementation-plan.md, test-plan.md, ci-gates.md, tasks.yml, context-manifest.md

STOP after `implementation-plan.md` this pass — no `backend-engineer`/
`bug-fix-engineer` implementation this pass.

## Optional Artifacts (default: no — set yes only with explicit reason)
| artifact | create? | reason |
|---|---|---|
| current-behavior.md | no | current behavior already captured comprehensively (file:line map) in change-request.md |
| proposal.md | no | no product/behavior investigation gap; goal is clear |
| spec.md | no | behavior decisions fit in design.md + implementation-plan.md |
| design.md | yes | Architecture Review Required = yes (BR-40 direction, detection-strategy fallback, bbox data-flow) |
| qa-report.md | no | execution-phase artifact; implementation deferred |
| regression-report.md | no | execution-phase artifact; regression scope captured in test-plan.md this pass |
| visual-review-report.md | no | deferred to implementation session — set yes then, PDF overlap needs durable visual evidence bundle |
| monkey-test-report.md | no | not applicable |
| stress-soak-report.md | no | not a high-load/long-running change |

## Required Contracts
- API: none
- CSS/UI: none (PDF render output, not web UI/CSS)
- Env: none (reuses existing MIN_READABLE_FONT_PT, FONT_SIZE_SHRINK_FACTOR, FONT_SIZE_CONFIG; no new var)
- Data shape: likely — contracts/data/data-shape-contract.md (TABLE_CELL bbox-correctness invariant; pdf_layout_mode overlay/side_by_side must both hold the same bbox contract). Confirm with contract-reviewer.
- Business logic: yes — contracts/business/business-rules.md: amend BR-40 (cascade-path-restriction) and/or add a rule for side-by-side/fallback wrap; possible new rule for additive table-detection fallback. Must preserve BR-36/BR-38/BR-84/BR-85 guarantees.
- CI/CD: none

## Required Tests
- unit: yes — fit_text_to_bbox/font_utils wrap logic; render_text_region wrap+no-silent-draw; pdf_parser detection-strategy fallback; 1:1 block-to-cell bbox correction
- contract: yes — BR-40 amendment conformance; TABLE_CELL bbox invariant
- integration: yes — parser → IR → renderer for both side_by_side and overlay; ReportLab-fallback path (fitz-crash) wrap
- E2E: candidate — full PDF translate job on a table-heavy borderless document (deferred to implementation session)
- visual: yes — rendered-PDF overlap/legibility verification in both modes (execution-phase, via visual-reviewer)
- data-boundary: yes — thin/borderless table shapes, merged multi-column blocks, empty/degenerate cells
- resilience: yes — fitz-crash → ReportLab-fallback path must still wrap (BR-34 boundary)
- fuzz/monkey: no
- stress: no
- soak: no

## Required Agents
This pass (planning only — STOP after implementation-plan.md):
- spec-architect — writes design.md (BR-40 direction; detection-strategy fallback and false-positive tolerance; whether 1:1 cell bbox is corrected)
- contract-reviewer — BR-40 amendment + data-shape TABLE_CELL bbox invariant; guards BR-36/38/84/85 non-regression
- test-strategist — test-plan.md incl. Acceptance Criteria → Test mapping, additive-detection regression coverage
- implementation-planner — terminal agent this pass

Deferred to the later, separately-approved implementation session: `backend-engineer`/`bug-fix-engineer`, `visual-reviewer`, `e2e-resilience-engineer`, `qa-reviewer`.

## Inferred Acceptance Criteria
- AC-1: In side-by-side/synchronized PDF mode, translated text wider than its bounding box wraps to multiple lines within that bbox — no single-line horizontal overflow into adjacent content.
- AC-2: The ReportLab-fallback renderer (invoked when fitz crashes, BR-34) applies the same wrap-within-bbox guarantee as AC-1.
- AC-3: When no fit is achievable, side-by-side/fallback paths do NOT silently draw the full unwrapped string at floor font; the no-silent-truncation contract (BR-38 / render_truncated) is honored on these paths too.
- AC-4: For thin/borderless table PDFs, table-cell bounding boxes are recovered via an additive detection fallback so per-cell text no longer spans multiple columns' worth of width.
- AC-5: When a block aligns 1:1 with a detected cell, its bbox is corrected to the true cell extents rather than left sized to the (often short) source text.
- AC-6: Overlay/fitz-path guarantees (BR-36 wrap, BR-85 iterative scale-fit, BR-84 whitening, BR-38 marker) are unchanged — no regression on the currently-working path.
- AC-7: Documents where find_tables() already succeeds today produce identical-or-better output; the added detection strategy is attempted-after (additive), never a replacement.
- AC-8: BR-40 is amended (or a documented equivalent wrap pass is defined) so side-by-side/fallback wrapping does not violate the cascade-path-restriction contract, and the contract and code agree.
- AC-9 (added post-design, scope amendment): the cascade's existing "controlled overflow" step (step (d), text_region_renderer.py:369-384) actually fires on the overlay path — the hardcoded `available_whitespace_below=0.0` at fitz_renderer.py:511 is fixed to reflect real local whitespace.
- AC-10 (added post-design, scope amendment): before falling back to truncation, a TABLE_CELL element whose text still doesn't fit after font-shrink/compression/AC-9's overflow step triggers a bounded row-height growth — the cell's row height increases and ONLY the other rows within the SAME table (on the same page) are pushed down by the same delta. This does NOT cascade beyond the table's own local region (no cross-table, no cross-page reflow — see Non-goals).
- AC-11 (added post-design, scope amendment): whenever truncation still occurs after AC-9/AC-10's growth steps are exhausted, a `job.warnings` entry is added (mirroring the BR-96 legacy-conversion-disclosure pattern) identifying the affected file/page/segment, so truncation is visible to the user without requiring manual PDF inspection.

## Tasks Not Applicable
- not-applicable: 2.1, 2.2, 2.3, 2.6

(2.1 API + 2.2 CSS/UI + 2.3 Env + 2.6 CI/CD contracts: none needed. Task 1.3
REMAINS applicable — design review required. Implementation and
test-execution tasks (sections 3-4) are NOT not-applicable — deferred to the
later approved session, left pending.)

## Clarifications or Assumptions
- Kept as a single change (not split): no atomic-split trigger fires, and
  Bug A/Bug B are coupled through one shared IR (bbox_reflow) and one
  spec-architect design decision.
- Assumed this pass ends at implementation-plan.md; no product code written,
  no implementation/visual/QA execution agents invoked now.
- TATR path (TABLE_RECOGNITION_ENABLED, table_recognizer.py) stays out of
  scope per Non-goals — fix targets the default non-TATR bbox path only.
- contracts/data/data-shape-contract.md involvement is "likely" pending
  contract-reviewer confirmation of whether TABLE_CELL bbox-correctness is
  an explicit data-shape invariant or purely a business rule.
- CER-002 (specs/archive/2026/p3-table-structure/design.md) is NOT
  approvable — `.cdd/context-policy.json`'s forbiddenPaths baseline lists
  `specs/archive/**` as a hard, non-overridable block, identical in kind to
  the `specs/changes/*` cross-change block seen elsewhere this session. Main
  Claude briefs spec-architect in-prompt with that archived design's
  relevant finding (already captured via this session's own Explore
  investigation) instead of granting the read.
