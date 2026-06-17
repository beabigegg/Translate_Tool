---
change-id: p1-sentence-mode-fix
schema-version: 0.1.0
last-changed: 2026-06-17
---

# Implementation Plan: p1-sentence-mode-fix

## Objective
Make the SENTENCE_MODE batch path in `translate_texts` behave consistently with the non-SENTENCE_MODE per-sentence path on failure marking, per-segment done/fail counting, mid-batch stop honoring, and post-batch outer-loop break. No public signature changes.

## Execution Scope

### In Scope
- Four targeted fixes (FIX 1-4) in `translation_service.py` SENTENCE_MODE branch and `translation_helpers.py` batch helper.
- New regression test file `tests/test_sentence_mode_consistency.py` (7 tests).

### Out of Scope
- API routes, request/response schemas, env vars, frontend.
- Document processors (docx/xlsx/pptx/pdf) and `verify_and_fill_dict`.
- The latent ok-flag discard at `translation_helpers.py:453` (noted code smell; do not refactor).
- `translate_texts` signature (AC-6) and any change that breaks the 389-test baseline (AC-7).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 (AC-1) | translation_service.py | In the SENTENCE_MODE result loop (`for text, (ok, res) in zip(...)`, ~177-190), when `not ok`, set `res = f"[Translation failed\|{tgt}] {text}"` before `tmap[(tgt, text)] = res`. Apply before the s2t-conversion `if`. | backend-engineer |
| IP-2 (AC-2) | translation_service.py | Remove post-batch bulk increment `done += len(texts_to_translate) + dedup_saved` (line 193). Inside the per-segment loop add `done += seen_texts.get(text, 1)`. | backend-engineer |
| IP-3 (AC-3) | translation_helpers.py | Add `stop_flag=None` optional kwarg to `translate_blocks_batch` (385). Thread into `BatchTranslator.__init__`, check between iterations in `_fallback_individual` and in `flush()`/`translate_all` so a set flag halts in-progress batch work. | backend-engineer |
| IP-4 (AC-4) | translation_service.py | After the SENTENCE_MODE block (after the new per-segment `done` increment, before the `else:` of `if SENTENCE_MODE:`), add `if stopped: break`, mirroring lines 223-224. Pass `stop_flag` into the `translate_blocks_batch(...)` call (162-168) and set `stopped = True` when it halts. | backend-engineer |
| IP-5 | tests/ | Create `tests/test_sentence_mode_consistency.py` with the 7 tests mapped in test-plan.md. | test-strategist |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | AC-1..AC-7, Constraints | scope + acceptance |
| agent-log/bug-fix-engineer.yml | ROOT CAUSE 1-4, fix.summary FIX 1-4 | exact fix locations |
| test-plan.md | AC->test mapping, Execution Ladder, Stop Rules | tests + verification |
| ci-gates.md | required gates table | gate commands |
| contracts/business/business-rules.md | BR-21/22/23 counting + failure-marker rules | confirm corrected behavior matches (review only) |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/services/translation_service.py | edit | IP-1, IP-2, IP-4; SENTENCE_MODE branch only (138-193). Do not touch non-SENTENCE_MODE path. |
| app/backend/utils/translation_helpers.py | edit | IP-3; `translate_blocks_batch` + `BatchTranslator`. New param optional (default None). |
| app/backend/utils/translation_verification.py | read-only | confirm `is_failed_translation` still matches `[Translation failed\|...]` (AC-5); no edit expected. |
| contracts/business/business-rules.md | review (edit only if rule diverges) | counting/failure-marker rule. |
| tests/test_sentence_mode_consistency.py | create | 7 tests (IP-5). |

## Contract Updates
- API: none
- CSS/UI: none
- Env: none (SENTENCE_MODE already exists in config.py)
- Data shape: none
- Business logic: review `contracts/business/business-rules.md`; update only if corrected SENTENCE_MODE counting/failure-marker behavior diverges from documented rule.
- CI/CD: none

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_sentence_mode_consistency.py::test_sentence_mode_failure_placeholder_includes_original | tmap value starts with `[Translation failed\|{tgt}]` and contains original text |
| AC-2 | tests/test_sentence_mode_consistency.py::test_sentence_mode_done_count_incremented_per_segment | done equals non-SENTENCE_MODE on identical input |
| AC-2 | tests/test_sentence_mode_consistency.py::test_sentence_mode_stop_flag_no_overcount | no over-count after mid-batch stop |
| AC-3 | tests/test_sentence_mode_consistency.py::test_translate_blocks_batch_respects_stop_flag | batch halts when stop_flag set |
| AC-4 | tests/test_sentence_mode_consistency.py::test_sentence_mode_outer_loop_breaks_when_stopped | remaining targets not processed |
| AC-5 | tests/test_sentence_mode_consistency.py::test_verify_and_fill_detects_sentence_mode_failures | verify_and_fill_tmap retries failed block |
| AC-6 | tests/test_sentence_mode_consistency.py::test_translate_texts_signature_unchanged | signature unchanged |
| AC-7 | tests/test_translation_strategy.py | 389-baseline maintained, new tests pass |
| AC-7 | tests/test_translation_profiles_scenarios.py | 389-baseline maintained, new tests pass |

Ladder (per test-plan.md, run via `cdd-kit test run`): collect -> targeted -> changed-area -> full. Do not run broad pytest before targeted and changed-area pass; stop at first failure per phase.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- backend-engineer must NOT touch: API routes, response schemas, env vars, document processors, or the non-SENTENCE_MODE path beyond what IP-1..IP-4 require.
- `translate_texts` signature stays unchanged (AC-6); `translate_blocks_batch` `stop_flag` is an optional kwarg default None so existing callers are unaffected.
- Do not re-copy design/test/CI/contract prose; follow source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved (CER-001 is pending and not required for these four fixes).

## Known Risks
- AC-5 detectability is already partial (bug-fix-engineer H-5): the inline marker matches `_FAILURE_PATTERNS` and retry uses the tmap KEY, so FIX 1 is a behavioral/readability consistency fix, not a retry-correctness fix. The AC-5 test must assert placeholder content, not retry breakage.
- IP-3 threading must reach both `flush()` (real batch path) and `_fallback_individual()` (per-sentence fallback) or mid-batch stop only partially works.
- Line ranges cited come from bug-fix-engineer pointers; if they have drifted, re-locate via `.cdd/code-map.yml` before editing.
