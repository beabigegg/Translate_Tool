---
change-id: pdf-stage-detail-snapshot
schema-version: 0.1.0
last-changed: 2026-07-08
risk: medium
tier: 3
---

# Test Plan: pdf-stage-detail-snapshot

AC ids per `change-classification.md` `## Inferred Acceptance Criteria`.

## Acceptance Criteria → Test Mapping
| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | integration | tests/test_job_manager_current_segment.py::test_pdf_job_populates_current_segment_stage_translate_end_to_end | 1 |
| AC-2 | unit | tests/test_pdf_stage_snapshot.py::test_pymupdf_path_on_segment_done_emits_translate_stage_snapshot | 0 |
| AC-3 | unit | tests/test_pdf_stage_snapshot.py::test_translate_pdf_signature_accepts_status_callback | 0 |
| AC-4 | unit | tests/test_pdf_stage_snapshot.py::test_pypdf2_and_to_pdf_paths_on_segment_done_emit_translate_stage_snapshot | 0 |
| AC-5 | integration | tests/test_job_manager_current_segment.py::test_pdf_job_populates_current_segment_stage_translate_end_to_end | 1 |
| AC-6 | contract (regression) | tests/test_jobstatus_stage_detail.py (existing suite), tests/test_translation_service_stage_snapshot.py::test_status_callback_emits_structured_snapshot_at_each_stage_transition, tests/test_job_manager_current_segment.py (existing AC-6/AC-8/AC-9 tests) | 1 |
| AC-7 | regression (output/perf unchanged) | tests/test_pdf_layout_table_fixes.py, tests/test_pdf_layout_viz_persistence.py, tests/test_pdf_render_warnings.py (existing, unmodified) | 1 |
| AC-8 | unit (RED→GREEN, ADR 0006) | tests/test_pdf_stage_snapshot.py::test_pymupdf_path_on_segment_done_emits_translate_stage_snapshot | 0 |

## Test Families Required
| family | tier | notes |
|---|---|---|
| unit | 0 | `translate_pdf` and its 3 sub-functions (`_translate_pdf_with_pymupdf`, `_translate_pdf_with_pypdf2`, `_translate_pdf_to_pdf`) thread `status_callback`; mock only `translate_blocks_batch` per branch, mirroring `tests/test_pdf_layout_viz_persistence.py`'s existing `patch.object(pdf_processor, "translate_blocks_batch", ...)` + fake-parser pattern — never mock `CurrentSegmentSnapshot` |
| integration | 1 | real `JobManager.create_job(...)` on a `.pdf` input, harness style of `tests/test_job_manager_current_segment.py`; orchestrator's `.pdf` branch and `translate_pdf` run for real, only `translate_blocks_batch`/LLM client mocked; asserts `job.current_segment.stage == "translate"` end-to-end (proves AC-1 + AC-5 together) |
| contract (regression) | 1 | existing `JobStatus` projection suite (`test_jobstatus_stage_detail.py`) and Office/judge snapshot suites stay green, unmodified — proves AC-6 |
| data-boundary | 0/1 | `current_segment` null → non-null transition specific to the PDF path (AC-1/AC-2); proven by the unit + integration rows above, not a separate test file |
| e2e / resilience / monkey / stress / soak | n/a | none — additive/observational backend wiring only, no UI or perf change (per change-classification.md) |

## Test Update Contract
| existing test | action | reason |
|---|---|---|
| tests/test_job_manager_current_segment.py | extend | add end-to-end `.pdf` job case proving `current_stage="translate"` populates via the same widened-callback path already proven for docx (AC-1, AC-5) |
| tests/test_pdf_stage_snapshot.py | new | unit coverage for `translate_pdf`'s new `status_callback` threading across all 3 PDF sub-paths (AC-2, AC-3, AC-4, AC-8) |
| tests/test_jobstatus_stage_detail.py, tests/test_translation_service_stage_snapshot.py, tests/test_pdf_layout_table_fixes.py, tests/test_pdf_layout_viz_persistence.py, tests/test_pdf_render_warnings.py | none | regression-only; must stay green unmodified (AC-6, AC-7) |

## Out of Scope
- Office (docx/pptx/xlsx) and judge snapshot logic — unchanged, regression-gated only.
- Real PDF rendering/output content or layout changes — none; existing PDF renderer suites are the regression proof.
- Performance/soak testing — additive callback only, no dedicated perf test (AC-7 is a no-observable-change claim, not a benchmark).
- Frontend/StageDetailPanel changes — already shipped in `translation-progress-detail-ui`.
- Orchestrator changes beyond passing the existing `status_callback` into the `.pdf` branch.

## Notes
- Anti-tautology: assert exact `stage`/`source`/`draft` VALUES per call, not mere non-null presence; with N segments assert N distinct, correctly-ordered snapshots (guards against one mutated/reused snapshot object making every captured call look like the LAST write).
- The `translate_blocks_batch` mock's side_effect MUST call `on_segment_done(src, translated)` itself — a mock that returns results without firing it would pass tautologically without exercising the wiring.
- Mock boundary: `translate_blocks_batch` (or its LLM client) only — never `CurrentSegmentSnapshot` construction or `job_manager` internals, per the `_run_job_with_process_files_side_effect` harness convention.
- AC-8 RED evidence (ADR 0006): run `test_pymupdf_path_on_segment_done_emits_translate_stage_snapshot` against pre-fix code first (fails — no `status_callback` param, or never invoked), then green post-fix; same node-id, no duplicate test.
- Env: generate evidence via `conda run -n translate-tool cdd-kit test run ...`, scoped to the exact node-ids above (never a `test_pdf_*` glob) — avoids the known onnxruntime import-ordering artifact and guarantees the torch-bearing interpreter.
