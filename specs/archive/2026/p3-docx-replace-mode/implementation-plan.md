---
change-id: p3-docx-replace-mode
schema-version: 0.1.0
last-changed: 2026-06-22
---

# Implementation Plan: p3-docx-replace-mode

## Objective
Add an `output_mode` parameter (`"append" | "replace"`, default `"append"`) to DOCX/PPTX
translation, threaded API → orchestrator → processor. `replace` overwrites source paragraphs
(DOCX) / text frames (PPTX) in-place; `append` is unchanged (backward compatible). Multi-target
jobs clamp to `"append"` in the orchestrator. Per BR-66, BR-67, Table S.

## Execution Scope

### In Scope
- `translate_docx` / `translate_pptx`: new `output_mode` param; replace path overwrites in-place.
- `_insert_docx_translations` (docx) + the inline append path in `translate_pptx`: branch on mode.
- Orchestrator `process_files`: accept `output_mode`, clamp to `"append"` when `len(targets) > 1`,
  pass to processor calls.
- API `POST /api/jobs` (`create_job`): accept `output_mode` as a Form field typed by the new
  `OutputMode(str, Enum)` so FastAPI rejects invalid values with HTTP 422.
- `job_manager.create_job`: thread `output_mode` from endpoint into `process_files`.
- New `OutputMode(str, Enum)` in schemas.py (`APPEND="append"`, `REPLACE="replace"`).

### Out of Scope
- PDF / XLSX behavior change — MUST accept `output_mode` as a no-op only (BR-66; Table S row).
- Frontend UI control for `output_mode` (separate follow-up change).
- PPTX SmartArt replace (`_update_smartart_texts`) — append retained; mark TODO.
- DOCX doc2doc long-doc path (`_translate_docx_via_doc2doc`, single-target >40K chars): replace NOT
  implemented this iteration — thread the kwarg, add a comment marking replace as follow-up; append
  remains the only behavior on that branch (Known Risk R1).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | schemas.py | Add `class OutputMode(str, Enum)` before any reference | backend-engineer |
| IP-2 | docx_processor.py | Add `output_mode="append"` to `translate_docx`; branch `_insert_docx_translations` to overwrite source paragraphs/cells in-place on replace | backend-engineer |
| IP-3 | pptx_processor.py | Add `output_mode="append"` to `translate_pptx`; overwrite text-frame/cell text in-place on replace instead of `_ppt_append`/`_cell_append` | backend-engineer |
| IP-4 | orchestrator.py | Add `output_mode="append"` to `process_files`; clamp to `"append"` when `len(targets) > 1`; pass to both processor calls alongside existing `terms_getter=` | backend-engineer |
| IP-5 | job_manager.py | Add `output_mode` to `create_job`; pass into `process_files(...)` call | backend-engineer |
| IP-6 | routes.py | Add `output_mode: OutputMode = Form(OutputMode.APPEND)` to `create_job`; forward to `job_manager.create_job` | backend-engineer |
| IP-7 | tests/ | New test files per test-plan.md + extend test_orchestrator_phase0.py stubs | test-strategist / backend-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | AC-1..AC-8; Tier 2; Required Tests | scope + acceptance |
| test-plan.md | AC→Test Mapping table; Test Families; Test Update Contract | tests to write/run |
| ci-gates.md | Required Gates table; Promotion Policy | verification commands |
| contracts/api/api-contract.md | 0.7.0; POST /jobs row; JobCreateRequest `output_mode` row | API contract (done) |
| contracts/business/business-rules.md | 0.16.0; BR-66, BR-67; Table S | replace/append + clamp rules |
| CLAUDE.md | tautological-test + mock.patch binding learnings | test correctness constraints |

