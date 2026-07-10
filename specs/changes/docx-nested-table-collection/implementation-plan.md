---
change-id: docx-nested-table-collection
schema-version: 0.1.0
last-changed: 2026-07-10
---

> **AMENDED AFTER MEASUREMENT (supersedes any `id()`-based statement below).**
> `seen_tc` holds the `<w:tc>` ELEMENTS, never `id(cell._tc)`. The dedup lookup happens
> before the cell is emitted, so nothing holds the lxml proxy at lookup time; CPython
> recycles the freed address. Measured on a 60x5 table: an `id()`-keyed walk that does
> not retain the element gives 8 distinct values for 300 cells, against 300 when the
> elements are held. (An earlier draft claimed this would turn the change's 17% silent
> drop into a 95% one; that overclaim was corrected — the main cell loop masks the
> hazard, the depth-limit flatten path does not. See `evidence/id-key-hazard.md`.)
> Likewise `table_id` is a monotonically increasing document-order counter, not
> `id(<w:tbl>)`, and `seen_par_keys` holds paragraph elements, not `id(p._p)`.
> After this change `docx_processor.py` contains no `id()`-keyed collection.
> Evidence: `evidence/probe_id_recycling.py`. Contract: BR-81 (amended), BR-113.


# Implementation Plan: docx-nested-table-collection

## Source-Verification Result (done first, before planning)
This planner has Read/Grep only (no shell/exec). Every seam, symbol, line number
and structural claim in the task brief was verified against LIVE source; the
python-docx API was verified by reading its installed source in the
`translate-tool` conda env
(`/home/egg/miniforge3/envs/translate-tool/lib/python3.11/site-packages/docx/`).
All claims held — no design.md or contract correction is required. Key confirmations
(`file:line`):

- `_process_container_content(container, ctx)` — nested closure at
  `docx_processor.py:254`; ONLY call sites `:315` (SDT wrapper) and `:317`
  (`doc._body`). No other production caller (tests call it directly).
- `tid = id(child_element)` `:269` → `Segment(..., table_id=tid)` `:284-287`.
- `seen_par_keys` document-scoped set `:237`; `_get_paragraph_key` = `id(p._p)`
  `:220-228` (the dedup-by-identity precedent for `seen_tc`).
- `translate_docx` groups on `s.table_id` `:812-815`; per-group `num_rows`/`num_cols`
  `:832-833`; `final_tmap[(tgt, s.text, c)]` `:919` (main) and `:984` (fallback).
- `if config.JSON_STRUCTURED_TRANSLATION_ENABLED:` main path `:846`; legacy
  `else:` `:883`; `cell_text.split("\n")` at `:962-963` lives ONLY in the
  `translated_by_pos is None` fallback branch `:933-993`. Confirmed.
- `MAX_TABLE_NESTING_DEPTH` occurs nowhere in `app/backend/`.
- `CONTEXT_DETECTION_ENABLED = True` — bare assignment `config.py:128`, no
  `os.environ`, 2-line intent comment `:126-127` (the style to mirror).
- `Table`, `_Cell` already imported at `docx_processor.py:14`; `config` module
  imported at `:17`.
- python-docx (translate-tool env): `_Cell.tables` (`table.py:257`),
  `_Cell._tc` set in `__init__` (`table.py:198`, `self._tc = self._element = tc`),
  `_Cell.grid_span` (`table.py:229` → `CT_Tc.grid_span` `oxml/table.py:473`, reads
  `w:tcPr/w:gridSpan/@val`, **defaults to 1**), `_Cell.paragraphs` = DIRECT
  paragraphs only (`table.py:248`), table grid-column count `table._tbl.col_count`
  = `len(tblGrid.gridCol_lst)` (`oxml/table.py:176-178`).
- `_Table._cells` (`table.py:163-180`): a horizontally gridSpan-merged `<w:tc>` is
  returned as the SAME `_Cell` object repeated once per spanned column
  (`cells.append(cells[-1])` `:176-177`) — this is both the 52-vs-49 duplication
  cause AND why `id(cell._tc)` is stable across the repeats within one table.

## Objective
Make the DOCX `<w:tbl>` collection walk in `docx_processor.py`:
1. **Recurse** into every cell's `cell.tables`, emitting each nested `<w:tbl>` as
   its own table group (own `table_id = id(nested_tbl_element)`, own private 0-based
   `(row, col)` space), bounded by `MAX_TABLE_NESTING_DEPTH = 3` with flatten-and-warn
   at the limit (BR-113). Zero characters silently dropped at any depth (AC-1, AC-5).
