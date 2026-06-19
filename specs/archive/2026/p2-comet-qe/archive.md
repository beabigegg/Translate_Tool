# Archive — p2-comet-qe

## Change Summary

Added COMET/xCOMET neural translation quality evaluation to the pipeline. After translation completes for a job, a reference-free COMET model scores each translated block pair (source, hypothesis). Scores are accumulated across all format processors via a new `post_translate_hook` observer callback wired through the orchestrator and all five format processors (PDF-IR, PDF-PyPDF2-fallback, DOCX, PPTX, XLSX), then stored in a per-job `JobQualityRecord` and exposed via a new REST endpoint `GET /jobs/{id}/quality`. The feature defaults to disabled (`QE_ENABLED=false`) and degrades safely on any model error.

## Final Behavior

- `GET /jobs/{job_id}/quality` → `{job_id, status, scores[]}` where status ∈ {available, pending, unavailable, disabled}
- `post_translate_hook` observer threads through `process_files()` → all 5 processors; each emits `(block_id, src, mt)` tuples after building their translation maps
- PDF-IR path: `block_id = element_id` (stable); non-IR (DOCX/PPTX/XLSX) and PDF-PyPDF2-fallback: `block_id = "{ext}:{file_stem}:{index}"` (run-stable, not durable across re-submissions; BR-58)
- QE runs synchronously in the job worker thread after all file groups complete; any exception sets `qe_status="unavailable"` — job proceeds (BR-56)
- Model is lazy-imported (only when `QE_ENABLED=true`) and process-cached per `(model_name, device)` key (BR-57)
- `QE_ENABLED=false` (default): endpoint returns `status=disabled`; `load_model` is never called

## Final Contracts Updated

- `contracts/api/api-contract.md` → v0.5.0: `BlockQualityScore`, `JobQualityResponse` schemas; `GET /jobs/{job_id}/quality` endpoint
- `contracts/api/api-inventory.md` → v0.2.0: new row for quality endpoint
- `contracts/api/openapi.yml` + `contracts/api/openapi.json`: regenerated to include new endpoint
- `contracts/data/data-shape-contract.md` → v0.7.0: QE Score Representation section; block_id semantics (IR vs non-IR)
- `contracts/env/env-contract.md` → v0.6.0: `QE_ENABLED`, `QE_MODEL_NAME`, `QE_DEVICE`; CC-BY-NC-SA license warning for default model
- `contracts/business/business-rules.md` → v0.11.0: BR-54 (per-element scores), BR-55 (reference-free input shape), BR-56 (safe degradation), BR-57 (lazy load), BR-58 (best-effort block_id for non-IR); Table P added
- `contracts/env/.env.example.template`, `contracts/env/env.schema.json`: updated for 3 new QE vars
- `contracts/CHANGELOG.md`: updated

## Final Tests Added / Updated

- `tests/test_quality_evaluation.py` (new, 14 tests): AC-1 score count, AC-2 endpoint 200/available, AC-3 status variants + 404, AC-7 disabled/unavailable/invalid-device paths, AC-8 model name + zero-element
- `tests/test_translation_strategy.py` (extended): `test_qe_hook_called_after_translation` — anti-tautology real XLSX processor emission + `hook_calls` assertion
- `tests/test_env_contract.py` (extended): 3 contract rows for QE env vars
- `tests/contract/response-samples.json` + `tests/contract/samples/job_quality_available.json` (new): ADR-0007 response-shape validation sample for quality endpoint

## Final CI/CD Gates

| gate | trigger |
|---|---|
| contract-validate | pre-commit / PR |
| change-gate (`cdd-kit gate p2-comet-qe`) | pre-commit / PR |
| openapi-sync | PR |
| unit-tests (`pytest tests/`) | PR |
| layout-detector-dependency-gate | PR |

## Production Reality Findings

QA round found 4 fixable findings (F-1 through F-4) — all resolved before gate:

- **F-1**: `tests/contract/response-samples.json` missing; `contracts/api/openapi.json` (JSON format) missing — response-shape validator needs both. Fixed: created both files.
- **F-2**: `test_qe_hook_called_after_translation` was tautological (called `translate_document()` which doesn't fire the hook). Fixed: replaced with real XLSX processor call + `hook_calls` assertion.
- **F-3**: `test_score_block_id_matches_element_id` hardcoded `qe_blocks` literals rather than running the real processor emission path. Fixed: replaced with actual `translate_xlsx_xls` call via tmp file.
- **F-4**: Two AC-7 tests reimplemented the if-logic / WARNING string inline. Fixed: route-level call with `mock_load.call_count == 0`; device-fallback test uses real `load_model` with `sys.modules` patch.
- **CI-only failure**: `jsonschema` installed locally but not added to `requirements.txt`; `cdd-kit validate --contracts` response-shape step failed on CI. Fixed: added `jsonschema>=4.0.0` to requirements.txt.

## Lessons Promoted to Standards

**A — jsonschema CI validator dependency (promote-to-contract)**
- Target: `contracts/ci/ci-gate-contract.md` § Validator Dependencies (new section, v0.4.3)
- Rule: `jsonschema>=4.0.0` must remain in `app/backend/requirements.txt` as long as `tests/contract/response-samples.json` exists; otherwise `cdd-kit validate --contracts` response-shape step fails on CI (passes locally if package is ad-hoc installed)
- Evidence: CI run 27813432588 fail → fix commit 4d9e539

**B — wrong-entry-point hook tautology (promote-to-guidance)**
- Target: `CLAUDE.md` managed region, existing tautological-tests line — extended in-place to add form (1b): "wrong entry point — calling a higher-level wrapper that doesn't reach the target hook/seam trivially passes"
- Evidence: QA finding F-2; corrected test `tests/test_translation_strategy.py::test_qe_hook_called_after_translation`

## Follow-up Work

- **BR-59 / Doc2Doc wiring** (p2-long-doc-chunking left-over): `translate_document()` is still unwired from all format processors. When wired, the `post_translate_hook` plumbing is already present; callers need only pass the hook through.
- **CC-BY-NC-SA legal review**: Default model `wmt22-cometkiwi-da` is non-commercial. Legal review required before `QE_ENABLED=true` in any commercial deployment. See `contracts/env/env-contract.md §QE_MODEL_NAME`.
- **Durable block_id** (non-IR formats): BR-58 documents run-stable-only semantics. Future work could persist element-level IDs for DOCX/PPTX/XLSX to make scores durable across re-submissions.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
