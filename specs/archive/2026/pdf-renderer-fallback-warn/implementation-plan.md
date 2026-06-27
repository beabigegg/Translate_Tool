---
change-id: pdf-renderer-fallback-warn
schema-version: 0.1.0
last-changed: 2026-06-27
---

# Implementation Plan: pdf-renderer-fallback-warn

## Objective

Expose silent PDF render-quality degradation on `GET /api/jobs/{id}` via a new
additive optional `warnings: list[str]` field. Populate it in two PDF processor
paths: (1) fitz→ReportLab fallback, (2) PDF→bilingual-DOCX routing. When no
degradation occurs the field is `None`/`[]` and existing API consumers are
unaffected. Regenerate the OpenAPI specs and add non-tautological tests. This is
purely additive — no existing field is modified or removed.

## Execution Scope

### In Scope
- `JobRecord` dataclass: add `warnings: Optional[List[str]] = None`.
- `JobStatus` Pydantic response model: add `warnings: Optional[List[str]] = None`.
- `routes.py` `job_status`: serialize `warnings=getattr(job, "warnings", None)`.
- Thread a `warnings_callback: Optional[Callable[[str], None]] = None` seam:
  job worker → `process_files` → `translate_pdf` → `_translate_pdf_to_pdf` →
  `_dispatch_render`, emitting the two exact strings at their sites.
- Job worker wires the callback to append-with-dedup onto `job.warnings`.
- Regenerate `contracts/api/openapi.yml` and `contracts/api/openapi.json`.
- Update `tests/test_jobstatus_download_url.py::_make_job` to set `job.warnings = None`.
- New test file `tests/test_pdf_render_warnings.py`.

### Out of Scope
- Fixing the fitz failure itself (request §Non-goals).
- Any frontend / UI display of warnings.
- Warnings for non-PDF formats (DOCX/PPTX/XLSX processors untouched).
- Redesigning the job model or render-dispatch architecture.
- Emitting a warning on the Windows COM **success** arm (test-plan §Out of Scope).
- Emitting a warning on the ReportLab-also-fails path — exception propagates to
  job failure; no warning (test-plan §Out of Scope).
