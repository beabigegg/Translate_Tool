---
change-id: pdf-text-overflow-fix
schema-version: 0.1.0
last-changed: 2026-07-07
---

# Implementation Plan: pdf-text-overflow-fix

> IMPORTANT: Planning-only pass. This plan is the execution packet for a LATER,
> separately-approved implementation session. Do NOT write product code, tests,
> or contract edits from this pass. Implementation agents (`backend-engineer`,
> `bug-fix-engineer`) act only when that session is opened.

## Objective

Make `fit_text_cascade`/`_wrap_lines_simple` the single shared fit/wrap authority
for ALL PDF renderer paths so translated text wraps within its bbox in BOTH PDF
presentation modes (overlay + side-by-side) and the fitz-crash ReportLab
fallback, and give table cells a correct bbox extent so per-cell text no longer
spans multiple columns. Concretely deliver AC-1..AC-8 (change-classification.md
`## Inferred Acceptance Criteria`) with zero regression on the fitz/overlay path.

AMENDMENT (post-design scope, change-request.md `## Scope Amendment`; design.md
Decisions 4/5/6; ADR 0013): additionally deliver AC-9..AC-11 — a bounded LOCAL
box-growth stage before truncation. (AC-9) compute real
`available_whitespace_below` once in `bbox_reflow.py`, carry it on `Placement`,
and have `fitz_renderer.py:511` read it instead of hardcoded `0.0`, reviving the
cascade's dead controlled-overflow step (d). (AC-10 / BR-100) a shared upstream
row-growth pre-pass in `_dispatch_render` grows an over-full TABLE_CELL's row and
shifts only same-table lower rows down, capped at the table's local page budget.
(AC-11 / BR-101) a post-render sweep in `_dispatch_render` surfaces residual
truncation as exactly one `job.warnings` entry per file. All new stages preserve
the AC-6 fitz-overlay non-regression guarantee.

## Execution Scope

### In Scope
- Thread source `StyleInfo` + an element/element_id reference through `TextRegion`
  and both `create_text_regions_from_*` builders (the plumbing gap; prerequisite
  for the cascade + BR-38 marker on the ReportLab path).
- Replace the shrink-only `fit_text_to_bbox` + literal-`\n` split in
  `render_text_region` with `fit_text_cascade` -> `_wrap_lines_simple` ->
  per-line `canvas.drawString`, honoring `decision.line_spacing` and setting
  `render_truncated` on `decision.truncated` (BR-38).
- Side-by-side path (`fitz_renderer._generate_side_by_side` ->
  `create_text_regions_from_elements`) and fitz-crash fallback path
  (`coordinate_renderer._render_side_by_side`/`_render_overlay` ->
  `create_text_regions_from_placements`) both inherit wrap via the ONE shared
  `render_text_region` — no cascade duplication in either legacy path.
- pdf_parser BR-98: additive looser-strategy `find_tables()` fallback
  (`lines_strict`->`lines`->`text`), only when the current strategy finds zero
  tables, accepted only through a sanity gate.
- pdf_parser BR-99: correct the 1:1 block-to-cell bbox (`_detect_and_mark_tables`
  :444-452) to true cell extent (right/bottom only), mirroring the extension
  logic `_split_elements_by_cells` already applies (:560-574).
- Contract edits (apply contract-reviewer's drafted text): amend BR-40; add
  BR-98, BR-99; data-shape `table_cell` bbox-extent invariant note; version bumps.
- Update the BR-40 convergence test to assert the shared-call invariant.
- (AC-9) Add `available_whitespace_below: float = 0.0` to `Placement`
  (bbox_reflow.py:35-50); compute the real gap-below once in
  `reflow_element`/`reflow_document`; fix the `fitz_renderer.py:511` read-site to
  consume it. Independent — lands first among the amendment items.
- (AC-10 / BR-100) Add a bounded, config-gated row-growth pre-pass (new function
  in text_region_renderer.py per design.md Decision 5) invoked once from
  `pdf_processor._dispatch_render` (:1035-1085) BEFORE either backend renders.
- (AC-11 / BR-101) Add a post-render `render_truncated` sweep in
  `_dispatch_render` emitting one aggregated `job.warnings` entry per file via the
  existing `warnings_callback`.
- (config flag, ADOPTED — see decision below) Add `PDF_TABLE_ROW_GROWTH_ENABLED`
  to config.py and an env-contract.md entry so the HIGH-risk row-growth stage can
  be disabled in production without reverting AC-1..AC-9/AC-11.
- Amendment contract edits: BR-36 clarifying sentence (whitespace computed in
  bbox_reflow, carried on Placement); add BR-100, BR-101; new data-shape section
  documenting the default-path metadata keys BR-100 joins on; version bumps folded
  into the SAME 0.24.0 / 0.16.0 bumps as the base pass.
- Test-infra: add a `metadata` param to test_pdf_layout_refactor.py's
  `_make_element`/`_make_doc` helpers before `TestBoundedRowGrowth` is authored.

### Out of Scope
- Any change to the fitz overlay path `_insert_text_in_rect`
  (fitz_renderer.py:407-552) — it is already correct and is the must-not-regress
  reference (AC-6). Do not touch it.
- The BR-36/BR-85 cascade algorithm itself (font-shrink -> spacing -> overflow ->
  truncation) — reuse as-is; do not redesign.
- ML/TATR table path (`TABLE_RECOGNITION_ENABLED`, `table_recognizer.py`,
  `_run_table_recognizer`) — stays disabled/out of scope; no renderer consumers.
- DOCX/XLSX/PPTX rendering and the office `OutputMode` enum.
- ReportLab fallback's weaker `canvas.rect` masking vs. PyMuPDF redaction (BR-84,
  fitz-only) — explicitly not in scope this change.
