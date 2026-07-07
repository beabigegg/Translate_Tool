# Archive: translation-progress-detail-ui

## Change Summary
The final change of the 7-change series. Gives a translator monitoring a long job a
live view of which pipeline stage is running (translate / critique / QE-score / adopt /
judge) and on what content, plus an ETA covering the full remaining pipeline including
judge work. Purely additive/observational — no execution-behavior change. Deliberately
sequenced LAST so it wires once against the now-final round-based critique loop (#5) and
the judge call points with cancellation (#2/#3). Tier 2. Implemented by a backend-engineer
agent (17 IPs, backend + frontend), independently qa-reviewed.

## Final Behavior
- `GET /jobs/{id}` returns 8 new optional/nullable progress-detail fields (5 core + 3
  judge: tier 高/中/低, attempt, substep scoring/retranslating); `current_stage` gains `judge`.
- `JobRecord.current_segment` is a single O(1) reference overwrite (never appended), written
  via a widened `status_callback` mapped onto the round-based critique loop and via an
  additive FAIL-SOFT `snapshot_cb` in `run_judge_loop` (a raising callback cannot abort the
  judge loop; composes with the existing cancel_event/stopped machinery).
- Multi-phase ETA (BR-105): translate / critique+QE / judge terms; phase-3 omitted when
  JUDGE_ENABLED=false or provider is deepseek (BR-97).
- Frontend `StageDetailPanel`/`StageBadge`: stage + judge tier/attempt/substep, null-tolerant;
  `qualityTier` hex migrated to CSS tokens.

## Final Contracts Updated
- api-contract.md JobStatus +8 fields + `judge` enum + drift close (0.10.1→0.10.2, openapi regen).
- business-rules.md BR-105 `eta-multi-phase-pipeline` (renumbered from the plan's BR-98, taken by #2).
- data-shape-contract.md +8 optional columns (0.17.1→0.17.2).
- css-contract.md StageDetailPanel/StageBadge row + design-tokens.md `--color-stage-*`/tier tokens (0.3.0→0.3.1).
- CHANGELOG ×4.

## Final Tests / Verification
- 5 new backend test files + adjacency mock fixes; frontend TranslationProgress.test.jsx.
- Full suite 1187 passed, 0 failed; frontend `npm test` 10 pass; validate --contracts/--versions +
  openapi --check green; 4 evidence phases green.
- qa-reviewer: release-ready-with-notes, 0 blocking code bugs (re-ran 23 new + 90 related tests).

## Production Reality Findings
- **Additive kwargs on the judge/critique seams break test fakes — the THIRD recurrence.**
  Adding `snapshot_cb` to `run_judge_loop` and `on_scored` to `_batched_critique_adopt` broke
  fake `run_loop` side_effect signatures in `test_orchestrator_judge.py` and the
  `_batched_critique_adopt` lambda in `test_fewshot_glossary.py`, and the `_make_job()` MagicMock
  helpers failed JobStatus pydantic validation once new fields existed — the same class of
  breakage seen when #3 added `cancel_event` and #5 added the batched-adopt path.
- Known non-blocking (surfaced in PR): retranslating attempt counter can display "N / 3" with
  N>3 (cumulative retranslate count vs static display denominator) — cosmetic; and the new panel
  has component tests but no rendered screenshot (human visual spot-check recommended before wide rollout).

## Lessons Promoted to Standards
1. **[promote-to-guidance]** `CLAUDE.md` cdd-kit:learnings — adding an additive optional
   kwarg/callback to the judge/critique seams (`run_judge_loop`, `_batched_critique_adopt`,
   `status_callback`) predictably breaks test fakes that reproduce the signature and `_make_job`
   pydantic mock helpers; grep for fake `run_loop`/`side_effect` signatures and `_make_job`-style
   mocks and update them in the same change (recurred in #3/#5/#7).

## Follow-up Work
- Human visual/UX spot-check of StageDetailPanel (incl. the "N / 3" attempt-counter cosmetic).
- Optional: add a `response-samples.json` entry for the modified `GET /jobs/{id}` (harness-level shape coverage).

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
