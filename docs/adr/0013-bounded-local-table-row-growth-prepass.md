# ADR 0013: Bounded local table-row growth as a shared upstream pre-pass

## Status
proposed

## Context
Industry DTP fix-order grows the frame/box BEFORE shrinking the font; commercial
layout-preserving PDF translators market table cells that auto-grow to fit
translated text. Our BR-36 cascade has no box-growth step: it shrinks font, then
compresses spacing, then (step d, currently dead — see ADR-0012 change) overflows
into local whitespace, then truncates. For table cells that still cannot fit, the
user-approved scope (pdf-text-overflow-fix Scope Amendment, AC-10) adds a BOUNDED
row-height growth: grow a cell's row and push ONLY the other rows within the SAME
table (same `table_id`, same page) down by the same delta. Full page/cross-table/
cross-page reflow is an explicit Non-goal, deferred to a future change.

This growth is a document-geometry mutation, not a per-element draw decision. It
requires the settled cascade font size and the actual wrapped-line count per cell
(known only AFTER translation), so a parser-time heuristic estimate is insufficient
and premature. Both PDF backends (fitz overlay, ReportLab side-by-side/fallback)
consume the same IR via `bbox_reflow.reflow_document`, so the growth must be applied
ONCE upstream of both — mirroring how Bug B's cell-extent correction already lives
in the parser upstream of both backends.

## Decision
Introduce a single shared row-growth pre-pass that runs on the translated
`TranslatableDocument` AFTER translation and BEFORE rendering — invoked once in
`pdf_processor._dispatch_render` (which holds `doc` before dispatching to either
backend), NOT inside either renderer and NOT at parse time. The pre-pass:
1. Groups TABLE_CELL elements by `(page_num, metadata["table_id"])`, then by
   `metadata["table_row"]` (all already populated by `_detect_and_mark_tables`).
2. For each row, measures each cell's required height at the settled cascade font
   size using the SAME `fit_text_cascade`/`_wrap_lines_simple` authority (ADR-0012),
   takes the row max, and computes `delta = required − current row height`.
3. When `delta > 0`, grows that row's cells' `y1` by `delta` and shifts every
   element in lower rows (and their `metadata["lines"]` whitening bboxes) down by
   the cumulative delta — in the IR, so BOTH backends inherit it.
4. Caps cumulative growth at the table's remaining local budget (page bottom margin
   or the top of the first non-table element below the table). When a row's required
   delta exceeds the remaining budget, it grows by the budget only and the residual
   falls through to cascade truncation + the AC-11 `job.warnings` entry. Growth is
   best-effort, never a new hard fit guarantee.

## Consequences
- New business rule (BR for bounded-local-row-growth; contract-reviewer owns) plus a
  data-shape note that TABLE_CELL bboxes and their sibling-row bboxes may be shifted
  post-translation, upstream of `reflow_document`.
- Reversing this later — e.g. relocating growth into one renderer, or estimating it
  parser-side from a fixed expansion factor — would silently desynchronise the two
  backends (the exact convergence failure BR-40/ADR-0012 guard against) or grow rows
  that do not need it; this ADR records the shared-upstream, post-translation,
  measured (not estimated) placement durably.
- Overlay-mode limitation: the source PDF background (original table rules/graphics
  preserved by `apply_redactions(graphics=0)`) is NOT moved, so pushed-down text can
  cross original horizontal rules. Side-by-side (fresh canvas) is unaffected. The
  bound (within-table, page-capped) limits but does not eliminate this; accepted as a
  best-effort improvement, with full reflow deferred.
- The pre-pass keeps the existing cascade ORDER (font-shrink → spacing → overflow →
  growth → truncation) rather than the pure DTP grow-first order — a deliberate
  lower-risk choice scoped to this change; a future reflow change may reorder.