# Design: docx-nested-table-collection

## Summary

The DOCX `<w:tbl>` walk in `docx_processor.py` reads only each cell's *direct*
paragraphs (`cell.paragraphs`) and never descends into nested tables
(`cell.tables`), silently dropping 7.3% and 25.2% of two real documents' body text (see `evidence/real-document-coverage.md`; the 17-36% figures in change-request.md used the emitted-character denominator, which double-counts the merged cell). It also emits a
merged cell once per spanned column, translating a 4,827-char body cell four
times. This change makes the walk (a) additively recurse into nested tables,
emitting each as its own table group with its own counter-assigned `table_id` and a
private `(row, col)` coordinate space; (b) route a *structurally identified*
layout-frame cell's direct paragraphs to the body path, so a document-body-sized
blob is not sent as one table cell; and (c) deduplicate a merged `<w:tc>` by
element identity before emitting, so it is translated once.

The JSON wire format (data-shape 0.18.0) is **unchanged** — a nested table already
ships as its own coordinate payload because that format carries no grid-shape
constraint. The existing table-group plumbing in `translate_docx` already supports
an arbitrary number of groups, so nested tables flow through it unmodified.

## Affected Components

| component | file path(s) | nature of change |
|---|---|---|
| DOCX segment walk | `app/backend/processors/docx_processor.py` (~L254-317) | recurse into `cell.tables` with a depth guard; dedup `<w:tc>` by element identity; counter-assigned `table_id`; structural frame-reroute of direct paragraphs to `para` segments |
| Table grouping | `app/backend/processors/docx_processor.py` `translate_docx` (~L807-993) | no logic change — nested groups flow through the existing `table_groups` loop; confirm each nested `table_id` reaches the serializer |
| Business rules | `contracts/business/business-rules.md` | new rule (nested collection, depth guard, frame-reroute gate); one clarifying sentence on BR-81; bump `schema-version` from live **0.30.0** |
| Data-shape notes | `contracts/data/data-shape-contract.md` §Table Serialization Wire Format | behaviour note only (a nested table is an independent payload with its own coordinate space; legacy degrade). Wire shape unchanged; bump `schema-version` from live **0.18.0** |
| ADR | `docs/adr/0018-nested-table-frame-routing.md` | records the frame-reroute gate and the rejected signals |

## Key Decisions

- **Q1 — Frame routing is a structural conjunction, not a fuzzy heuristic.** A
  cell's direct paragraphs are rerouted to the body path only when it satisfies
  BOTH structural OOXML facts: it contains at least one nested table, AND it spans
  the full width of its row (a merged cell covering every column). That is exactly
  the `W-RM0901-G6` row-12 frame shape.
  → **Rejected:** "many direct paragraphs" as an independent trigger. A genuine
  data cell legitimately holds many paragraphs, so it would misfire and strip row
  context — the AC-4 regression. Paragraph count is not used as a signal at all.

- **Tie-break when the signals disagree: never reroute.** Full-width but no nested
  table, or a nested table but not full-width → the cell's direct paragraphs stay on
  the table path (today's behaviour; still collected, still translated, row context
  intact). The conservative default provably cannot false-positive a data cell, at
  the cost of leaving a rare true frame on the table path — which is not a
  regression.
  → **Rejected:** any disjunctive or thresholded rule. Its failure mode is silent
  row-context loss that no sample document would catch.

- **Q2 — Bounded recursion; flatten and warn at the limit, never drop.** Recurse to
  `MAX_TABLE_NESTING_DEPTH` (proposed 3; the observed need is 1). At the limit the
  deepest cell's aggregated text is still collected as ordinary cell text and one
  WARNING is logged.
  → **Rejected:** a silent drop at the limit — it would recreate the exact defect
  being fixed. → **Rejected:** unbounded recursion — a malformed or cyclic document
  could hang the worker.

- **Q3 — Nested identity via a document-order counter; a private coordinate space.**
  Confirmed in source: `Segment.table_id` is what `translate_docx` groups on
  (L812-814); each group derives its own `num_rows` / `num_cols` and its own payload.
  A nested `<w:tbl>` therefore forms an independent group and payload with zero
  changes to the grouping code. It MUST NOT be merged into the outer table's
  coordinates.
  **Amended during implementation, on measured evidence.** Q3 originally specified
  `table_id = id(<w:tbl>)`, matching the live `tid = id(child_element)` (L269). That
  is unsafe as a general mechanism: lxml frees an element proxy the moment the walk
  releases it, and CPython recycles the address. It is correct today only because
  every cell `Segment` transitively holds its `<w:tbl>` alive via `cell._parent._tbl`
  — an undocumented invariant that nothing tests. `table_id` becomes a monotonically
  increasing per-document counter in document order. Nothing depends on its value:
  it is a grouping key and a log label, and no test asserts it.
  Noted, not changed: the `tmap` key `(tgt, text, col)` omits `table_id`, so
  identical `(text, col)` across two tables share a translation. Pre-existing and
  benign; flagged so a future change does not mistake it for new behaviour.

