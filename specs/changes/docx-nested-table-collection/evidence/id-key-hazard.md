# Evidence: why `id()` may not key a cell-dedup set

Two measurements, both executed. The second corrects an overclaim in the first
draft of BR-81/BR-113.

## 1. The address really is recycled

`evidence/probe_id_recycling.py`, run under the `translate-tool` env:

```
A) id() key, no explicit gc  -> distinct: 8    false collisions: 292
B) element key               -> distinct: 300  false collisions: 0
C) emitted: [(0,0,'FRAME'), (1,0,'d0'), (1,1,'d1'), (1,2,'d2'), (1,3,'d3')]
```

Walking a 60×5 table and recording `id(cell._tc)` **without retaining the cell**
sees 8 distinct keys for 300 cells. lxml frees the element proxy as soon as the
walk releases it and CPython reuses the address. Holding the elements gives
300/300, and still dedups a merged `<w:tc>` to a single emit at its origin column.

## 2. But the main cell loop masks it — the first draft overclaimed

The initial BR-81 text asserted that an `id()`-keyed `seen_tc` "silently collapses
distinct cells into one", and design.md Q4 claimed shipping it "would have turned
this change's 17% silent drop into a 95% one". **Both were wrong**, and were
corrected before merge.

`backend-engineer` reported the masking; main Claude verified it by sabotage
(snapshot → edit → run → restore from snapshot; never `git checkout`):

| sabotage | result |
|---|---|
| `_process_table`'s `seen_tc` → `id(cell._tc)` keys | `tests/test_docx_nested_tables.py`: **13 passed** — hazard masked |
| `_flatten_nested_table_text`'s `seen_tc_local` → `id(cell._tc)` keys | **1 failed**, 12 passed — `TestNestingDepthGuard::test_flatten_at_depth_limit_survives_id_recycling_60x5` |

The reason for the asymmetry: in `_process_table` every cell is emitted into a
`Segment` (which stores the `_Cell`, hence `cell._tc`) before the next lookup, so
every key in `seen_tc` names a still-live element and no fresh proxy can reuse its
address. `_flatten_nested_table_text` retains nothing — it only accumulates text —
so it genuinely collapses cells.

## 3. The rule that survives

Never key a collection on `id()` of an lxml proxy. Not because the current main
loop breaks — it does not — but because its correctness rests on an unstated
retention invariant that nothing tests, and one sibling path in the same module
has no such retention and does break. Holding the element costs nothing and
removes the invariant.

The same reasoning retires the two pre-existing `id()` keys:
`tid = id(child_element)` (masked: each cell `Segment` transitively holds the
`<w:tbl>` via `cell._parent._tbl` — verified, 40 back-to-back tables, forced GC,
40 distinct ids, zero coordinate clashes) and `_get_paragraph_key = id(p._p)`
(masked: the key is recorded only after `segs.append(Segment(..., p, ...))`).
Both were correct. Neither was correct *for a stated reason*.

`docx_processor.py` now contains no `id()`-keyed collection.
