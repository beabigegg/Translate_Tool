---
change-id: p2-term-audit
archived: 2026-06-19
gate-status: passed
qa-decision: release-ready
---

# Archive: p2-term-audit

## Change Summary

Added `app/backend/services/term_audit.py` — a new read-only post-translation audit module that scans translated output against the approved and rejected terminology sets. The module produces a `TerminologyAuditResult` (5 fields: `terminology_hit_rate`, `unapplied_terms`, `rejected_injections`, `total_approved`, `matched_approved`) and attaches it to `JobRecord.audit` via the existing `qe_blocks` post-translate hook seam in `_run_job`, mirroring the COMET/xCOMET QE attachment pattern. Required by P2-8 in `docs/p2-change-requests.md`.

## Final Behavior

- After each translation job, `audit_terms()` measures how many approved glossary terms (scoped by `target_lang` / `domain`) appear in the translated output and flags any rejected terms that leaked in using whole-token boundary matching.
- `JobRecord.audit: Optional[TerminologyAuditResult]` is populated immediately after the QE scoring block in `_run_job`. On exception (BR-61): WARNING logged, `audit=None`, job continues.
- `terminology_hit_rate = 1.0` when `total_approved == 0` (vacuously satisfied, BR-59).
- Rejected term detection uses `\b` word-boundary regex, not bare substring, to avoid false positives when a rejected term is a substring of an approved term (e.g. rejected "bar" ⊂ approved "foobar").
- Default matching algorithm: case-insensitive exact substring (no NLP dep). Optional configurable lemmatized mode via `blingfire` (lazy import, default off, D-1/D-4).

## Final Contracts Updated

| contract | version | change |
|---|---|---|
| `contracts/business/business-rules.md` | 0.11.0 → 0.12.0 | BR-59 (audit scope), BR-60 (match algorithm), BR-61 (safe degradation), Table Q (9 condition rows) |
| `contracts/data/data-shape-contract.md` | 0.7.0 → 0.8.0 | `## Terminology Audit Representation` (TerminologyAuditResult shape, JobRecord.audit optional field, nullability rules, known-consumers table) |
| `contracts/CHANGELOG.md` | — | Entries for business 0.12.0 and data 0.8.0 |

API, env, and CI contracts unchanged (AC-6).

## Final Tests Added

| test | family | AC |
|---|---|---|
| `test_hit_rate_exact_match` | unit | AC-4 |
| `test_hit_rate_case_insensitive` | unit | AC-4 |
| `test_unapplied_terms_list` | unit | AC-8 |
| `test_rejected_injection_detected` | unit | AC-3 |
| `test_rejected_injection_not_detected` | unit | AC-3 |
| `test_vacuous_hit_rate` | data-boundary | AC-7 |
| `test_scope_excludes_non_approved` | unit | AC-7 |
| `test_whole_token_rejected_injection` | unit | AC-3 (open-risk pin) |
| `test_hit_rate_20_approved_terms` | unit | AC-2 |
| `test_get_rejected_interface` | unit | TermDB.get_rejected() |
| `test_result_shape_conforms_to_data_contract` | contract | AC-5 |
| `test_no_parallel_report_format` | contract | AC-5 |
| `test_audit_wired_at_hook_seam` | integration | AC-1 |
| `test_audit_disabled_when_exception` | resilience | BR-61 |
| `test_empty_block_list` | data-boundary | — |
| `test_zero_approved_terms` | data-boundary | — |
| `test_multi_language_target` | data-boundary | — |
| `test_no_parallel_report_format` | contract | AC-5 |

All 18 tests pass. 690 pre-existing tests pass (no regressions).

## Final CI/CD Gates

5 required gates, all pre-existing (no new gate added):
- `contract-validate` — `cdd-kit validate --contracts`
- `change-gate` — `cdd-kit gate p2-term-audit`
- `openapi-sync` — `cdd-kit openapi export --check`
- `unit-tests` — `pytest tests/ -x -q --tb=short`
- `layout-detector-dependency-gate` — grep for forbidden packages

`tier-floor-override: 2` applied; "integration" vocabulary in change-request would have misfired cdd-kit tier heuristic.

## Production Reality Findings

No surprises. One note from qa-reviewer: `domain=None` passed to `audit_terms()` at the seam in `job_manager.py` is correct — `RouteGroup` carries no `domain` field, so `get_approved(target_lang, None)` widens to all domains for the target language. This is consistent with BR-59's optional domain filter and the conservative/correct behavior when the job has no domain binding.

`TermDB` was promoted to module-level import in `job_manager.py` (previously a local import) to enable consumer-binding `mock.patch` at `app.backend.services.job_manager.audit_terms`.

## Lessons Promoted to Standards

No new lessons promoted. Assessment:

- **Whole-token boundary for `rejected_injections`**: product behavior rule, already elevated to `contracts/data/data-shape-contract.md §Nullability and invalid-data rules`. No CLAUDE.md entry needed.
- **tier-floor-override for "integration" vocab**: already in existing CLAUDE.md learnings entry ("`cdd-kit gate` tier-floor false-positives").
- **mock.patch consumer binding / wrong-entry-point tautology**: already in existing CLAUDE.md learnings entries; test_audit_wired_at_hook_seam confirms the pattern but adds no new rule.
- **blingfire lazy import**: one-off implementation detail; already documented in design.md D-4 and code comment. Not a cross-change workflow rule.

## Follow-up Work

- Optional lemmatized matching mode (D-1 optional mode, configurable flag) is not tested. Backend-engineer noted `blingfire` lazy import path is present but untested. A future change can add the configurable flag + tests when the product requires it.
- `audit` field is in-memory only and not surfaced in any HTTP response. A future endpoint (e.g. `GET /jobs/{id}/audit`) would follow the `GET /jobs/{id}/quality` pattern from p2-comet-qe.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
