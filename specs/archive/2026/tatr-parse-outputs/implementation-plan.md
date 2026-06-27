---
change-id: tatr-parse-outputs
schema-version: 0.1.0
last-changed: 2026-06-27
---

# Implementation Plan: tatr-parse-outputs

## Objective

Replace the placeholder body of `TableRecognizer._parse_outputs()` in
`app/backend/parsers/table_recognizer.py` (currently lines 279-307, the
hardcoded 1x1 cell stub) with a real TATR decoder that turns ONNX detection
output into a row/column grid of `TableCell` objects, returned as the tuple
`(cells, num_rows, num_cols)`. Add three SELECTION test classes to
`tests/test_table_recognizer.py` that call `_parse_outputs` directly. Satisfy
AC-1 through AC-8 (see change-classification.md `## Inferred Acceptance
Criteria`). No other behavior changes; the feature stays gated off.

## Execution Scope

### In Scope
- Rewrite the body of `_parse_outputs(self, outputs, element_id)` only. Keep the
  method name, signature, and `(cells, num_rows, num_cols)` tuple return shape.
- Decode `outputs[0]` (pred_logits, shape `(1,N,C)`) and `outputs[1]`
  (pred_boxes, shape `(1,N,4)`, normalized CXCYWH) into a row/column grid using
  the algorithm in `## Decoder Algorithm` below.
- Add three test classes to `tests/test_table_recognizer.py`:
  `TestParseOutputsGrid`, `TestParseOutputsDegenerate`,
  `TestParseOutputsBoxFormat` (exact node ids in `## Test Execution Plan`).

### Out of Scope
- `recognize()`, `_run_recognition()`, `_load_session()`, `_resolve_model_path()`,
  weight resolution, or any ONNX session logic — do not touch.
- `TableCell` / `TableStructure` dataclasses in
  `app/backend/models/translatable_document.py` — read-only.
- `TABLE_RECOGNITION_ENABLED` and anything in `app/backend/config.py` — leave at
  `false`; do not edit.
- Cell `content` text extraction (stays `""`); spanning-cell row_span/col_span
  (stays 1); `recognition_confident` handling in `_run_recognition`.
- Any file other than the two named in `## File-Level Plan`. No opportunistic
  refactor of imports, logging, or surrounding methods.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | parsers/table_recognizer.py | Replace `_parse_outputs` body with TATR CXCYWH decoder per `## Decoder Algorithm`; return `(cells, num_rows, num_cols)`; degenerate input returns `([], 0, 0)` instead of raising (AC-6) | backend-engineer |
| IP-2 | tests/test_table_recognizer.py | Add `TestParseOutputsGrid`, `TestParseOutputsDegenerate`, `TestParseOutputsBoxFormat` as SELECTION tests calling `_parse_outputs` directly on a bare `TableRecognizer()` instance (AC-8) | backend-engineer |
| IP-3 | verification | Run the bounded test ladder in `## Test Execution Plan` and capture `test-evidence.yml` via `cdd-kit test run` | backend-engineer |

## Decoder Algorithm (IP-1 — authoritative)

`_parse_outputs(self, outputs, element_id)` must:

1. Read `logits = np.asarray(outputs[0])` and `boxes = np.asarray(outputs[1])`;
   squeeze the batch dim → `logits` shape `(N, C)`, `boxes` shape `(N, 4)`.
2. Per detection: `cls = argmax(logits[i])`; `score = softmax(logits[i])[cls]`.
3. Keep detections where `cls in {1 (column), 2 (row)}` and
   `score > _CONFIDENCE_THRESHOLD` (the existing module constant `0.5`, line 43).
   Class 5 (spanning cell) is allowed through the filter per test-plan.md
   §TATR Mock Output Shape but is NOT used for grid assignment (no AC covers
   spanning cells — out of scope); only classes 1 and 2 feed row/col lists.
4. Convert each kept box from normalized CXCYWH to pixel XYXY: multiply
   `cx,cy,w,h` by `768` (model input size), then
   `x0=cx-w/2, y0=cy-h/2, x1=cx+w/2, y1=cy+h/2`.
5. Split into `row_boxes` (cls 2) and `col_boxes` (cls 1).
6. Sort `row_boxes` by pixel y-center ascending → row index 0,1,...
7. Sort `col_boxes` by pixel x-center ascending → col index 0,1,...
8. For each `(row_i, row_box) x (col_j, col_box)`: compute intersection area of
   the two pixel XYXY boxes; if area > 0, emit a `TableCell`.
