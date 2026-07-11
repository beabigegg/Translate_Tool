# Evidence: the id(shape) hazard is MASKED in the real PPTX loop (same as DOCX)

BR-116's first draft cited "30 distinct table shapes collapsed to 2 keys under a
forced GC" as if `id(shape)` were a LIVE collision hazard the counter fix prevents.
Verified by sabotage that this is an OVERCLAIM — the same masking already documented
for DOCX (`specs/archive/2026/docx-nested-table-collection/evidence/id-key-hazard.md`).

## Sabotage (main Claude, snapshot → edit → run → restore; never git checkout)

Reverted `tid = next_table_id` to `tid = id(shape)` in `_emit_table` and ran the new
suite:

```
AC-4 collision/counter test under id() sabotage: 1 passed
full tests/test_pptx_group_shapes.py under id() sabotage: 8 passed
```

Restored from snapshot; sha256 byte-identical afterward.

## Why it is masked

Every populated table cell is emitted as `(SEGMENT_TABLE_CELL, cell, ...)`, storing
the `_Cell`. `_Cell._parent → Table → Table._graphic_frame` is the shape, so each
retained cell segment transitively keeps its shape alive. While `segs` is held, no
two simultaneously-live tables can share an `id()`. The isolated probe that showed
28/30 collisions did NOT retain the shapes (it only recorded `id()` in a set), which
is why it collided; the real collector retains them.

## Why the counter fix still stands (not reverted)

The `id()` key was correct ONLY by that unstated, untested retention invariant — the
exact fragility BR-81/BR-113 forbid relying on — and this change ADDS group recursion,
creating more shapes. The document-order counter removes the invariant entirely at
zero cost. Correct to keep; the JUSTIFICATION in BR-116 must not claim a live
collision in the real loop. Reworded accordingly (BR-116, CHANGELOG business 0.33.0).

## The AC-4 test is honest

`test_pptx_group_shapes.py` AC-4 docstring already states it cannot reproduce a
collision (cells retain shapes) and instead asserts the counter yields distinct keys
and no cross-table coordinate collision. It is a genuine guard on the counter's
correctness, not a tautology claiming to catch the id() bug.
