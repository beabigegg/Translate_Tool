---
change-id: pdf-layout-refactor
schema-version: 0.1.0
last-changed: 2026-06-27
---

# Implementation Plan: pdf-layout-refactor

## Objective
Deliver the seven PDF-fidelity fixes (3.1→3.7) that satisfy AC-1..AC-8 (change-classification.md
§Inferred Acceptance Criteria) and BR-84..BR-88 + amended BR-36 (business-rules.md Table W / Table L),
inside one sequential worktree on branch `feat/pdf-layout-refactor`. Upgrade the PDF
parse→detect→translate→render pipeline (whitening, paragraph IR, scale-fit, per-span style,
reading-order model, render DPI, formula pass-through + lazy OCR seam) while preserving the
fitz-primary / ReportLab-fallback convergence (BR-34/35) and the TATR path
(TABLE_RECOGNITION_ENABLED=false).

## Execution Scope

### In Scope
- 3.1 bbox-exact whitening (AC-1, BR-84) — `renderers/fitz_renderer.py`
- 3.2 paragraph aggregation + reflow IR (AC-2) — `parsers/pdf_parser.py`
- 3.3 iterative binary-search scale-fit (AC-3, BR-85, amended BR-36 step a/e) — `renderers/text_region_renderer.py`, `config.py`
- 3.4 per-span StyleInfo incl. `is_underline` (AC-4) — `models/translatable_document.py`, `parsers/pdf_parser.py`, `renderers/fitz_renderer.py`
- 3.5 column-aware `LayoutReader` reading order (AC-5) — `parsers/layout_detector.py`
- 3.6 `PDF_RENDER_DPI` render-matrix upgrade (AC-6) — `parsers/pdf_parser.py`, `config.py`
- 3.7 FORMULA pass-through (BR-86) + lazy OCR seam (BR-87) — `processors/pdf_processor.py`, `parsers/pdf_parser.py`, new `parsers/ocr_backend.py`, `config.py`
- New tests in `tests/test_pdf_layout_refactor.py`; extend the existing tests named in test-plan.md §Test Update Contract.

