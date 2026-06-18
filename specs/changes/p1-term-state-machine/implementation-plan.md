---
change-id: p1-term-state-machine
schema-version: 0.1.0
last-changed: 2026-06-18
---

# Implementation Plan: p1-term-state-machine

## Objective

Expand `Term.status` to four states (`unverified → needs_review → approved` / `→ rejected`), fix the injection gate to remove the `confidence=1.0` bypass so only `approved` terms are injected by default, protect `rejected` terms in conflict strategies, expose `reject` / `flag-needs-review` via API, add LLM confidence cap, and update the business-rules contract. No public signature regressions; existing 389 tests pass.

## Execution Scope

### In Scope
- IP-1..IP-10: all changes listed in Required Changes table
- New test file `tests/test_term_state_machine.py` covering AC-1..AC-8
- Contract updates: business-rules.md, env-contract.md, api-contract.md, data-shape-contract.md

### Out of Scope
- `term_audit.py` hit-rate tracking (separate change)
- Frontend UI status transitions
- XLIFF / TBX / TMX formats (P3)
- RAG / embedding retrieval (P2/P3)
- `term_extractor.py` prompt restructuring (only confidence cap at line ~456)
- `approve()` method — existing implementation is correct for all four source statuses; no change
- `edit_term()` — sets `status='approved'` directly; intentionally unchanged

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 (AC-1,2) | term_db.py | In `get_top_terms()` (line 109) and `get_document_terms()` (line 138): replace `AND (status='approved' OR confidence=1.0)` with strict `AND status='approved'` (default path). Add `_VALID_STATUSES` and `_INJECTABLE_STATUSES` module constants. | backend-engineer |
| IP-2 (AC-3) | term_db.py + config.py | Import `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED` and `TERM_INJECT_CONF_THRESHOLD` from config; in both injection methods, when the flag is true add `OR (status='unverified' AND confidence >= ?)` to the WHERE clause with threshold as bind param. Add the two vars to `config.py`. | backend-engineer |
| IP-3 (AC-4) | term_db.py | Add `reject(source_text, target_lang, domain) -> bool` and `flag_needs_review(source_text, target_lang, domain) -> bool` methods (mirror `approve()` at line 294). `flag_needs_review` is valid from any status. | backend-engineer |
| IP-4 (AC-5) | term_db.py | In `insert()` `overwrite` strategy (line 189): add `existing_rejected = existing["status"] == "rejected"`; change guard to `if existing_approved or existing_rejected: return "skipped"`. Same guard in `merge` strategy (line 235). `force` strategy is unchanged (already overwrites everything). | backend-engineer |
| IP-5 (AC-6) | term_db.py | Update `get_stats()` (line 339): add query `SELECT status, COUNT(*) FROM terms GROUP BY status`; return result as `by_status: Dict[str, int]` in the stats dict alongside existing keys. | backend-engineer |
| IP-6 | term_db.py | Update `_all_terms()` (line 479): extend `status_filter` check to also accept `needs_review` and `rejected` (currently only `approved | unverified`). | backend-engineer |
| IP-7 (AC-7) | schemas.py | Update `TermStatsResponse`: add `needs_review: int = 0`, `approved: int = 0`, `rejected: int = 0`, `by_status: Dict[str, int] = {}`. Add `TermRejectRequest` (identical fields to `TermApproveRequest`). | backend-engineer |
| IP-8 (AC-7) | routes.py | Add `POST /terms/reject` (calls `_term_db.reject()`; 404 on not found). Add `POST /terms/flag-needs-review` (calls `_term_db.flag_needs_review()`; 404 on not found). Update `terms_export` `status_filter` (line 330) to also accept `needs_review` and `rejected`. | backend-engineer |
| IP-9 (AC-8) | term_extractor.py | Add module constant `_LLM_CONFIDENCE_CAP = 0.85`. At line ~456 (`conf = t.get("confidence", 1.0)`): change to `conf = min(float(t.get("confidence", 1.0)), _LLM_CONFIDENCE_CAP)`. Same at lines ~344 and ~361 in `_parse_translation_json`. | backend-engineer |
| IP-10 | models/term.py | Update status field comment (line 20): `"unverified" | "needs_review" | "approved" | "rejected"`. | backend-engineer |
| IP-11 (AC-8) | contracts/ | Update `contracts/business/business-rules.md` with state machine (allowed transitions), injection gate rule (approved-only default, optional loose gate), `_LLM_CONFIDENCE_CAP=0.85` source-weight convention, and `rejected` conflict-strategy protection. Update `contracts/env/env-contract.md` with two new vars. Update `contracts/api/api-contract.md` with two new endpoints and `TermStatsResponse` schema change. Update `contracts/data/data-shape-contract.md` with valid `status` values. | contract-reviewer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | AC-1..AC-8, Required Contracts, Tasks Not Applicable | scope + acceptance |
| change-request.md | Constraints, Known Context (exact line numbers) | implementation guards |
| test-plan.md | AC→test mapping, Execution Ladder | tests to write + verification |
| ci-gates.md | required gates table | gate commands |
| contracts/business/business-rules.md | existing BR numbering | know next BR number to assign |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `app/backend/models/term.py` | edit | IP-10: comment only (line 20) |
| `app/backend/services/term_db.py` | edit | IP-1..IP-6: injection gate, new methods, stats, conflict strategy, _all_terms filter |
| `app/backend/config.py` | edit | IP-2: add `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED`, `TERM_INJECT_CONF_THRESHOLD` |
| `app/backend/services/term_extractor.py` | edit | IP-9: add `_LLM_CONFIDENCE_CAP = 0.85`; cap at lines ~344, ~361, ~456 |
| `app/backend/api/schemas.py` | edit | IP-7: `TermStatsResponse` additive fields, new `TermRejectRequest` |
| `app/backend/api/routes.py` | edit | IP-8: two new POST endpoints, export filter, stats |
| `contracts/business/business-rules.md` | edit | IP-11: state machine + injection gate rules |
| `contracts/env/env-contract.md` | edit | IP-11: two new env vars |
| `contracts/api/api-contract.md` | edit | IP-11: new endpoints + TermStatsResponse schema |
| `contracts/data/data-shape-contract.md` | edit | IP-11: Term.status valid values |
| `tests/test_term_state_machine.py` | create | 8 ACs coverage (see Test Execution Plan) |