- `apply_judge` re-translation path warning propagation (see Known Risks).

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | data model | Add `warnings: Optional[List[str]] = None` to `JobRecord` dataclass | backend-engineer |
| IP-2 | API schema | Add `warnings: Optional[List[str]] = None` to `JobStatus` Pydantic model | backend-engineer |
| IP-3 | API serialize | In `job_status` route, pass `warnings=getattr(job, "warnings", None)` into the `JobStatus(...)` constructor | backend-engineer |
| IP-4 | processor seam | Add `warnings_callback` param to `process_files`, `translate_pdf`, `_translate_pdf_to_pdf`, `_dispatch_render`; forward it down the chain | backend-engineer |
| IP-5 | fitz-fallback emit | In `_dispatch_render` `except` block, emit the AC-1 string via `warnings_callback` (alongside existing `logger.warning`) | backend-engineer |
| IP-6 | docx-routing emit | In `translate_pdf`, after the COM block and before parser dispatch (DOCX route only), emit the AC-2 string via `warnings_callback` | backend-engineer |
| IP-7 | job wiring | In `create_job` worker, pass `warnings_callback` to `process_files` that append-dedups onto `job.warnings` | backend-engineer |
| IP-8 | contracts | Regenerate `openapi.yml` + `openapi.json` from already-updated `api-contract.md` | backend-engineer |
| IP-9 | tests | Write `tests/test_pdf_render_warnings.py`; update `_make_job` helper | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | AC-1..AC-6 (§Inferred Acceptance Criteria) | exact warning strings + behavior |
| test-plan.md | §Acceptance Criteria → Test Mapping; §Notes (em-dash, AC-6 mock target) | test names, mock targets, non-tautology guards |
| test-plan.md | §Test Update Contract | `_make_job` helper update |
| ci-gates.md | §Required Gates table; §Pre-commit prerequisite | verification commands |
| contracts/api/api-contract.md | line 158 (`warnings` row, already present) | regeneration source for openapi |
| contracts/data/data-shape-contract.md | §"JobStatus / JobRecord — warnings field" (lines 38-41, already present) | field type/semantics (string[] or null, never bare string) |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| app/backend/services/job_manager.py | edit | `JobRecord` dataclass (lines 80-109): add `warnings: Optional[List[str]] = None` after line 109. `List`/`Optional` already imported (line 14). In `create_job` worker, at the `process_files(...)` call (~lines 348-372, parallel to existing `status_callback=`), add `warnings_callback=lambda w: _record_job_warning(job, w)`. Add module-level helper `_record_job_warning(job, message)` that inits `job.warnings` to `[]` when `None` and appends only if not already present (dedup). |
| app/backend/api/schemas.py | edit | `JobStatus` (lines 20-44): add `warnings: Optional[List[str]] = None` after line 44. `List`/`Optional` already imported (line 6). |
| app/backend/api/routes.py | edit | `JobStatus(...)` construction in `job_status` (lines 318-343): add `warnings=getattr(job, "warnings", None),` after line 342. |
| app/backend/processors/pdf_processor.py | edit | (a) `translate_pdf` (signature 61-77): add `warnings_callback: Optional[Callable[[str], None]] = None`. Forward it into the `_translate_pdf_to_pdf(...)` call (lines 110-125). Emit AC-2 string **between line 152 and 154** (after the COM block, before `# Determine which parser to use`) — this point is only reached on the DOCX route (pdf output returns at 111; COM success returns at 150), satisfying the COM-success exclusion. (b) `_translate_pdf_to_pdf` (signature 566-): add `warnings_callback` param and forward to `_dispatch_render`. (c) `_dispatch_render` (803-850): add `warnings_callback` param; in the `except Exception` block (836-850), after the existing `logger.warning`, emit the AC-1 string via `warnings_callback` if not None, then proceed to ReportLab fallback. `Callable`/`Optional` already imported (line 14). |
| app/backend/processors/orchestrator.py | edit | `process_files` signature (340-364): add `warnings_callback: Optional[Callable[[Optional[str]], None]] = None` (parallel to `status_callback` line 363). Forward `warnings_callback=warnings_callback` into the `translate_pdf(...)` call (lines 776-790). `Callable`/`Optional` already imported. |
| contracts/api/openapi.yml | regenerate | Run `cdd-kit openapi export --out contracts/api/openapi.yml`; JobStatus currently lacks `warnings` (stale vs api-contract.md line 158). |
| contracts/api/openapi.json | regenerate | Regenerate alongside openapi.yml (whichever export command/target produces it; keep in sync). |
| tests/test_jobstatus_download_url.py | edit | In `_make_job` (lines 22-52) add `job.warnings = None` so the MagicMock JobRecord is structurally complete when `routes.py` reads `getattr(job, "warnings", None)` (test-plan §Test Update Contract). |
| tests/test_pdf_render_warnings.py | create | New file per test-plan.md §Acceptance Criteria → Test Mapping. See Test Execution Plan below. |

### Exact warning strings (byte-for-byte — em-dash `—`, NOT ASCII hyphen)

- AC-1 (fitz fallback):
  `PDF rendering quality reduced: fell back to basic renderer — images and formatting may be lost`
- AC-2 (DOCX routing):
  `Layout preservation skipped: PDF was converted to bilingual DOCX mode — use output_format=pdf for layout-faithful output`

Define these as module-level constants in `pdf_processor.py` (e.g.
`FITZ_FALLBACK_WARNING`, `DOCX_ROUTING_WARNING`) so tests import and assert with
`==` against the same source-of-truth literal.

## Execution Steps (ordered)

1. IP-1: add `warnings` to `JobRecord` and the `_record_job_warning` helper.
2. IP-2: add `warnings` to `JobStatus`.
3. IP-3: serialize `warnings` in the `job_status` route.
4. IP-4/IP-5/IP-6: add the `warnings_callback` param through pdf_processor +
   orchestrator and emit the two constants at their sites.
5. IP-7: wire `warnings_callback` from the `create_job` worker.
6. IP-9: update `_make_job`; write `tests/test_pdf_render_warnings.py`.
7. IP-8: `cdd-kit openapi export --out contracts/api/openapi.yml` (and the json
   target), then `cdd-kit validate --contracts`.
8. Run the test ladder (below).

## Contract Updates

- API: `contracts/api/api-contract.md` already documents `warnings` (line 158). Do
  not re-edit prose; only regenerate `openapi.yml`/`openapi.json`.
- CSS/UI: none.
- Env: none.
- Data shape: `contracts/data/data-shape-contract.md` already documents
  `JobRecord.warnings` (lines 38-41). No further edit unless validation flags drift.
- Business logic: none.
- CI/CD: none (existing `openapi-sync` + `contract-validation` gates cover it).

## Test Execution Plan