### Out of Scope
- XLSX / DOCX / PPTX processors and parsers.
- Table-structure recognition (p3-table-structure shipped; TABLE_RECOGNITION_ENABLED=false verified only).
- LLM critique / judge loop logic (do NOT alter the `block_overrides` keying scheme — see IP-R1).
- Any REST endpoint / API contract / frontend change. LLM client changes.
- Full visual golden-pixel comparison (durable evidence lives in visual-review-report.md).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | renderers/fitz_renderer.py | Replace `search_for`-quad whitening with direct bbox redaction (3.1) | backend-engineer |
| IP-2 | parsers/pdf_parser.py | Aggregate consecutive in-block lines into one paragraph element; keep per-line bboxes in `metadata["lines"]` (3.2) | backend-engineer |
| IP-3 | renderers/text_region_renderer.py + config.py | Binary-search font fit between 8pt and original; unify font floor to `MIN_READABLE_FONT_PT=8` (3.3) | backend-engineer |
| IP-4 | models/translatable_document.py + pdf_parser.py + fitz_renderer.py | Add `StyleInfo.is_underline`; capture + re-apply per-span style runs (3.4) | backend-engineer |
| IP-5 | parsers/layout_detector.py | Add internal `LayoutReader` (column clustering + y-sort + RTL) replacing the x-gap threshold (3.5) | backend-engineer |
| IP-6 | parsers/pdf_parser.py + config.py | Add `PDF_RENDER_DPI` (150) and DPI-scaled rasterise matrix (3.6) | backend-engineer |
| IP-7 | processors/pdf_processor.py + pdf_parser.py + new ocr_backend.py + config.py | FORMULA pass-through on all paths; lazy OCR seam gated by `OCR_ENABLED` (3.7) | backend-engineer |
| IP-8 | tests/test_pdf_layout_refactor.py (+extends) | TDD tests per item; extend metrics/golden/convergence tests | backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | D-1..D-7, Open Risks, Affected Components table | per-item implementation constraints |
| change-classification.md | AC-1..AC-8 | acceptance criteria |
| test-plan.md | §AC→Test Mapping, §Test Update Contract, §Test Execution Ladder | tests to write/extend, ladder |
| ci-gates.md | §Required Gates (residual-text, ocr-absent-gate, full-regression) | verification gates |
| contracts/business/business-rules.md | BR-84..BR-88, Table W; amended BR-36/BR-38 Table L; Invalid-Data rows (scanned PDF) | behavior rules |
| contracts/data/data-shape-contract.md | §StyleInfo `is_underline` (line ~201), §`formula` pass-through (lines ~128/159), §Known consumers of the IR | IR shape rules |
| contracts/env/env-contract.md | `OCR_ENABLED` (line 47), `PDF_RENDER_DPI` | config-flag contract |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/renderers/fitz_renderer.py | edit | 3.1 whitening (~lines 290-332); 3.4 per-span `insert_text` (render block ~538-548 area) |
| app/backend/parsers/pdf_parser.py | edit | 3.2 paragraph aggregation; 3.4 span capture (flags ~213-296); 3.6 DPI matrix; 3.7 near-empty→OCR routing |
| app/backend/renderers/text_region_renderer.py | edit | 3.3 `fit_text_cascade` step (a) binary search (~lines 180-250); fix 4pt docstring (line 191) |
| app/backend/renderers/bbox_reflow.py | edit-if-needed | placement seam; only touch if it references the old floor constant |
| app/backend/utils/font_utils.py | edit | repoint `fit_text_to_bbox` default floor to `MIN_READABLE_FONT_PT` (lines 471/480) |
| app/backend/models/translatable_document.py | edit | 3.4 add `is_underline` to `StyleInfo` + `to_dict`/`from_dict` (lines 189-220) |
| app/backend/parsers/layout_detector.py | edit | 3.5 add `LayoutReader`; replace `_assign_reading_order` x-gap heuristic |
| app/backend/config.py | edit | add `PDF_RENDER_DPI`, `OCR_ENABLED`, `MIN_READABLE_FONT_PT=8`; reconcile `MIN_FONT_SIZE_PT` (line 177) |
| app/backend/processors/pdf_processor.py | edit | 3.7 FORMULA pass-through before dispatch; do NOT change `pdf:{stem}:{idx}` keying |
| app/backend/parsers/ocr_backend.py | create | lazy-import `run_ocr(page) -> list[TranslatableElement]`; import OCR lib inside function body only |
| tests/test_pdf_layout_refactor.py | create | all AC-1..AC-8 new tests |
| tests/test_layout_metrics.py, test_golden_regression.py, test_renderer_convergence.py | extend | per test-plan.md §Test Update Contract |

## Execution Order (strict sequential — each item's targeted test green before the next)

### 3.1 — Bbox-exact whitening (AC-1, BR-84) — D-1
Files: `renderers/fitz_renderer.py`.
- Remove the `page.search_for(original_text, quads=True)` call and its quad-matching block (~lines 290-328).
- Build the redaction rect directly from the element IR `bbox`; for paragraph elements (3.2) iterate `element.metadata["lines"]` and whiten each per-line bbox so every source line is masked.
- Retain `PDF_MASK_MARGIN_PT` shrink to spare table borders; keep the existing redaction-annotation apply mechanism (do not switch to draw-rect-only cover — see fitz_renderer.py:632 note about removal vs cover).
- Skip invalid rects (width/height < 1) as today.
- Test first: `test_bbox_whitening_uses_draw_rect`, `test_whitening_non_latin_no_bleed`.
Gate: those two pass; residual source-text count = 0 on a non-Latin / multi-line run.