## File-Level Plan
| path | action | notes |
|---|---|---|
| app/backend/api/schemas.py | edit | Define `OutputMode(str, Enum)` near top (`from enum import Enum`). |
| app/backend/api/routes.py:140 `create_job` | edit | New `output_mode: OutputMode = Form(OutputMode.APPEND)`; forward to `job_manager.create_job`. NOTE: endpoint uses `Form(...)`, NOT a JSON `JobCreate` body — invalid enum → FastAPI 422 (Table S 422 row). |
| app/backend/services/job_manager.py:247 `create_job` + :324 `process_files(...)` | edit | Add `output_mode: str = "append"` param; pass `output_mode=output_mode` into `process_files`. |
| app/backend/processors/orchestrator.py:339 `process_files` | edit | Add `output_mode: str = "append"`; compute `effective = "append" if len(targets) > 1 else output_mode` (BR-67); pass `output_mode=effective` to all 3 `translate_docx`/`translate_pptx` calls (~677, ~708, ~728) alongside `terms_getter=`. Do not remove/reorder kwargs. |
| app/backend/processors/docx_processor.py:535 `translate_docx` + :291 `_insert_docx_translations` | edit | Add `output_mode: str = "append"`; pass into `_insert_docx_translations`; on `"replace"` overwrite source paragraph/cell text in-place (no `_append_after`). Thread kwarg into `_translate_docx_via_doc2doc` call (:580) but mark replace as follow-up (R1). |
| app/backend/processors/pptx_processor.py:182 `translate_pptx` | edit | Add `output_mode: str = "append"`; on `"replace"` set text-frame/cell text in-place instead of `_ppt_append`/`_cell_append`; SmartArt stays append (TODO comment). |
| tests/test_output_mode_processors.py | create | AC-1..AC-4, AC-7 unit. Selection assertions (WHICH paras hold translation). |
| tests/test_output_mode_api.py | create | AC-5 contract via TestClient; assert HTTP 422 invalid; mock at job_manager boundary only. |
| tests/test_output_mode_orchestrator.py | create | AC-6, AC-7 integration. Call `process_files()` directly; patch consumer-bound names. |
| tests/test_orchestrator_phase0.py | edit | Extend `_fake_translate_docx` (+ any pptx stub) to accept `output_mode=None`. |
| tests/fixtures/ | create if absent | Minimal PPTX fixture; repo root via `Path(__file__).parent.parent`. |

## Contract Updates
- API: DONE — `contracts/api/api-contract.md` 0.7.0 (`JobCreateRequest.output_mode` row; POST /jobs).
  After any further edit: `cdd-kit openapi export --out contracts/api/openapi.yml` (openapi-sync gate).
- CSS/UI: none.
- Env: none.
- Data shape: none (runtime param, not persisted IR).
- Business logic: DONE — `business-rules.md` 0.16.0 (BR-66, BR-67, Table S).
- CI/CD: gate step per ci-gates.md (`cdd-kit gate p3-docx-replace-mode` in contract-and-fast-tests).

## Test Execution Plan
Run via `cdd-kit test run` ladder. Minimum phases for this Tier 2 change: `collect`, `targeted`,
`changed-area`, plus `contract` (api-contract + openapi conformance touched) and `full` (regression).

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1, AC-2 | tests/test_output_mode_processors.py | default append; param accepted; append unchanged |
| AC-3 | tests/test_output_mode_processors.py | DOCX replace: no source paragraph remains (selection) |
| AC-4 | tests/test_output_mode_processors.py | PPTX replace: no source text frame remains (selection) |
| AC-5 | tests/test_output_mode_api.py | POST /jobs accepts append/replace; invalid → HTTP 422 |
| AC-6 | tests/test_output_mode_orchestrator.py | `call_args.kwargs["output_mode"]` reaches processor |
| AC-7 | tests/test_output_mode_processors.py, tests/test_output_mode_orchestrator.py | multi-target clamped to append |
| AC-8 | `cdd-kit validate --contracts`; `cdd-kit openapi export --check` | exit 0 |

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- `POST /api/jobs` body is multipart `Form(...)`, not a JSON `JobCreate` Pydantic model — add
  `output_mode` as a Form field typed `OutputMode`; do not introduce a JSON request body.
- Orchestrator call sites: add `output_mode=` ALONGSIDE the existing
  `terms_getter=lambda: list(_glossary_terms_holder)` kwarg; do not remove or reorder existing kwargs.
- Orchestrator wiring tests must patch `app.backend.processors.orchestrator.translate_docx` /
  `…translate_pptx` (module-level consumer binding) and call `process_files()` directly, not
  `translate_document` (CLAUDE.md tautological-test + mock-binding learnings).
- New/updated stubs must accept `terms_getter=None` and `output_mode=None` kwargs.
- Do not re-copy full design/test/CI/contract prose; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks
- R1: DOCX doc2doc long-doc path (single-target >40K chars) does not implement replace this
  iteration — kwarg threaded, append-only, code comment marks follow-up. AC-3 fixtures must stay
  under 40K chars so they exercise the standard `_insert_docx_translations` path.
- R2: PPTX SmartArt path remains append-only (out of scope per test-plan.md); document with TODO.
- R3: In-place replace must preserve paragraph/run formatting (font, size). Overwrite run text,
  do not delete runs, to avoid losing styling — verify in AC-3/AC-4 selection assertions.
- R4: openapi.yml must be re-exported if api-contract.md changes again, else openapi-sync fails.
