---
change-id: p1-sentence-mode-fix
schema-version: 0.1.0
last-changed: 2026-06-17
risk: medium
tier: 2
---

# Test Plan: p1-sentence-mode-fix

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_sentence_mode_consistency.py::test_sentence_mode_failure_placeholder_includes_original | 0 |
| AC-2 | unit | tests/test_sentence_mode_consistency.py::test_sentence_mode_done_count_incremented_per_segment | 0 |
| AC-2 | unit | tests/test_sentence_mode_consistency.py::test_sentence_mode_stop_flag_no_overcount | 0 |
| AC-3 | unit | tests/test_sentence_mode_consistency.py::test_translate_blocks_batch_respects_stop_flag | 0 |
| AC-4 | unit | tests/test_sentence_mode_consistency.py::test_sentence_mode_outer_loop_breaks_when_stopped | 0 |
| AC-5 | integration | tests/test_sentence_mode_consistency.py::test_verify_and_fill_detects_sentence_mode_failures | 1 |
| AC-6 | unit | tests/test_sentence_mode_consistency.py::test_translate_texts_signature_unchanged | 0 |
| AC-7 | integration | tests/test_translation_strategy.py | 0 |
| AC-7 | integration | tests/test_translation_profiles_scenarios.py | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | AC-1 to AC-4, AC-6: pure logic, mock `client.translate_once` and `translate_blocks_batch` at module boundary; use `threading.Event` for stop_flag |
| integration | 1 | AC-5: real `verify_and_fill_tmap` with a pre-built failure tmap and mock client; AC-7: 389-test baseline |

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
| (none) | — | no existing test behavior changes; new file only |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- `verify_and_fill_dict` (PDF processor path) — explicitly excluded per change-classification.md.
- E2E, visual, stress, monkey, and soak tests.
- API route and HTTP response schema changes (no route changes in this fix).
- Frontend surfaces.

## Notes

- AC-3 and AC-4 tests must fail before implementation: `translate_blocks_batch` has no `stop_flag` param yet and the outer loop has no `if stopped: break` in SENTENCE_MODE.
- AC-1: assert `tmap[(tgt, src_text)]` starts with `[Translation failed|{tgt}]` and contains the original source text when batch returns `(False, ...)`.
- AC-7 baseline: confirm `pytest --tb=short -q` reports 389 passed before merge; new tests add to that count.
- Mock only at module boundary (`app.backend.services.translation_service.translate_blocks_batch`), not at internal class level.