9. Each emitted cell: `cell_id=f"{element_id}:r{row_i}:c{col_j}"`, `row=row_i`,
   `col=col_j`, `content=""`, `row_span=1`, `col_span=1`, `is_numeric=False`.
10. If `row_boxes` is empty OR `col_boxes` is empty (or `outputs` is empty/
    malformed), return `([], 0, 0)` — do NOT raise (AC-6).
11. Otherwise return `(cells, len(row_boxes), len(col_boxes))`.

Notes:
- Return type is the tuple `(cells, num_rows, num_cols)`; the empty/degenerate
  case is `([], 0, 0)`, NOT a `TableStructure`. `_run_recognition` wraps the
  tuple into `TableStructure` and is unchanged.
- This intentionally changes the old stub's "raise on empty outputs" to a safe
  empty return, because tests call `_parse_outputs` directly and AC-6 requires a
  well-formed return rather than an exception. `recognize()` still fail-soft via
  its own latch and `_load_session` guards.
- Use `numpy` only (already imported); do not add new imports.

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-request.md | `## Constraints` | TATR CXCYWH format, sort/IoU rules, content="" |
| change-classification.md | `## Inferred Acceptance Criteria` AC-1..AC-8 | behavior to satisfy |
| test-plan.md | `## Acceptance Criteria → Test Mapping` | exact test node ids per AC |
| test-plan.md | `## Entry-Point Enforcement Rule` | call `_parse_outputs` directly; never `recognize()`/`_run_recognition()` |
| test-plan.md | `## TATR Mock Output Shape` | mock `[logits(1,N,7), boxes(1,N,4)]`, filter classes |
| test-plan.md | `## Notes` | use canonical non-overlapping 2x3 layout; tests must be RED first |
| ci-gates.md | `## Required Gates for This Change` | verification commands |
| change-classification.md | `## Required Contracts` (Data shape: review-only) | confirm IR conformance, no schema edit |
| table_recognizer.py | `_parse_outputs` lines 279-307; `_run_recognition` lines 220-277; `_CONFIDENCE_THRESHOLD` line 43 | edit target + how `outputs` is produced |
| translatable_document.py | `TableCell` (lines 38-83), `TableStructure` (lines 86-127) | field names/order for emitted IR |

(No design.md — Architecture Review Required: no.)

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `app/backend/parsers/table_recognizer.py` | edit | Replace body of `_parse_outputs` (lines 279-307) per `## Decoder Algorithm`. Keep signature and tuple return. No other method or import changed. |
| `tests/test_table_recognizer.py` | edit | Append `TestParseOutputsGrid`, `TestParseOutputsDegenerate`, `TestParseOutputsBoxFormat`. Build `[logits, boxes]` numpy mocks; call `TableRecognizer()._parse_outputs(mock_outputs, element_id)` directly. Do not modify existing tests. |

## Contract Updates

- API: none.
- CSS/UI: none.
- Env: none (`TABLE_RECOGNITION_MODEL_PATH` / `TABLE_RECOGNITION_ENABLED` unchanged).
- Data shape: review-only. Emitted `TableCell`/`TableStructure` must conform to
  `contracts/data/data-shape-contract.md` §TableCell / §TableStructure; no schema
  edit. contract-reviewer confirms no drift.
- Business logic: none. `TABLE_RECOGNITION_ENABLED` stays `false`; behavior opt-in.
- CI/CD: none. ci-gates.md confirms the existing `contract-and-fast-tests` job
  already covers all three required gates; no workflow edit.

## Test Execution Plan