### 3.2 — Paragraph aggregation + reflow (AC-2) — D-2
Files: `parsers/pdf_parser.py`.
- Group consecutive fitz `line` dicts within the same block/region into one `TranslatableElement`; paragraph `content` = joined line text; paragraph `bbox` = union of line bboxes.
- Persist each original line bbox in `metadata["lines"]` (consumed by 3.1 whitening).
- Keep style capture compatible with 3.4 (span list per paragraph).
- IP-R1 (resolve BEFORE coding): the judge `block_overrides` key `pdf:{stem}:{idx}` indexes into `unique_texts = list(set(content))` (pdf_processor.py:338-339, 696-697, 435-438), NOT raw element count. Aggregation changes element/text content but the index derivation stays internally consistent within a single parse; cross-version stale maps already fail-soft per BR-77 (the `else: = src_text` branch). Decision: do NOT introduce `element_id`-based keys — keep the existing scheme; document this stability finding in the agent log. Confirm pdf_processor.py:312-323 partition logic still produces a deterministic `unique_texts` after aggregation.
- Test first: `test_paragraph_aggregation_reduces_element_count`.
Gate: test passes; whitening (3.1) still masks every source line via `metadata["lines"]`.

### 3.3 — Iterative scale-fitting (AC-3, BR-85, amended BR-36/BR-38) — D-3
Files: `renderers/text_region_renderer.py`, `config.py`, `utils/font_utils.py`.
- IP-R2 (resolve BEFORE coding): unify three competing floors to ONE source of truth `config.MIN_READABLE_FONT_PT = 8` (BR-88). Add it to config.py; repoint `fit_text_cascade` and `fit_text_to_bbox` (font_utils.py:471/480) to it; correct the stale "4 pt floor" docstring at text_region_renderer.py:191. Reconcile/retire `MIN_FONT_SIZE_PT = 6` (config.py:177) — leave only if still needed by an unrelated path; BR-88 forbids a competing render floor.
- Replace the linear `font_size = max(font_size * _SHRINK, ...)` shrink loop (~lines 235-250) with a binary search between `MIN_READABLE_FONT_PT` and the original size, selecting the largest fitting size.
- Set `render_truncated = True` and fire cascade step (e) ONLY when text still overflows at 8pt; keep the `CascadeDecision`/`render_truncated` contract (BR-38) unchanged so the ReportLab fallback and QA net keep working.
- Test first: `test_scale_fit_stays_above_readable_floor`, `test_scale_fit_truncated_only_at_8pt_overflow`.
Gate: both pass; floor is 8pt; truncation fires only on 8pt overflow.

### 3.4 — Per-span style fidelity (AC-4) — D-4
Files: `models/translatable_document.py`, `parsers/pdf_parser.py`, `renderers/fitz_renderer.py`.
- Add `is_underline: bool = False` to `StyleInfo` (after `is_italic`, line 195) and to `to_dict()` / `from_dict()` with `.get("is_underline", False)` (backward-compatible per data-shape-contract.md line ~201).
- Capture a per-span style list (font, size, color, bold, italic, underline) into `metadata["spans"]` (design D-4). Existing flags: bold=`2**4`, italic=`2**1` (pdf_parser.py:213-296). IP-R3: the planner-supplied "bit 4 = underline" COLLIDES with bold (`2**4`); do NOT reuse bit 4. Derive `is_underline` from the correct PyMuPDF signal in the installed version (span/char underline flag) and default to `False` when unavailable — never alias the bold bit.
- fitz renderer: emit one `insert_text` per span run applying that span's `StyleInfo` (color/bold/italic/underline); elements without a `spans` list fall back to the single-style path.
- Test first: `test_span_color_preserved`, `test_span_bold_preserved`, `test_is_underline_backward_compat` (from_dict on a dict missing the key → False).
Gate: three pass; render asserts source StyleInfo is preserved per span.