2. **Reroute** a layout-frame cell's DIRECT paragraphs to the body/`para` path under
   the structural conjunction `cell.tables non-empty AND cell.grid_span ==
   table._tbl.col_count`; never otherwise (BR-114, AC-2, AC-4).
3. **Dedup** a horizontally-merged `<w:tc>` by `id(cell._tc)` (per-table `seen_tc`
   set) so it is emitted once at its origin column, not once per spanned column
   (BR-81 clarified; 49 distinct `<w:tc>` → 49 segments, AC-3).

All three live in the one `_process_container_content` `}tbl` branch. No wire-format
change; nested tables flow through the existing `translate_docx` grouping loop
unmodified. Behavior is additive and degrades sanely at
`JSON_STRUCTURED_TRANSLATION_ENABLED=0` (AC-6). Existing single-level table behavior
unchanged (AC-7).

## Execution Scope

### In Scope
- `docx_processor.py::_collect_docx_segments` — the `}tbl` branch inside
  `_process_container_content` (`:263-288`): recursion, frame-reroute gate, `seen_tc`
  dedup, depth guard + flatten-and-warn.
- `config.py` — add the `MAX_TABLE_NESTING_DEPTH = 3` module constant.
- New tests in `tests/test_docx_nested_tables.py` (owned by test-strategist per
  test-plan.md; backend-engineer makes them pass and re-runs the AC-7 set).

### Out of Scope
- No change to `translate_docx`'s grouping/serializer loop (`:807-993`) — nested
  groups flow through it as-is. The engineer's only duty there is to CONFIRM each
  nested `table_id` reaches `table_serializer`/`json_translation` (accepting ≠
  delivering — assert on the outgoing payload, per Known Risks).
- No JSON wire-format change (data-shape 0.18.x cell list unchanged).
- No BR-81 `tmap` key change (`(tgt, text, col)` shape and axis untouched).
- No new env var; no `JSON_STRUCTURED_TRANSLATION_ENABLED` change; no migration.
- BR-109 doc-context sampler thin-sampling on nested-only docs (follow-up, per
  design.md Open Risks / test-plan.md Out of Scope).
- Per-cell length-ratio truncation guard (separate change, design.md Open Risks).
- `.pptx`/`.xlsx` (no nesting surface); any `docs/TEST_DOC/` dependency (AC-8).
- No opportunistic refactor of `translate_docx`, the serializer, or the SDT branch.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | config | Add `MAX_TABLE_NESTING_DEPTH = 3` as a bare module constant in `config.py` with a comment marking it a hardcoded constant, NOT an env var (mirror `CONTEXT_DETECTION_ENABLED`; BR-113; env-contract.md forbids an env row). | backend-engineer |
| IP-2 | docx walk | Factor the `}tbl` handling (`docx_processor.py:263-288`) into a depth-parameterized inner helper so it can be invoked on a nested `<w:tbl>` at `depth+1` without changing the two `_process_container_content` call sites. | backend-engineer |
| IP-3 | docx walk | Per-table `seen_tc = set()` created fresh per `<w:tbl>`; skip a cell whose `id(cell._tc)` is already in it, so a merged `<w:tc>` emits exactly one cell segment at its origin (lowest) column (BR-81 clarified; AC-3). | backend-engineer |
| IP-4 | docx walk | Frame-reroute gate (BR-114): reroute the cell's DIRECT paragraphs to `para` via `_add_paragraph` iff `len(cell.tables) > 0 AND cell.grid_span == table._tbl.col_count`; emit an empty-text placeholder `cell` segment at `(row,col,table_id)` in place of the aggregated-text cell segment. Never reroute otherwise (AC-2, AC-4). | backend-engineer |
| IP-5 | docx walk | Recurse into `cell.tables` (each as its own group, own `id()`, own `(row,col)`) when `depth < MAX_TABLE_NESTING_DEPTH`, for BOTH frame and non-frame cells (BR-113/BR-114). At the depth limit, flatten each over-limit nested table's full text into the current cell's aggregated cell text and log exactly ONE WARNING per collection call (AC-5). | backend-engineer |
| IP-6 | verification | Confirm (assert at the outgoing boundary) that each nested `table_id` group reaches `table_serializer.serialize()`/`json_translation.build_table_payload` and that the flag-OFF path emits an independent grid per nested table (AC-6). | backend-engineer |
| IP-7 | tests | Make `tests/test_docx_nested_tables.py` (test-strategist-authored) pass; re-run the AC-7 breakage set green. | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | Q1 (structural conjunction), Q2 (bounded recursion, flatten-and-warn), Q3 (`id(<w:tbl>)` identity + private coords), Q4 (BR-81 key unchanged) | ratified constraints — do not relitigate |
| contracts/business/business-rules.md | BR-113 (nested collection + depth), BR-114 (frame reroute), BR-81 (merged-cell `id(cell._tc)` dedup clause), Table T rows 366-369 | behavior spec |
| contracts/data/data-shape-contract.md | §Table Serialization Wire Format; Known-consumers row for `docx_processor.py` (`:510`); schema-version 0.18.1 | wire boundary + nested payload note (already written) |
| test-plan.md | AC→test mapping table; Falsifiability; "Existing Tests Checked for Breakage (AC-7)"; Test Execution Ladder | tests to write/run + phases |
| ci-gates.md | Required Gates table; Local Pre-PR Command Sequence | verification commands |
| change-request.md | measured loss table; 52-vs-49; W-RM0901-G6 shape | fixture intent |