Required phases (floor): `collect`, `targeted`, `changed-area`. Generate
evidence with `cdd-kit test run`; the gate validates `test-evidence.yml`. Full
ladder/policy lives in test-plan.md and references/sdd-tdd-policy.md.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_pdf_render_warnings.py::TestFitzFallbackWarning::test_fitz_exception_emits_exact_fallback_warning | patch `app.backend.processors.pdf_processor._run_fitz_render` to raise; patch `_run_reportlab_render` to no-op; call `_dispatch_render` directly with a capturing `warnings_callback`; assert captured `== FITZ_FALLBACK_WARNING` |
| AC-1 | tests/test_pdf_render_warnings.py::TestWarningsApiPropagation::test_fitz_fallback_warning_in_api_response | mock `app.backend.api.routes.job_manager`; job with `warnings=[FITZ_FALLBACK_WARNING]`; `GET /api/jobs/{id}` JSON `warnings` contains the string |
| AC-2 | tests/test_pdf_render_warnings.py::TestDocxRoutingWarning::test_docx_routing_emits_exact_layout_skip_warning | force DOCX route (`output_format="docx"`), patch `is_win32com_available`→False and `_translate_pdf_with_pymupdf`→no-op; call `translate_pdf` with capturing `warnings_callback`; assert captured `== DOCX_ROUTING_WARNING` |
| AC-2 | tests/test_pdf_render_warnings.py::TestWarningsApiPropagation::test_docx_routing_warning_in_api_response | mocked job with `warnings=[DOCX_ROUTING_WARNING]`; API JSON includes it |
| AC-3 | tests/test_pdf_render_warnings.py::TestNoDegradationNoWarning::test_no_warning_when_fitz_succeeds | `_run_fitz_render` succeeds (no raise); `warnings_callback` never invoked |
| AC-3 | tests/test_pdf_render_warnings.py::TestWarningsApiPropagation::test_no_warnings_is_null_or_empty_in_api_response | job with `warnings=None`; API JSON `warnings` is null/absent |
| AC-4 | tests/test_pdf_render_warnings.py::TestWarningsSchema::test_warnings_field_is_list_or_none_not_bare_string | `JobStatus(warnings="x")` rejected by pydantic; `JobStatus(warnings=["x"])` and `warnings=None` accepted |
| AC-5 | tests/test_pdf_render_warnings.py::TestWarningsSchema::test_jobstatus_schema_has_warnings_field | `JobStatus` model fields include `warnings` |
| AC-6 | tests/test_pdf_render_warnings.py::TestFitzFallbackWarning::test_fitz_mock_targets_consumer_call_site_not_renderer_module | patch is on `pdf_processor._run_fitz_render` (consumer binding) and entry is `_dispatch_render`, not `translate_pdf`/renderer module |

Ladder commands (ci-gates.md §Pre-commit prerequisite):

```bash
cdd-kit openapi export --out contracts/api/openapi.yml
pytest tests/test_pdf_render_warnings.py -x -q       # targeted (Tier 0/1)
cdd-kit validate --contracts                          # contract gate
pytest tests/ -x -q --tb=short                        # changed-area / full safety net
```

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Warning strings must match byte-for-byte including the em-dash `—`; emit each
  via the module-level constant and assert with `==` (not `in` for the constant).
- `warnings` is `None`/`[]` when no degradation; never a bare string.
- Mock fitz failure at the **consumer** binding `pdf_processor._run_fitz_render`
  and enter via `_dispatch_render`, not `translate_pdf` (AC-6 / test-plan §Notes;
  CLAUDE.md tautology pattern 1b).
- Do not warn on the COM-success arm or the ReportLab-also-fails arm.

## Known Risks

- Propagation depth: the `warnings_callback` threads through 4 functions
  (`process_files` → `translate_pdf` → `_translate_pdf_to_pdf` → `_dispatch_render`).
  Verify each forwards the param (orphaned/un-forwarded callback = silent no-warn).
  Confirm by running the AC-1/AC-2 propagation tests, not just unit emit tests.
- `_make_job` uses `MagicMock`; without `job.warnings = None`, `getattr` returns a
  truthy auto-attr Mock and serialization may fail or emit a Mock. The helper
  update (IP-9) is mandatory, not optional.
- `apply_judge` (job_manager.py ~589) re-invokes `process_files` without a
  `warnings_callback`; degradation during judge re-translation will not surface.
  Out of scope for this change; if later required, wire the same callback there.
- `pypdf2` DOCX fallback arm (`_translate_pdf_with_pypdf2`) is reached only on
  pymupdf failure and is not an emit site here; the AC-2 emit in `translate_pdf`
  fires before that fallback, and `_record_job_warning` dedups, so no double-warn.
- `.cdd/code-map.yml` line ranges were used to scope reads; if the file is edited
  before backend-engineer starts, re-confirm the cited line numbers (they are
  anchors, not guarantees).
