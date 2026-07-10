# ADR 0018: DOCX nested-table collection and structural layout-frame routing

## Status
proposed

## Context

`docx_processor.py` walked each `<w:tbl>` reading only `cell.paragraphs`, dropping
all nested-table text (`cell.tables` was never read) — 17.1% and 35.8% of the
characters in two real documents. A merged `<w:tc>` was emitted once per spanned
column, translating one 4,827-char body cell four times.

The JSON wire format (data-shape 0.18.0, ADR-0017) carries no grid-shape constraint,
which for the first time makes it possible to ship a nested table as its own
coordinate payload. The superseded Markdown pipe-grid demanded a single
`num_rows × num_cols` matrix that a nested table cannot occupy.

Two of the user's documents also use a top-level table purely as a page frame: one
full-width merged cell holds the entire document body plus real nested tables.
Sending that cell as a single table cell risks the silent-shortening failure already
recorded in code — a 4,827-char cell returned 370 chars with `ok=True`, no error,
because the reply was not empty, only cut short.

## Decision

1. The `<w:tbl>` walk recurses into `cell.tables`, emitting each nested table as an
   independent table group keyed by a document-order counter (never `id(<w:tbl>)`) with its own 0-based `(row, col)`
   space, never merged into the parent's coordinates. Recursion is bounded by
   `MAX_TABLE_NESTING_DEPTH`; at the limit the content is flattened into cell text and
   one WARNING is logged — never dropped.
2. A merged `<w:tc>` is deduplicated by `<w:tc>` element identity (the set holds the elements, never `id(cell._tc)`, whose address lxml recycles) before emission and translated
   once at its origin column. BR-81's `(tgt, text, col)` key is unchanged: its axis is
   *different columns*, orthogonal to *one cell spanning columns*.
3. A cell's direct paragraphs are rerouted to the body path ONLY under the
   conjunction: it contains at least one nested table AND it spans the full width of
   its row. When the signals disagree, the cell is NOT rerouted. Paragraph count is
   explicitly not a routing signal.

## Consequences

- **The invariant future changes must not reverse:** the frame-reroute trigger must
  remain a structural conjunction that defaults to no-reroute. Loosening it to a
  paragraph-count or full-width-only signal would silently reroute genuine
  multi-column data cells to the body path, destroying their row context — a quality
  regression that neither sample document nor the character-parity assertion would
  catch.
- Nested tables become first-class independent payloads on both the flag-ON JSON path
  and the flag-OFF legacy pipe-grid (each as its own small dense grid), so the kill
  switch remains a true revert.
- Additive recursion strictly increases collected text. The only behaviour-changing
  edge is the tightly-gated frame reroute, guarded by an explicit false-positive
  fixture.
- A complete-but-shortened cell translation passes validation on BOTH wire formats
  (verified by execution). That is a pre-existing hazard, not introduced here. The
  frame reroute bounds the largest single call on the main path; a general per-cell
  length-ratio guard is a separate change.
- Supersedes nothing. Extends the ADR-0017 wire format without changing its shape.
