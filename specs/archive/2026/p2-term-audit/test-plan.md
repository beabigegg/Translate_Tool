---
change-id: p2-term-audit
schema-version: 0.1.0
last-changed: 2026-06-19
risk: medium
tier: 2
---

# Test Plan: p2-term-audit

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 (audit producible end-to-end at hook seam) | integration | tests/test_term_audit.py::test_audit_wired_at_hook_seam | 1 |
| AC-2 (hit rate ≥ 95% on 20-approved-term fixture) | unit | tests/test_term_audit.py::test_hit_rate_20_approved_terms | 0 |
| AC-3 (rejected injection detected when present) | unit | tests/test_term_audit.py::test_rejected_injection_detected | 0 |
| AC-3 (rejected_injections == [] when absent) | unit | tests/test_term_audit.py::test_rejected_injection_not_detected | 0 |
| AC-3 (whole-token boundary; substring-of-approved edge case) | unit | tests/test_term_audit.py::test_whole_token_rejected_injection | 0 |
| AC-4 (case-insensitive exact match) | unit | tests/test_term_audit.py::test_hit_rate_case_insensitive | 0 |
| AC-4 (exact match; assert WHICH terms matched) | unit | tests/test_term_audit.py::test_hit_rate_exact_match | 0 |
| AC-5 (result shape has exactly 5 fields) | contract | tests/test_term_audit.py::test_result_shape_conforms_to_data_contract | 1 |
| AC-5 (audit field on JobRecord; no parallel format) | contract | tests/test_term_audit.py::test_no_parallel_report_format | 1 |
| AC-6 (no new endpoint; api-contract unchanged) | out of scope | n/a — enforced by cdd-kit validate --contracts gate | 1 |
| AC-7 (unverified/needs_review/rejected excluded from denominator) | unit | tests/test_term_audit.py::test_scope_excludes_non_approved | 0 |
| AC-7 (vacuous 1.0 when total_approved == 0; no ZeroDivisionError) | data-boundary | tests/test_term_audit.py::test_vacuous_hit_rate | 0 |
| AC-8 (unapplied_terms list identifies correct terms by value) | unit | tests/test_term_audit.py::test_unapplied_terms_list | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Matching algorithm, hit-rate arithmetic, unapplied-term identity, rejected-injection detection; all selection assertions (WHICH terms, not count-only) |
| contract | 1 | TerminologyAuditResult 5-field shape; JobRecord.audit placement; data-shape-contract.md §Terminology Audit |
| integration | 1 | Seam wiring via process_files(); patch at consumer path; assert call_count >= 1 |
| data-boundary | 0 | Empty block list; zero approved terms; multi-language-pair scope isolation |

## Additional Tests (not directly mapped to an AC but required for completeness)

| test name | family | tier |
|---|---|---|
| tests/test_term_audit.py::test_audit_disabled_when_exception | resilience | 1 |
| tests/test_term_audit.py::test_empty_block_list | data-boundary | 0 |
| tests/test_term_audit.py::test_zero_approved_terms | data-boundary | 0 |
| tests/test_term_audit.py::test_multi_language_target | data-boundary | 0 |
| tests/test_term_audit.py::test_get_rejected_interface | unit | 0 |

## Tautology Guards

**Wrong-entry-point (AC-1):** `test_audit_wired_at_hook_seam` must invoke `process_files()` or `_run_job()` directly — never `translate_document()`. Patch `app.backend.services.job_manager.audit_terms` (the consumer-module binding, per CLAUDE.md mock-binding lesson). Assert `mock_audit_terms.call_count >= 1`.

**Selection (AC-2, AC-8, AC-3):** `test_hit_rate_exact_match`, `test_unapplied_terms_list`, `test_rejected_injection_detected` must assert each matched/unmatched term's `target_text` value, not only `len() > 0`.

**Open-risk pin (design.md §Open Risks):** `test_whole_token_rejected_injection` pins the substring-of-approved edge case — a rejected `target_text` that is a strict substring of an approved `target_text` must not appear in `rejected_injections` unless it is present at a whole-token boundary in the output. This test must fail before a boundary-aware matcher is implemented.

## Out of Scope

- AC-6 API conformance: enforced mechanically by `cdd-kit validate --contracts`; no test case in `test_term_audit.py`.
- Lemmatized matching (D-1 optional mode, off by default): not tested until the configurable flag is introduced.
- Frontend, E2E, visual, monkey, stress, soak: excluded per change-classification.md.

## Notes

- `tests/test_term_audit.py` does not yet exist; backend-engineer creates it alongside `app/backend/services/term_audit.py`.
- Fixture pattern: `TermDB(db_path=tmp_path / "test.sqlite")` mirrors `test_term_db.py::db`; reuse `_make_term(**kwargs)` helper shape.
- `get_rejected` is a new `TermDB` query (design.md §Affected Components); test via `test_get_rejected_interface` in `test_term_audit.py`, not `test_term_db.py`.
- Run tier-0 tests: `pytest tests/test_term_audit.py -k "not wired_at_hook_seam"`. Run all: `pytest tests/test_term_audit.py`.
