---
change-id: pptx-group-shape-collection
schema-version: 0.1.0
last-changed: 2026-07-11
---

# Implementation Plan: pptx-group-shape-collection

## Objective
Make `translate_pptx` (`app/backend/processors/pptx_processor.py`) additively recurse
into `GroupShape.shapes` so every text frame and table nested inside a PowerPoint
group (at any depth up to a config bound) is collected, translated, and written back —
today a `GroupShape` reports `has_table=False`/`has_text_frame=False` and is silently
skipped by the flat `for shape in slide.shapes` loop (L214-239). In the same edit,
replace the table-cell grouping key `shape_id = id(shape)` (L220) with a
per-presentation, monotonically increasing document-order counter so distinct tables
never collide under GC. Add `MAX_GROUP_NESTING_DEPTH` to `config.py`. This is a
**bug-fix lane** change: a RED reproduction (grouped text absent from the outgoing
`translate_texts` payload) must be captured before the fix lands. Behavior mirrors the
already-ratified DOCX sibling (ADR-0018, BR-113, BR-81) on the PPTX surface; the
contract entry is **BR-116** (already written).

## Live-Source Verification (implementation-planner's first duty — DONE)
Every seam named in the task brief and BR-116 was verified against current source. Results:

1. **Collection loop L214-239 — CONFIRMED.** `for slide in prs.slides:` → `for shape in slide.shapes:`; `has_table` branch L217-230 with `shape_id = id(shape)` at **L220** and the cell tuple `(SEGMENT_TABLE_CELL, cell, txt, r_idx, c_idx, shape_id)` at L225 (`continue` at L227); `has_text_frame` branch L233-239 emitting `(SEGMENT_TEXT_FRAME, tf, txt, None, None, None)` at L238. Segment tuple shape = `(segment_type, obj_ref, text, row, col, table_id)` (declared L209-211).
2. **`GroupShape.shapes` / `MSO_SHAPE_TYPE.GROUP` — CONFIRMED as the recursion target.** `MSO_SHAPE_TYPE` is **NOT imported** in `pptx_processor.py` (grep found the enum only in `parsers/pptx_parser.py:191`, which uses the magic number `6`). **The fix MUST add** `from pptx.enum.shapes import MSO_SHAPE_TYPE` to the imports (or, acceptably, test `shape.shape_type == MSO_SHAPE_TYPE.GROUP`). Do not copy the bare-`6` magic-number style from the parser.
3. **Restore loop L451-500 — CONFIRMED it writes back purely via `obj_ref`.** Text frames write to `obj_ref` (the tf) directly; cells write to `obj_ref.text_frame`; the `final_tmap` lookup key uses `seg[4]` (col) only. Grouped tf/cell segments carry their own `obj_ref`, so **the restore path needs NO change** (contract-reviewer's claim re-confirmed).
4. **`_cell_text` (L61) / `_ppt_text_of_tf` (L37) — CONFIRMED reusable unchanged** for grouped shapes.
5. **`MAX_TABLE_NESTING_DEPTH = 3` at `config.py:134` — CONFIRMED**, with the "Hardcoded constant, NOT an env var" comment (L131-133). `MAX_GROUP_NESTING_DEPTH` goes immediately beside it with a mirrored comment.
6. **The collection loop is a PLAIN function body** inline in `translate_pptx` (NOT a nested closure like DOCX's `_collect_docx_segments`). Decision below: introduce a nested helper inside `translate_pptx` and thread the counter via `nonlocal` (mirrors the DOCX closure style).
7. **`table_id` (`seg[5]`) consumer check — CONFIRMED safe to swap.** Grepped every consumer: it is used ONLY as (a) the `defaultdict` grouping key at L339 (`table_groups[seg[5]].append(seg)`) and (b) a log **display** value in the `[PPTX] Table %s …` messages (L378-394, L410-422, L341 iteration). Nothing treats it as an `id()`/address. A monotonic int is a drop-in.

**Nuance flagged (BR-116 depth-limit wording):** BR-116 says at the limit "a group's
contents are still collected via the same flat extraction **rather than recursed into
further**" AND "content is **never silently dropped**". Read literally, "not recursed
into further" could drop a still-deeper group's leaves. The never-drop clause governs:
the depth-limit flat extraction MUST still reach every leaf tf/table (descending
through deeper groups structurally) — it just stops using the bounded, warning-emitting
path and logs no further warnings. This matches the DOCX sibling `_flatten_nested_table_text`
(`docx_processor.py:284-305`), which recurses **without bound** at the limit. AC-6's
test asserts the over-limit group's content **is still collected** plus exactly one
WARNING, which this reading satisfies. No contract correction needed; implement per the
never-drop reading.

## Execution Scope

### In Scope
- Recurse into `GroupShape.shapes` in `translate_pptx`'s collection walk; emit the SAME `SEGMENT_TEXT_FRAME` / `SEGMENT_TABLE_CELL` tuples for grouped tf/tables.
- Depth-bound the recursion by a new `config.MAX_GROUP_NESTING_DEPTH`; at the bound, flat-extract (never drop) and log exactly one WARNING per over-limit group via the `TranslateTool` logger.
- Replace `shape_id = id(shape)` (L220) with a per-presentation document-order counter assigned as each table-bearing shape is visited (top-level and grouped alike).
- Add `MAX_GROUP_NESTING_DEPTH` to `config.py` beside `MAX_TABLE_NESTING_DEPTH` (hardcoded, NOT an env var).
- New test file `tests/test_pptx_group_shapes.py` (bug-fix RED→GREEN + AC-1..AC-7).

### Out of Scope
- SmartArt path (`_extract_smartart_texts` / `_update_smartart_texts`) — untouched; AC-7 asserts non-invocation.
- The restore/write-back loop (L451-500), `translate_texts`/table-serializer plumbing, JSON envelope logic — unchanged (grouped segments ride existing paths via `obj_ref`).
- DOCX/XLSX processors, orchestrator, API, UI, env/data-shape/CI contracts — no edits (change-classification.md "Required Contracts": all no except business-logic).
- No new `.env` variable; no feature flag / kill-switch (rollback = git revert).
- No refactor of unrelated pptx_processor code.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | config | Add `MAX_GROUP_NESTING_DEPTH = 3` at `config.py:135` (just after `MAX_TABLE_NESTING_DEPTH`) with a mirrored "Hardcoded constant, NOT an env var (mirrors MAX_TABLE_NESTING_DEPTH/BR-113)" comment. | bug-fix-engineer |
| IP-2 | pptx import | Add `from pptx.enum.shapes import MSO_SHAPE_TYPE` to `pptx_processor.py` imports (near L13-14). | bug-fix-engineer |
| IP-3 | pptx collection | Replace the flat loop body L214-239 with a nested recursive walker (see File-Level Plan) that recurses into `GroupShape.shapes` up to `MAX_GROUP_NESTING_DEPTH`, emits identical tf/cell tuples for grouped shapes, and flat-extracts + warns at the bound. | bug-fix-engineer |
| IP-4 | pptx counter | Initialize `next_table_id = 0` once before the slide loop; in the table branch do `next_table_id += 1; tid = next_table_id` (replacing `shape_id = id(shape)` L220) and use `tid` as `seg[5]`. Applies to top-level AND grouped tables. | bug-fix-engineer |
| IP-5 | tests | Author `tests/test_pptx_group_shapes.py` with the 7 classes/methods named in test-plan.md; build all fixtures in-test with `python-pptx` (no `docs/TEST_DOC/` reads). Capture the RED reproduction first. | bug-fix-engineer |
| IP-6 | evidence | Produce bug-fix agent-log with a genuinely-FAILED pre-fix `cdd-kit test run` for the AC-1 repro, then GREEN post-fix (see Test Execution Plan). | bug-fix-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| test-plan.md | AC→test mapping table; §Bug-Fix RED Reproduction; §Falsifiability; Test Execution Ladder | test files, RED target, phase commands |
| ci-gates.md | Required Gates table; §Local Pre-PR Command Sequence | verification commands (conda-scoped) |
| contracts/business/business-rules.md | BR-116 (this change), BR-113 (DOCX sibling), BR-81 (id()-hazard + col key) | implementation invariants (do not re-derive) |
| docs/adr/0018-nested-table-frame-routing.md | Decision §1 (document-order counter, bounded recursion, flatten-and-warn) | reused pattern |
| app/backend/processors/docx_processor.py | `_collect_docx_segments` L247-398 (`next_table_id`, `_process_table`, `_flatten_nested_table_text`, `depth < config.MAX_TABLE_NESTING_DEPTH`) | closure/counter/flatten pattern to mirror |
| app/backend/config.py | L131-134 `MAX_TABLE_NESTING_DEPTH` | sibling constant + comment style |
| change-classification.md | AC-1..AC-7; Lane: bug-fix; Tier 3 | scope, acceptance, owner map |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/config.py | edit (~L135) | IP-1: add `MAX_GROUP_NESTING_DEPTH = 3` beside `MAX_TABLE_NESTING_DEPTH`; hardcoded, NOT an env var. |
| app/backend/processors/pptx_processor.py | edit (imports ~L13-14) | IP-2: `from pptx.enum.shapes import MSO_SHAPE_TYPE`. Optionally add a module-level `from app.backend.utils.logging_utils import logger as _log` (already imported locally at L369/L410/L417) for the depth-limit WARNING. |
| app/backend/processors/pptx_processor.py | edit (replace L214-239) | IP-3/IP-4: new walker (see below). |
| tests/test_pptx_group_shapes.py | create | IP-5: 7 classes per test-plan.md; python-pptx in-test fixtures. |

### Recursion mechanism (IP-3/IP-4) — the exact shape of the replacement
Replace the current L214-239 body with a nested-closure walker inside `translate_pptx`
(the loop is a plain function body, so a `nonlocal`-threaded closure — mirroring DOCX
`_collect_docx_segments` — is the chosen mechanism; do NOT make it a module-level
helper, so it can close over `segs`, `src_lang`, and the counter without new params):

```
next_table_id = 0                       # per-presentation, document-order (replaces id())

def _emit_table(shape) -> None:
    nonlocal next_table_id, total_text_length
    table = shape.table
    next_table_id += 1
    tid = next_table_id                 # replaces `shape_id = id(shape)` (old L220)
    for r_idx, row in enumerate(table.rows):
        for c_idx, cell in enumerate(row.cells):
            txt = _cell_text(cell)
            if txt:
                segs.append((SEGMENT_TABLE_CELL, cell, txt, r_idx, c_idx, tid))
                total_text_length += len(txt)

def _emit_text_frame(shape) -> None:
    nonlocal total_text_length
    if not getattr(shape, "has_text_frame", False):
        return
    tf = shape.text_frame
    txt = _ppt_text_of_tf(tf)
    if txt.strip():
        segs.append((SEGMENT_TEXT_FRAME, tf, txt, None, None, None))
        total_text_length += len(txt)

def _emit_leaf(shape) -> None:
    # SAME branch order/semantics as the pre-fix flat loop (table wins, then tf).
    if getattr(shape, "has_table", False):
        try:
            _emit_table(shape)
            return
        except Exception:
            pass                        # shape claims has_table but has none (pre-fix L228-230)
    _emit_text_frame(shape)

def _flat_collect(shapes) -> None:
    # depth-limit flat extraction: reach every leaf tf/table WITHOUT the bound and
    # WITHOUT further warnings (never-drop). Mirrors _flatten_nested_table_text.
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            _flat_collect(shape.shapes)
        else:
            _emit_leaf(shape)

def _collect(shapes, depth) -> None:    # depth = group-nesting depth; 0 = not inside a group
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            if depth < config.MAX_GROUP_NESTING_DEPTH:
                _collect(shape.shapes, depth + 1)
            else:
                _log.warning(                       # name == "TranslateTool" (AC-6 filter)
                    "[PPTX] Group nesting exceeds MAX_GROUP_NESTING_DEPTH=%d; "
                    "flattening its contents instead of recursing further",
                    config.MAX_GROUP_NESTING_DEPTH,
                )
                _flat_collect(shape.shapes)
        else:
            _emit_leaf(shape)

for slide in prs.slides:
    _collect(slide.shapes, 0)
```

Notes for the engineer:
- **Counter (IP-4):** `next_table_id` is initialized ONCE before the slide loop (per-presentation, document order across all slides) and incremented per table-bearing shape in `_emit_table` — top-level and grouped alike. This is the exact BR-113/BR-116 mechanism. Nothing downstream assumes `seg[5]` is an `id()` (verified above), so no other edit is required.
- **Branch order must match pre-fix:** `has_table` is tested before `has_text_frame`, and the `has_table` `try/except` swallow (pre-fix L228-230) is preserved. This keeps AC-5 (flat-shape output unchanged) exact.
- **Depth semantics:** top-level `slide.shapes` is `depth=0`; a group encountered at depth `d` recurses to `d+1` iff `d < MAX_GROUP_NESTING_DEPTH`. With `MAX=3`, groups nested up to 3 levels are fully recursed; a 4th-level group is flat-extracted with one warning. State this in a code comment.
- **Reading order (AC-1/AC-2):** because `_collect` recurses at the point the group appears in its parent's shape list, a group's contents land in `segs` **at the group's document-order position** — interleaved after preceding flat siblings and before following ones, matching python-pptx shape-tree order. Do not sort or defer grouped segments.
- **WARNING channel (AC-6):** use `logging_utils.logger` (`logging.getLogger("TranslateTool")`) so `record.name == "TranslateTool"`; a `getLogger(__name__)` call would fail the caplog filter. Exactly one warning per over-limit group encountered on the bounded path; `_flat_collect` logs none.
- The `_extract_smartart_texts(in_path)` call (L242) and everything from L241 onward stay exactly as-is.

## Contract Updates
- API: none.
- CSS/UI: none.
- Env: none (`MAX_GROUP_NESTING_DEPTH` is a hardcoded `config.py` constant, NOT an `.env` var — mirrors `MAX_TABLE_NESTING_DEPTH`).
- Data shape: none (grouped tf/cell reuse existing segment tuple + IR; no new field).
- Business logic: BR-116 already authored (contract-reviewer). Implementation must conform; do not edit the BR. `schema-version` bump owned by contract-reviewer, not this agent.
- CI/CD: none (no workflow/Makefile edit; new test file rides the existing blanket sweep — ci-gates.md §Workflow Changes Applied).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (flat + single-level group text) — RED repro | tests/test_pptx_group_shapes.py::TestGroupTextCollection::test_grouped_textbox_reaches_translate_texts_payload | grouped textbox literal string present in captured `translate_texts` `uniq` arg; FAILS (behavioral) pre-fix |
| AC-2 (nested group-within-group text) | tests/test_pptx_group_shapes.py::TestGroupTextCollection::test_nested_group_text_reaches_translate_texts_payload | nested-group text present in `uniq` payload |
| AC-3 (grouped table coord mapping) | tests/test_pptx_group_shapes.py::TestGroupedTableCoordinates::test_grouped_table_cells_map_to_correct_row_col | each cell maps to correct `(row, col)`; assert selection, not count |
| AC-4 (counter replaces id(), no collision) | tests/test_pptx_group_shapes.py::TestTableIdCounterNoCollision::test_many_grouped_tables_no_shared_key_under_forced_gc | distinct tables → distinct `seg[5]` keys under forced `gc.collect()`; assert captured key at grouping boundary |
| AC-5 (flat-shape regression) | tests/test_pptx_group_shapes.py::TestFlatShapeRegression::test_flat_textbox_and_table_output_unchanged | non-grouped output identical to pre-fix baseline |
| AC-6 (bounded depth, never-drop + 1 WARNING) | tests/test_pptx_group_shapes.py::TestGroupNestingDepthGuard::test_over_limit_group_still_collected_with_one_warning | over-limit content still collected; exactly one `record.name == "TranslateTool"` WARNING |
| AC-7 (SmartArt untouched) | tests/test_pptx_group_shapes.py::TestSmartArtUntouched::test_smartart_path_not_invoked_for_group_collection | `_extract_smartart_texts` call count unchanged |

**Required phases (floor):** `collect`, `targeted`, `changed-area` — always. `contract`
(`cdd-kit validate --contracts`) applies (BR-116 landed). `full` for final/CI. Full ladder
and stop rules live in test-plan.md §Test Execution Ladder / §Stop Rules; do not restate.

**Conda-scoped run commands** (evidence via `cdd-kit test run`; child pytest must resolve
to the `translate-tool` interpreter):
- targeted: `conda run -n translate-tool cdd-kit test run --phase targeted` (target `tests/test_pptx_group_shapes.py`)
- changed-area: `conda run -n translate-tool cdd-kit test run --phase changed-area` (targets `tests/test_pptx_parser.py tests/test_table_context_translation.py -k pptx`)
- full: `conda run -n translate-tool cdd-kit test run --phase full`

## Bug-Fix RED→GREEN Boundary (bug-fix lane)
1. **RED first:** with the fix NOT applied (pre-fix `pptx_processor.py`), run the AC-1 repro
   `TestGroupTextCollection::test_grouped_textbox_reaches_translate_texts_payload` via
   `conda run -n translate-tool cdd-kit test run --phase targeted`. It MUST fail with a
   **behavioral assertion failure** (grouped text absent from the captured `uniq`), NOT a
   collection/import error. Recipe if the test file imports a fix-introduced symbol: keep any
   new pure symbol in place and temporarily restore ONLY the pre-fix collection body from a
   **scratch copy** (never `git checkout`/`stash`/`restore`). The failed run-dir persists as
   the referenced evidence.
2. **GREEN:** apply IP-1..IP-4, re-run the same phase — the repro passes.
3. Record both in `agent-log/bug-fix-engineer.yml` with a `bug-fix:` block whose
   `test-reproduced` reproduction points at the FAILED pre-fix run and whose reproduction/
   regression `command` equals that run's recorded command minus runner-added flags
   (see CLAUDE.md bug-fix evidence rule / ADR-0006 §6/§7).

## Existing-Test / Fakes Sweep
test-plan.md §Existing-Test Sweep already grepped the whole `tests/` tree for
`translate_pptx`, `pptx_processor`, `SEGMENT_*`, `shape_id`, `id(shape)`: no fake collection
loop, no fake `SEGMENT_*` tuple, no mock shape relying on `id(shape)` identity. All call
sites patch `translate_pptx` at the orchestrator boundary or drive a single real python-pptx
table (no collision surface). **No existing test needs updating.** Re-confirm with a grep
before marking done (CLAUDE.md shared-seam fakes rule), but expect zero edits.

## Rollback
Standard git revert of the `pptx_processor.py` + `config.py` changes (and the new test file).
No feature flag, no CI/CD artifact, no env var to unwind (ci-gates.md §Rollback Policy).

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history; this plan +
  BR-116 + test-plan.md are the packet.
- Do not re-copy full design/test-strategy/CI/contract prose; follow the Source Artifact Pointers.
- Keep edits within the File-Level Plan. Any read/write outside `## Allowed Paths` needs a
  Context Expansion Request approved first.
- If design/contract/source cannot all be satisfied (e.g. a seam is not where BR-116 claims),
  stop and report `blocked` — do not guess.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.

## Known Risks
- **Depth-limit wording (flagged above):** implement the never-drop reading; AC-6 enforces it. If a future reviewer reads BR-116 literally as "shallow flatten," the `_flat_collect` recursion is the reconciling choice — leave the code comment explaining it.
- **Branch-order regression:** if the engineer reorders `has_table`/`has_text_frame` in `_emit_leaf`, a table-bearing shape could be mis-collected; AC-5 guards this but keep the pre-fix order.
- **Logger name drift:** the WARNING MUST go through `logging_utils.logger` ("TranslateTool"), not `getLogger(__name__)`, or AC-6's caplog filter silently never matches (caplog root-logger-bleed hazard).
- **Counter scope:** `next_table_id` must be per-presentation (initialized before the slide loop), not per-slide — otherwise two tables on different slides could share key 1. AC-4 covers cross-shape collision but build the fixture across slides to be safe.
- `.cdd/code-map.yml` was not consulted for this plan (line ranges were verified directly against live source, which is authoritative); no staleness risk to this plan.
