# QA Report: translation-progress-detail-ui

## Verdict
**release-ready-with-notes** — no blocking correctness bugs (independent qa-reviewer pass that
re-ran the tests + validators, plus main-Claude verification).

## Evidence
- Full suite `pytest tests/` = **1187 passed, 4 skipped, 0 failed** (torch env). Frontend
  `cd app/frontend && npm test` = 10 passed (2 files). `cdd-kit validate --contracts`/`--versions`
  + `openapi export --check` green. 4 evidence phases (collect/targeted/changed-area/contract) passed.
- BR-105 (`eta-multi-phase-pipeline`) collision-free (highest prior BR was 104). Versions bumped:
  api 0.10.1→0.10.2, business 0.24.1→0.24.2, data 0.17.1→0.17.2, css 0.3.0→0.3.1; CHANGELOG entries;
  openapi.yml/json regenerated.

## qa-reviewer confirmations (all 7 focus areas sound)
1. **AC-6/AC-8** — `JobRecord.current_segment` is a single-object overwrite at all 3 write sites
   (job_manager.py:390/557/574); never appends; tests prove only the last write survives.
2. **Judge `snapshot_cb` fail-soft** — both invocations (quality_judge.py scoring + retranslating)
   wrapped in try/except, placed AFTER the `_cancelled()` checks; the cancel_event/`_stopped()`
   machinery (from qa-judge-hang-recovery) is untouched; the fail-soft test uses a callback that
   actually raises and asserts a valid JudgeResult still returns.
3. **`status_callback` widening** — every processor only forwards the callable; sole invokers are in
   translation_service.py (2-arg) + `_status_cb` (segment=None default), so the final 1-arg
   `status_callback(None)` still clears both; `_batched_critique_adopt`'s List[str] return + strict-`>`
   adoption unchanged; the `on_scored` hook observes the SAME captured scores (no re-scoring).
4. **Multi-phase ETA** — every division guarded (no None-arith / div-by-zero); phase-3 (judge) term
   omitted when `JUDGE_ENABLED=false` OR winning provider is `deepseek` (BR-97, case-insensitive).
5. **Additive/optional fields** — all 8 JobStatus fields default None; no rename/retype; route reads
   via getattr/guarded access so older/partial payloads don't throw; `current_stage` gains `judge`.
6. **Non-tautological tests** — assert exact stage order, ETA numbers, surviving-snapshot values,
   judge tier/attempt/substep; uses `translate_texts` (not the wrong-entry-point wrapper).
7. **Deviations sound** — `JUDGE_MAX_ITERATIONS_DISPLAY=3` is a documented display-only denominator;
   4 new `--color-quality-tier-*` tokens migrate hardcoded hex, distinct from the judge 3-level scale.

## Non-blocking notes (carried to PR + follow-up)
- **N1** — the modified `GET /jobs/{id}` (JobStatus +8 fields) has no entry in the contract
  `response-samples.json` harness; `validate --contracts` still reports `response shape passed`
  (not skipped) and `test_jobstatus_stage_detail.py` asserts the exact HTTP payload for all 8 fields
  via TestClient, so shape coverage exists — harness-level sample is an optional follow-up.
- **N2** — the retranslating-substep judge attempt counter is the cumulative retranslate-call count,
  so on multi-block jobs the UI can display e.g. "5 / 3" (the display denominator is the static
  `JUDGE_MAX_ITERATIONS_DISPLAY`). Documented design choice; **cosmetic UI-polish only, no functional
  impact** — flagged for a frontend/ui-ux follow-up if pursued.
- **N3** — the new `StageDetailPanel`/`StageBadge`/`JudgeTierBadge` have component tests but no rendered
  screenshot. A human visual/UX spot-check is recommended before wide rollout (this is an observational,
  additive, null-tolerant panel; not a blocker).

## Owner / follow-up
- Human visual + UX spot-check of StageDetailPanel (incl. the N2 "N / 3" attempt-counter cosmetic) →
  before wide rollout. Not automatable in this pipeline; not a correctness blocker.
