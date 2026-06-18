---
change-id: p1-term-state-machine
schema-version: 0.1.0
last-changed: 2026-06-18
risk: medium
tier: 2
---

# Test Plan: p1-term-state-machine

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_term_state_machine.py::test_injection_gate_excludes_rejected_and_needs_review | 2 |
| AC-2 | unit | tests/test_term_state_machine.py::test_injection_gate_unverified_confidence_1_not_injected_by_default | 2 |
| AC-3 | unit | tests/test_term_state_machine.py::test_injection_gate_loose_mode_includes_high_confidence_unverified | 2 |
| AC-4 | unit | tests/test_term_state_machine.py::test_reject_and_flag_needs_review_transitions | 2 |
| AC-5 | data-boundary | tests/test_term_state_machine.py::test_insert_conflict_strategy_protects_rejected | 2 |
| AC-6 | contract | tests/test_term_state_machine.py::test_get_stats_returns_by_status | 2 |
| AC-7 | integration | tests/test_term_state_machine.py::test_reject_and_flag_api_endpoints | 2 |
| AC-8 | unit | tests/test_term_state_machine.py::test_llm_confidence_cap | 2 |
| AC-8 (baseline) | integration | `pytest` full suite | 2 |

## Test Families Required

unit, contract, integration, data-boundary

## Test Notes (per AC)

**AC-1** — `test_injection_gate_excludes_rejected_and_needs_review`
- Insert two terms via `TermDB.insert()`: one with `status='rejected'`, one with `status='needs_review'`
- Call `get_top_terms()` and `get_document_terms()` with matching `target_lang` / `domain`
- Assert both terms absent from both result sets

**AC-2** — `test_injection_gate_unverified_confidence_1_not_injected_by_default`
- Insert term with `status='unverified'`, `confidence=1.0`
- Confirm `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED` is `False` (monkeypatch if needed)
- Assert term absent from `get_top_terms()` and `get_document_terms()`

**AC-3** — `test_injection_gate_loose_mode_includes_high_confidence_unverified`
- Monkeypatch `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=True` and `TERM_INJECT_CONF_THRESHOLD=0.9`
- Insert two unverified terms: `confidence=0.95` and `confidence=0.5`
- Assert `confidence=0.95` term IS in results; `confidence=0.5` IS NOT

**AC-4** — `test_reject_and_flag_needs_review_transitions`
- Insert `unverified` term; call `reject()` → assert `status='rejected'` in DB; returns `True`
- Insert `unverified` term; call `flag_needs_review()` → assert `status='needs_review'`; returns `True`
- Insert `approved` term; call `flag_needs_review()` → assert `status='needs_review'`
- Call `reject()` / `flag_needs_review()` with nonexistent key → assert returns `False`

**AC-5** — `test_insert_conflict_strategy_protects_rejected`
- Insert `rejected` term; call `insert(new_term, strategy='overwrite')` → assert returns `'skipped'`, status remains `'rejected'`
- Same with `strategy='merge'` → assert `'skipped'`
- Same with `strategy='force'` → assert `'overwritten'`, status updated to new term's status

**AC-6** — `test_get_stats_returns_by_status`
- Insert one term of each status (unverified, needs_review, approved, rejected)
- Call `get_stats()` → assert `by_status` dict present with all four keys; counts match

**AC-7** — `test_reject_and_flag_api_endpoints`
- Use FastAPI TestClient; `POST /terms/reject` with existing term key → assert 200
- `POST /terms/reject` with nonexistent key → assert 404
- `POST /terms/flag-needs-review` with existing term key → assert 200
- `POST /terms/flag-needs-review` with nonexistent key → assert 404
- `GET /terms/export?status=needs_review` → assert 200 (no error); `GET /terms/export?status=rejected` → assert 200

**AC-8** — `test_llm_confidence_cap`
- Monkeypatch / patch `_LLM_CONFIDENCE_CAP = 0.85` in term_extractor
- Call the translation-batch parser with a mock response where `"confidence": 1.0`
- Assert the resulting term has `confidence <= 0.85`
- Verify both `_parse_translation_json()` and the inline insert path apply the cap

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | pytest tests/test_term_state_machine.py | 1 | test-evidence.yml |
| changed-area | yes | pytest tests/test_term_db.py tests/test_term_state_machine.py | 1 | test-evidence.yml |
| contract | yes | cdd-kit validate --contracts | 1 | test-evidence.yml |
| full | final/CI | pytest | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| any test that checks `get_stats()` response shape | update | `TermStatsResponse` gains `by_status` + individual status fields (additive, but snapshot tests may fail) |
| any test that checks `get_top_terms()` returns `confidence=1.0 unverified` terms | update | injection gate fix (AC-2) removes this behavior; test expectation must change |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- E2E / browser tests (no frontend surface)
- Resilience / stress / soak (Tier 2)
- Wikidata integration tests (Wikidata source weighting is documented as convention only in P1; implementation in P2)

## Notes

- AC-3 requires monkeypatching config values at the module level where `term_db.py` imports them — use `monkeypatch.setattr("app.backend.services.term_db.TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED", True)` pattern.
- The TermDB in tests should use a `tmp_path` SQLite file (not the real data directory) to avoid cross-test pollution.
