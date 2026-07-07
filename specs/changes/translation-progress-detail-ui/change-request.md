# Change Request

## Original Request

Improve the frontend job-progress display so it shows real-time pipeline
detail, not just aggregate segment counts.

Current behavior (user-observed, live example from a running job): the
progress UI shows only "處理中: <filename>", "555 / 555 段" (segments
done/total), "0.0 段/秒" (segments/sec rate), and "預計剩餘 7919s" (ETA). Once
all segments finish the initial translation pass, the pipeline moves into the
critique loop / QE (COMET) scoring phase (see `status_detail` field like
"品質審校中… (12/72)" produced by `app/backend/services/job_manager.py` and the
critique loop in `app/backend/services/translation_service.py`) which can take
a very long time (this is also the subject of a separate, already-planned
change: `batch-critique-qe-scoring`, `specs/changes/batch-critique-qe-scoring/`).
The current frontend progress display does not surface this critique/scoring
phase at all — the user sees "555/555 段" (looks 100% done) while the job is
actually still running for a long time in the background doing critique+QE,
and the ETA calculation (`segments_per_second`-based) does not account for the
remaining critique/QE work, producing wildly inaccurate remaining-time
estimates.

Desired change: the frontend progress display should show, for the
segment/file currently being processed, richer live detail reflecting the
actual translate → critique → QE-score → adopt pipeline stages, e.g.: the
current original source text, the translation obtained (draft), the
QE/critique score(s) computed, and the final adopted translation result
(draft vs. revised — whichever was kept). The user wants to be able to clearly
see, at a glance, which pipeline stage is currently running and on what
content, rather than just a flat segment counter. The remaining-time estimate
should also be improved to reflect the full remaining pipeline (translation +
critique + QE), not just remaining raw segment count.

## Business / User Goal

Give the user (a translator/reviewer monitoring long-running jobs) an
accurate, legible view of what the system is doing right now — which pipeline
stage (translate / critique / QE score / adopt), on what content — instead of
a segment counter that looks "done" while the job is still running for a long
time in the background. Improve trust in the ETA so the user can plan around
it instead of dismissing it as unreliable.

## Non-goals

- Not changing the underlying critique-loop/QE execution behavior or its
  performance characteristics — that is the separate `batch-critique-qe-scoring`
  change. This change is about **visibility** into the existing pipeline, not
  its speed. Cross-reference that change for context only.
- Not building a full historical/scrollable log of every past segment's
  translate/critique/score detail — scope is the CURRENT segment/activity's
  live detail, unless the classifier or design finds a full history is cheap
  and clearly wanted (open question below).
- Not adding new user controls to intervene in the pipeline (e.g., manually
  overriding an adopted translation from this view) — display only.
- Not changing terminology review, job history, or other unrelated pages.

## Constraints

- Backend must expose whatever new real-time state is needed via the job
  status API (`GET /api/jobs/{id}` or a new/extended endpoint) — additive only,
  must not break the existing job status contract for other consumers.
- Must not add heavy overhead to the hot translation path (e.g., no expensive
  synchronous work solely to populate UI state) — capturing "current segment"
  snapshot data must be cheap relative to the LLM calls already happening.
- STOP after `implementation-plan.md` is ready — do not commission
  backend-engineer/frontend-engineer to write product code, and do not modify
  `app/backend/` or `app/frontend/` in this pass. Implementation is deferred to
  a later, separately-approved session.

## Known Context

- Job status polling: `app/frontend/src/hooks/useJobPolling.js` polls
  `GET /api/jobs/{id}` until terminal state.
- Job status fields observed live this session: `status`, `processed_files`,
  `total_files`, `current_file`, `segments_done`, `segments_total`,
  `file_segments_done`, `file_segments_total`, `elapsed_seconds`,
  `overall_progress`, `segments_per_second`, `eta_seconds`, `status_detail`
  (e.g. "品質審校中… (12/72)"), `quality_score_avg`, `judge_score`, etc. — see
  `app/backend/services/job_manager.py` (`JobRecord`) and
  `app/backend/api/schemas.py` for the authoritative current shape.
- Critique loop emits `status_callback(f"品質審校中… ({_critique_done}/{_segments_to_critique})")`
  in `app/backend/services/translation_service.py` — this is the only
  existing signal for the critique/QE phase, and it's a plain string, not
  structured per-segment detail (no source text, draft, score, or adopted
  result surfaced).
- Related change: `batch-critique-qe-scoring`
  (`specs/changes/batch-critique-qe-scoring/`) restructures the critique
  loop's internal QE call pattern (round-based batching) for performance —
  unrelated to this change's scope (visibility) but touches the same code
  region (`translation_service.py` critique loop), so the eventual
  implementation-planner for this change should account for both changes
  potentially touching overlapping lines and coordinate ordering/rebasing if
  both land close together.
- Frontend job-progress display: likely `app/frontend/src/pages/TranslatePage`
  (exact component TBD by classifier/frontend context).

## Open Questions

- Should the UI show only the CURRENT segment's live pipeline detail, or a
  short rolling history (e.g. last N segments)? User's request describes
  "目前進行到的" (currently at) — leaning toward current-only, but classifier/
  spec-architect should confirm the minimal-overhead design and whether a
  short rolling buffer is cheap enough to be worth it.
- Exact mechanism for the backend to capture and expose "current segment"
  detail: extend `JobRecord` with a small in-memory struct (source, draft,
  score, adopted, stage) updated in-place as translation/critique progress,
  polled the same way as existing fields — vs. a separate lightweight
  endpoint. Design decision, not user decision — spec-architect/
  implementation-planner should decide and document rationale.
- Whether the improved ETA should be a simple two-phase weighted estimate
  (translate-phase rate + critique-phase rate observed so far) or something
  more sophisticated — should stay simple/heuristic per existing
  `segments_per_second`-style calculation rather than introducing new
  dependencies.

## Scope Amendment (post-planning, pre-implementation)

A live job hung for 30+ minutes during the **judge phase** specifically
(`app/backend/services/quality_judge.py`, `JUDGE_ENABLED=true`) — same local
TCP ports unchanged the entire time (single stuck HTTP call to the panjit
judge endpoint, not a retry loop), `status_detail` frozen, ETA still showing a
large stale value. The original design.md deliberately scoped the judge phase
OUT of the structured `current_stage` snapshot and OUT of the BR-98 two-phase
ETA formula (judge only ever set the plain string `status_detail`) — meaning
this proposal, as originally designed, would NOT have helped the user notice
or diagnose that exact incident. This is the same problem this change exists
to solve, just in a third phase the original design didn't cover.

**Amendment**: extend the `current_stage` enum and the structured snapshot
fields, and the BR-98 ETA formula, to also cover the judge phase
(`run_judge_loop`/`_run_judge_loop_impl` in `quality_judge.py`, invoked from
`job_manager.py` around the existing `job.status_detail = "品質評審中…"` call
site). Re-run `spec-architect` (design.md + ADR-0010), then `test-strategist`
and `implementation-planner` for the resulting delta. `contract-manifest.md`
has been updated with CER-004 approving `app/backend/services/quality_judge.py`
as an allowed read path for this amendment.

Non-goal (unchanged): this amendment does NOT include fixing the judge loop's
missing cancellation check or the cloud client's missing total-timeout
guard — those are real defects, tracked separately in the new
`qa-pipeline-consolidation` change. This change remains display/ETA-only.
