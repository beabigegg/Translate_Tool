---
change-id: pptx-group-shape-collection
schema-version: 0.1.0
last-changed: 2026-07-11
risk: medium
tier: 3
---

# Test Plan: pptx-group-shape-collection

Bug-fix lane (BR-116, referencing BR-113/BR-81). All fixtures for the new
test file are built in-test with `python-pptx`; no `docs/TEST_DOC/` or user
`.pptx` file is read anywhere in this plan.

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 (flat + single-level group text) | data-boundary | tests/test_pptx_group_shapes.py::TestGroupTextCollection::test_grouped_textbox_reaches_translate_texts_payload | 0 |
| AC-2 (nested group-within-group text) | data-boundary | tests/test_pptx_group_shapes.py::TestGroupTextCollection::test_nested_group_text_reaches_translate_texts_payload | 0 |
| AC-3 (grouped table coord mapping) | data-boundary | tests/test_pptx_group_shapes.py::TestGroupedTableCoordinates::test_grouped_table_cells_map_to_correct_row_col | 0 |
| AC-4 (counter replaces id(), no collision under GC) | resilience | tests/test_pptx_group_shapes.py::TestTableIdCounterNoCollision::test_many_grouped_tables_no_shared_key_under_forced_gc | 0 |
| AC-5 (flat-shape regression, output unchanged) | unit | tests/test_pptx_group_shapes.py::TestFlatShapeRegression::test_flat_textbox_and_table_output_unchanged | 0 |
| AC-6 (bounded depth, never-drop + one WARNING) | resilience | tests/test_pptx_group_shapes.py::TestGroupNestingDepthGuard::test_over_limit_group_still_collected_with_one_warning | 0 |
| AC-7 (SmartArt untouched) | unit | tests/test_pptx_group_shapes.py::TestSmartArtUntouched::test_smartart_path_not_invoked_for_group_collection | 0 |

## Bug-Fix RED Reproduction

`TestGroupTextCollection::test_grouped_textbox_reaches_translate_texts_payload`
(AC-1) is the named RED reproduction: build a slide with one plain textbox
and one 2-shape group; patch `translate_texts` and assert the grouped
textbox's literal text string is present in the captured `uniq` list
argument (the actual outgoing batch payload), never a collected-segment
count. Pre-fix, `GroupShape` reports `has_table=False`/`has_text_frame=False`
and is skipped by the flat loop, so this assertion FAILS with a behavioral
(not import/collection) error until the recursion lands.

## Falsifiability (production line whose deletion/inversion turns each family RED)

- AC-1/AC-2: deleting the `GroupShape.shapes` recursion branch (walking
  `shape.shapes` when `shape_type == MSO_SHAPE_TYPE.GROUP`) drops grouped
  text from the `uniq`/segment list.
- AC-3: same recursion branch applied to grouped `has_table` shapes;
  inverting row/col assignment inside the walk breaks the `(row, col) ->
  text` map.
- AC-4: reverting the document-order counter to `shape_id = id(shape)`
  (pptx_processor.py L220) collapses distinct tables' cells onto shared
  keys under forced GC (mirrors the measured 30-shapes-to-2-keys evidence).
- AC-6: deleting the `MAX_GROUP_NESTING_DEPTH` guard or its WARNING log call
  either recurses unbounded or silently drops the deepest group's content.
- AC-5/AC-7 are non-invocation/regression guards (no single deletable line):
  AC-5 pins pre-fix flat-shape output as its own baseline; AC-7 asserts
  `_extract_smartart_texts` call count is unchanged.

## Test Families Required

| family | tier | notes |
|---|---|---|
| data-boundary | 0 | AC-1/AC-2/AC-3 — assert on the collected segment list / captured `translate_texts` `uniq` payload, or on the `(row, col) -> text` map; never on `len(segs)` alone or an internal flag |
| resilience | 0 | AC-4 (id()-collision-under-GC, forced `gc.collect()` between table constructions) and AC-6 (depth-bound never-drop + exactly one WARNING; filter `record.name == "TranslateTool"` per the caplog root-logger-bleed hazard) |
| unit | 0 | AC-5 flat-shape regression (text/output diff vs pre-fix baseline) and AC-7 SmartArt non-invocation (call-count spy on `_extract_smartart_texts`, untouched) |

## Existing-Test Sweep (fakes/stubs that could break)

Grepped the whole `tests/` tree for `translate_pptx`, `pptx_processor`,
`SEGMENT_TEXT_FRAME`, `SEGMENT_TABLE_CELL`, `shape_id`, `id(shape)`. No test
constructs a fake collection loop, a fake `SEGMENT_*` tuple, or a mock shape
relying on `id(shape)` identity. All call sites
(`test_table_context_translation.py`, `test_output_mode_processors.py`,
`test_output_mode_orchestrator.py`, `test_orchestrator_phase0.py`,
`test_orchestrator_context_detection.py`, `test_ir_pipeline_decoupling.py`,
`test_layout_qa.py`, `tests/contract/test_legacy_conversion_disclosure.py`)
either patch `translate_pptx` at the orchestrator call boundary with a
generic `(*a, **kw)` fake, or drive it against a real python-pptx-built
single-table fixture (no collision risk, one table only). None require
updates for this change.

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | `conda run -n translate-tool pytest tests/test_pptx_group_shapes.py -v` | 1 | test-evidence.yml |
| changed-area | yes | `conda run -n translate-tool pytest tests/test_pptx_parser.py tests/test_table_context_translation.py -k pptx -v` | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| (none) | — | No existing test asserts flat-only collection as a contract; no update/delete required (see Existing-Test Sweep). |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- SmartArt extraction/translation path (`_extract_smartart_texts`) — separate, unmodified.
- Real user `.pptx` files / `docs/TEST_DOC/` — no fixture reads them.
- XLSX/DOCX processors — sibling surfaces already covered by `test_docx_nested_tables.py`; untouched here.
- UI, API, CSS, env, data-shape, CI contract surfaces — none required per change-classification.md.

## Notes

No QE/COMET or torch-dependent seam is touched; standard conda env suffices.
Bug-fix evidence (RED before fix) must be captured via `cdd-kit test run`
against the named AC-1 test per the bug-fix-lane agent-log rules.
