---
change-id: pdf-text-overflow-fix
schema-version: 0.1.0
last-changed: 2026-07-07
risk: medium
tier: 2
---

# Test Plan: pdf-text-overflow-fix

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_text_region_renderer.py::TestRenderTextRegion::test_render_text_region_wraps_via_shared_cascade | 0 |
| AC-1 | integration | tests/test_coordinate_renderer.py::TestCoordinateRenderer::test_render_side_by_side_mode_wraps_long_text | 1 |
| AC-2 | integration | tests/test_coordinate_renderer.py::TestCoordinateRenderer::test_render_overlay_mode_fallback_wraps_long_text | 1 |
| AC-2 | resilience | tests/test_pdf_render_warnings.py::TestFitzFallbackWarning::test_fitz_crash_fallback_still_wraps_long_text | 1 |
| AC-3 | unit | tests/test_text_region_renderer.py::TestTruncationMarker::test_reportlab_path_sets_render_truncated_on_overflow | 0 |
| AC-3 | integration | tests/test_coordinate_renderer.py::TestCoordinateRendererEdgeCases::test_side_by_side_unfittable_text_sets_render_truncated | 1 |
| AC-4 | unit | tests/test_pdf_parser.py::TestTableDetectionStrategyFallback::test_strict_empty_lines_strategy_succeeds | 0 |
| AC-4 | unit | tests/test_pdf_parser.py::TestTableDetectionStrategyFallback::test_strict_and_lines_empty_text_strategy_succeeds | 0 |
| AC-4 | unit | tests/test_pdf_parser.py::TestTableDetectionStrategyFallback::test_all_strategies_fail_leaves_blocks_unchanged | 0 |
| AC-4 | unit | tests/test_pdf_parser.py::TestTableDetectionStrategyFallback::test_text_strategy_false_positive_discarded_by_sanity_gate | 0 |
| AC-4 | integration | tests/test_pdf_layout_table_fixes.py::TestTableDetectionFallbackIntegration::test_borderless_table_pdf_recovers_cells | 1 |
| AC-5 | unit | tests/test_pdf_parser.py::TestTableCellBboxCorrection::test_1to1_block_to_cell_bbox_corrected_to_cell_extent | 0 |
| AC-5 | unit | tests/test_pdf_layout_table_fixes.py::TestPdfTableCellSplit::test_row_blocks_split_into_cells (EXTEND: exact x1/y1, x0/y0 unchanged, metadata["lines"]) | 0 |
| AC-6 | unit (regression) | tests/test_pdf_layout_refactor.py (unmodified, full file) | 0 |
| AC-6 | unit (regression) | tests/test_text_region_renderer.py::TestFitCascade (unmodified, full class) | 0 |
| AC-6 | unit (regression) | tests/test_pdf_parser.py::TestTableDetection::test_detect_and_mark_tables_marks_elements (unmodified) | 0 |
| AC-7 | unit | tests/test_pdf_parser.py::TestTableDetectionStrategyFallback::test_strict_success_skips_fallback | 0 |
| AC-8 | contract | tests/test_renderer_convergence.py::TestLayoutEquivalence (REQUIRED REWRITE — exact node TBD by implementer; see Known Risk) | 1 |
| AC-8 | unit (regression) | tests/test_text_region_renderer.py::TestSinglePathEnforcement::test_no_cascade_logic_in_legacy_paths (unmodified) | 0 |
| AC-9 | unit | tests/test_pdf_layout_refactor.py::TestAvailableWhitespaceBelow::test_reflow_element_computes_nonzero_gap_below_same_column | 0 |
| AC-9 | unit | tests/test_pdf_layout_refactor.py::TestAvailableWhitespaceBelow::test_reflow_document_zero_gap_last_row_or_no_neighbor | 0 |
| AC-9 | unit (regression-guard, exact line) | tests/test_pdf_generator.py::TestPDFGenerator::test_insert_text_in_rect_reads_placement_whitespace_not_literal_zero | 0 |
| AC-10 (BR-100, case 1) | unit | tests/test_pdf_layout_refactor.py::TestBoundedRowGrowth::test_single_table_row_grows_and_shifts_only_same_table_id_lower_rows | 0 |
| AC-10 (BR-100, case 2) | unit | tests/test_pdf_layout_refactor.py::TestBoundedRowGrowth::test_growth_capped_at_table_budget_residual_truncates_and_warns | 0 |
| AC-10 (BR-100, case 3) | unit | tests/test_pdf_layout_refactor.py::TestBoundedRowGrowth::test_no_table_id_metadata_skips_growth_unchanged_cascade | 0 |
| AC-10 (BR-100, case 4) | unit | tests/test_pdf_layout_refactor.py::TestBoundedRowGrowth::test_metadata_lines_whitening_bboxes_shift_by_identical_delta | 0 |
| AC-10 (BR-100, case 5) | contract | tests/test_renderer_convergence.py::TestLayoutEquivalence::test_row_growth_geometry_identical_fitz_vs_reportlab | 1 |
| AC-11 (BR-101, case 1) | unit | tests/test_pdf_render_warnings.py::TestTruncationDisclosureWarning::test_one_aggregated_warning_per_file_regardless_of_truncated_count | 0 |
| AC-11 (BR-101, case 2) | unit | tests/test_pdf_render_warnings.py::TestTruncationDisclosureWarning::test_no_warning_entry_when_no_truncation | 0 |
| AC-11 (BR-101, case 3, CONTINGENT — see Notes) | unit | tests/test_pdf_render_warnings.py::TestTruncationDisclosureWarning::test_warning_fires_identically_fitz_or_reportlab_truncation_source | 0 |
| AC-9/AC-10 regression guard | unit (regression) | tests/test_pdf_layout_refactor.py + tests/test_text_region_renderer.py (unmodified suites, no-overflow fixtures) | 0 |