- Reuses `MIN_READABLE_FONT_PT`, `FONT_SIZE_SHRINK_FACTOR`, `FONT_SIZE_CONFIG`;
  no schema / data migration. NOTE: the amendment DOES add ONE new env var
  (`PDF_TABLE_ROW_GROWTH_ENABLED`) — see IP-12 and the config-flag decision.
- Full flowing-layout / cross-table / cross-page reflow (recomputing page layout,
  pushing content across table boundaries, cascading pagination) — explicit
  Non-goal (change-request.md `## Non-goals`). AC-10 growth is bounded WITHIN a
  single table on its own page; residual overflow past the local budget falls to
  cascade truncation + the AC-11 warning, not to reflow.
- Reordering the cascade to the pure DTP grow-first order — deliberately kept as
  font-shrink-first with growth inserted just before truncation (ADR 0013
  Consequences); a future reflow change may reorder.
- Moving the overlay-mode source-PDF background/graphics when a row is grown — the
  redaction-preserved background is NOT shifted (design.md Open Risks; ADR 0013);
  the config flag is the mitigation, not a background-reflow implementation.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | renderer plumbing (prereq) | Add `style: Optional[StyleInfo]` (or `font_size`+`font_name`) and an element/element_id ref to `TextRegion` (text_region_renderer.py:399-462). In `create_text_regions_from_elements` (:646-693) pass `element.style` + `element` (or `element.element_id`); in `create_text_regions_from_placements` (:696-722) carry `placement`'s style/element if exposed by bbox_reflow `Placement`, else document the degraded fallback (cascade starts from `FONT_SIZE_CONFIG` max, truncation logs-only). Do NOT change fit behavior yet. | backend-engineer |
