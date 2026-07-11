# Archive — pptx-group-shape-collection

## Change Summary

PPTX text and tables nested inside a `GroupShape` were never translated: the flat
`for shape in slide.shapes` loop had no group branch, and a `GroupShape` reports
`has_table=False`/`has_text_frame=False` so it was silently skipped. The loop now
recurses into `GroupShape.shapes` (bounded by `MAX_GROUP_NESTING_DEPTH=3`, never
dropping at the bound), emitting the same tf/cell segment tuples so translation and
`obj_ref` write-back are unchanged. Same loop: the `shape_id = id(shape)` table-cell
grouping key was replaced by a per-presentation document-order counter.

## Final Behavior

Grouped and nested-group text frames and tables are collected and translated; grouped
table cells map to correct coordinates. Flat-shape PPTX output is unchanged.

## Final Contracts Updated

- `contracts/business/business-rules.md` 0.32.0 → 0.33.0: BR-116
  (`pptx-group-shape-collection`), referencing BR-113/BR-81.
- `contracts/CHANGELOG.md`: paired entry.

## Final Tests Added / Updated

`tests/test_pptx_group_shapes.py` (8 tests, all in-test python-pptx fixtures, none
reads `docs/TEST_DOC/`). Full suite 1401 passed, 0 failed.

## Final CI/CD Gates

No new gate, no CI/CD contract change, no workflow edit. Blanket sweep covers the new
file.

## Production Reality Findings

- **BR-116 overclaimed the `id()` hazard, and it was corrected before merge — a
  verbatim repeat of the DOCX sibling.** The first draft cited "30 tables → 2 keys
  under GC" as if `id(shape)` were a live collision in the real loop. The
  bug-fix-engineer flagged it did not reproduce; QA and main Claude independently
  confirmed by sabotage that reverting the counter to `id(shape)` leaves all 8 group
  tests green — the key is masked because each cell segment retains its parent shape
  via `_Cell._parent`. The counter fix stands (removes reliance on an unstated
  retention invariant; group recursion adds more shapes), but the justification was
  reworded honestly. Evidence: `evidence/id-key-masking.md`. This is the second time
  in this loop the `id()`-blast-radius overclaim recurred despite the promoted rule —
  see Lessons.
- The bug-fix RED (`test-runs/20260711-101108`) was a genuine behavioral assertion
  failure (grouped text absent from the outgoing payload), not an import error.

## Lessons Promoted to Standards

- **Contract (applied during the change):** BR-116 encodes the group recursion, the
  bounded-depth never-drop behavior, and the document-order counter, referencing
  BR-113/BR-81. The overclaim correction is recorded in BR-116 and evidence/id-key-masking.md.
- **CLAUDE.md (sharpened at close, net growth ≈ 0):** folded into the existing
  `id()`-on-lxml-proxy line — the `id()` key is now CONFIRMED masked-by-retention in
  BOTH office collectors, so an isolated no-retention probe's collision figure is the
  fragility, not a live defect, and a contract citing it as a live collision is an
  overclaim (recurred and corrected on BR-81, BR-113, AND BR-116). Frame the fix as
  removing an unstated invariant, not preventing a current collision.
- **Not re-promoted:** the bounded-recursion-never-drop pattern (BR-113/ADR-0018 already
  cover it); the tautological-test taxonomy.

## Follow-up Work

- `<w:sdt>` content controls INSIDE DOCX table cells are still dropped (top-level
  handled, cell-level not) — probed during the nested-table change; absent in the real
  files.
- The complete-but-shortened cell truncation (both wire formats accept a 15%-length
  translation with `ok=True`; the 4,827→370 live case) still has no per-cell
  length-ratio guard. Cache data shows expansion runs 0.8×–4.9× with source
  CJK-density, so the guard must model script composition. The biggest remaining
  correctness hazard; needs a design pass because a naive threshold false-positives
  (replacing a correct translation with source is worse than the bug).
- The body's pre-existing textbox double-count.
- The BR-109 doc-context sampler walks only top-level `doc.tables`.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and
active project guidance.
