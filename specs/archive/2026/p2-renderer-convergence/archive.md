# Archive: p2-renderer-convergence

## Change Summary

The PDF rendering layer was converged on a primary/fallback architecture: fitz (PyMuPDF) is the primary renderer and ReportLab Canvas is the fallback, invoked only when fitz raises an unhandled exception. Both backends were reduced to thin adapters that delegate all IR→placement logic to a new shared component `app/backend/renderers/bbox_reflow.py`. The shared component consumes `TranslatableDocument` IR fields (`bbox`, `reading_order`, `element_type`, `page_num`, `translated_content`) and produces backend-neutral `Placement` objects, guaranteeing that both backends make identical element-level include/exclude, reading-order, and text-source decisions (BR-35). Dispatch in `pdf_processor._translate_pdf_to_pdf` calls fitz inside a try, logs a WARNING (exception type + document id) on failure, and retries via ReportLab; double-failure propagates (BR-34, Table K). `pdf_generator.py` was renamed to `fitz_renderer.py`; a backward-compat shim was left at the old path.

## Final Behavior

- PDF translation uses `fitz_renderer` as the primary render path and `coordinate_renderer` as the fallback.
- Both render paths call `reflow_document(document)` from `bbox_reflow.py` and make identical element-level decisions.
- Fallback trigger: any unhandled exception from the fitz path. Non-triggers: malformed IR (null bbox → skip, null reading_order → positional sort, unknown element_type → treat as text, null translated_content → use content).
- On fallback: WARNING log with exception type and document id.
- Double failure (both paths raise): exception propagates; job transitions to `failed`.
- Golden placement snapshots (`*.layout.json`) committed to `tests/fixtures/golden/pdf/` for placement-regression detection.
- New CI gate `renderer-equivalence` verifies both paths agree at element-level decisions on every PR.

## Final Contracts Updated

| contract | version | change |
|---|---|---|
| `contracts/data/data-shape-contract.md` | 0.4.3 | Added `### Renderer IR-consumption contract` with field obligations and malformed IR handling table |
| `contracts/business/business-rules.md` | 0.7.1 | Added BR-34 (renderer-primary-fallback), BR-35 (renderer-ir-consumption-consistency), Table K |
| `contracts/ci/ci-gate-contract.md` | 0.4.1 | Added `renderer-equivalence` gate row and full gate section |

Evidence: `specs/changes/p2-renderer-convergence/agent-log/backend-engineer.yml` (contracts-touched); agent-log notes confirm contracts were pre-authored then consumed.

## Final Tests Added / Updated

| file | what changed |
|---|---|
| `tests/test_renderer_convergence.py` (new, 28 tests) | AC-1 through AC-7: TestIRBboxReflow, TestFitzPrimary, TestFitzFallback, TestLayoutEquivalence (mock-based wiring assertions), TestMalformedIRDataBoundary, TestEquivalenceGolden (snapshot-based) |
| `tests/test_pdf_generator.py` | Added TestFallbackPath (2 tests, AC-3); updated patch targets from pdf_generator to fitz_renderer |
| `tests/test_ir_pipeline_decoupling.py` | Added TestReadingOrderPreservedBothPaths, TestElementTypingPreservedBothPaths, TestMalformedIRBothPaths |
| `tests/fixtures/golden/pdf/fitz_snapshot.layout.json` | New pre-committed placement snapshot |
| `tests/fixtures/golden/pdf/reportlab_snapshot.layout.json` | New pre-committed placement snapshot |

Evidence: `specs/changes/p2-renderer-convergence/agent-log/backend-engineer.yml` (tests-added); test-evidence.yml all phases passed.

## Final CI/CD Gates

| gate | trigger | status |
|---|---|---|
| contract-validate | pre-commit / PR | required |
| change-gate | pre-commit / PR | required |
| unit-tests | PR | required |
| golden-sample-regression | PR | required |
| layout-detector-dependency-gate | PR | required |
| renderer-equivalence | PR | required (new) |

Source: `specs/changes/p2-renderer-convergence/ci-gates.md`. Added `renderer-equivalence` job to `.github/workflows/contract-driven-gates.yml`.

## Production Reality Findings

**F-0 (critical — closed):** `bbox_reflow.py` was implemented correctly but neither `fitz_renderer` nor `coordinate_renderer` imported or called `reflow_document`. The shared component was orphaned. Additionally, the equivalence tests were tautological — `TestLayoutEquivalence` called `reflow_document` twice against itself, which is guaranteed to match regardless of whether the backends consume it. This was caught by the QA reviewer via `grep -rn "reflow_document|bbox_reflow"` across all renderer files. Fix: backend-engineer re-invoked to wire both adapters and replace tautological tests with mock-based wiring assertions (`mock.patch` to assert each backend calls `reflow_document`). Evidence: `agent-log/backend-engineer.yml` (status: complete (re-invocation: QA fixes applied)).

**VR-1 (non-blocking residual):** The fitz quad refinement path (`page.search_for()`) is used only for `redact_rect` (original text mask), not `text_rect` (translated placement). This means the Open Risk from design.md is mitigated at the architecture level: reflow output drives translated text placement directly; quad search only refines the mask rect. No tolerance violation observed. A follow-up test for adapter-level coordinate extraction is deferred. Evidence: `visual-review-report.md` §2, `agent-log/backend-engineer.yml` note on AC-1.

## Lessons Promoted to Standards

| lesson | target | text | evidence |
|---|---|---|---|
| Shared component wiring verification | `CLAUDE.md §Promoted Learnings` | "When introducing a shared module that multiple backends must import, verify all consumer imports via `grep` before marking implementation done — orphaned shared components are a common QA-catch miss — see `contracts/data/data-shape-contract.md §Renderer IR-consumption contract`." | `agent-log/backend-engineer.yml:4` (F-0 critical), `archive.md §Production Reality Findings` |
| Tautological wiring tests | `CLAUDE.md §Promoted Learnings` | "When testing multi-backend shared-component wiring, use `mock.patch` to assert each backend calls the shared function — calling the component twice against itself is tautological and always passes even when backends are unwired — see `tests/test_renderer_convergence.py::TestLayoutEquivalence`." | `agent-log/backend-engineer.yml:11` (tests-added fix), `archive.md §Production Reality Findings` |

## Follow-up Work

- **VR-1 follow-up**: Add an adapter-level coordinate extraction test that drives `fitz_renderer._generate_overlay` end-to-end and extracts placed text coordinates from the resulting PDF, then asserts they match `reflow_document` output within ±2.0 pt. This closes the "adapter-level integration gap" identified by the visual reviewer.
- **VR-3**: Update `TestEquivalenceGolden` to drive at least one golden fixture PDF through `reflow_document` (using its parsed IR) rather than the synthetic `_make_doc()` document.
- **VR-6**: Strengthen null reading_order test to assert the sort order produced, not just "at least one placement returned".

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