| IP-2 | ReportLab draw path (BR-40, AC-1/AC-2) | In `render_text_region` (:491-603) replace the `region.font_size is None` -> `fit_text_to_bbox` branch and the `region.text.split("\n")` single-draw loop with: build `BoundingBox` from region + `StyleInfo` from the threaded style (fallback to language `FONT_SIZE_CONFIG` max), call `fit_text_cascade(text, bbox, style, available_whitespace_below=0.0)`, then `_wrap_lines_simple(decision.fitted_text, font_name, decision.font_size, region.width)`, draw each wrapped line via `canvas.drawString` honoring `decision.line_spacing`. Mirror the fitz reference (fitz_renderer.py:473-552). Keep RTL alignment + background rect. Legacy `fit_text_to_bbox` must NOT be called on this path. | backend-engineer |
| IP-3 | no-silent-truncation on ReportLab path (BR-38, AC-3) | After IP-2, when `decision.truncated` set `element.render_truncated = True` via the ref threaded in IP-1 (matching fitz_renderer.py:514-517). If no element ref is available on the placement path, degrade to log-only (document as a known BR-38 gap on that sub-path). Depends on IP-1. | backend-engineer |
| IP-4 | fallback path inheritance (AC-2, resilience) | Confirm `coordinate_renderer._render_side_by_side`/`_render_overlay` (:102-300) reach `render_text_region` through `create_text_regions_from_placements`/`render_text_regions` and now inherit wrap with no per-path cascade code. Add none; verify no BR-40-violating duplicate logic remains. | backend-engineer |
| IP-5 | table-detection fallback (BR-98, AC-4/AC-7) | In `_detect_and_mark_tables` (pdf_parser.py:361-464) at the `page.find_tables()` call (:387): when the default `lines_strict` returns empty (`not tables.tables`), retry `strategy="lines"` then `strategy="text"`; accept a fallback result ONLY if it passes a sanity gate (>=2 rows AND >=2 cols from `_build_cell_grid`, and each cell rect wider/taller than the existing `>2.0pt` floor used in `_spans_multiple_cells`). If the gate fails, discard and keep current paragraph blocks (`continue`). Never override a non-empty strict detection. Additive only. | bug-fix-engineer |
| IP-6 | 1:1 cell bbox correction (BR-99, AC-5) | In the 1:1 mark loop (pdf_parser.py:444-452), after `rc = self._locate_cell(...)`, look up the cell rect for `rc` from `cell_grid` and extend `elem.bbox.x1 = max(elem.bbox.x1, rect[2]-_pad)`, `elem.bbox.y1 = max(elem.bbox.y1, rect[3]-_pad)` with `_pad=2.0`; leave `x0`/`y0`. Preserve the original tight bbox in `elem.metadata["lines"]` (single-entry list) for BR-84 whitening. Mirror `_split_elements_by_cells` :560-574 (that split path ALREADY does this — reference it, do not re-touch it). | bug-fix-engineer |
| IP-7 | contract edits | Apply contract-reviewer's drafted text (agent-log/contract-reviewer.yml): amend BR-40 (single-path -> single shared cascade authority across all PDF paths; retires `fit_text_to_bbox` as a fit authority); add BR-98 (table-detection-strategy-fallback) and BR-99 (table-cell-bbox-extent-correction); data-shape `table_cell` bbox-extent invariant note; bump business-rules 0.23.0->0.24.0, data-shape 0.15.0->0.16.0. RE-CHECK live last-used BR number at edit time and renumber BR-98/BR-99 if a sibling change has landed them first (see Known Risks). | backend-engineer |
| IP-8 | BR-40 test update | Update `tests/test_renderer_convergence.py` to assert the shared-call invariant (all PDF paths call the one `fit_text_cascade`) instead of the fitz-exclusivity invariant (per ADR 0012 Consequences). Logged in test-plan.md `## Test Update Contract` once that file is finalized. | backend-engineer |
| IP-9 | AC-9: real whitespace-below (design Decision 4, BR-36 note) | Add `available_whitespace_below: float = 0.0` to `Placement` (bbox_reflow.py:35-50) — MUST have a default so existing `Placement(...)` call sites stay green (test-plan.md Test Update Contract). In `reflow_element`/`reflow_document` (:53-131) compute the gap ONCE: for a TABLE_CELL, distance from this cell's `y1` to the nearest `y0` of the next row in the SAME `table_id`/`table_col` (else table bottom, else page bottom margin); for a non-table element, distance to the next element below whose x-range overlaps (no overlap ⇒ leave `0.0`). Requires page-grouping elements inside `reflow_document` (currently element-at-a-time). Then fix `fitz_renderer.py:511` to pass the field instead of literal `0.0`. Do NOT touch the cascade core or `_insert_text_in_rect` logic beyond that one call arg. Independent — can land first. | backend-engineer |
| IP-10 | AC-10: config flag (ADOPTED) | Add `PDF_TABLE_ROW_GROWTH_ENABLED: bool = os.getenv("PDF_TABLE_ROW_GROWTH_ENABLED", "true").lower() in ("1","true","yes")` to config.py (near the other PDF flags ~:174-179, matching the established `os.getenv` bool idiom). Gates the AC-10 pre-pass ONLY (AC-9/AC-11 and all base fixes stay unconditional). Prereq for IP-11's gate check and IP-13's env-contract entry. | backend-engineer |
| IP-11 | AC-10: bounded row-growth pre-pass (design Decision 5, BR-100, ADR 0013) | Add a new pre-pass function in text_region_renderer.py (alongside `fit_text_cascade`, reusing it + `_wrap_lines_simple` for measurement — ADR 0012), invoked ONCE in `pdf_processor._dispatch_render` (:1035-1085) on `doc` BEFORE the `_run_fitz_render` call, guarded by `PDF_TABLE_ROW_GROWTH_ENABLED`. Group TABLE_CELL elements by `(page_num, metadata["table_id"])` then `metadata["table_row"]`; per row take max required height at the settled cascade font size; if `delta > 0` grow that row's cells' `y1` by `delta` and shift every lower-row element's `bbox` AND its `metadata["lines"]` whitening bboxes down by the cumulative delta, in the IR. Cap cumulative growth at the table's remaining local budget (page bottom margin, or top of first non-table element below the table); residual past budget falls to cascade truncation + AC-11. Skip entirely when no `table_id`/`table_row` metadata exists (no `cell_grid`). MUST sequence AFTER IP-6 (BR-99 1:1 bbox correction) so cell bboxes are already correct before measuring; depends loosely on IP-9. | backend-engineer |
| IP-12 | AC-11: truncation-disclosure sweep (design Decision 6, BR-101) | In `_dispatch_render` (:1035-1085), AFTER the render call returns (both the fitz and ReportLab branches), sweep `doc` for elements with `render_truncated=True`; if any, emit exactly ONE aggregated `warnings_callback(...)` entry per file naming `doc_id` + affected page(s), mirroring the `FITZ_FALLBACK_WARNING`→`warnings_callback` pattern already at :1074-1075 (which routes to `_record_job_warning`, BR-96 plumbing). Disclosure-only: never fails the job, never alters output. MUST sequence AFTER IP-1's element-ref threading actually lands — otherwise the ReportLab path never sets `render_truncated` and AC-11 degrades to fitz-only coverage on day one (design.md Decision 6 dependency; contract-reviewer second-pass; hard dependency, NOT nice-to-have). | backend-engineer |
| IP-13 | env-contract.md entry (config-flag adoption) | Add a `PDF_TABLE_ROW_GROWTH_ENABLED` entry to `contracts/env/env-contract.md` (default `true`, disclosure of the HIGH-risk overlay-background-collision rationale, non-secret, no restart semantics beyond process env). REQUIRED because IP-10 adopts the flag. NOTE: `contracts/env/env-contract.md` is NOT in this change's context-manifest Allowed Paths and Env was `none` in change-classification.md — the implementation session MUST expand the manifest (add `contracts/env/env-contract.md`) and re-run `cdd-kit context check` before this edit; flagged by contract-reviewer as a scope-decision. Beware tier-floor false-positives on env-vocab (see CLAUDE.md promoted learning). | backend-engineer |
| IP-14 | amendment contract edits (contract-reviewer second-pass) | Apply contract-reviewer's second-pass drafted text: append the BR-36 clarifying sentence (`available_whitespace_below` computed once in bbox_reflow.py, carried as a `Placement` field — revives dead step (d), not new cascade logic; no new rule number); add BR-100 (bounded-local-table-row-growth, with cap/fallback + ADR-0013 pointer + config-flag note) and BR-101 (pdf-render-truncation-disclosure, one aggregated `job.warnings` entry per file, disclosure-only). Add a new data-shape-contract.md section documenting the previously-UNDOCUMENTED default-path metadata keys (`table_id`/`table_row`/`table_col`/`in_table`/`lines`) that BR-100's join logic depends on. The SINGLE 0.24.0 (business) / 0.16.0 (data-shape) bump from IP-7 now covers BR-40 amend + BR-36 note + BR-98/99/100/101 together — do NOT double-bump. RE-CHECK live last-used BR number at edit time; BR-100 now collides 3-way (see Known Risks) — renumber all four new rules + every in-plan reference if a sibling change landed first. Confirm zero regression to BR-38/84/85/89/90/96/97. | backend-engineer |
| IP-15 | test-infra prereq + AC-9/10/11 test authoring | FIRST add a `metadata` param (default `{}`) to `tests/test_pdf_layout_refactor.py`'s `_make_element`/`_make_doc` helpers (currently hardcoded `{}`) — a blocker for authoring `TestBoundedRowGrowth` (test-strategist second-pass TEST-INFRA GAP). Then author the mapped tests: `TestAvailableWhitespaceBelow` + the exact-line regression guard in test_pdf_generator.py (AC-9); `TestBoundedRowGrowth` 4 unit cases + the convergence dual-backend parity node (AC-10); `TestTruncationDisclosureWarning` 3 cases (AC-11, case 3 CONTINGENT on IP-1/IP-12). Anti-tautology: assert line counts / drawn text / numeric bbox deltas, not just that the pre-pass was called. Author per test-plan.md `## Acceptance Criteria → Test Mapping`. | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| design.md | Decision 1 (BR-40 shared cascade) | IP-2/IP-3 constraint |
| design.md | Decision 2 (additive sanity-gated detection fallback) | IP-5 constraint |
| design.md | Decision 3 (1:1 cell bbox right/bottom extension) | IP-6 constraint |
| design.md | Decision 4 (AC-9 whitespace-below in bbox_reflow) | IP-9 constraint |
| design.md | Decision 5 (AC-10 shared row-growth pre-pass) | IP-11 constraint |
| design.md | Decision 6 (AC-11 truncation-disclosure sweep) | IP-12 constraint |
| design.md | `## Open Risks` (cascade starting font; render_truncated marker; overlay border-crossing; `metadata["lines"]` shift) | IP-1/IP-3/IP-11/IP-12 |
| docs/adr/0012-shared-fit-cascade-all-pdf-paths.md | Decision + Consequences | IP-2/IP-8/IP-11 |
| docs/adr/0013-bounded-local-table-row-growth-prepass.md | Decision (steps 1-4) + Consequences (overlay limitation, cascade order) | IP-11 constraint |
| agent-log/contract-reviewer.yml | drafted BR-40/BR-98/BR-99 + data-shape note, version bumps | IP-7 |
| agent-log/contract-reviewer.yml | second-pass-summary (BR-36 note, BR-100, BR-101, new data-shape metadata-keys section, 3-way BR-100 collision, BR-101 sequencing dependency, env-contract OPEN ITEM) | IP-13/IP-14 |
| agent-log/test-strategist.yml | second-pass-summary (TestAvailableWhitespaceBelow / TestBoundedRowGrowth / warnings-sweep cases, `_make_element`/`_make_doc` metadata-param gap) | IP-15 |
| change-classification.md | `## Inferred Acceptance Criteria` AC-1..AC-11 (AC-9/10/11 post-design) | scope + test mapping |
| change-classification.md | `## Required Tests` | test families |
| test-plan.md | `## Acceptance Criteria → Test Mapping` (AC-1..AC-11, now FINALIZED) + `## Test Update Contract` (Placement additive field; convergence rewrite) | Test Execution Plan |
| ci-gates.md | Required Gates table | verification |
| contracts/business/business-rules.md:51-55 | BR-36/38/39/40 current text | IP-2/IP-7 |
| contracts/data/data-shape-contract.md:122,180-191,334-404 | table_cell row, BoundingBox shape, ML TableCell (out of scope) | IP-7 |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| app/backend/renderers/text_region_renderer.py | modify | `TextRegion` :399-462 add style/element fields; `render_text_region` :491-603 swap shrink-only fit for cascade+wrap+truncation; `create_text_regions_from_elements` :646-693 and `create_text_regions_from_placements` :696-722 thread style+element ref (IP-1/2/3). Import `StyleInfo`/`BoundingBox` from models. ALSO add the new row-growth pre-pass function here (IP-11), reusing `fit_text_cascade`/`_wrap_lines_simple` for measurement; do NOT alter the cascade core. |
| app/backend/renderers/coordinate_renderer.py | verify-only | :102-300 fallback paths inherit wrap via shared `render_text_region`; add no cascade code (IP-4). |
| app/backend/renderers/bbox_reflow.py | modify | `Placement` :35-50 add `available_whitespace_below: float = 0.0` (defaulted — additive, non-breaking); `reflow_element`/`reflow_document` :53-131 compute the real gap-below once, page-grouping elements for the geometry (IP-9). Backend-neutral; no fitz/ReportLab imports (module invariant). |
| app/backend/renderers/fitz_renderer.py | modify (one line) | :511 change `available_whitespace_below=0.0` to read `Placement.available_whitespace_below` (IP-9). Do NOT otherwise touch :407-552 `_insert_text_in_rect` — it is the AC-6 must-not-regress reference; :473-552 is the pattern IP-2 mirrors. `_generate_side_by_side` :554-669 unchanged. |
| app/backend/processors/pdf_processor.py | modify | `_dispatch_render` :1035-1085: invoke the row-growth pre-pass on `doc` BEFORE `_run_fitz_render`, gated by `PDF_TABLE_ROW_GROWTH_ENABLED` (IP-11); after the render call returns, sweep `doc` for `render_truncated` and emit ONE aggregated `warnings_callback` per file (IP-12), reusing the :1074-1075 `warnings_callback` pattern. |
| app/backend/config.py | modify | Add `PDF_TABLE_ROW_GROWTH_ENABLED` bool near the PDF flags (~:174-179), matching the `os.getenv(...,"true")...` idiom (IP-10). |
| contracts/env/env-contract.md | modify (SCOPE EXPANSION) | Add `PDF_TABLE_ROW_GROWTH_ENABLED` entry (IP-13). NOT in current context-manifest Allowed Paths — implementation session must expand the manifest + re-run `cdd-kit context check` first. |
| app/backend/parsers/pdf_parser.py | modify | `_detect_and_mark_tables` :387 add sanity-gated looser-strategy fallback (IP-5); :444-452 add 1:1 cell bbox extension + `metadata["lines"]` (IP-6). Reuse `_build_cell_grid` :608-644, `_locate_cell` :646-657, `>2.0pt` floor from `_spans_multiple_cells` :466-485. Do NOT re-touch `_split_elements_by_cells` :560-574 (already extends). |
| app/backend/utils/font_utils.py | do NOT modify | `fit_text_to_bbox` :496-550 retired as a PDF-path fit authority (retained for any non-PDF callers); no code change, only ceases to be called from render_text_region. |
| contracts/business/business-rules.md | modify | Amend BR-40 :55; add BR-98/BR-99 after BR-97 :109 (renumber if collision); append BR-36 clarifying sentence; add BR-100/BR-101 (IP-14). SINGLE 0.23.0->0.24.0 bump covers all of BR-40+BR-36-note+BR-98/99/100/101 (IP-7 + IP-14). |
| contracts/data/data-shape-contract.md | modify | Add `table_cell` bbox-extent invariant note after BoundingBox section (~:191) or annotate the `table_cell` row (:122); disambiguate from ML `TableCell` (:334-404, no bbox field). ALSO add a new section documenting the default-path metadata keys `table_id`/`table_row`/`table_col`/`in_table`/`lines` + post-translation row-shift of cell/sibling bboxes upstream of `reflow_document` (IP-14). SINGLE 0.15.0->0.16.0 bump. |
| tests/test_renderer_convergence.py | modify | Assert shared-call invariant, not fitz-exclusivity (IP-8); add the AC-10 dual-backend post-growth geometry-parity node (IP-15). |
| tests/test_text_region_renderer.py | extend | Wrap/no-silent-draw/render_truncated coverage on the ReportLab path (per test-plan.md). |
| tests/test_pdf_parser.py, tests/test_pdf_layout_table_fixes.py | extend | BR-98 additive fallback + false-positive gate; BR-99 1:1 bbox extension (per test-plan.md). |
| tests/test_pdf_layout_refactor.py | extend | Add `metadata` param to `_make_element`/`_make_doc`; add `TestAvailableWhitespaceBelow` (AC-9) + `TestBoundedRowGrowth` (AC-10) (IP-15). |
| tests/test_pdf_generator.py | extend | AC-9 exact-line regression guard `test_insert_text_in_rect_reads_placement_whitespace_not_literal_zero` (IP-15). |
| tests/test_pdf_render_warnings.py | extend | AC-11 `TestTruncationDisclosureWarning` 3 cases (case 3 CONTINGENT on IP-1/IP-12) (IP-15). |

