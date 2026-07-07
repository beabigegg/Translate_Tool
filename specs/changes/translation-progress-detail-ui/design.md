# Design: translation-progress-detail-ui

> **Implementation is DEFERRED pending explicit user approval** (per change-request.md
> `## Constraints`: STOP after implementation-plan.md; no edits to `app/backend/` or
> `app/frontend/` this pass). This is a PLANNING artifact only.

## Summary
Additively extend the polled `GET /api/jobs/{id}` payload with a small, single-overwrite
"current segment" snapshot (stage + source + draft + QE/critique score + adopted result, plus
judge-phase tier/attempt/substep) so the frontend can show which pipeline stage
(translate / critique / QE-score / adopt / judge) is running and on what content, and replace
the single-phase ETA with a multi-phase heuristic that also amortizes remaining critique+QE
**and judge** work. The judge phase (`quality_judge.py`, `JUDGE_ENABLED=true`) is folded in per
the post-planning scope amendment: a live incident hung 30+ min inside the judge phase while the
stage display and ETA gave no signal, so judge is now a first-class stage/snapshot/ETA term. The snapshot is captured by widening the *payload*
of the existing `status_callback` mechanism (the same hook that already sets `status_detail`),
written in-place onto `JobRecord`, and surfaced through the existing 2s poll — no new endpoint,
no streaming channel, no rolling history. See ADR-0010 for the poll-piggyback / single-snapshot
trade-off. Contract-reviewer's findings (`agent-log/contract-reviewer.yml`) govern the
authoritative schema, the additive-compat precedent, and the pre-existing drift to close.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| JobStatus response schema | `app/backend/api/schemas.py` (JobStatus, L23) | add 8 OPTIONAL/nullable fields — the original 5 (`current_stage` [enum now incl. `judge`], `current_segment_source`, `current_segment_draft`, `current_segment_qe_score`, `current_segment_adopted`) plus 3 judge-phase fields (`current_segment_judge_tier`, `current_segment_judge_attempt`, `current_segment_judge_substep`) |
| Job status route + ETA calc | `app/backend/api/routes.py` (L290-371) | populate new fields from `JobRecord`; replace single-phase ETA (L318-320) with the multi-phase (translate / critique+QE / judge) heuristic |
| Job state store | `app/backend/services/job_manager.py` (JobRecord L80; callback L388; judge call site L472-518) | add one mutable `current_segment` struct field; widen the callback lambda to also write the struct; track per-phase throughput timestamps for ETA. At the judge call site, write the judge snapshot (`stage="judge"`, source/draft/attempt/substep) directly onto the struct from the `_translate_fn` closure (retranslate sub-step) and from a snapshot callback passed into `run_judge_loop` (scoring sub-step); track judge-iteration timestamps for the phase-3 ETA term |
| Translation/critique producer | `app/backend/services/translation_service.py` (critique loop L351-417) | at each stage transition, emit the structured snapshot through the widened `status_callback` (source/draft already in hand; score from `_critique_gate_adopt`) — a cheap reference assignment |
| Judge loop producer | `app/backend/services/quality_judge.py` (`run_judge_loop`/`_run_judge_loop_impl` L278-444) | accept an OPTIONAL snapshot callback (additive param, default `None`) so the per-block scoring sub-step, attempt index, and just-computed aggregate tier become observable — without it, a stuck `evaluate()` scoring call is invisible (the incident's exact failure mode) |
| Progress display | `app/frontend/src/components/domain/TranslationProgress.jsx` (rendered in `pages/TranslatePage.jsx` L327) | add a conditionally-rendered StageDetailPanel consuming the new fields, incl. the judge stage (tier badge 高/中/低, attempt `N`/`JUDGE_MAX_ITERATIONS`, scoring-vs-retranslating substep); also migrate its hardcoded hex (`qualityTier`, L4-7) to tokens while touched |
| Polling hook | `app/frontend/src/hooks/useJobPolling.js` | no change — new fields flow through the existing `fetchJobStatus` poll unmodified |
| i18n stage labels | `app/frontend/src/i18n/zh-TW.js`, `en.js` | add stage-label strings (translate/critique/qe-score/adopt/judge) + judge substep labels (scoring/retranslating) |
| Contracts | see `## Contract Updates` below | api / css / design-tokens / business-rules / data-shape |

## Key Decisions

- **Current-only snapshot, NOT a rolling history** → rationale: the user's wording "目前進行到的"
  (currently at) and change-request `## Non-goals` both scope this to the *current* activity, not a
  scrollback log. A rolling buffer of N segments' source/draft/score/adopted strings would multiply
  per-job memory across the 50-job cap and add per-segment append cost on the hot path; a single
  overwritten struct is O(1) memory and one reference swap. → rejected: last-N ring buffer — cost/
  overhead not justified by an explicitly out-of-scope want (AC-8).

- **Extend the existing `status_callback` payload; surface via the existing poll — NOT a new endpoint
  or streaming channel** → rationale: `status_callback` is already threaded from `job_manager`
  through the orchestrator/processors to `translation_service`; the intermediate layers only *forward*
  the callable (they never construct its payload), so widening the payload type from `str|None` to a
  small snapshot object touches only the producer (`translation_service`) and the consumer lambda
  (`job_manager`) — no ripple into forwarders. The frontend already polls `GET /jobs/{id}` every 2s,
  so the snapshot rides that response for free. → rejected: (a) separate lightweight endpoint —
  duplicate JobRecord read + second poll loop for data that changes in lockstep with existing fields;
  (b) SSE/websocket streaming — a new transport/availability surface unjustified for a 2s-granularity
  display (ADR-0010).

- **New JobRecord fields are set only by the backend, null in several legitimate cases** (job just
  started; `CRITIQUE_LOOP_ENABLED=false` / `QE_ENABLED=false` so no critique/QE phase; mid-transition
  between stages; non-translation stages like output-assembly/audit/judge that set `status_detail`
  directly). This matches the `provider`/`warnings` nullability precedent and drives the data-shape
  entry and the frontend null-tolerance requirement (AC-7).

- **Add a `judge` value to the `current_stage` enum; do NOT conflate `qe` / `qe-score` with `judge`**
  → rationale (per this session's spec-drift-auditor findings): three distinct mechanisms exist and
  must stay distinct in the enum. (1) `qe-score` = the INLINE per-segment COMET critique gate inside
  `translation_service`'s critique loop (mechanism-1, hot path). (2) a post-job BULK COMET rescore
  (`GET /jobs/{id}/quality`, mechanism-2) is dashboard-only and already brief — it is NOT a
  `current_stage` value and is out of scope here. (3) `judge` = the LLM-as-judge re-translation gate
  (`quality_judge.run_judge_loop`, mechanism-3) that can loop up to `JUDGE_MAX_ITERATIONS` and was the
  30-min hang. → rejected: reusing a single `qe` label for both COMET rescore and the judge gate —
  it hides exactly the phase that hung and makes the stage display ambiguous.

- **Judge score tier gets its OWN field (`current_segment_judge_tier`, enum `高`/`中`/`低`|null); do
  NOT overload the numeric `current_segment_qe_score`** → rationale: the two are semantically and
  representationally different — COMET QE is a continuous 0–1 estimate rendered as a bar/percentage;
  the judge tier is a discrete LLM verdict driving loop control, rendered as a categorical badge. A
  `numeric|enum-string` union forces the frontend to type-sniff every poll and forces a `oneOf` into
  the OpenAPI schema and contract test, breaking the repo's monomorphic-field / additive-compat
  precedent. Cost is one extra nullable field, consistent with the additive-only migration. → rejected:
  union-typed `current_segment_qe_score` — cheaper in field count but pays for it in type ambiguity at
  every consumer. Judge blocks reuse `current_segment_source` / `current_segment_draft` unchanged
  (source text + current translation of the block being scored/retranslated); `current_segment_qe_score`
  and `current_segment_adopted` stay null during judge. Two more judge-only fields cover what the
  existing shape cannot express: `current_segment_judge_attempt` (1-based iteration vs
  `JUDGE_MAX_ITERATIONS`, a config constant surfaced via the existing config/settings surface, not
  repeated in every 2s poll) and `current_segment_judge_substep` (`scoring`|`retranslating`|null) — the
  substep is what makes the incident diagnosable: a stuck scoring call and a stuck retranslate call are
  now distinguishable, and either stays static-but-visible when genuinely hung.

- **Multi-phase ETA becomes a business rule (BR-98), NOT a silent implementation detail** → rationale:
  the repo BR-tags every quantified pipeline-behavior claim, and AC-5 needs a canonical, testable
  statement; contract-reviewer flagged that no BR currently governs `eta_seconds`/`segments_per_second`.
  → rejected: keep-as-implementation-detail — leaves AC-5 untestable against a contract and repeats the
  pre-existing drift pattern. **ETA heuristic (prose):** phase-1 (translation) uses the observed
  segment rate `segments_done / translate_elapsed`; phase-2 (critique+QE) uses the observed critiqued-
  segment rate `_critique_done / critique_elapsed` once that phase has started. Remaining time =
  `remaining_translate_segments / rate_translate + remaining_critique_segments / rate_critique`. Before
  the critique phase begins (so its rate is not yet observable), phase-2 is estimated as a coarse
  multiple of the translate cost using `CRITIQUE_MAX_ITERATIONS` as the extra-LLM-call factor, and is
  omitted entirely when `CRITIQUE_LOOP_ENABLED`/`QE_ENABLED` are false. **Phase-3 (judge)** mirrors
  phase-2: it uses the observed per-block judge rate `_judge_units_done / judge_elapsed` once the judge
  phase has started; before it starts (rate not yet observable) it is estimated as a coarse multiple of
  the per-segment translate cost scaled by `N_judge_blocks × JUDGE_MAX_ITERATIONS` (the max
  scoring+re-translation passes), exactly as phase-2 uses `CRITIQUE_MAX_ITERATIONS`. Phase-3 is
  **omitted entirely (term = 0)** when `JUDGE_ENABLED=false` OR when the winning translation provider is
  `deepseek` (BR-97 — judge is skipped for that provider), mirroring the phase-2 omission. Total
  remaining = phase-1 + phase-2 + phase-3 terms. All inputs are counters and timestamps already tracked
  (`_judge_retranslate_count`, `_judge_total`, judge start time) — no new dependency.

## Contract Updates (references, not re-derivations)
- **`contracts/api/api-contract.md` › Schemas › JobStatus** — add the 8 new optional fields (incl. the 3
  judge fields; `current_stage` enum gains `judge`; `current_segment_judge_tier` is enum `高`/`中`/`低`) AND close
  the pre-existing drift by adding the already-live `status_detail` and `layout_viz_available` rows
  (contract-reviewer `pre-existing-drift` pointer); minor version bump; then regenerate
  `contracts/api/openapi.yml` + `openapi.json` (export-check gate). This schema is authoritative;
  openapi.* are generated exports (contract-reviewer `contract-authority`).
- **`contracts/css/css-contract.md`** — add a component-rules row for the new StageDetailPanel/StageBadge
  following the JudgePanel/JudgeBadge precedent (L25-32), including an explicit "renders nothing when
  no current-segment detail / stage detail unavailable" visibility rule; colors via CSS vars only.
- **`contracts/css/design-tokens.md`** — add stage-color tokens (e.g. `--color-stage-translate`,
  `--color-stage-critique`, `--color-stage-qe`, `--color-stage-adopt`, `--color-stage-judge`) plus
  judge-tier tokens (高/中/低) before implementation ships; no hardcoded hex (this also covers migrating
  `TranslationProgress.jsx`'s existing `qualityTier` hex).
- **`contracts/business/business-rules.md`** — add **BR-98** (`eta-multi-phase-pipeline`) per the ETA
  heuristic above, including the phase-3 (judge) term and its `JUDGE_ENABLED=false`/`deepseek` (BR-97)
  omission (next free number after BR-97).
- **`contracts/data/data-shape-contract.md` › Optional Columns** — add a JobStatus/JobRecord entry for
  the 8 current-segment fields (incl. the enum-string `current_segment_judge_tier`), mirroring the
  `provider` (L33-36) and `warnings` (L38-41) precedent, documenting the null cases and backend-only
  origin.

## Migration / Rollback
Additive-only: 8 new OPTIONAL response fields (default null), new stage/judge-tier CSS tokens, one new
frontend subcomponent, one new BR, and one additive OPTIONAL param on `run_judge_loop` (default `None`,
so existing callers are unaffected). No existing field is renamed, removed, or retyped; the ETA change replaces
an internal calculation feeding an existing field (`eta_seconds`) whose type is unchanged. Rollback is
trivial — reverting the commit restores the prior payload; old clients already ignore unknown fields and
new clients treat the absent fields as null (AC-2, AC-7). No data migration, no state format change
(the snapshot lives only in the in-memory `JobRecord`, never persisted). Confirmed: rollback holds.

## Open Risks
- **Sequencing with `batch-critique-qe-scoring`** (change-classification `## Clarifications`, CER-002):
  that change restructures the same `translation_service.py` critique loop into round-based batches. The
  "current segment" concept must be re-mapped onto the batched shape; recommend landing that change
  first (or explicit coordination) so the snapshot hook is designed against the final loop shape. Owner:
  implementation-planner.
- **Read-scope note:** widening the `status_callback` *payload* was verified (via grep) to touch only
  `translation_service.py` + `job_manager.py` because `orchestrator.py`/`processors/*` merely forward
  the callable. If the implementation-planner finds a forwarder that *constructs* a payload, those files
  are outside current Allowed Paths and require a CER before edit.
- **`.cdd/code-map.yml` not consulted** for this design (frontend/backend ranges were located via
  targeted Grep/Read within Allowed Paths); acceptable here but flagged for transparency.
- **Judge scoring sub-step needs a callback into `run_judge_loop`.** Today only the `_translate_fn`
  closure (retranslate sub-step) touches `job.status_detail`; the per-block `self.evaluate()` scoring
  sub-step — where the incident's single stuck panjit HTTP call sat — emits nothing. Surfacing
  `substep="scoring"` and the attempt index therefore requires the additive snapshot-callback param on
  `run_judge_loop`; without it the scoring hang stays as opaque as it is today. Owner: implementation-planner.
- **This change makes a judge hang OBSERVABLE, it does NOT fix it.** The judge loop's missing
  cancellation check and the cloud client's missing total-timeout guard are real defects tracked in a
  SEPARATE change (`qa-pipeline-consolidation`), explicitly out of scope here. After this ships the UI
  can show "judge · block 3/12 · attempt 2/3 · scoring" which stays static if genuinely stuck, versus
  today's opaque unchanging `status_detail` string — but the job still hangs until that other change
  lands. Do not couple the two.