### 3.5 — Reading-order model (AC-5) — D-5
Files: `parsers/layout_detector.py`.
- Add an internal `LayoutReader` class (no new ONNX dependency): assign each element to a column via x-coordinate clustering (gap-threshold with multi-column support); within a column sort by y; return column-first, top-to-bottom.
- RTL: when the majority of elements are right-anchored, order columns right-to-left.
- Replace the single `_COLUMN_GAP_THRESHOLD` x-gap / `round(y0/10)` heuristic in `_assign_reading_order`; fail-soft to the existing heuristic on any error.
- Test first: `test_reading_order_column_assignment_two_column`.
Gate: test passes on the two-column fixture; normalized reading-order edit distance drops vs x-gap baseline.

### 3.6 — DPI upgrade (AC-6) — D-6
Files: `parsers/pdf_parser.py`, `config.py`.
- Add `PDF_RENDER_DPI: int = int(os.getenv("PDF_RENDER_DPI", "150"))` to config.py (env-contract.md).
- Change the detector rasterise matrix from `fitz.Matrix(1, 1)` (72 DPI) to `fitz.Matrix(dpi/72, dpi/72)` with `dpi = config.PDF_RENDER_DPI`.
- Detection bboxes are normalized 0..1, so no downstream coordinate math changes.
- Test first: `test_pdf_render_dpi_matrix_scaling` (mock `fitz.Matrix`, assert `PDF_RENDER_DPI/72` scale), `test_high_dpi_pixel_dimensions`.
Gate: both pass; matrix uses the configured DPI; DPI=72 reproduces old behavior.

### 3.7 — Formula pass-through + OCR (AC-7, BR-86/BR-87) — D-7
Files: `processors/pdf_processor.py`, `parsers/pdf_parser.py`, new `parsers/ocr_backend.py`, `config.py`.
- (a) Formula pass-through (path-independent, BR-86): before translation dispatch, for every element with `element_type == ElementType.FORMULA` force `should_translate = False` and set `translated_content = content`. IP-R4: `layout_detector._assign_element_types` already sets `should_translate=False` for FORMULA on the detector path; D-7(a) EXTENDS the same identity copy to the heuristic path at the processor — do not duplicate the detector logic, just guarantee path-independence at the processor seam.
- (b) OCR seam (BR-87): create `parsers/ocr_backend.py` with `run_ocr(page) -> list[TranslatableElement]` importing Surya/PaddleOCR INSIDE the function body (never at module top level). Add `OCR_ENABLED: bool = os.getenv("OCR_ENABLED", "false").lower() == "true"` to config.py. In pdf_parser.py, after `page.get_text()`, when text is near-empty and visible objects exist: if `OCR_ENABLED` → call `ocr_backend.run_ocr(page)`; else → emit one WARNING per job (reuse `has_text_layer`) and produce near-blank IR; never crash. When `OCR_ENABLED=True` but the library is absent, catch ImportError, log WARNING, fall back to near-blank (BR-87 Invalid-Data rows).
- Test first: `test_formula_pass_through`, `test_formula_only_page_no_translation`, `test_scanned_ocr_routing_when_enabled`, `test_ocr_absent_no_crash`.
Gate: all pass with the OCR library NOT installed (OCR_ENABLED=False default).