## Contract Updates

- API: none.
- CSS/UI: none (PDF render output, not web UI/CSS).
- Env: `contracts/env/env-contract.md` — ADD `PDF_TABLE_ROW_GROWTH_ENABLED`
  (default `true`; disableable kill-switch for the HIGH-risk overlay-background
  collision; non-secret; process-env only). CHANGED from the base pass's "none":
  the config-flag decision (ADOPTED — see below) introduces this one var.
  env-contract.md must be added to the manifest Allowed Paths for the
  implementation session (IP-13). Non-secret — avoid tier-floor env-vocab false
  positives (CLAUDE.md promoted learning).
- Data shape: `contracts/data/data-shape-contract.md` — (a) new `table_cell`
  bbox-extent invariant (bbox right/bottom = true cell rect minus `_pad=2.0`;
  tight per-line bbox preserved in `metadata["lines"]` for BR-84 whitening),
  disambiguated from the unrelated ML `TableCell` sub-record; (b) new section
  documenting the previously-undocumented default-path metadata keys
  `table_id`/`table_row`/`table_col`/`in_table`/`lines` and the post-translation
  row-shift of cell/sibling bboxes upstream of `reflow_document` (BR-100 depends
  on these). Version 0.15.0 -> 0.16.0 (minor, additive; single bump).
