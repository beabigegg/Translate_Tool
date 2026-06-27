---
change-id: layout-fidelity-metrics
schema-version: 0.1.0
last-changed: 2026-06-27
---

# Implementation Plan: layout-fidelity-metrics

## Objective

Deliver a self-contained, importable layout-fidelity metrics harness under
`tests/`, plus a full test suite proving it. Three pure metric functions
(`compute_biou`, `check_residual_text`, `compute_truncation_rate`), one
committed deterministic golden PDF fixture, and `tests/test_layout_metrics.py`
(22 nodes) must pass under `pytest` from the project root. No `app/backend/` or
`app/frontend/` file is touched. Track G consumes these modules as CI metric
gates in a separate change; this change only provides the importable modules and
their tests.

## Execution Scope

### In Scope
- New package `tests/metrics/` with `biou.py`, `residual_text.py`,
  `truncation_rate.py`, and `__init__.py`.
- Committed binary fixture `tests/fixtures/golden/simple_test.pdf` plus the
  one-shot generator script that produced it.
- New test suite `tests/test_layout_metrics.py` implementing all 22 nodes in
  `test-plan.md §Acceptance Criteria → Test Mapping`.
- Read-only reference to `app/backend/models/translatable_document.py` for
  `BoundingBox` field names and `TranslatableElement.render_truncated` /
  `.metadata` semantics — no edits to that file.

### Out of Scope
- Any modification to `app/backend/` or `app/frontend/` (AC-7 forbids it).
- Wiring these metrics as CI gates or editing
  `.github/workflows/contract-driven-gates.yml` (Track G owns this).
- Real PyMuPDF page I/O in unit tests for residual-text (stub the `page`).
- New runtime deps: no scipy / skimage / numpy. Only stdlib math + `fitz`
  (already in the conda env) are allowed.
- Performance/stress/integration testing of the metric functions.
- Opportunistic refactors of existing tests or any IR change.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | tests/metrics | Create `tests/metrics/__init__.py` (empty package marker) | backend-engineer |
| IP-2 | tests/metrics | Implement `tests/metrics/biou.py`: `BIOU_REGRESSION_BUDGET = 0.8` and `compute_biou(source_bboxes, rendered_bboxes) -> float` (mean of per-source best-match IoU) | backend-engineer |
| IP-3 | tests/metrics | Implement `tests/metrics/residual_text.py`: `check_residual_text(page, whiteover_bboxes) -> list[dict]` | backend-engineer |
| IP-4 | tests/metrics | Implement `tests/metrics/truncation_rate.py`: `compute_truncation_rate(elements) -> dict` | backend-engineer |
| IP-5 | tests/fixtures | Generate `tests/fixtures/golden/simple_test.pdf` once via a committed fitz script; commit the binary | backend-engineer |
| IP-6 | tests | Implement `tests/test_layout_metrics.py` (22 nodes) with selection-style assertions | backend-engineer |
| IP-7 | verification | Run the test ladder via `cdd-kit test run` (collect, targeted, changed-area, full) and emit `test-evidence.yml` | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | `## Inferred Acceptance Criteria` AC-1..AC-7 | behavior each module must satisfy |
| test-plan.md | `## Acceptance Criteria → Test Mapping` | exact 22 test node names to implement |
| test-plan.md | `## Anti-Tautology Note (AC-6)` | matched source→rendered index assertion in `test_partial_overlap_value_and_matched_pair` |
| test-plan.md | `## Fixture Path Convention (AC-5, AC-7)` | `Path(__file__).parent.parent` repo-root rule |
| test-plan.md | `## Test Execution Ladder` | phases collect / targeted / changed-area / full |
| ci-gates.md | `## Required Gates` | `pytest tests/test_layout_metrics.py -v` and `pytest` full-suite |
| app/backend/models/translatable_document.py | `BoundingBox` (x0/y0/x1/y1, top-left origin); `TranslatableElement.render_truncated` (line ~237), `.bbox` (Optional), `.metadata["overflow_area"]` | field names the metrics read (read-only) |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `tests/metrics/__init__.py` | create | empty; enables `from tests.metrics.biou import compute_biou` (AC-7) |
| `tests/metrics/biou.py` | create | `BIOU_REGRESSION_BUDGET = 0.8`; `compute_biou`. IoU = intersection/union with top-left coords. inter = `max(0, min(x1,x1')-max(x0,x0')) * max(0, min(y1,y1')-max(y0,y0'))`; union = `areaA + areaB - inter`. For each source bbox take max IoU over all rendered bboxes, then return mean. Return `0.0` if either list empty; zero-area pair yields IoU `0.0` (guard union==0, no exception) |
| `tests/metrics/residual_text.py` | create | `check_residual_text`: for each whiteover bbox call `page.get_text("blocks", clip=(x0,y0,x1,y1))`; emit `{"bbox": bbox, "text": str, "blocks": list}` only for regions with ≥1 block; clean page -> `[]`. Duck-type `page` — do not import fitz here |
| `tests/metrics/truncation_rate.py` | create | `compute_truncation_rate`: returns `{"count","total","ratio","overflow_area_sum"}`. `ratio = count/total` (0.0 when total==0). Elements with `bbox is None` still counted in total/count; `overflow_area_sum = sum(el.metadata.get("overflow_area", 0.0) for truncated el)` |
| `tests/fixtures/golden/generate_simple_test_pdf.py` | create | one-shot fitz generator: 1 page, 2–3 text blocks at fixed coords; run once locally, output committed. Not invoked at test time |
| `tests/fixtures/golden/simple_test.pdf` | create (commit binary) | deterministic committed binary; tests only open it (AC-5) |
| `tests/test_layout_metrics.py` | create | 22 nodes per mapping table; `REPO_ROOT = Path(__file__).parent.parent`; stub `page` for residual-text; open `REPO_ROOT/"tests/fixtures/golden/simple_test.pdf"` with fitz for `TestGoldenFixture` |
| `app/backend/**`, `app/frontend/**` | do NOT touch | AC-7; `TestModuleImports::test_no_app_backend_files_modified` enforces |