- **Q4 — BR-81's key does NOT move. The need for it was refuted.** BR-81's
  `(tgt, text, col)` axis means *different columns are translated independently*
  (Table T rows 364-365). A merged cell is ONE `<w:tc>` spanning columns — an
  orthogonal axis. The fix is to dedup by `<w:tc>` ELEMENT IDENTITY — a per-table
  `seen_tc` set holding the elements themselves — and emit the cell once at its
  origin column. The key shape is untouched: 49 distinct `<w:tc>` → 49 segments. The
  contract change is a one-sentence clarification on BR-81, not a key mutation. This
  materially shrinks the change.
  **The set must NOT hold `id(cell._tc)`.** CPython recycles a freed lxml proxy's
  address: a walk that records `id(cell._tc)` without retaining the element sees 8
  distinct keys for a 60×5 table's 300 cells, against 300 when the elements are held.
  An earlier draft of this decision claimed shipping the `id()` form would turn this
  change's 17% silent drop into a 95% one. **That was an overclaim, caught by
  `backend-engineer` and verified by sabotage before merge.** In the main cell loop
  every cell is emitted into a `Segment` — which retains `cell._tc` — before the next
  lookup, so `id()` keys are in fact masked there: switching them turns none of the 13
  new tests red. The depth-limit flatten path retains nothing, and switching *it*
  turns exactly one test red. The prohibition therefore stands on a different footing:
  correctness must not rest on an unstated, untested retention invariant that a
  sibling path in the same module does not satisfy. Same reasoning retires
  `seen_par_keys`' `id(p._p)`, leaving the module with no `id()`-keyed collection.
  Evidence: `evidence/id-key-hazard.md`.

- **Split exit: declined.** The `<w:tc>` dedup axis is genuinely independent of
  nested collection — that independence is *why* BR-81 stays put — which is the
  condition the classifier set for *permitting* a split, not for requiring one. Both
  fixes live in the one `<w:tbl>` emit loop and share one synthetic fixture;
  splitting would fork that loop and duplicate the fixture for no rollback benefit.

## Migration / Rollback

No data migration. Behaviour is gated by the existing
`JSON_STRUCTURED_TRANSLATION_ENABLED` kill switch (unchanged).

**Flag ON:** nested tables ship as independent coordinate JSON payloads; a rerouted
frame's prose takes the body / `translate_texts` path.
**Flag OFF (frozen legacy pipe-grid):** each nested table is its own small dense
`num_rows × num_cols` grid via the unchanged `serialize()` / `parse()`. It is never
merged into the parent matrix, so no phantom shape arises. A rerouted frame cell
leaves an empty positional placeholder in the parent grid and its prose goes to the
paragraph path. Both paths degrade sanely and never drop nested text.
Rollback is a flag flip; the new walk still collects the same segments, only the
table-translation transport reverts.

## Open Risks

- **Frame-reroute false positive (primary).** Mitigated by the structural
  conjunction, the never-reroute tie-break, and the AC-4 guard fixture (a real
  multi-column table that must stay on the table path). `regression-report.md` is
  required and must record the guarded cases.

- **A complete-but-shortened cell translation passes every validation, on BOTH wire
  formats.** Verified by execution against live source, not inferred. Sending a
  2,400-char cell and receiving a 360-char translation (15% of the source length) is
  accepted by `parse_json`: it parses, every sent coordinate is present, it is not an
  echo, and the schema holds. The legacy pipe-grid accepts the same reply when the
  shape is right (sent 2,400 chars, accepted 14). Both formats DO catch a
  mid-generation truncation — pipe-grid because rows go missing, JSON because the
  reply becomes unparseable — and both then fall back. **This is therefore a
  pre-existing hazard shared by both formats, NOT a regression introduced by
  `json-structured-translation-io`.** It is, however, the concrete reason the code
  already splits a big cell on `\n` in the BR-82 fallback path
  (`docx_processor.py` L950-985 records a live case: a 4,827-char cell returned 370
  chars with `ok=True`). The Q1 frame-reroute keeps any single LLM call bounded on
  the *main* path, which is the same protection at the collection stage rather than
  the fallback stage. A general per-cell length-ratio guard is a separate change;
  do not add one here.

- **`tmap` key lacks `table_id`.** Cross-table `(text, col)` collisions reuse one
  translation. Pre-existing; acceptable (same source text in the same column implies
  the same intent). Flagged only.

- **BR-109 doc-context sampler** (`orchestrator.py`) walks only top-level
  `doc.tables`, so a nested-only document samples thin. Out of scope here — it
  affects the one-sentence summary, not output text. Recorded as a follow-up.

- **Fixtures must be self-built** with `python-docx`; no test may touch the untracked
  `docs/TEST_DOC/`. The fixture set must exercise: nested-collection character parity
  (outer 1×1 frame + inner 2×2), single-emit for a merged cell, the AC-4
  real-multi-column false-positive guard, depth-guard termination, and a
  full-width-merged-cell-plus-nested-table frame reroute (prose lands as `para`
  segments, the nested table as its own group). Assert on collected segment content,
  never on an internal attribute.