- Business logic: `contracts/business/business-rules.md` — amend BR-40
  (single-shared-cascade authority across all PDF paths; retires
  `fit_text_to_bbox` as a fit authority); add BR-98 (table-detection-strategy
  fallback, additive + sanity-gated), BR-99 (table-cell-bbox-extent correction);
  append a BR-36 clarifying sentence (`available_whitespace_below` computed once
  in bbox_reflow.py, carried on `Placement`); add BR-100
  (bounded-local-table-row-growth) and BR-101 (pdf-render-truncation-disclosure).
  Preserve BR-36/BR-38/BR-84/BR-85/BR-89/BR-90/BR-96/BR-97 guarantees. Version
  0.23.0 -> 0.24.0 (single minor bump covers BR-40 + BR-36 note + BR-98/99/100/101
  together — do NOT double-bump). Apply contract-reviewer's drafted + second-pass
  wording verbatim.
- CI/CD: none.

## Test Execution Plan

> test-plan.md is now FINALIZED (AC-1..AC-11 mapped, incl. test-strategist's
> second-pass). The rows below are the authoritative node ids from test-plan.md
> `## Acceptance Criteria → Test Mapping`; the selector reads the `test file /
> command` column. Required phase floor: collect, targeted, changed-area; add
> contract (contracts touched) + full (final/CI). Implementation agents generate
> evidence via `cdd-kit test run`; the gate validates `test-evidence.yml`.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (side-by-side wrap) | tests/test_text_region_renderer.py::TestRenderTextRegion::test_render_text_region_wraps_via_shared_cascade | translated text wider than bbox produces multiple wrapped lines; no single-line horizontal overflow |
| AC-2 (fallback wrap) | tests/test_coordinate_renderer.py | fitz-crash fallback path wraps within bbox identically to AC-1 |
| AC-3 (no silent truncation) | tests/test_text_region_renderer.py::TestTruncationMarker | unfittable text sets `render_truncated=True`; full unwrapped string not drawn at floor font (starts red until IP-1 plumbing lands) |
| AC-4 (borderless table detection) | tests/test_pdf_parser.py::TestTableDetectionStrategyFallback | thin/borderless grid recovered via looser-strategy fallback; per-cell bbox no longer multi-column; text-strategy false positive discarded by sanity gate |
| AC-5 (1:1 cell bbox) | tests/test_pdf_parser.py::TestTableCellBboxCorrection | 1:1 block-to-cell bbox extended to cell right/bottom; `metadata["lines"]` holds tight bbox |
| AC-6 (fitz path unchanged) | tests/test_pdf_layout_refactor.py | overlay/fitz cascade, BR-85, BR-84, BR-38 behavior unchanged (unmodified suites stay green) |
| AC-7 (additive, no regression) | tests/test_pdf_parser.py::TestTableDetectionStrategyFallback::test_strict_success_skips_fallback | strict `find_tables()` hit produces identical output; fallback never overrides it |
| AC-8 (BR-40 amended, contract=code) | tests/test_renderer_convergence.py::TestLayoutEquivalence + `cdd-kit validate --contracts` | shared-call invariant asserted; contract/code agree; no fitz-exclusivity assertion remains |
| AC-9 (real whitespace-below) | tests/test_pdf_layout_refactor.py::TestAvailableWhitespaceBelow ; tests/test_pdf_generator.py::TestPDFGenerator::test_insert_text_in_rect_reads_placement_whitespace_not_literal_zero | non-zero gap computed for same-column below-neighbor; zero for last-row/no-neighbor; fitz:511 reads the field, not literal `0.0` |
| AC-10 (BR-100 row-growth) | tests/test_pdf_layout_refactor.py::TestBoundedRowGrowth ; tests/test_renderer_convergence.py::TestLayoutEquivalence::test_row_growth_geometry_identical_fitz_vs_reportlab | row grows + only same-`table_id` lower rows shift by identical delta (bbox AND `metadata["lines"]`); budget cap → truncation+warning; no-metadata skip; dual-backend geometry parity |
| AC-11 (BR-101 disclosure) | tests/test_pdf_render_warnings.py::TestTruncationDisclosureWarning | exactly one aggregated `job.warnings` entry per file when any truncation; none when no truncation; fitz-vs-ReportLab parity (case 3 CONTINGENT on IP-1/IP-12) |

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- STRICT dependency order: IP-1 (plumbing) BEFORE IP-3 (render_truncated wiring). IP-2 depends on IP-1. IP-4 is verify-only after IP-2. IP-6 references but must NOT re-touch `_split_elements_by_cells` :560-574.
- AMENDMENT dependency order (pipeline: Placement field → row-growth pre-pass → truncation sweep):
  - IP-9 (AC-9 Placement field + whitespace compute + fitz:511 read) is independent — lands first among amendment items.
  - IP-10 (config flag) BEFORE IP-11 (pre-pass reads the flag) and BEFORE IP-13 (env-contract entry).
  - IP-11 (AC-10 row-growth pre-pass) MUST sequence AFTER IP-6 (BR-99 1:1 bbox correction) — cell bboxes must be correct before measuring row-growth needs — and loosely after IP-9.
  - IP-12 (AC-11 truncation sweep) MUST sequence AFTER IP-1 (element-ref threading) — HARD dependency, not nice-to-have; without it the ReportLab path never sets `render_truncated` and AC-11 degrades to fitz-only coverage. Also after IP-11 so residual-past-budget truncation is disclosed.
  - IP-13 (env-contract) requires a manifest expansion (`contracts/env/env-contract.md` not currently in Allowed Paths) + `cdd-kit context check` before editing.
  - IP-15 test-infra prereq (`metadata` param on `_make_element`/`_make_doc`) BEFORE authoring `TestBoundedRowGrowth`.
