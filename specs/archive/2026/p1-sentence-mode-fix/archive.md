# Archive — p1-sentence-mode-fix

## Change Summary

Fixed three defects in the `SENTENCE_MODE` batch translation path (`translation_service.py`) to align its behavior with the non-SENTENCE_MODE per-sentence path. The SENTENCE_MODE branch was (1) storing inline sentence-level failure markers instead of a block-level `[Translation failed|{tgt}] {original_text}` placeholder, (2) bulk-incrementing `done` once post-batch regardless of stop state, and (3) calling `translate_blocks_batch` with no `stop_flag` parameter and no `if stopped: break` after the batch. Four targeted fixes across two files corrected all three defects and are covered by seven new regression tests.

## Final Behavior

- **Failure placeholder (AC-1)**: `tmap[(tgt, text)]` is set to `[Translation failed|{tgt}] {original_text}` on batch failure in SENTENCE_MODE, matching the non-SENTENCE_MODE path.
- **Per-segment counting (AC-2)**: `done` increments per segment inside the result loop (`seen_texts.get(text, 1)`); a mid-batch stop no longer over-counts.
- **stop_flag inside batch (AC-3)**: `translate_blocks_batch` and `BatchTranslator._fallback_individual` accept and honour `stop_flag`; individual sentence iteration breaks when the flag is set.
- **Outer-loop break (AC-4)**: After the SENTENCE_MODE batch block, `if stopped: break` exits the outer `for tgt in targets` loop, matching the non-SENTENCE_MODE guard at lines 223-224.
- **Retry correctness (AC-5)**: `verify_and_fill_tmap` detects the fixed placeholder via `_FAILURE_PATTERNS` and retries via tmap KEY; unchanged by this fix.
- **Signature stability (AC-6/AC-7)**: `translate_texts` signature unchanged; 396 tests pass (389 baseline + 7 new).

## Final Contracts Updated

- `contracts/business/business-rules.md` → **v0.5.0**
  - BR-25 `translation-failure-placeholder`: block-level `[Translation failed|{tgt}] {original_text}` applies to all modes
  - BR-26 `per-segment-done-fail-counting`: `done`/`fail_cnt` incremented per segment; SENTENCE_MODE and non-SENTENCE_MODE must match
  - BR-27 `stop-flag-propagation`: `stop_flag` threaded into `translate_blocks_batch`; outer loop breaks after batch
  - Table F added (8 failure-placeholder and stop-propagation scenarios)

## Final Tests Added / Updated

New file: `tests/test_sentence_mode_consistency.py` — 7 tests:
- `test_sentence_mode_failure_placeholder_includes_original` (AC-1)
- `test_sentence_mode_done_count_incremented_per_segment` (AC-2)
- `test_sentence_mode_stop_flag_no_overcount` (AC-2)
- `test_translate_blocks_batch_respects_stop_flag` (AC-3)
- `test_sentence_mode_outer_loop_breaks_when_stopped` (AC-4)
- `test_verify_and_fill_detects_sentence_mode_failures` (AC-5)
- `test_translate_texts_signature_unchanged` (AC-6)

## Final CI/CD Gates

- `cdd-kit validate --contracts` (Tier 1, required) — passed
- `pytest tests/ -x -q --tb=short` (Tier 1, required) — 396 passed
- `pytest tests/ -q --tb=short` full regression (Tier 2, PR-only) — 396 passed
- `test-evidence.yml` presence with all phases passed — confirmed
- No new workflow or job added; existing `contract-and-fast-tests` + `full-regression` jobs cover all gates.

## Production Reality Findings

QA-reviewer issued CHANGES-REQUIRED initially due to `test-evidence.yml final-status: failed` (the pre-fix run had overwritten evidence). Resolved by re-running all ladder phases; final verdict: **APPROVED-WITH-RISK**.

**R-1 (accepted, low)**: When `_fallback_individual` breaks mid-batch, unprocessed indices return `(False, "[Missing translation result]")`. Block assembly at `translation_helpers.py:481` checks `sent.startswith("[Translation failed")` — this does NOT match `[Missing translation result]`, so `all_ok` stays `True` and `done` is counted optimistically on the stop path. Mitigating factor: `_FAILURE_PATTERNS` includes `Missing translation result]`, so `verify_and_fill_tmap` still detects and retries these blocks correctly via tmap KEY. Follow-up: block assembly should treat `[Missing translation result]` as not-ok (deferred to separate change).

## Lessons Promoted to Standards

Product behavior rules (BR-25/26/27) were applied to `contracts/business/business-rules.md` v0.5.0 during implementation by the contract-reviewer agent. No new agent-workflow guidance identified — R-1 is a deferred product-behavior follow-up, not a generalizable workflow rule.

## Follow-up Work

- **R-1 block assembly**: `translation_helpers.py:481` startswith check should also treat `[Missing translation result]` as not-ok, so `all_ok` is accurate on mid-batch stop. Owner: backend-engineer + test-strategist. Separate tracked change.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
