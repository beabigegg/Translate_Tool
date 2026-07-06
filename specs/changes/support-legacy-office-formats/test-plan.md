---
change-id: support-legacy-office-formats
schema-version: 0.1.0
last-changed: 2026-07-06
risk: medium
tier: 2
---

# Test Plan: support-legacy-office-formats

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_libreoffice_helpers.py::test_ppt_to_pptx_converts_when_libreoffice_available | 0 |
| AC-1 | unit | tests/test_libreoffice_helpers.py::test_ppt_to_pptx_signature_and_error_semantics_match_doc_to_docx | 0 |
| AC-2 | integration | tests/test_orchestrator_phase0.py::test_ppt_phase0_extraction_branch_converts_via_libreoffice | 1 |
| AC-2 | integration | tests/test_orchestrator_phase0.py::test_ppt_main_branch_routes_through_ppt_to_pptx_to_translate_pptx | 1 |
| AC-2 | unit | tests/test_libreoffice_helpers.py::test_supported_extensions_includes_ppt | 0 |
| AC-3 | unit | tests/test_libreoffice_helpers.py::test_doc_to_docx_converts_via_subprocess | 0 |
| AC-3 | unit | tests/test_libreoffice_helpers.py::test_xls_to_xlsx_converts_via_subprocess | 0 |
| AC-3 | integration | tests/test_orchestrator_phase0.py::test_doc_main_branch_converts_and_routes_to_translate_docx | 1 |
| AC-3 | integration | tests/test_orchestrator_phase0.py::test_xls_phase0_extraction_branch_converts_via_libreoffice | 1 |
| AC-4 | unit | tests/test_libreoffice_helpers.py::test_is_libreoffice_available_true_when_binary_found | 0 |
| AC-4 | unit | tests/test_libreoffice_helpers.py::test_is_libreoffice_available_false_when_no_binary_found | 0 |
| AC-4 | data-boundary | tests/test_orchestrator_phase0.py::test_doc_xls_ppt_skip_without_crash_when_libreoffice_unavailable | 1 |
| AC-4 | resilience | tests/test_orchestrator_phase0.py::test_conversion_failure_for_one_file_does_not_abort_job_or_other_files | 1 |
| AC-5 | none (docs-only; verified by contract-reviewer/env-contract, not an automated test) | — | — |
| AC-6 | none (frontend; covered by ui-ux-reviewer/visual-reviewer, out of test-strategist scope) | — | — |
| AC-7 | contract | tests/contract/test_legacy_conversion_disclosure.py::test_warnings_has_one_disclosure_entry_per_converted_file_with_exact_format | 1 |
| AC-7 | unit | tests/test_quality_evaluation.py::test_qe_scoring_invoked_identically_for_converted_legacy_document | 1 |
| AC-8 | contract | cdd-kit validate --contracts (api-contract.md / openapi.yml sync gate) | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | libreoffice_helpers.py: all four functions incl. both is_libreoffice_available branches, mocked subprocess/shutil.which — no real binary required |
| integration | 1 | orchestrator.py process_files() Phase-0 extraction + main conversion branches for .doc/.xls/.ppt, called directly (not via translate_document()) per anti-tautology guard |
| contract | 1 | job.warnings exact disclosure-string content per BR-96; api-contract.md/openapi.yml sync via existing contract gate |
| data-boundary | 1 | corrupt/empty/misnamed legacy file input and missing-binary path degrade to skip+log, never crash, never job status=failed for this reason alone |
| resilience | 1 | per-file try/except isolation — one file's conversion exception must not abort the job or other files |

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_orchestrator_phase0.py (existing phase0-hook tests) | none — extend, do not modify | new .doc/.xls/.ppt branch tests are additive; existing hook-injection assertions are unaffected |

## Out of Scope

- Native binary `.doc`/`.xls`/`.ppt` parser correctness (design.md non-goal — LibreOffice-headless only).
- Frontend `ACCEPTED_EXTENSIONS`/drop-zone visual rendering (AC-6) — owned by ui-ux-reviewer/visual-reviewer.
- `environment.yml`/README install-doc content (AC-5) — docs-only, verified by contract-reviewer.
- Stress/soak, and fuzz/monkey beyond the corrupt/empty/misnamed data-boundary cases above (no dedicated e2e-resilience/monkey/stress-soak engineer commissioned at Tier 2).
- `.doc` COM (`win32com`) fallback path parity for `.ppt` — deferred per design.md Open Risks; only the LibreOffice + graceful-skip path is required.

## Notes

Data-boundary and resilience cases are written directly by backend-engineer in TDD fashion (failing first) inside `tests/test_libreoffice_helpers.py` / `tests/test_orchestrator_phase0.py` — no dedicated test-engineer deliverable per classification. `is_libreoffice_available()`-absent branch must always be tested via mock (`shutil.which` → None), never by requiring the real binary, so CI is deterministic regardless of LibreOffice presence on the runner. Warning-string assertions must check exact content (BR-96 format), not merely list non-emptiness.