## Decisions this plan pins (within ratified design + contracts)

- **Depth semantics.** Top-level table = depth 1. Recurse into `cell.tables` only
  while `depth < MAX_TABLE_NESTING_DEPTH` (= 3), so depths 1, 2, 3 each emit as
  independent groups. At depth 3 do NOT descend into depth-4 tables; instead FLATTEN
  each such nested table's aggregated text into the depth-3 cell's cell text (BR-113
  "still collected as ordinary cell text"). Emit the depth-limit WARNING exactly once
  per `_collect_docx_segments` call via a `nonlocal` once-guard flag (AC-5's
  `test_recursion_terminates_at_max_depth_with_single_warning` nests to MAX+2 and
  asserts a SINGLE warning).

- **Full-width predicate (task item #3, the LIVE 1-column case).** Expression:
  `cell.grid_span == table._tbl.col_count` (grid_span defaults to 1; col_count =
  `len(tblGrid.gridCol_lst)`). For the AC-2 outer **1×1** frame: `grid_span(1) ==
  col_count(1)` → full-width TRUE; combined with `cell.tables` non-empty → REROUTE.
  This is correct and intended: a 1-column outer frame that also contains a nested
  table IS a frame by BR-114's definition, and its direct prose SHOULD go to the body
  path while the nested table ships as its own group. A 1-column DATA cell does NOT
  reroute because it fails the conjunction's first operand (`cell.tables` empty) —
  guarded by AC-4 `test_full_width_cell_without_nested_table_not_rerouted`. Grid rows
  with `w:gridBefore`/`w:gridAfter` (omitted leading/trailing cells) make grid_span <
  col_count → not full-width → conservative not-rerouted; acceptable (never a
  false-positive), documented, not handled specially.

- **Reroute placeholder (fills a design gap, contract-faithful).** For a rerouted
  frame cell: (a) emit each `cell.paragraphs` paragraph via `_add_paragraph(p, ctx)`
  (reuses `seen_par_keys` dedup and the body-path `(tgt, text, None)` key), and (b)
  emit an EMPTY-text `cell` segment (`text=""`) at `(row, col, table_id)` as the
  positional placeholder — consistent with the existing "collect cell even if empty"
  line (`:283-287`) and with BR-114's flag-OFF "empty positional placeholder" clause.
  For the degenerate outer-1×1 frame this yields a 1×1 all-empty outer group: harmless
  no-op (JSON path short-circuits on empty `content_cells` at `:853-854`; no LLM call).
  Do NOT emit the aggregated-text cell segment for a rerouted cell (that is the defect).

- **`seen_tc` scope (task item #4).** `seen_tc = set()` is a LOCAL, created fresh at
  the top of each table's processing (per `<w:tbl>`, including each nested recursion),
  NOT document-scoped like `seen_par_keys`. Reset-per-table is required because
  `id()` identity is only guaranteed stable/unique among objects simultaneously alive;
  a document-scoped set would risk CPython `id()` recycling across tables wrongly
  deduping a distinct cell in a later sibling table. A fresh per-table set makes
  correctness independent of cross-table `id()` reuse and cannot leak across siblings.
  Within one table the merged-cell repeats are the SAME `_Cell` object (verified
  `table.py:176-177`), so the first occurrence (lowest col = origin) is kept and the
  spanned-column repeats are skipped.

- **Recursion / reading order (task item #5).** Within a cell, emit the cell's
  direct-paragraph content FIRST (the aggregated `cell` segment, or the rerouted
  `para` segments), THEN recurse into `cell.tables` in document order. Justification:
  the pre-existing model already AGGREGATES a cell's direct paragraphs into one atomic
  `cell` segment (`:274-288`), so fine-grained interleaving of paragraphs and nested
  tables *within* a cell is already collapsed — a raw XML-child walk of `<w:tc>` would
  contradict that aggregation. Ordering does not affect output placement (translations
  are restored by segment identity in `_insert_docx_translations`, not by position in
  `segs`) nor grouping (each nested table is an independent `table_id` group). It only
  affects BR-78 context-window quality, for which "cell prose then nested tables" is a
  sensible reading order. The outer `_process_container_content` continues to walk the
  BODY in true document order (`:258`); only within-cell nested content uses
  prose-then-tables.

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/config.py` | edit (add ~3 lines after `:129`, the context-detection block, or adjacent to the table constants at `:222-227`) | `MAX_TABLE_NESTING_DEPTH = 3` bare constant + comment: hardcoded, NOT an env var (mirror `CONTEXT_DETECTION_ENABLED`; BR-113; env-contract.md). No `os.environ`. Read as `config.MAX_TABLE_NESTING_DEPTH` at the call site (module-attribute access, not `from config import`, so `monkeypatch.setattr(config, ...)` works — mirrors the `:153-156` guidance). |
| `app/backend/processors/docx_processor.py` | edit `_collect_docx_segments` `:254-317` | Factor `}tbl` body (`:263-288`) into a depth-parameterized inner helper (IP-2); add per-table `seen_tc` + `id(cell._tc)` dedup (IP-3); add BR-114 frame gate using `cell.grid_span`/`table._tbl.col_count` + empty placeholder (IP-4); recurse into `cell.tables` with depth guard + flatten-and-warn once-guard (IP-5). `Table`/`_Cell`/`config` already imported (`:14`,`:17`). |
| `tests/test_docx_nested_tables.py` | make pass (authored by test-strategist) | per test-plan.md AC→test map; every fixture built in-test via python-docx; no `docs/TEST_DOC/`. |
| AC-7 re-run set (see Test Execution Plan) | run, keep green | no edits expected (test-plan.md Test Update Contract: additive change). |

## Contract Updates
All contract text is ALREADY WRITTEN by contract-reviewer; the engineer must not
re-edit it, only satisfy it. Confirm on disk before coding:
- API: none.
- CSS/UI: none.
- Env: none. `MAX_TABLE_NESTING_DEPTH` is a hardcoded constant; env-contract.md
  forbids an env row (tasks.yml 4.3 skipped).
- Data shape: `contracts/data/data-shape-contract.md` — schema-version **0.18.1**,
  §Table Serialization Wire Format + Known-consumers row for `docx_processor.py`
  (`:510`) already note nested-table identity/payload boundaries and legacy degrade.
  Wire shape unchanged.
- Business logic: `contracts/business/business-rules.md` — schema-version **0.31.0**;
  BR-113, BR-114 present (`:124-125`); BR-81 dedup clause present (`:93`); Table T
  rows 366-369 present. No further contract edit in this plan.
- CI/CD: none (ci-gates.md; tasks.yml 2.6 / 4.4 skipped; workflow byte-for-byte
  unchanged).

## Test Execution Plan
Backend runs REQUIRE the conda env (torch hard-errors outside it, CLAUDE.md):
`conda run -n translate-tool cdd-kit test run --phase <p>`. `cdd-kit test select`
reads the AC→test mapping in test-plan.md (§"Acceptance Criteria → Test Mapping");
the bare node-ids below are the same targets, provided as the selector fallback.

| acceptance criterion | test file / target (node-id) | expected signal |
|---|---|---|
| AC-1 | `tests/test_docx_nested_tables.py::TestNestedCollectionCharacterParity::test_nested_table_text_not_dropped_recursive_walk` | collected-segment chars == full recursive-walk chars (0 dropped) |
| AC-2 | `tests/test_docx_nested_tables.py::TestLayoutFrameReroute::test_frame_cell_direct_paragraphs_routed_to_body_path` | frame prose appears as `para` segments |
| AC-2 | `tests/test_docx_nested_tables.py::TestLayoutFrameReroute::test_nested_table_under_frame_cell_reaches_serializer` | nested `table_id` group reaches `serialize()`/`build_table_payload` |
| AC-3 | `tests/test_docx_nested_tables.py::TestMergedCellDedup::test_merged_cell_spanning_columns_emits_single_segment_at_origin` | 1 segment at origin col, not one per spanned col |
| AC-3 | `tests/test_docx_nested_tables.py::TestMergedCellDedup::test_49_distinct_tc_not_52_segments` | 49 cell segments; correct text at each `(row,col)` |
| AC-4 | `tests/test_docx_nested_tables.py::TestFrameRerouteFalsePositiveGuard::test_multi_column_data_table_many_paragraphs_not_rerouted` | data cells stay on table path |
| AC-4 | `tests/test_docx_nested_tables.py::TestFrameRerouteFalsePositiveGuard::test_full_width_cell_without_nested_table_not_rerouted` | full-width-only cell NOT rerouted |
| AC-4 | `tests/test_docx_nested_tables.py::TestFrameRerouteFalsePositiveGuard::test_nested_table_cell_not_full_width_not_rerouted` | nested-but-not-full-width cell NOT rerouted |
| AC-5 | `tests/test_docx_nested_tables.py::TestNestingDepthGuard::test_recursion_terminates_at_max_depth_with_single_warning` | terminates; exactly one WARNING; no dropped text |
| AC-6 | `tests/test_docx_nested_tables.py::TestLegacyPipeGridDegrade::test_legacy_flag_off_nested_table_own_grid_no_crash` | flag-off: nested table = own grid, no crash, no parent-merge |
| AC-6 | `tests/test_docx_nested_tables.py::TestLegacyPipeGridDegrade::test_legacy_flag_off_rerouted_frame_leaves_placeholder` | flag-off: empty placeholder at frame `(row,col)` |
| AC-7 | `tests/test_table_context_translation.py` `tests/test_table_serialization.py` `tests/test_docx_parser.py::test_parse_deduplication` `tests/test_translatable_document.py` `tests/test_translation_service.py` `tests/test_orchestrator_phase0.py` | all green (single-level + BR-81 non-merged unchanged) |
| AC-8 | n/a (no runtime node; `grep -L "docs/TEST_DOC" tests/test_docx_nested_tables.py` at review) | directory stays untracked |

**Phase ladder (test-plan.md §Test Execution Ladder; ci-gates.md §Local Pre-PR):**
required floor is `collect`, `targeted`, `changed-area`; `contract` (affected — BR
+ data-shape) and `full` (final) also apply. Run:
```
conda run -n translate-tool cdd-kit test run --phase collect
conda run -n translate-tool cdd-kit test run --phase targeted
conda run -n translate-tool cdd-kit test run --phase changed-area
conda run -n translate-tool cdd-kit validate --contracts
conda run -n translate-tool cdd-kit test run --phase full
cdd-kit gate docx-nested-table-collection
```
Stop rules per test-plan.md §Stop Rules (`--maxfail=1`; no broad pytest before
targeted+changed-area pass; do not classify any failure as pre-existing/waived).

## Rollback
Git revert only. No flag, no migration, no wire-format break — the change is
additive to the `<w:tbl>` walk and adds one config constant; a revert restores
byte-for-byte pre-change collection behavior (ci-gates.md §Rollback Policy).

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this
  plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report
  `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request
  is approved.

## Known Risks
- **Accepting ≠ delivering (recurring subsystem defect).** A nested `table_id` that
  is set on a `Segment` but never reaches the serializer would pass a naive test.
  Assert AC-2 integration on the OUTGOING payload
  (`table_serializer.serialize()` / `json_translation.build_table_payload` input),
  never on `seen_tc` membership, a flag, or an attribute assignment (test-plan.md
  §Assertion Boundary Discipline; CLAUDE.md tautological-test forms).
- **`id(cell._tc)` stability on lxml proxies.** The plan relies on `_Table._cells`
  returning the SAME `_Cell` object for a horizontally-merged cell's repeats
  (verified in installed source). The backend-engineer (shell-capable) MUST execute
  the AC-3 merged-cell and AC-1 nested fixtures once to confirm `id(cell._tc)`
  stability empirically before claiming done — this planner could only read source,
  not run it.
- **Frame-reroute false positive (primary quality risk).** A real multi-column data
  cell wrongly rerouted loses row context and no sample document would catch it.
  Mitigated by the structural conjunction, the never-reroute tie-break, and the three
  AC-4 guards. `regression-report.md` (required per change-classification.md) must
  record the guarded cases.
- **Depth-limit flatten correctness.** At MAX depth the over-limit nested table's text
  must be FOLDED into cell text (not dropped, not emitted as a group). Verify AC-5
  asserts both no-drop (parity) AND exactly-one-warning; a silent drop here recreates
  the original defect.
- **`.cdd/code-map.yml` freshness.** Line numbers here were read directly from live
  source, not the map, so they are current as of this plan; if the engineer's live
  file differs (a sibling change landed), re-anchor by symbol name, not line number.