- Do NOT modify `fitz_renderer._insert_text_in_rect` (:407-552) except the single :511 call-arg change (IP-9) — otherwise must-not-regress reference (AC-6).
- Apply contract text from `agent-log/contract-reviewer.yml` (base + second-pass-summary); do not re-derive it.

## Known Risks

- CROSS-CHANGE BR-NUMBER COLLISION (now 3-way on BR-100): BR-98/BR-99/BR-100/BR-101
  are free in the live file today (highest live is BR-97), but sibling changes not
  yet landed claim them — `qa-judge-provider-consistency` claims BR-98,
  `qa-judge-hang-recovery` claims BR-99/BR-100. THIS change now ALSO adds a BR-100
  (bounded-local-table-row-growth) and BR-101, so BR-100 is a 3-WAY convergence
  (this change + qa-judge-hang-recovery + the earlier BR-99/100 claim). BR-101 is
  currently uncontested but could still collide. Whichever change edits
  business-rules.md first owns the numbers; IP-7 + IP-14 MUST re-check the live
  last-used BR number at actual edit time and renumber ALL of this change's new
  rules (BR-98/99/100/101) and every in-plan reference if a collision has landed.
  Flagged by contract-reviewer (base + second-pass) + in tasks.yml.
- OVERLAY-BACKGROUND COLLISION (HIGH risk, AC-10): in overlay mode the source PDF
  background (original table rules/graphics preserved by
  `apply_redactions(graphics=0)`) is NOT moved by the row-growth pre-pass — only
  the whitening + drawn text shift down, so pushed-down rows can land over original
  horizontal rules. Side-by-side (fresh canvas) is unaffected. The within-table
  page-capped bound limits but does not eliminate this. MITIGATION DECISION
  (below): ADOPTED — `PDF_TABLE_ROW_GROWTH_ENABLED` config flag (default `true`)
  is the production kill-switch; visual-reviewer in the implementation session must
  specifically inspect overlay-mode row-growth for background crossing, and ops can
  flip the flag `false` without reverting AC-1..AC-9/AC-11.
