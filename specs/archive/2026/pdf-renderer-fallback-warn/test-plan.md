---
change-id: pdf-renderer-fallback-warn
schema-version: 0.1.0
last-changed: 2026-06-27
risk: medium
tier: 3
---

# Test Plan: pdf-renderer-fallback-warn

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_pdf_render_warnings.py::TestFitzFallbackWarning::test_fitz_exception_emits_exact_fallback_warning | 0 |
| AC-1 | contract | tests/test_pdf_render_warnings.py::TestWarningsApiPropagation::test_fitz_fallback_warning_in_api_response | 1 |
| AC-2 | unit | tests/test_pdf_render_warnings.py::TestDocxRoutingWarning::test_docx_routing_emits_exact_layout_skip_warning | 0 |
| AC-2 | contract | tests/test_pdf_render_warnings.py::TestWarningsApiPropagation::test_docx_routing_warning_in_api_response | 1 |
| AC-3 | unit | tests/test_pdf_render_warnings.py::TestNoDegradationNoWarning::test_no_warning_when_fitz_succeeds | 0 |
| AC-3 | contract | tests/test_pdf_render_warnings.py::TestWarningsApiPropagation::test_no_warnings_is_null_or_empty_in_api_response | 1 |
| AC-4 | data-boundary | tests/test_pdf_render_warnings.py::TestWarningsSchema::test_warnings_field_is_list_or_none_not_bare_string | 0 |
| AC-5 | data-boundary | tests/test_pdf_render_warnings.py::TestWarningsSchema::test_jobstatus_schema_has_warnings_field | 0 |
| AC-6 | unit | tests/test_pdf_render_warnings.py::TestFitzFallbackWarning::test_fitz_mock_targets_consumer_call_site_not_renderer_module | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | `_dispatch_render` fitz-fallback path and bilingual-DOCX routing path. Mock at `app.backend.processors.pdf_processor._run_fitz_render` (consumer binding); call `_dispatch_render` directly — not `translate_pdf` — to avoid wrong-entry-point tautology (CLAUDE.md pattern 1b). |
| data-boundary | 0 | `JobStatus` Pydantic schema: `warnings` accepts `Optional[List[str]]`, rejects bare `str`. `JobRecord` dataclass: `warnings` field exists and defaults to `None` or `[]`. |
| contract | 1 | Mock `app.backend.api.routes.job_manager` (consumer binding, same pattern as `test_jobstatus_download_url.py::_make_job`). `GET /api/jobs/{id}` JSON: `warnings` is list when set, null/absent when not set. |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_jobstatus_download_url.py::_make_job helper | update | add `warnings` attribute so the mock JobRecord is structurally complete when routes.py reads it |

## Out of Scope
- Frontend display of warnings (no UI change)
- E2E tests against real PDF files (no live binary needed to prove the warning seam)
- `openapi.yml` regeneration verified by existing CI `openapi export --check` gate; no additional pytest needed
- ReportLab-also-fails path (exception propagates to job failure; no warning emitted)
- Windows COM conversion routing arm (not a warning source in this change)

## Notes
- Exact warning strings contain em-dash `—` (not ASCII hyphen); assert with `==` not `in`.
- AC-6: fitz-fallback unit test must patch `app.backend.processors.pdf_processor._run_fitz_render` and call `_dispatch_render` directly; patching the renderer module or calling `translate_pdf` is a tautology.
- All new tests go in `tests/test_pdf_render_warnings.py` (new file); do not add to `test_pdf_parser.py` or `test_pdf_generator.py`.
