---
change-id: support-legacy-office-formats
schema-version: 0.1.0
last-changed: 2026-07-06
---

# Implementation Plan: support-legacy-office-formats

## Objective
Add full `.ppt` upload support by converting it to `.pptx` via LibreOffice-headless before the existing pipeline, mirroring the shipped `.doc`/`.xls` conversion paths; backfill the currently-untested `.doc`/`.xls`/`.ppt` conversion helpers and orchestrator branches with TDD coverage; wire the BR-96 lossy-conversion disclosure into `job.warnings`; and open `.doc`/`.xls`/`.ppt` on the frontend upload whitelist. No native binary parser, no new API field. See design.md § Summary/Key Decisions.

## Execution Scope

### In Scope
- `app/backend/processors/libreoffice_helpers.py`: new `ppt_to_pptx(input_path: str, output_path: str) -> None`.
- `app/backend/config.py:245`: add `.ppt` to `SUPPORTED_EXTENSIONS`.
- `app/backend/processors/orchestrator.py`: `.ppt` Phase-0 extraction branch; `.ppt` main-conversion branch; `.ppt` output-name mapping; BR-96 warnings disclosure for `.doc`/`.xls`/`.ppt`.
- `tests/test_libreoffice_helpers.py` (new) + `tests/test_orchestrator_phase0.py` (extended) per test-plan.md node IDs, TDD failing-first.
- `app/frontend/src/constants/fileTypes.js`: add `.doc`/`.xls`/`.ppt` (and matching MIME types) to the upload whitelist.

### Out of Scope
- Native `.doc`/`.xls`/`.ppt` binary parser (design.md Non-goals).
- `.ppt` COM (`win32com`/`powerpoint_convert`) fallback parity — LibreOffice + graceful-skip is the minimum bar (design.md Open Risks; test-plan.md Out of Scope).
- Any new API/job field — reuse `warnings[]` only (design.md Decision 1; api-contract L158).
- QE threshold / reinterpretation for converted docs — QE path unchanged (design.md Decision 2; BR-96; ADR-0009).
- `app/backend/environment.yml` / README edits — NOT backend-engineer's job; LibreOffice is an OS binary documented only in env-contract by contract-reviewer. Do NOT add a conda/pip entry.
- `contracts/*`, `openapi.yml`, `.github/workflows/*` — already finalized by contract-reviewer / ci-cd-gatekeeper.
- `FileDropZone.jsx` code (renders `ACCEPTED_EXTENSIONS.join(', ')` and uses it for `accept` + filename filter; constant change is sufficient — verify, do not edit).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | backend/helpers | Add `ppt_to_pptx(input_path, output_path) -> None` mirroring `xls_to_xlsx()` exactly: `tempfile.mkdtemp(prefix="lo_ppt_")`, `_libreoffice_convert(input_path, "pptx", tmp_dir)`, `shutil.move(converted, output_path)`, cleanup in `finally`. | backend-engineer |
| IP-2 | backend/config | Add `.ppt` to `SUPPORTED_EXTENSIONS` set (config.py:245). | backend-engineer |
| IP-3 | backend/orchestrator Phase-0 | Add `.ppt` branch mirroring `.doc` (L271-285): if `is_libreoffice_available()` → temp `.pptx`, `ppt_to_pptx()`, extract via `pptx.Presentation` (same shape-text walk as the `.pptx` branch L226-237), cleanup temp; else filename-stem fallback. | backend-engineer |
| IP-4 | backend/orchestrator main | Add `.ppt` branch beside `.pptx` (insert between L765 and L766) mirroring `.doc` main branch (L727-765) minus COM: temp `.pptx` in `output_dir`, `if is_libreoffice_available(): ppt_to_pptx(...)` else log actionable install message + `continue` (mirror L735-742, no `win32com` elif), then `translate_pptx(tmp_pptx, ...)` with the same kwargs as the existing `.pptx` call (L767-782), temp cleanup in `finally`. | backend-engineer |
| IP-5 | backend/orchestrator naming | Add `.ppt` to `_output_name` (L334): return `.pptx` for `.ppt`. Without this `.ppt` falls through to L336 and emits a `.ppt` output name. (Gap not covered by design.md — see Known Risks.) | backend-engineer |
| IP-6 | backend/orchestrator warnings | Wire BR-96 disclosure via the existing `warnings_callback` seam: emit exactly one entry per successfully converted legacy file (see IP-6 exact wiring below). | backend-engineer |
| IP-7 | backend/tests | Author failing-first tests per test-plan.md node IDs (see Test Execution Plan). | backend-engineer |
| IP-8 | frontend/whitelist | Add `.doc`/`.xls`/`.ppt` to `ACCEPTED_EXTENSIONS` and their MIME types to `ACCEPTED_MIME_TYPES` in fileTypes.js. Confirm FileDropZone.jsx needs no code change. | frontend-engineer |

