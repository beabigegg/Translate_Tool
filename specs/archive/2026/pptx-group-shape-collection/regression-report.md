# Regression Report — pptx-group-shape-collection

The classifier required this report because the change alters observable output on
every PPTX translation job (grouped content now collected) and swaps the table-cell
grouping key.

## 1. Grouped content now collected (AC-1, AC-2, AC-3)

The flat `for shape in slide.shapes` walk was refactored into a bounded recursive
walker that descends into `GroupShape.shapes`. Grouped text frames and grouped
tables are emitted with the SAME segment tuples as flat shapes, so translation and
`obj_ref` write-back are unchanged once a shape is reached (contract-reviewer and
implementation-planner both verified the restore loop is `obj_ref`-based; no restore
edit).

Bug-fix RED (before the fix), recorded in `agent-log/bug-fix-engineer.yml`: a
synthetic slide with a plain textbox plus a 2-textbox group had the grouped text
ABSENT from the `translate_texts` `uniq` payload — a behavioral assertion failure,
not an import/collection error. After the fix all grouped/nested/table text is
present. Falsifiability: deleting the `GroupShape.shapes` recursion branch turns
AC-1/AC-2 RED (verified by the engineer's snapshot-sabotage).

## 2. Existing flat-shape PPTX unchanged (AC-5)

The leaf-emit branch order (`has_table` first with the same has_table-but-empty
swallow, then `has_text_frame`) is preserved exactly from the pre-fix flat loop.
`tests/test_pptx_parser.py` and the full suite stay green (`test-evidence.yml`,
phase `full`, `final-status: passed`). Evidence timestamp postdates every source/
test/contract file it covers.

## 3. The `id(shape)` → counter migration — and a contract overclaim corrected

`shape_id = id(shape)` (L220) is replaced by a per-presentation document-order
counter (`next_table_id`), mirroring DOCX BR-113.

**BR-116's first draft overclaimed the hazard, and it was corrected before merge.**
The draft cited "30 distinct table shapes collapsed to 2 keys under a forced GC" as
if `id(shape)` were a live collision in the real loop. The bug-fix-engineer flagged
that it does NOT reproduce against real code, and main Claude confirmed by sabotage
(snapshot→edit→run→restore, never `git checkout`): reverting the counter to
`id(shape)` leaves ALL 8 group tests green, including the AC-4 collision test. The
`id()` key is MASKED in the live loop because every emitted cell segment stores the
`_Cell`, which retains its parent shape via `_Cell._parent` — two simultaneously-live
tables cannot share an address while `segs` is held. This is the exact same masking
already documented for DOCX (`docx-nested-table-collection/evidence/id-key-hazard.md`).

The counter fix STANDS: it removes reliance on that unstated, untested retention
invariant (which BR-81/BR-113 forbid relying on), and this change adds group
recursion that creates more shapes. But the JUSTIFICATION was reworded in BR-116 and
the CHANGELOG to say so honestly. Evidence: `evidence/id-key-masking.md`.

The AC-4 test is itself honest: its docstring states it cannot reproduce a collision
(cells retain shapes) and instead asserts the counter yields distinct keys and no
cross-table coordinate collision — a genuine guard on the counter's correctness, not
a tautology claiming to catch the id() bug.

## 4. Depth bound never drops (AC-6)

Recursion is bounded by `MAX_GROUP_NESTING_DEPTH = 3` (config.py, not an env var).
At the bound a group's deeper contents are still collected via unbounded flat
extraction (mirrors DOCX `_flatten_nested_table_text`), with exactly one WARNING per
over-limit group via the `TranslateTool` logger. Falsifiability: the depth test
verified the never-drop behavior and the single warning (caplog filtered on
`record.name == "TranslateTool"`).

## 5. Residual risk (non-blocking)

- SmartArt (`_extract_smartart_texts`) is untouched and out of scope (AC-7).
- No user `.pptx` files exist, so verification is synthetic-fixture only — the same
  constraint the classifier set. The fixtures exercise single group, nested group,
  grouped table coordinates, ≥2 grouped tables, flat regression, and the depth bound.

## Verdict

No regression found. Grouped content collected (AC-1/2/3), flat PPTX unchanged
(AC-5), counter migration correct (AC-4), depth bound never drops (AC-6). The one
contract overclaim was caught and corrected before merge.
