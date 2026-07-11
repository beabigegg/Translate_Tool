---
change-id: docx-nested-table-collection
schema-version: 0.1.0
last-changed: 2026-07-10
risk: medium
tier: 2
---

# Test Plan: docx-nested-table-collection

All new tests live in `tests/test_docx_nested_tables.py` (confirmed absent
today). Every fixture is built in-test with `python-docx` (`add_table()`,
nested `cell.add_table()`); no test reads `docs/TEST_DOC/` (AC-8). New tests
call `_collect_docx_segments`/`_process_container_content` directly (unit) or
drive `translate_docx()` with a mocked `client` (integration/data-boundary) —
never a real Ollama/cloud call. Backend runs require conda env
`translate-tool`: `conda run -n translate-tool cdd-kit test run --phase <p>`.

## Acceptance Criteria → Test Mapping
| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_docx_nested_tables.py::TestNestedCollectionCharacterParity::test_nested_table_text_not_dropped_recursive_walk | 0 |
| AC-2 | unit | tests/test_docx_nested_tables.py::TestLayoutFrameReroute::test_frame_cell_direct_paragraphs_routed_to_body_path | 0 |
| AC-2 | integration | tests/test_docx_nested_tables.py::TestLayoutFrameReroute::test_nested_table_under_frame_cell_reaches_serializer | 1 |
| AC-3 | unit | tests/test_docx_nested_tables.py::TestMergedCellDedup::test_merged_cell_spanning_columns_emits_single_segment_at_origin | 0 |
| AC-3 | contract | tests/test_docx_nested_tables.py::TestMergedCellDedup::test_49_distinct_tc_not_52_segments | 0 |
| AC-4 | unit | tests/test_docx_nested_tables.py::TestFrameRerouteFalsePositiveGuard::test_multi_column_data_table_many_paragraphs_not_rerouted | 0 |
| AC-4 | unit | tests/test_docx_nested_tables.py::TestFrameRerouteFalsePositiveGuard::test_full_width_cell_without_nested_table_not_rerouted | 0 |
| AC-4 | unit | tests/test_docx_nested_tables.py::TestFrameRerouteFalsePositiveGuard::test_nested_table_cell_not_full_width_not_rerouted | 0 |
| AC-5 | resilience | tests/test_docx_nested_tables.py::TestNestingDepthGuard::test_recursion_terminates_at_max_depth_with_single_warning | 0 |
| AC-6 | data-boundary | tests/test_docx_nested_tables.py::TestLegacyPipeGridDegrade::test_legacy_flag_off_nested_table_own_grid_no_crash | 1 |
| AC-6 | data-boundary | tests/test_docx_nested_tables.py::TestLegacyPipeGridDegrade::test_legacy_flag_off_rerouted_frame_leaves_placeholder | 1 |
| AC-7 | regression | tests/test_table_context_translation.py | 0/1 |
| AC-8 | structural | n/a (no runtime node; enforced by construction, see Notes) | n/a |

## Test Families Required
| family | tier | notes |
|---|---|---|
| unit | 0 | pure `_collect_docx_segments` calls on an in-memory fixture; no client, no network |
| contract | 0 | pins BR-81's clarified dedup key shape and the BR-113/BR-114 wire-format consumer note |
| integration | 1 | full `translate_docx()` with a mocked `client`; nested `table_id` group reaches `table_serializer`/`json_translation` |
| data-boundary | 1 | `JSON_STRUCTURED_TRANSLATION_ENABLED=0` end-to-end; no crash, no nested-into-parent grid merge |
| resilience | 0 | depth-guard fixture nested to `MAX_TABLE_NESTING_DEPTH + 2`; termination, single WARNING, no silent drop |

## Falsifiability (production line that must go RED if deleted/inverted)
- AC-1: the recursive descent into `cell.tables` in the `}tbl` branch — removed, inner-table chars vanish from the parity sum.
- AC-2: the BR-114 conjunction (`cell.tables` non-empty AND full-row-width span) gating `para` vs `cell` emission — removed, frame prose never appears as `para` segments.
- AC-3: the per-table `seen_tc` element-identity dedup guard before emission — removed, merged cell reverts to one segment per spanned column.
- AC-4: the same conjunction loosened to OR or one operand dropped — the adversarial data-table cell gets wrongly rerouted, losing row context.
- AC-5: the `MAX_TABLE_NESTING_DEPTH` stop-recursion check — removed, either the depth/warning-count assertion fails or the fixture never returns.
- AC-6: legacy `serialize()`/`parse()` scoping a nested table to ITS OWN grid — if merged into the parent's `cells_by_pos`, either raises or mispositions text.

## Assertion Boundary Discipline
Assert on collected `Segment.text`/`.kind`/`.row`/`.col`/`.table_id` and on the
outgoing `client.translate_json`/`table_serializer.serialize()` payload —
never on `seen_tc` existing or a flag being set. AC-3 asserts WHICH text sits
at WHICH `(row, col)`, not `len(segs) == 49` alone. AC-6 asserts the empty
placeholder in the actual serializer input/output, not an intermediate var.

## Existing Tests Checked for Breakage (AC-7)
Grepped whole `tests/` tree for `Segment(`, `_collect_docx_segments`,
`_process_container_content`, `merge_cells`/`gridSpan`: only
`tests/test_table_context_translation.py` (`_make_client_mock`,
`_StubTableClient`-adjacent doubles) and `tests/test_output_mode_processors.py`
construct `Segment` directly; neither builds a merged or nested-table
fixture, so none require changes. Also re-run: `tests/test_table_serialization.py`,
`tests/test_docx_parser.py::test_parse_deduplication` (unrelated parser path),
`tests/test_translatable_document.py`, `tests/test_translation_service.py`,
`tests/test_orchestrator_phase0.py`.

## Test Execution Ladder
| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select (from mapping table above) | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | `conda run -n translate-tool cdd-kit test run --phase full` | 1 | test-evidence.yml |

## Test Update Contract
No existing test requires update or deletion — this change is additive
(nested recursion, a routing conjunction, and a dedup guard); the AC-7 list
above is a re-run, not a rewrite.

## Stop Rules
- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope
- LLM call-volume/batching behavior (unrelated to collection).
- Per-cell length-ratio truncation guard (pre-existing hazard on both wire formats; separate change per design.md Open Risks).
- BR-109 doc-context sampler thin-sampling on nested-only documents (read-only; follow-up).
- `tmap` key omitting `table_id` (pre-existing, benign per BR-81/BR-113).
- Any test depending on `docs/TEST_DOC/` (forbidden, AC-8).

## Notes
AC-8 has no pytest node: it is enforced by construction (every fixture built
via `python-docx` inside the test body) and verified by
`grep -L "docs/TEST_DOC" tests/test_docx_nested_tables.py` at review time,
not a runtime behavior. `qa-reviewer` should confirm this grep, not add a gate.