## Contract Updates
- API: none.
- CSS/UI: none.
- Env: `PDF_RENDER_DPI`, `OCR_ENABLED` — already specified in env-contract.md; ensure config.py + `.env.example` match.
- Data shape: `StyleInfo.is_underline`, `metadata["spans"]`, FORMULA `translated_content=content` — already in data-shape-contract.md; implementation must conform (no further contract edits expected).
- Business logic: BR-84..BR-88, amended BR-36/BR-38 — already in business-rules.md; implementation must conform.
- CI/CD: gates already in ci-gates.md; no new gate authoring (planner does not write CI).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_pdf_layout_refactor.py::test_bbox_whitening_uses_draw_rect | residual source-text = 0; no search_for |
| AC-2 | tests/test_pdf_layout_refactor.py::test_paragraph_aggregation_reduces_element_count | element count drops; BIoU up |
| AC-3 | tests/test_pdf_layout_refactor.py::test_scale_fit_stays_above_readable_floor | min font ≥ 8pt |
| AC-4 | tests/test_pdf_layout_refactor.py::test_span_color_preserved | per-span style preserved |
| AC-5 | tests/test_pdf_layout_refactor.py::test_reading_order_column_assignment_two_column | column-first order |
| AC-6 | tests/test_pdf_layout_refactor.py::test_pdf_render_dpi_matrix_scaling | matrix = DPI/72 |
| AC-7 | tests/test_pdf_layout_refactor.py::test_formula_pass_through | translated==content; no LLM |
| AC-7/8 | tests/test_pdf_layout_refactor.py::test_ocr_absent_no_crash | no crash, OCR not imported |
| AC-8 | tests/test_renderer_convergence.py (extend) | fitz↔ReportLab converge; TATR off |

Required phase floor: collect, targeted, changed-area, contract (test-plan.md §Test Execution Ladder; full ladder there). After all 7 items pass their item-gates, generate evidence with `cdd-kit test run`:
1. collect — `pytest tests/test_pdf_layout_refactor.py --collect-only -q`
2. targeted — `pytest tests/test_pdf_layout_refactor.py -x -q --tb=short` (`--required-phases collect,targeted,changed-area,contract`)
3. changed-area — `pytest tests/test_pdf_layout_refactor.py tests/test_renderer_convergence.py tests/test_pdf_render_warnings.py tests/test_pdf_parser.py tests/test_layout_detector.py tests/test_layout_metrics.py tests/test_text_region_renderer.py -x -q --tb=short`
4. contract — `cdd-kit validate --contracts`
5. full — `pytest -x -q --tb=short`

## Handoff Constraints
- Work in the worktree `/home/egg/Projects/Translate_Tool/.claude/worktrees/pdf-layout-refactor/` on branch `feat/pdf-layout-refactor`.
- Strictly sequential 3.1→3.7; do not start an item until the prior item's targeted tests are green.
- TDD: write the failing test for each item first, then implement.
- OCR library MUST be lazy-imported (inside `run_ocr` body), never at module top level; CI must pass without it.
- Implementation agents must not infer missing requirements from chat history; follow this plan and the source pointers.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- Keep implementation within the file-level plan; if a needed path is not in context-manifest.md §Allowed Paths, file a Context Expansion Request and stop.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Run `cdd-kit gate pdf-layout-refactor --strict` before commit. Tier-floor watch: if the gate floors on OCR/cache/integration vocabulary, apply `tier-floor-override` with rationale "OCR_ENABLED is a lazy feature flag, not auth/cache/migration; genuine tier is 1" (ci-gates.md §Notes).

## Known Risks
- IP-R1 block_id stability: `pdf:{stem}:{idx}` indexes `unique_texts` (a per-parse `list(set())`), not element count; aggregation is index-stable within a parse and stale cross-version maps fail-soft (BR-77). Do not change the keying scheme.
- IP-R2 font-floor reconciliation: `MIN_FONT_SIZE_PT=6` (config.py:177), 4pt docstring (text_region_renderer.py:191), and 8pt all coexist; BR-88 mandates a single `config.MIN_READABLE_FONT_PT=8`. Reconcile before 3.3.
- IP-R3 underline bit collision: bold already uses `2**4`; do not alias it for underline. Derive from the correct PyMuPDF signal or default False.
- IP-R4 FORMULA partial impl: detector path already forces `should_translate=False`; extend identity copy to the heuristic path at the processor without duplicating detector logic.
- DPI cost: 150 DPI raises per-page memory/latency vs 72; flag is opt-out (set DPI=72). Bound by `PDF_RENDER_DPI`.
- `.cdd/code-map.yml` was not consulted as a precise line index for this plan; the line numbers above were verified directly via Grep/Read against the worktree source and are accurate as of writing — the implementer should re-confirm exact ranges before editing.