- CONFIG-FLAG DECISION (resolved this pass): ADOPT the flag. Reasoning — the
  overlay collision is flagged HIGH risk and row-growth is the largest/highest-risk
  sub-fix (design.md Migration explicitly recommends gating it); a single additive,
  non-secret env var + one env-contract.md entry is cheap and keeps the other five
  sub-fixes shippable/revertible independently (feature-staging per design.md). The
  AC-11 truncation warning means output stays safe+disclosed even with the flag
  off, so defaulting the feature `true` is acceptable. Cost: expands contract scope
  to `contracts/env/env-contract.md` (a manifest expansion the implementation
  session must approve — IP-13). Rejected alternative: leave undecided / no flag —
  rejected because a HIGH-risk overlay behavior with no production kill-switch would
  force a full revert to disable, defeating the independent-staging design.
- `metadata["lines"]` SHIFT COUPLING (AC-10): when a lower row is pushed down, its
  per-line whitening bboxes (`metadata["lines"]`, BR-84) MUST shift by the same
  delta as the element bbox, or whitening masks the OLD location. Concrete
  implementation hazard (design.md Open Risks) — IP-11 must shift both together;
  test-plan.md AC-10 case 4 pins this parity.
- AC-11 FITZ-ONLY DEGRADATION if sequencing slips: IP-12's sweep only covers the
  ReportLab path once IP-1's element-ref threading sets `render_truncated` there.
  If IP-12 lands before IP-1, AC-11 silently degrades to fitz-only. Hard-ordered in
  Handoff Constraints; test-plan.md AC-11 case 3 is CONTINGENT on this.