## Test Families Required

Applies: unit, integration, contract, resilience, data-boundary. Deferred (not this pass): e2e, visual. Not applicable: monkey, stress, soak.

| family | tier | notes |
|---|---|---|
| unit | 0 | fit_text_cascade/_wrap_lines_simple reuse assertions, BR-98 strategy-ladder, BR-99 bbox-extent math, BR-36-note `available_whitespace_below` computation (AC-9), BR-100 row-growth pre-pass measured via real `fit_text_cascade`/`_wrap_lines_simple` calls on constructed IR (AC-10) — mock at fitz `page`/`Document` boundary or reportlab `Canvas` boundary, never at internal renderer-class boundary |
| integration | 1 | parser→IR(bbox_reflow)→renderer round trip for both `side_by_side` and `overlay`(-as-fallback) RenderModes via real Canvas/PDF bytes; one real-PDF fixture (borderless table) for BR-98/99 |
| contract | 1 | test_renderer_convergence.py cross-path shared-cascade invariant (BR-40 amended); BR-100 dual-backend post-growth geometry parity (AC-10 case 5) |
| resilience | 1 | BR-34 boundary: fitz-crash → `_run_reportlab_render` fallback must still wrap, not just log a warning; BR-101 disclosure sweep must not alter output or fail the job (AC-11) |
| data-boundary | 0/1 | thin/borderless tables, merged multi-column blocks, empty/degenerate cells, text-strategy false-positive grids |
| e2e (deferred) | 3 | full PDF translate job on table-heavy borderless doc — deferred to implementation session per change-classification |
| visual (deferred) | manual | rendered-PDF overlap/legibility check — owned by visual-reviewer in implementation session, not authored here |

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_renderer_convergence.py::TestLayoutEquivalence | update | ADR-0012/BR-40 amendment flips the invariant from "cascade fires only on the fitz path" to "the same shared cascade fires regardless of which of the 3 PDF renderer paths (fitz overlay, ReportLab side-by-side, ReportLab fitz-crash fallback) is exercised" — old fitz-exclusivity assertion must be replaced, not just extended. ADR-0013 (this pass) adds one more node to the same class asserting post-row-growth geometry (bbox + `metadata["lines"]`) is identical on both backends. |
| app/backend/renderers/bbox_reflow.py::Placement (dataclass) | extend | AC-9 adds `available_whitespace_below` as a new field with a default value — existing `Placement(...)` construction call sites in test_pdf_layout_refactor.py/test_renderer_convergence.py (positional/keyword, pre-amendment field set) must keep passing unchanged; this is additive, not breaking. |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope
- ML/TATR table-structure path (`TABLE_RECOGNITION_ENABLED`, `table_recognizer.py`).
- DOCX/XLSX/PPTX rendering — PDF-specific change.
- Redesigning the BR-36/85 cascade algorithm itself — reuse only.
- ReportLab fallback's weaker `canvas.rect` masking (BR-84 gap) unless implementation-planner bundles it.
- fuzz/monkey, stress, soak.
- Cross-table/cross-page reflow when AC-10 growth exceeds budget (Non-goal) — case 2 tests only truncation+BR-101-warning fallback. Config-flag-gated row-growth disable (design.md's undecided overlay-collision mitigation) — no test until that scope decision lands.

## Notes
- **Known Risk (blocks AC-3 as currently scoped):** design.md's Open Risks says `create_text_regions_from_placements`/`create_text_regions_from_elements` drop the element ref, so `render_truncated` cannot be set on the ReportLab path without a StyleInfo/element-ref plumbing decision deferred to implementation-planner. The two AC-3 tests must start red (assert the marker IS set); their exact assertion target (element-level marker vs. a returned-decision field) is undecided until that plumbing lands — implementation-planner must resolve the threading approach, not silently downgrade to log-only.
- `tests/test_renderer_convergence.py` was added to this agent's context-manifest for the AC-9/10/11 amendment pass and has now been read; `TestLayoutEquivalence`/`TestIRBboxReflow` structure confirmed directly (not inferred from CLAUDE.md).
- `TestSinglePathEnforcement::test_no_cascade_logic_in_legacy_paths` needs no change: it only forbids `coordinate_renderer.py`/`inline_renderer.py`/`pdf_generator.py`; `fit_text_cascade` already lives alongside `render_text_region` in `text_region_renderer.py`, so reuse adds no new import there.
- All "wraps"/"grows"/"shifts" assertions must check actual line count, drawn text, or numeric bbox deltas — not just that `fit_text_cascade`/the pre-pass was called (anti-tautology).
- **Test-infra gap (AC-10):** no direct-construction fixture exists for a multi-row TABLE_CELL IR with controllable per-cell text length + `table_id`/`table_row`/`table_col` metadata (only `_make_table_pdf()` in test_pdf_layout_table_fixes.py, via a real rendered PDF — too heavy for pre-pass unit tests). Fix: give test_pdf_layout_refactor.py's `_make_element`/`_make_doc` a `metadata` param (currently hardcoded `{}`) before writing `TestBoundedRowGrowth`.
- AC-11 case 3 is CONTINGENT on Decision-1/AC-8's element-ref threading (ReportLab `render_truncated` marker) actually landing — same dependency already tracked for AC-3 in the first pass and echoed in contract-reviewer's second-pass-summary; do not implement/assume-green until that plumbing exists.
