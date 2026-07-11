# Regression Report — docx-nested-table-collection

The classifier required this report because the change alters behaviour on a path
every DOCX job uses, and because the BR-114 frame-reroute carries a specific
silent-regression risk: a genuine multi-column data cell rerouted to the body path
would lose its row context, and neither sample document would necessarily catch it.

## 1. The guarded false positive (AC-4)

BR-114 reroutes a cell's direct paragraphs only under a **structural conjunction**:
the cell contains ≥1 nested table AND spans the full width of its row. When the
signals disagree, it never reroutes. Paragraph count is not a signal at all.

Three tests hold both disagreement directions and the tempting-but-wrong signal:

| guarded case | test | outcome |
|---|---|---|
| genuine multi-column data cell holding many paragraphs | `test_multi_column_data_table_many_paragraphs_not_rerouted` | stays on the table path |
| full-width cell, **no** nested table | `test_full_width_cell_without_nested_table_not_rerouted` | stays on the table path |
| nested table, **not** full-width | `test_nested_table_cell_not_full_width_not_rerouted` | stays on the table path |

The 1×1 outer frame (`grid_span == col_count == 1`) with a nested table **does**
reroute. That is intended, not a false positive: a 1-column table whose only cell
wraps another table is a layout frame by construction. AC-2's fixture depends on it.

Falsifiability confirmed by sabotage (snapshot → edit → run → restore; never
`git checkout`): inverting either operand of the conjunction, or replacing `and`
with `or`, turns these tests red.

## 2. Existing behaviour held (AC-7)

Re-run green, no edits required:
`tests/test_table_context_translation.py`, `tests/test_table_serialization.py`,
`tests/test_docx_parser.py`, `tests/test_output_mode_processors.py`,
`tests/test_translatable_document.py`, `tests/test_translation_service.py`,
`tests/test_orchestrator_phase0.py`.

Full suite: **1375 passed, 4 pre-existing skips, 0 failures** (`test-evidence.yml`,
phase `full`). Evidence mtime verified to postdate every source, test and contract
file it covers — the staleness gap that blocked `json-structured-translation-io`.

No test double needed updating. `_process_container_content` is a nested closure
with only two internal call sites, and `translate_docx`'s public signature is
unchanged; grep across the whole `tests/` tree found no fake reproducing either.

## 3. Real-document verification

`evidence/real-document-coverage.md`, run against the user's two untracked files.
Paragraph drop: 65/275 → **0** and 218/523 → **0**. Table groups collected: 1 → 3
and 1 → 7. Redundant emitted characters: 26,203 → 101. Largest single table cell
handed to the LLM: 8,729 chars → 207.

That last row matters beyond this change. A comment in `docx_processor.py` records
a live failure where a 4,827-char cell returned 370 chars with `ok=True`. Both wire
formats accept a complete-but-shortened cell and cannot detect it (`design.md`
§Open Risks). After the reroute, no main-path cell approaches that size.

## 4. Two claims corrected before merge, not after

Recorded because both were wrong in an artifact that had already been approved.

- **`id()` overclaim.** BR-81's first draft asserted an `id(cell._tc)`-keyed dedup
  set "silently collapses distinct cells into one", and design.md put the damage at
  "17% → 95%". `backend-engineer` reported the main cell loop masks the hazard.
  Verified by sabotage: switching `_process_table`'s set to `id()` keys leaves all
  13 new tests green, because every cell is emitted into a `Segment` before the next
  lookup. Only `_flatten_nested_table_text`, which retains nothing, goes red. The
  prohibition stands — correctness must not rest on an unstated retention invariant
  a sibling path does not satisfy — but the contract now says so for the true
  reason. `evidence/id-key-hazard.md`.

- **Unreproducible drop figures.** The contracts initially carried
  change-request.md's 17.1% / 35.8%. Those denominators count the pre-change
  collector's *emitted* characters, which include the merged cell's duplicates, so
  they are not a document-text ratio. Replaced with the reproducible 7.3% / 25.2%
  and the method that produces them.

## 5. Residual risk

- A general per-cell length-ratio truncation guard is **not** added here. Both wire
  formats still accept a complete-but-shortened cell. The reroute bounds cell size
  on the main path but does not detect a short reply. Separate change.
- The BR-109 doc-context sampler in `orchestrator.py` still walks only top-level
  `doc.tables`, so a nested-only document samples thin. Affects the one-sentence
  summary, not output text. Separate change.
- The `tmap` key omits `table_id`, so identical `(text, col)` across two tables
  shares a translation. Pre-existing, benign, now stated in BR-81 and Table T.

## Verdict

No regression found. The three reroute false-positive guards, the AC-7 suite, and
the two-document real-run all hold.