- `available_whitespace_below` GEOMETRY (AC-9): `reflow_document` is currently
  element-at-a-time; IP-9 must page-group elements to compute the gap-below without
  regressing the existing ordering/skip contract (bbox_reflow.py module docstring).
  Keep the field defaulted so all existing `Placement(...)` call sites stay green.
- test-plan.md is now FINALIZED (AC-1..AC-11 mapped). ci-gates.md Required Gates
  must still be cross-checked against the phase floor before implementation; if
  ci-gates.md remains a scaffold, reconcile it in the implementation session.
- OVERLAY/FITZ NON-REGRESSION: the shared `fit_text_cascade`/`_wrap_lines_simple`
  and the fitz overlay path (`_insert_text_in_rect`) need ZERO changes per
  design.md; any edit to text_region_renderer's shared cascade functions could
  regress the working overlay path. Constrain edits to `render_text_region`,
  `TextRegion`, and the two builder functions; keep the cascade core untouched.
- TABLE-DETECTION FALSE POSITIVE: `strategy="text"` clusters whitespace and can
  hallucinate a grid over ordinary prose with aligned indentation (e.g. a
  columnar-looking plain-prose document). The sanity gate (>=2 rows, >=2 cols,
  cell rects above the `>2.0pt` floor) mitigates but does not eliminate this —
  needs explicit test coverage on real-world borderless-but-NOT-tabular
  documents to prove AC-7 (attempted-after, never worsens).
- CASCADE STARTING FONT / render_truncated ON PLACEMENT PATH: `Placement` from
  bbox_reflow may not expose source `StyleInfo` or an element ref; if IP-1 cannot
  thread them, the cascade starts from the language `FONT_SIZE_CONFIG` max
  (slightly less faithful) and truncation degrades to log-only on that sub-path
  (a bounded BR-38 gap, matching the existing fitz legacy `element=None`
  behavior). Verify what `Placement` carries in bbox_reflow.py at implementation
  time before choosing to thread element vs. element_id.
- `.cdd/code-map.yml` freshness not re-validated this pass; File-Level Plan line
  ranges were read directly from source and matched the map for the files
  touched. Note: `_split_elements_by_cells` :560-574 ALREADY implements the
  BR-99 right/bottom extension (design.md "already applies") — the only BR-99
  CODE delta is the 1:1 path :444-452; do not double-apply.