### IP-6 exact wiring
Insert, inside the per-file `try` block after the format-dispatch if/elif chain sets `stopped` and **before** `processed_count += 1` (currently L821):

```python
if ext in (".doc", ".xls", ".ppt") and is_libreoffice_available():
    if warnings_callback:
        warnings_callback(
            f"{src.name} converted from a legacy format via LibreOffice; "
            f"layout fidelity may be lower than a native format."
        )
```

Rationale (do not deviate): on the post-dispatch success path this fires only when conversion + translation succeeded — a conversion that raised jumps to the `except` at L826 and emits nothing; the `.doc`-branch "no converter available" case `continue`s at L742 and never reaches here. This is a single wiring point covering all three formats (the `.xls` conversion is encapsulated inside `translate_xlsx_xls`, so orchestrator cannot emit at the `.xls` conversion site). The string matches BR-96's canonical example (business-rules.md BR-96) and the api-contract L158 `warnings[]` note. Seam template: the output_mode-degrade calls at L695-706 and the `warnings_callback=warnings_callback` pass-through to `translate_pdf` at L816.

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | § Affected Components, § Key Decisions (Decision 1 warnings, Decision 2 QE), § Open Risks (no `.ppt` COM) | constraints on `.ppt` wiring, disclosure mechanism, non-goals |
| business-rules.md | BR-9, BR-96, Table X (L406-413) | exact disclosure semantics + string; skip/no-crash/QE-unchanged behavior |
| api-contract.md | `warnings` field note (L158); upload `file` param (L310) | disclosure is additive to `warnings[]`; accepted-types already updated |
| env-contract.md | § External Binary Dependencies | confirms LibreOffice env docs are contract-owned, not backend-engineer's job |
| test-plan.md | AC→Test Mapping, Test Execution Ladder | exact test node IDs + phases to run |
| ci-gates.md | Required Gates table | `@pytest.mark.skipif(not is_libreoffice_available(), ...)` requirement + `libreoffice-conversion-gate` |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/processors/libreoffice_helpers.py` | edit | Add `ppt_to_pptx` after `xls_to_xlsx` (L173-185); copy that function verbatim, swap `xls`→`ppt`, `xlsx`→`pptx`, prefix `lo_ppt_`. |
| `app/backend/config.py` | edit | L245: `{".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".pdf"}`. |
| `app/backend/processors/orchestrator.py` | edit | Phase-0 `.ppt` branch (after L285); main `.ppt` branch (between L765/L766); `_output_name` `.ppt`→`.pptx` (L334-335); BR-96 warnings (pre-L821). Add `ppt_to_pptx` to the L30 import from `libreoffice_helpers`. |
| `tests/test_libreoffice_helpers.py` | create | All `libreoffice_helpers` unit tests; mock `shutil.which`/`subprocess`/`_libreoffice_convert` — never require the real binary. Real-binary tests use `@pytest.mark.skipif(not is_libreoffice_available(), ...)` per ci-gates.md. |
| `tests/test_orchestrator_phase0.py` | edit (extend, do not modify existing) | Add `.doc`/`.xls`/`.ppt` branch integration tests; call `process_files()`/Phase-0 directly, NOT via `translate_document()` (anti-tautology, test-plan.md Test Families note + CLAUDE.md promoted learning). |
| `app/frontend/src/constants/fileTypes.js` | edit | `ACCEPTED_EXTENSIONS` += `.doc`,`.xls`,`.ppt`; `ACCEPTED_MIME_TYPES` += `application/msword`, `application/vnd.ms-excel`, `application/vnd.ms-powerpoint`. |
| `app/backend/environment.yml`, `README.md` | DO NOT TOUCH | LibreOffice is an OS binary; documented in env-contract only (env-contract.md § External Binary Dependencies, owned by contract-reviewer). Adding a conda/pip dependency is incorrect. |

## Contract Updates
- API: none (api-contract.md + openapi.yml already updated by contract-reviewer; `warnings[]` note at L158 already covers legacy disclosure). Do not edit.
- CSS/UI: none.
- Env: none by backend-engineer (env-contract § External Binary Dependencies already written).
- Data shape: none (converted docs reuse existing IR).
- Business logic: none (BR-9/BR-96 already finalized); implementation must conform to BR-96 exactly.
- CI/CD: none (workflow + ci-gate-contract already finalized by ci-cd-gatekeeper).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_libreoffice_helpers.py::test_ppt_to_pptx_converts_when_libreoffice_available | `ppt_to_pptx` produces a `.pptx` (mocked convert) |
| AC-1 | tests/test_libreoffice_helpers.py::test_ppt_to_pptx_signature_and_error_semantics_match_doc_to_docx | signature/error parity with `doc_to_docx` |
| AC-2 | tests/test_orchestrator_phase0.py::test_ppt_phase0_extraction_branch_converts_via_libreoffice | Phase-0 `.ppt` routes through `ppt_to_pptx` |
| AC-2 | tests/test_orchestrator_phase0.py::test_ppt_main_branch_routes_through_ppt_to_pptx_to_translate_pptx | main `.ppt` → `ppt_to_pptx` → `translate_pptx` |
| AC-2 | tests/test_libreoffice_helpers.py::test_supported_extensions_includes_ppt | `.ppt` in `SUPPORTED_EXTENSIONS` |
| AC-3 | tests/test_libreoffice_helpers.py::test_doc_to_docx_converts_via_subprocess | `.doc` helper covered |
| AC-3 | tests/test_libreoffice_helpers.py::test_xls_to_xlsx_converts_via_subprocess | `.xls` helper covered |
| AC-3 | tests/test_orchestrator_phase0.py::test_doc_main_branch_converts_and_routes_to_translate_docx | `.doc` main branch covered |
| AC-3 | tests/test_orchestrator_phase0.py::test_xls_phase0_extraction_branch_converts_via_libreoffice | `.xls` Phase-0 covered |
| AC-4 | tests/test_libreoffice_helpers.py::test_is_libreoffice_available_true_when_binary_found | `shutil.which` → path |
| AC-4 | tests/test_libreoffice_helpers.py::test_is_libreoffice_available_false_when_no_binary_found | `shutil.which` → None, no crash |
| AC-4 | tests/test_orchestrator_phase0.py::test_doc_xls_ppt_skip_without_crash_when_libreoffice_unavailable | skip+log, no crash, no `status=failed` |
| AC-4 | tests/test_orchestrator_phase0.py::test_conversion_failure_for_one_file_does_not_abort_job_or_other_files | per-file try/except isolation |
| AC-7 | tests/contract/test_legacy_conversion_disclosure.py::test_warnings_has_one_disclosure_entry_per_converted_file_with_exact_format | `warnings[]` exact BR-96 string, one per file |
| AC-7 | tests/test_quality_evaluation.py::test_qe_scoring_invoked_identically_for_converted_legacy_document | QE path unchanged for converted docs |
| AC-8 | cdd-kit validate --contracts | api-contract/openapi sync (already exported) |

Order of operations: backend-engineer writes the tests above FIRST (failing), then implements IP-1..IP-6, confirms green. Frontend-engineer (IP-8) has no backend dependency but runs after backend so any manual smoke exercises a real end-to-end legacy upload.

Test phases (run via `cdd-kit test select` / `cdd-kit test run`, evidence in `test-evidence.yml`) per test-plan.md Test Execution Ladder and CLAUDE.md SDD/TDD policy: **collect → targeted → changed-area → contract → quality → full**. Required floor is collect/targeted/changed-area; contract applies (contracts under test); full runs at CI. Real-binary tests must carry `@pytest.mark.skipif(not is_libreoffice_available(), ...)` so the required `contract-and-fast-tests` job never reddens on LibreOffice absence (ci-gates.md).

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history; follow this plan and the cited artifacts.
- Do not re-copy full design, test strategy, CI policy, or contract prose; follow the source pointers above.
- The BR-96 disclosure string must match byte-for-byte the form in IP-6 (per business-rules.md BR-96 / api-contract L158) — the AC-7 contract test asserts exact content, not list non-emptiness.
- Mock `shutil.which`/subprocess for all availability + conversion unit tests; never require the real binary (CI determinism).
- Keep changes within the File-Level Plan; anything else needs a Context Expansion Request. If a required file, behavior, contract, or test seems missing, stop and report `blocked`.

## Known Risks
- `_output_name` (L314, used at L520) has no `.ppt` case today — design.md did not flag this; without IP-5 the `.ppt` output filename keeps the `.ppt` extension. Explicitly assigned to backend-engineer.
- `.xls` conversion happens inside `translate_xlsx_xls` (main branch L783), not in the orchestrator, so the BR-96 warning for `.xls` must be emitted at the single post-dispatch success point (IP-6), not at a per-format conversion site.
- `.doc` win32com fallback (L732-734) converts without LibreOffice; the IP-6 warning is gated on `is_libreoffice_available()` and the BR-96 string says "via LibreOffice", so a COM-only `.doc` conversion emits no disclosure. Accepted minor gap (Windows-only fallback, non-goal for `.ppt`); flag to qa-reviewer if COM disclosure parity is later required.
- Design.md line ranges verified against current source and are accurate (config.py:245; Phase-0 `.doc` L271-285 / `.xls` L243-257; main `.doc` L727-765, `.pptx` L766-782; warnings_callback L695-706 + L816; per-file except L826). Only minor drift: the `.xls` Phase-0 else-branch extends to L256-257 (design cited "L243-255"). No planning impact.
