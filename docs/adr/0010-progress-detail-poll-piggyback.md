# ADR 0010: Live pipeline-progress detail rides the existing poll as a single overwritten snapshot

## Status
proposed

## Context
The frontend job-progress UI shows only aggregate segment counts and a plain
`status_detail` string; users cannot see which pipeline stage (translate /
critique / QE-score / adopt) is running or on what content, and the ETA ignores
remaining critique+QE work. `GET /api/jobs/{id}` is already polled every 2s by
`useJobPolling.js`, and `translation_service` already reports coarse stage
progress upward via a `status_callback(str|None)` that `job_manager` binds to
`JobRecord.status_detail`. Intermediate layers (orchestrator, processors) only
forward that callable; they never construct its payload. Two boundary questions
arise: (1) whether to expose a live per-segment detail as a rolling history or a
single current snapshot, and (2) whether to add a new/streaming transport or
reuse the existing poll. Constraints: no heavy overhead on the hot translation
path, and additive backward-compatibility of the job-status contract.

## Decision
Capture only the CURRENT segment as a single mutable struct on `JobRecord`,
overwritten in place. Populate it by widening the *payload* of the existing
`status_callback` (from `str|None` to a small snapshot object) — which touches
only the producer (`translation_service`) and consumer lambda (`job_manager`),
not the payload-agnostic forwarders. Surface the snapshot as additive OPTIONAL
fields on the existing `GET /api/jobs/{id}` response, consumed via the existing
2s poll. Do NOT add a rolling-history buffer, a separate endpoint, or an
SSE/websocket streaming channel.

## Consequences
- O(1) per-job memory and one reference swap per stage transition — negligible
  hot-path cost across the 50-job cap.
- No new transport/availability surface; the feature inherits the poll's 2s
  granularity, which is adequate for human monitoring of long jobs.
- New fields are null in legitimate cases (job start, critique/QE disabled,
  mid-transition, non-translation stages) — frontend and schema must tolerate
  absence; rollback is a trivial commit revert.
- A future need for true real-time streaming or a scrollback log would require
  reopening this decision — engineers must not silently swap in SSE/websocket or
  a history buffer, since doing so re-introduces the transport and memory costs
  this ADR deliberately avoids.
- Reversal cost is low precisely because the shape is additive and in-memory
  only (never persisted).

## Amendment (post-planning, pre-implementation)
A live job hung 30+ min inside the LLM-as-judge phase (`quality_judge.run_judge_loop`,
`JUDGE_ENABLED=true`) on a single stuck panjit HTTP call, while the stage display
and ETA gave no signal. The original design scoped judge OUT of the structured
`current_stage`/snapshot fields and the BR-98 ETA. This poll-piggyback /
single-overwritten-snapshot decision is REAFFIRMED and now extended to cover
phase-3 (judge): `current_stage` gains a `judge` value; three additive OPTIONAL
fields (`current_segment_judge_tier` [enum 高/中/低, deliberately NOT a numeric-vs-string
union on `current_segment_qe_score`], `current_segment_judge_attempt`,
`current_segment_judge_substep`) ride the same 2s poll; and BR-98 gains a phase-3
ETA term (omitted when `JUDGE_ENABLED=false` or the winning provider is `deepseek`
per BR-97). Surfacing the per-block scoring sub-step requires one additive OPTIONAL
snapshot-callback param on `run_judge_loop` (default `None`) — consistent with this
ADR's "widen the existing hook, add no new transport" principle.

This display change makes a judge hang OBSERVABLE (a static "judge · block N · attempt
M · scoring" panel) but does NOT fix it. The judge loop's missing cancellation check
and the cloud client's missing total-timeout guard are corrected independently in a
SEPARATE change (`qa-pipeline-consolidation`), which is explicitly out of scope here.
The two decisions are decoupled: this ADR only governs visibility/ETA, not pipeline
control flow.