## Contract Updates

- API: add `POST /terms/reject` and `POST /terms/flag-needs-review`; extend `GET /terms/export` `status` param to accept `needs_review` and `rejected`; `TermStatsResponse` gains `by_status` + individual status count fields (additive, non-breaking)
- CSS/UI: none
- Env: `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=false` (bool), `TERM_INJECT_CONF_THRESHOLD=0.9` (float)
- Data shape: `Term.status` valid values expand to 4; `TermStatsResponse` schema additive change
- Business logic: Term state machine (transitions, injection gate, source-weight convention, conflict-strategy protection)
- CI/CD: none

## Test Execution Plan

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | `tests/test_term_state_machine.py::test_injection_gate_excludes_rejected_and_needs_review` | get_top_terms / get_document_terms return empty for rejected+needs_review terms |
| AC-2 | `tests/test_term_state_machine.py::test_injection_gate_unverified_confidence_1_not_injected_by_default` | unverified confidence=1.0 term absent from injection results (default config) |
| AC-3 | `tests/test_term_state_machine.py::test_injection_gate_loose_mode_includes_high_confidence_unverified` | env flag=true + conf>=threshold → term present in injection results |
| AC-4 | `tests/test_term_state_machine.py::test_reject_and_flag_needs_review_transitions` | status updated; method returns True; returns False for nonexistent term |
| AC-5 | `tests/test_term_state_machine.py::test_insert_conflict_strategy_protects_rejected` | overwrite+merge skip rejected; force overwrites rejected |
| AC-6 | `tests/test_term_state_machine.py::test_get_stats_returns_by_status` | by_status dict present with all four keys |
| AC-7 | `tests/test_term_state_machine.py::test_reject_and_flag_api_endpoints` | 200 on found; 404 on missing; export accepts needs_review status |
| AC-8 | `tests/test_term_state_machine.py::test_llm_confidence_cap` | term inserted via extractor path has confidence ≤ 0.85 even if LLM returned 1.0 |
| baseline | `pytest` (full) | 389 existing + new tests; 0 failures |

Ladder (per test-plan.md): collect → targeted → changed-area → full. Do not run broad pytest before targeted and changed-area pass.

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not touch `approve()` or `edit_term()` behavior — they are correct for all four source statuses.
- `TermStatsResponse` change is additive only — do not remove or rename existing `total`, `unverified`, `by_target_lang`, `by_domain` fields.
- The `force` strategy in `insert()` must remain able to overwrite `rejected` — do NOT apply the same guard to `force`.
- In `term_extractor.py`, only cap confidence at the three already-identified call sites (lines ~344, ~361, ~456). Do not restructure the prompt or extraction logic.
- Do not re-copy design, test, CI, or contract prose into this plan; follow source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks

- **Migration**: existing `unverified` terms with `confidence=1.0` will no longer be auto-injected after IP-1. The `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=true` escape hatch allows operators to restore the old behavior during a review window. Document this in env-contract.md.
- **Line drift**: line numbers cited (term_db.py:109, :138, :189, :235, :294, :339, :479; term_extractor.py:344, :361, :456) are based on the last-read source. Re-verify via `.cdd/code-map.yml` or a targeted grep before editing if the file has been modified since this plan was written.
- **`_all_terms` filter**: IP-6 extends the accepted values in the `status_filter in ("approved", "unverified")` guard — ensure export routes that call `_all_terms` also accept the new values consistently.