## Contract Updates

- API: none
- CSS/UI: none
- Env: none
- Data shape: none — read-only consumer of `BoundingBox` and
  `TranslatableElement.render_truncated`/`.metadata`; the IR contract is not
  modified.
- Business logic: none
- CI/CD: none in this change — Track G registers these metrics as gates separately.

## Test Execution Plan

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | `tests/test_layout_metrics.py::TestBIoU` (4 nodes: identical→1, disjoint→0, partial-overlap+matched-pair, float-in-[0,1]) | identical sets return 1.0, disjoint return 0.0, partial value matches hand-computed IoU |
| AC-2 | `tests/test_layout_metrics.py::TestBIoUDegenerate` (empty source, empty rendered, zero-area source, zero-area rendered) | each returns defined float, no exception raised |
| AC-3 | `tests/test_layout_metrics.py::TestResidualText` (clean→[], leaking flagged, record has bbox+text fields) | clean stub page returns `[]`; leaking stub yields per-region record |
| AC-4 | `tests/test_layout_metrics.py::TestTruncationRate` (all→1.0, none→0.0, partial ratio+overflow_area, none-bbox counted) | ratio and overflow_area_sum match hand-computed values |
| AC-5 | `tests/test_layout_metrics.py::TestGoldenFixture` (file exists/valid PDF, exactly one page) | committed PDF opens with fitz, `page_count == 1` |
| AC-6 | `tests/test_layout_metrics.py::TestBIoU::test_partial_overlap_value_and_matched_pair` | asserts which source index matched which rendered index (not only scalar mean) |
| AC-7 | `tests/test_layout_metrics.py::TestModuleImports` (3 import nodes + no-app-modified) | metric modules import from `tests.metrics.*`; no `app/backend` file touched |

Phases (per `test-plan.md §Test Execution Ladder`; required floor collect /
targeted / changed-area, plus full for CI smoke). Generate evidence with
`cdd-kit test run`:

1. `cdd-kit test run layout-fidelity-metrics --phase collect --command "pytest --collect-only tests/test_layout_metrics.py"`
2. `cdd-kit test run layout-fidelity-metrics --phase targeted --command "pytest tests/test_layout_metrics.py -v"`
3. `cdd-kit test run layout-fidelity-metrics --phase changed-area --command "pytest tests/test_layout_metrics.py -v"`
4. `cdd-kit test run layout-fidelity-metrics --phase full --command "pytest"`

Implementation order: IP-1 → IP-2 → IP-3 → IP-4 → IP-5 → IP-6 → IP-7.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved. Geometry conventions beyond `translatable_document.py` are gated behind CER-001 (status: pending) — do not read `bbox_reflow.py`/`bbox_utils.py` until it is approved.
- The three metrics use only stdlib `math` and `fitz`; adding scipy/skimage/numpy is out of scope and a `blocked` trigger if deemed necessary.

## Known Risks
- Selection-tautology (AC-6): asserting only the scalar BIoU mean lets mismatched source→rendered pairs pass. `test_partial_overlap_value_and_matched_pair` must assert the matched index identity. See `test-plan.md §Anti-Tautology Note`.
- Non-deterministic fixture: generating the PDF at test runtime would make its hash CI-unstable. Commit the binary; tests must only open it (AC-5, `test-plan.md §Notes`).
- Hardcoded paths: any absolute path to the fixture breaks on CI runners. Use `Path(__file__).parent.parent` per the promoted learning (`tests/test_text_region_renderer.py` pattern).
- Missing `tests/metrics/__init__.py` breaks the import assertions (AC-7) — create it first (IP-1).
- Zero-area / empty-list inputs must not raise (AC-2, AC-4); guard division by zero in both IoU union and ratio.
- `.cdd/code-map.yml` was refreshed in the latest commit; line numbers for `translatable_document.py` (e.g. `render_truncated` ~line 237) are reference-only — match by symbol name, not line number.
