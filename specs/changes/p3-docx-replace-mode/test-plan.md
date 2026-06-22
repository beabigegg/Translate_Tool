---
change-id: p3-docx-replace-mode
schema-version: 0.1.0
last-changed: 2026-06-22
risk: medium
tier: 2
---

# Test Plan: p3-docx-replace-mode

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_output_mode_processors.py::test_translate_docx_accepts_output_mode_param | 0 |
| AC-1 | unit | tests/test_output_mode_processors.py::test_translate_pptx_accepts_output_mode_param | 0 |
| AC-1 | unit | tests/test_output_mode_processors.py::test_output_mode_default_is_append | 0 |
| AC-2 | unit | tests/test_output_mode_processors.py::test_append_mode_behavior_unchanged_docx | 0 |
| AC-2 | unit | tests/test_output_mode_processors.py::test_append_mode_behavior_unchanged_pptx | 0 |
| AC-3 | unit | tests/test_output_mode_processors.py::test_replace_mode_docx_no_source_paragraphs_remain | 0 |
| AC-3 | unit | tests/test_output_mode_processors.py::test_replace_mode_docx_translation_is_in_place | 0 |
| AC-4 | unit | tests/test_output_mode_processors.py::test_replace_mode_pptx_no_source_text_frames_remain | 0 |
| AC-4 | unit | tests/test_output_mode_processors.py::test_replace_mode_pptx_translation_is_in_place | 0 |
| AC-5 | contract | tests/test_output_mode_api.py::test_post_jobs_accepts_output_mode_append | 1 |
| AC-5 | contract | tests/test_output_mode_api.py::test_post_jobs_accepts_output_mode_replace | 1 |
| AC-5 | contract | tests/test_output_mode_api.py::test_post_jobs_rejects_invalid_output_mode_422 | 1 |
| AC-5 | contract | tests/test_output_mode_api.py::test_post_jobs_output_mode_defaults_to_append | 1 |
| AC-6 | integration | tests/test_output_mode_orchestrator.py::test_orchestrator_threads_output_mode_to_translate_docx | 1 |
| AC-6 | integration | tests/test_output_mode_orchestrator.py::test_orchestrator_threads_output_mode_to_translate_pptx | 1 |
| AC-7 | unit | tests/test_output_mode_processors.py::test_multi_target_output_mode_clamped_to_append | 0 |
| AC-7 | integration | tests/test_output_mode_orchestrator.py::test_orchestrator_clamps_replace_to_append_for_multi_target | 1 |
| AC-8 | contract | tests/test_env_contract.py | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Direct calls to `translate_docx` / `translate_pptx` with minimal real fixtures. Selection assertions on WHICH paragraphs/text-frames hold translation text, not just count. |
| contract | 1 | FastAPI TestClient for `POST /api/jobs`; mock at `job_manager` boundary only; do not mock Pydantic validation. Verify HTTP 422 on invalid `output_mode` values. |
| integration | 1 | Call `process_files()` directly (not `translate_document` wrapper). Patch at consumer-bound names `app.backend.processors.orchestrator.translate_docx` and `…translate_pptx`. Assert `call_args.kwargs["output_mode"]` value — selection, not count. |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_orchestrator_phase0.py | extend | Add `output_mode` kwarg assertions to existing `_run_process_files_with_hooks` helper if wiring assertions are reused. |

## Out of Scope

- PDF and XLSX processors (explicitly excluded in change-classification.md).
- Frontend UI control for `output_mode` (separate follow-up change).
- SmartArt replace-mode (PPTX SmartArt patch path is separate from text-frame path).
- E2E / browser-level tests (unit + integration are sufficient).
- Stress / soak / monkey / resilience tests (additive parameter; no load or fault path added).

## Notes

- AC-3/AC-4 selection assertion: open output file after processor call; assert source text absent AND translation present in-place.
- AC-6 anti-tautology: patch `translate_docx`/`translate_pptx` at orchestrator consumer module, not definition module (module-level import pattern per CLAUDE.md).
- AC-7 clamping tested at both layers so either enforcement location in the implementation satisfies the gate without special-casing.
- Minimal PPTX fixture must be added under `tests/fixtures/` if not already present; derive repo root via `Path(__file__).parent.parent` per CLAUDE.md, never hardcoded absolute paths.