SELECTION tests only (assert specific row/col assignments and cell_ids, not just
counts). Every test calls `recognizer._parse_outputs(mock_outputs, element_id)`
directly on a bare `TableRecognizer()` — calling `recognize()` or
`_run_recognition()` is forbidden (test-plan.md §Entry-Point Enforcement Rule).

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 row ordering | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_row_ordering_top_row_is_index_zero` | top (smallest y-center) row → index 0 |
| AC-1 num_rows/cols | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_num_rows_and_num_cols_match_grid` | returns num_rows=2, num_cols=3 |
| AC-1,2,3 happy path | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_2x3_grid_returns_six_cells` | 6 cells with distinct (row,col) |
| AC-2 col ordering | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_col_ordering_leftmost_col_is_index_zero` | leftmost (smallest x-center) col → index 0 |
| AC-3 overlap assign | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_cell_assigned_correct_row_col_by_overlap` | cell carries (row,col) of its overlapping row/col, not fixed |
| AC-4 empty content | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_all_cells_have_empty_content` | every cell content == "" |
| AC-8 cell_id format | `tests/test_table_recognizer.py::TestParseOutputsGrid::test_cell_id_format_includes_row_col` | cell_id == `f"{element_id}:r{row}:c{col}"` |
| AC-5 pixel conversion | `tests/test_table_recognizer.py::TestParseOutputsBoxFormat::test_cxcywh_normalized_converts_to_pixel_coords` | known CXCYWH maps to expected pixel XYXY |
| AC-5 pixel sort | `tests/test_table_recognizer.py::TestParseOutputsBoxFormat::test_row_sort_uses_pixel_y_center` | row order driven by pixel y-center |
| AC-6 no detections | `tests/test_table_recognizer.py::TestParseOutputsDegenerate::test_no_detections_above_threshold_returns_empty` | returns `([], 0, 0)`, no raise |
| AC-6 only cols | `tests/test_table_recognizer.py::TestParseOutputsDegenerate::test_zero_rows_only_cols_returns_empty` | returns `([], 0, 0)` |
| AC-6 only rows | `tests/test_table_recognizer.py::TestParseOutputsDegenerate::test_zero_cols_only_rows_returns_empty` | returns `([], 0, 0)` |
| AC-6 overlapping | `tests/test_table_recognizer.py::TestParseOutputsDegenerate::test_overlapping_bboxes_no_crash` | no exception; well-formed tuple |
| AC-7 flag unchanged | existing `tests/test_table_recognizer.py::TestModelUnavailableFallback` | no new test; remains green |

Required test phases (run via `cdd-kit test run` to produce `test-evidence.yml`;
floor is collect + targeted + changed-area, with full as final smoke per
ci-gates.md `full-suite` gate):

1. `cdd-kit test run tatr-parse-outputs --phase collect --command "pytest tests/test_table_recognizer.py --collect-only -q"`
2. `cdd-kit test run tatr-parse-outputs --phase targeted --command "pytest tests/test_table_recognizer.py::TestParseOutputsGrid tests/test_table_recognizer.py::TestParseOutputsDegenerate tests/test_table_recognizer.py::TestParseOutputsBoxFormat -x -q --tb=short"`
3. `cdd-kit test run tatr-parse-outputs --phase changed-area --command "pytest tests/test_table_recognizer.py -x -q --tb=short"`
4. `cdd-kit test run tatr-parse-outputs --phase full --command "pytest tests/ -x -q --tb=short"` (final smoke)

Order of work: write the three test classes first and confirm they are RED
against the current stub (the 1x1 stub fails any 2x3 selection assertion —
test-plan.md §Notes), then implement IP-1 to turn them GREEN.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan (the two files in `## File-Level Plan`) unless a Context Expansion Request is approved.
- Read boundary is `context-manifest.md` `## Allowed Paths`; backend-engineer's allowed set is `specs/changes/tatr-parse-outputs/`, `app/backend/parsers/table_recognizer.py`, `app/backend/models/translatable_document.py`, `app/backend/config.py` (config.py read-only). `tests/test_table_recognizer.py` is the named test target. Need anything else → file a Context Expansion Request and stop.

## Known Risks

- Tautology risk: tests must assert WHICH cell got WHICH (row,col)/cell_id on a 2x3 grid (SELECTION), not just cell counts (CLAUDE.md anti-tautology rule). A count-only assertion would pass even with a broken mapping.
- Wrong-entry-point risk: routing a test through `recognize()`/`_run_recognition()` requires a live ONNX session and would trivially skip/fail-soft — forbidden by test-plan.md §Entry-Point Enforcement Rule.
- Behavior change at the seam: the old stub raised on empty `outputs`; the new decoder returns `([], 0, 0)`. `recognize()` retains its own fail-soft latches so this does not weaken production fail-soft, but the backend-engineer must not reintroduce a raise that breaks AC-6 tests.
- `.cdd/code-map.yml` was not consulted for this plan (small, fully-scoped two-file change with exact line ranges already supplied); if line numbers have drifted, locate `_parse_outputs` by name rather than by the cited lines.
- Softmax numerical stability: subtract max-logit before `exp` to avoid overflow when computing the per-detection score.
