---
change-id: p2-term-audit
schema-version: 0.1.0
last-changed: 2026-06-19
---

# Implementation Plan: p2-term-audit

## Objective
Deliver a read-only, per-job terminology audit. After translation, measure whether
`approved` glossary terms (filtered by the job's `(target_lang, domain)`) landed in
the translated output and whether any `rejected` terms leaked in, producing a
`TerminologyAuditResult` attached to the in-memory `JobRecord.audit` field. The audit
runs over the existing `qe_blocks` accumulator (the same `post_translate_hook` seam
already proven by COMET QE), mutates no translations, and adds no endpoint, env var,
or DB migration.

## Execution Scope

### In Scope
Owner: `backend-engineer`. TDD order — write the failing tests first, then implement.

1. Write `tests/test_term_audit.py` covering all 5 test families in `test-plan.md`
   (unit, contract, integration, data-boundary, plus the resilience/`get_rejected`
   additions). Tests fail first.
2. Add `TermDB.get_rejected(target_lang=None, domain=None)` — a pure read query
   mirroring `get_approved` (see `app/backend/services/term_db.py:406-423`).
3. Create `app/backend/services/term_audit.py`:
   `audit_terms(blocks, targets, domain, term_db, lemmatized=False, ...) -> TerminologyAuditResult`.
4. Add `TerminologyAuditResult` (dataclass, 5 fields per `design.md §Data Model`).
   Place it where the consumer/contract expects it (see File-Level Plan IP-4 notes).
5. Wire `audit_terms` into `app/backend/services/job_manager.py::_run_job` at the
   post-loop site immediately adjacent to the QE scoring block, reading the existing
   `qe_blocks` accumulator; add the `audit: Optional[TerminologyAuditResult] = None`
   field to `JobRecord`.
6. Run the bounded `cdd-kit test run` ladder (collect → targeted → changed-area →
   contract → full smoke) and produce `test-evidence.yml` before handing off to
   `qa-reviewer`.

### Out of Scope
Per `change-classification.md §Tasks Not Applicable` and `§Required Contracts`:
- No new HTTP endpoint; `contracts/api/api-contract.md` and `openapi.yml` unchanged
  (AC-6). Do not add or rename any route.
- No frontend, CSS/UI, env var, secret, or DB migration.
- No mutation of translated output; the audit is strictly read-only.
- Lemmatized matching ships as an optional, default-off code path only (D-1, D-4).
  Do not enable it by default and do not write tests for it (`test-plan.md §Out of
  Scope`); it is not tested until the configurable flag is exercised.
- No new parallel report file/format; reuse `JobRecord.audit` (D-3).
- No opportunistic refactor of the QE path, `process_files`, or `term_db` beyond the
  additive `get_rejected` query.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | tests | Create `tests/test_term_audit.py` with all 5 families from `test-plan.md`; tautology + selection + whole-token guards; fail first | backend-engineer |
| IP-2 | term_db | Add `TermDB.get_rejected(...)` read query mirroring `get_approved` | backend-engineer |
| IP-3 | new module | Create `app/backend/services/term_audit.py` with `audit_terms(...)` + matcher (case-insensitive exact default; whole-token boundary for rejected; lazy `blingfire` import for optional lemmatized mode) | backend-engineer |
| IP-4 | data model | Define `TerminologyAuditResult` dataclass (5 fields, `design.md §Data Model`) | backend-engineer |
| IP-5 | job seam | Add `JobRecord.audit` field; call `audit_terms` over `qe_blocks` in `_run_job` post-loop; wrap in try/except → `audit=None` on failure (BR-61) | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | AC-1..AC-8; §Tasks Not Applicable | scope, acceptance, non-goals |
| design.md | D-1 (exact-match default), D-2 (qe_blocks seam, NOT translate_document), D-3 (JobRecord.audit, no parallel format), D-4 (lazy blingfire), §Data Model, §Open Risks (substring-of-approved) | implementation constraints |
| test-plan.md | AC→test mapping table; §Tautology Guards; §Notes (fixture pattern) | tests to write/run |
| ci-gates.md | required-gates table; `tier-floor-override: 2` | verification commands |
| contracts/business/business-rules.md | BR-59 (approved-only scope), BR-60 (match algorithm/unapplied), BR-61 (safe degradation); Table Q | business invariants |
| contracts/data/data-shape-contract.md | §Terminology Audit Representation; TerminologyAuditResult shape; JobRecord.audit nullability; whole-token rule; Known-consumers table | result shape + contract test target |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `tests/test_term_audit.py` | create (IP-1) | All tests from `test-plan.md` AC-map + additional table. Fixture: `TermDB(db_path=tmp_path / "test.sqlite")` mirroring `tests/test_term_db.py::db`. Integration test patches `app.backend.services.job_manager.audit_terms` (consumer binding) and asserts `call_count >= 1`. Selection tests assert WHICH `target_text` values matched/unapplied/injected, not `len()`. `test_whole_token_rejected_injection` must fail before the boundary-aware matcher exists. |
| `app/backend/services/term_db.py` | modify (IP-2) | Add `get_rejected(target_lang=None, domain=None) -> List[Term]` mirroring `get_approved` at lines 406-423: same optional-filter pattern, `status='rejected'` clause, `_DB_LOCK` + `_connect()`, `_row_to_term`. Pure read; no schema change. |
| `app/backend/services/term_audit.py` | create (IP-3, IP-4) | `audit_terms(blocks, targets, domain, term_db, lemmatized=False)`. `blocks` is the `qe_blocks` list of `(block_id, src, mt)` tuples (audit reads `mt` only — see job_manager.py:301,374). Query `term_db.get_approved` / `get_rejected` per target × domain. Default matcher: case-insensitive substring of each approved `target_text` against the `mt` text. `rejected_injections`: whole-token boundary match (design.md §Open Risks). `terminology_hit_rate = matched_approved/total_approved`, `1.0` when `total_approved == 0` (no ZeroDivisionError). `unapplied_terms` = `source_text` keys of unmatched approved terms (data-shape-contract.md). Optional lemmatized mode imports `blingfire` LAZILY inside the function body, never at module top (D-4). Define `TerminologyAuditResult` dataclass here. |
| `app/backend/services/job_manager.py` | modify (IP-5) | Add `audit: Optional[TerminologyAuditResult] = None` to `JobRecord` (after line 82, parallel to `quality`). Import `audit_terms`/`TerminologyAuditResult` from `term_audit`. In `_run_job` (lines 286-419), after the route-group loop and adjacent to the QE block (lines 370-398), call `audit_terms(qe_blocks, <targets>, <domain>, term_db)`. Reuse the existing `term_db` (line 305) and `qe_blocks` (line 301) — do NOT add a second accumulator or hook. Targets/domain derive from the same route-group/profile data the loop already uses. Wrap the call in try/except: on any exception set `job.audit = None`, log a WARNING, do NOT fail the job (BR-61). Mirror the QE `mode != "extraction_only"` guard. |

## Contract Updates
Contracts are already authored by `contract-reviewer`; backend-engineer conforms to
them and must not re-edit unless implementation reveals a gap (then report `blocked`).

- API: none — `api-contract.md` / `openapi.yml` unchanged (AC-6); conformance gate must report no drift.
- CSS/UI: none.
- Env: none.
- Data shape: conform to `contracts/data/data-shape-contract.md §Terminology Audit Representation` — `TerminologyAuditResult` 5-field shape, `JobRecord.audit` optional/nullable, whole-token rule, Known-consumers table.
- Business logic: conform to `contracts/business/business-rules.md` BR-59 (approved-only denominator), BR-60 (match algorithm + unapplied list), BR-61 (catch-and-degrade to `audit=None`).
- CI/CD: none — no new gate (ci-gates.md).

## Test Execution Plan
Required phase floor: `collect`, `targeted`, `changed-area`; add `contract` and a
`full` smoke per ci-gates.md `unit-tests`. Generate evidence with `cdd-kit test run`;
the gate validates `test-evidence.yml`.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (audit wired at hook seam) | tests/test_term_audit.py::test_audit_wired_at_hook_seam | mock_audit_terms.call_count >= 1; patched at consumer binding |
| AC-2 (hit rate ≥ 95%) | tests/test_term_audit.py::test_hit_rate_20_approved_terms | hit_rate >= 0.95 on 20-approved fixture |
| AC-3 (rejected injection detected) | tests/test_term_audit.py::test_rejected_injection_detected | injected term value present in rejected_injections |
| AC-3 (no false positive) | tests/test_term_audit.py::test_rejected_injection_not_detected | rejected_injections == [] |
| AC-3 (whole-token boundary) | tests/test_term_audit.py::test_whole_token_rejected_injection | substring-of-approved NOT flagged unless whole-token |
| AC-4 (case-insensitive) | tests/test_term_audit.py::test_hit_rate_case_insensitive | case-differing term counts as hit |
| AC-4 (exact match selection) | tests/test_term_audit.py::test_hit_rate_exact_match | asserts WHICH terms matched |
| AC-5 (5-field shape) | tests/test_term_audit.py::test_result_shape_conforms_to_data_contract | exactly the 5 contract fields |
| AC-5 (no parallel format) | tests/test_term_audit.py::test_no_parallel_report_format | result on JobRecord.audit only |
| AC-6 (no endpoint drift) | `cdd-kit validate --contracts` | exit 0; no api drift |
| AC-7 (approved-only scope) | tests/test_term_audit.py::test_scope_excludes_non_approved | non-approved excluded from denominator |
| AC-7 (vacuous 1.0) | tests/test_term_audit.py::test_vacuous_hit_rate | 1.0, no ZeroDivisionError |
| AC-8 (unapplied list identity) | tests/test_term_audit.py::test_unapplied_terms_list | asserts correct term values |
| (resilience) | tests/test_term_audit.py::test_audit_disabled_when_exception | audit=None, job not failed (BR-61) |
| (data-boundary) | tests/test_term_audit.py::test_empty_block_list / test_zero_approved_terms / test_multi_language_target | graceful, scope-isolated |
| (get_rejected interface) | tests/test_term_audit.py::test_get_rejected_interface | rejected set returned, mirrors get_approved |

Tier-0 fast loop: `pytest tests/test_term_audit.py -k "not wired_at_hook_seam"`.
Full file: `pytest tests/test_term_audit.py`. Full smoke: `pytest tests/ -x -q --tb=short`.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- `term_audit.py` MUST run over the `qe_blocks` accumulator at the `post_translate_hook`
  seam (D-2), NOT via `translate_document()` or any higher-level wrapper — the wrapper
  does not reach the processor hook, so a test through it passes tautologically (CLAUDE.md
  wrong-entry-point lesson; `tests/test_translation_strategy.py::test_qe_hook_called_after_translation`).
- The integration test's `mock.patch` target MUST be `app.backend.services.job_manager.audit_terms`
  (the consumer-module binding), NOT `app.backend.services.term_audit.audit_terms` —
  Python binds names at import time (CLAUDE.md mock-binding lesson).
- `TermDB.get_rejected` MUST be a pure read query mirroring `get_approved`; spec-architect
  flagged that the rejected set is not currently exposed.
- `blingfire` MUST be imported lazily inside `audit_terms()` only when the optional
  lemmatized mode is enabled — never at module top (D-4).
- All 5 test families from `test-plan.md` live in `tests/test_term_audit.py`.
- `audit_terms` failure MUST be caught and recorded as `JobRecord.audit = None` without
  failing the job (BR-61).
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- Backend-engineer runs the `cdd-kit test run` bounded ladder and produces
  `test-evidence.yml` before handing off to `qa-reviewer`.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks

- Substring over-counting (design.md §Open Risks): a `rejected` `target_text` that is a
  strict substring of an `approved` `target_text` must not be flagged unless present at a
  whole-token boundary. Pinned by `test_whole_token_rejected_injection`.
- Targets/domain plumbing into `audit_terms`: the audit must be scoped to the same
  `(targets, domain)` the route-group/profile used so the BR-59 denominator is correct;
  derive from the existing loop/profile data, not a fresh source.
- `.cdd/code-map.yml` is from cdd-kit 3.3.0 (2026-06-17) and matched the source reads
  this session (job_manager.py:301/342/370-398, term_db.py:406-423). If it has drifted
  before implementation, re-confirm no second `post_translate_hook` consumer exists.
- `qe_blocks` is populated only on the translation path (`mode != "extraction_only"`);
  the audit should mirror the QE guard so it does not run on extraction-only jobs.
