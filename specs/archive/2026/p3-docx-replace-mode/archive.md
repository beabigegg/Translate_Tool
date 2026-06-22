# Archive: p3-docx-replace-mode

## Change Summary

Added an `output_mode` parameter (`append` | `replace`) to `POST /api/jobs`. In **append** mode (the
default) translated text is inserted after the source paragraphs, preserving existing behaviour.
In **replace** mode the source paragraphs are overwritten in-place, keeping run-level formatting
(font, size) on the first run while zeroing surplus runs.  The parameter flows end-to-end: HTTP
Form field → `job_manager.create_job` → `orchestrator` → `translate_docx` / `translate_pptx`.
Multi-target jobs are clamped to `append` at the orchestrator layer (BR-67).

## Final Behavior

- `POST /api/jobs` accepts `output_mode=append` (default) or `output_mode=replace`; invalid values
  return HTTP 422.
- DOCX replace mode: translation overwrites source paragraph runs in-place; no source paragraph remains.
- PPTX replace mode: translation overwrites text-frame paragraphs and table cells in-place.
- Doc2Doc path (>40 K chars) falls back silently to append regardless of requested mode (R1 guard).
- PPTX SmartArt remains append-only (R2; SmartArt XML path is not iterated by the replace branch).
- Multi-target jobs always use append; replace is clamped at orchestrator level before dispatch.

## Final Contracts Updated

- `contracts/api/api-contract.md` — `output_mode` field added to `POST /api/jobs`; version bumped 0.6.0 → 0.7.0
- `contracts/api/openapi.yml` — regenerated to match; `openapi export --check` gate passes
- `contracts/business/business-rules.md` — BR-67 (multi-target clamp) and BR-68 (replace semantics) added

## Final Tests Added / Updated

- `tests/test_output_mode_processors.py` — 10 unit tests covering AC-1/2/3/4/7
- `tests/test_output_mode_api.py` — 4 contract tests covering AC-5 (HTTP accept/reject/default)
- `tests/test_output_mode_orchestrator.py` — 3 integration tests covering AC-6/7 (orchestrator threading + clamp)
- `tests/test_orchestrator_phase0.py` — extended `_fake_translate_docx` stub with `output_mode=None`

## Final CI/CD Gates

All gates Tier 1 (block merge):
- `cdd-kit validate --contracts`
- `cdd-kit openapi export --check`
- `cdd-kit gate p3-docx-replace-mode`
- `pytest tests/test_output_mode_processors.py` (unit)
- `pytest tests/test_output_mode_api.py` (contract)
- `pytest tests/test_output_mode_orchestrator.py` (integration)
- `pytest tests/ -x` (full suite)

## Production Reality Findings

Three pre-existing test failures were discovered during implementation and fixed in closing commits:

1. **Golden IR fixtures** (`multipage/simple/test.ir.json`) — stale snapshots from before the ONNX
   bug fix (b4374f8); updated and test assertion made robust to ONNX vs heuristic classification.
2. **`test_model_config_api.py` sys.modules contamination** — `routes_module` fixture used
   `sys.modules.pop` (untracked) and was missing `JOBS_DIR` in the fake module; fixed with
   `monkeypatch.delitem` + package-attribute restore + `OutputMode.APPEND` in direct calls.
3. **`test_providers_api.py` module identity** — `patch("app.backend.api.routes.X")` navigates via
   the parent-package attribute (`getattr(app.backend.api, "routes")`), which was not restored after
   `importlib.import_module` wrote M2 to it; fixed by restoring the attribute via `monkeypatch.setattr`
   and switching to `patch.object(_routes, "X")` in all affected test files.

## Lessons Promoted to Standards

- **promote-to-guidance** (CLAUDE.md learnings, folded into existing `mock.patch` entry):
  `patch("a.b.c.X")` resolves via parent-package attribute (`getattr(a.b, "c")`), not `sys.modules`.
  `importlib.import_module` writes to both; `monkeypatch.delitem` only restores `sys.modules`.
  Fix: also restore package attribute via `monkeypatch.setattr(pkg, "mod", original)` AND use
  `patch.object(module_ref_captured_at_collection, "X")`.
  Evidence: `tests/test_model_config_api.py`, `tests/test_providers_api.py`, `tests/test_output_mode_api.py`
  (all modified in this closing commit); CI green after fixes.

## Follow-up Work

- R2: PPTX SmartArt replace support (deferred; SmartArt XML iteration not in scope)
- Frontend: no UI control for `output_mode` is in scope for P3-9; a toggle widget is a future P3 item

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
