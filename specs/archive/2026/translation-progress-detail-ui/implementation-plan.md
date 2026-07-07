---
change-id: translation-progress-detail-ui
schema-version: 0.1.0
last-changed: 2026-07-07
---

# Implementation Plan: translation-progress-detail-ui

> **IMPLEMENTATION IS DEFERRED pending explicit user approval in a later session.**
> Per `change-request.md` `## Constraints` ("STOP after implementation-plan.md ...
> do not modify `app/backend/` or `app/frontend/` in this pass"), this document is
> a PLANNING artifact only. The `backend-engineer` and `frontend-engineer` owners
> named below are **NOT to be commissioned, and no product/test/contract code is
> to be written, until the user explicitly approves implementation in a new
> session.** When that session opens, execute strictly from this packet; do not
> infer scope from chat history.

## Objective
Give a translator monitoring a long-running job an accurate, legible live view of
which pipeline stage is running (translate / critique / QE-score / adopt / **judge**)
and on what content, plus an ETA that covers the full remaining pipeline. Deliver this by
**additively** extending the polled `GET /api/jobs/{id}` payload with a single
overwritten "current segment" snapshot (**8 optional fields** — 5 core + 3 judge-phase)
and rendering it in a new frontend `StageDetailPanel`, and by replacing the single-phase
ETA with a **multi-phase heuristic (BR-98, `eta-multi-phase-pipeline`)** that also
amortizes remaining judge work. No new endpoint, no streaming, no rolling history.
Full rationale: `design.md`; poll-piggyback / single-snapshot trade-off:
`docs/adr/0010-progress-detail-poll-piggyback.md` (do not restate).

> **JUDGE-PHASE AMENDMENT (post-incident, IP-11..IP-17 below).** A live incident hung
> 30+ min inside the judge phase (`quality_judge.py`, `JUDGE_ENABLED=true`) while the
> stage display and ETA gave no signal. design.md / test-plan.md were amended by
> spec-architect / test-strategist to make judge a first-class stage/snapshot/ETA term.
> IP-11..IP-17 are the surgical delta; IP-1..IP-10's translate/critique/QE content is
> unchanged except where a count or name is load-bearing (noted inline).

## Execution Scope

### In Scope
- Backend: add 8 optional/nullable `JobStatus` response fields (5 core + 3 judge-phase);
  capture an in-place single-overwrite `current_segment` snapshot on `JobRecord` via the
  widened `status_callback` payload AND (for judge) via an additive OPTIONAL snapshot
  callback threaded into `quality_judge.run_judge_loop`; multi-phase ETA (translate /
  critique+QE / judge) computed in the job-status route.
- Frontend: new conditionally-rendered `StageDetailPanel` (+ `StageBadge`)
  subcomponent inside `TranslationProgress.jsx` covering the judge stage (tier badge
  高/中/低, attempt counter, scoring/retranslating substep); new i18n stage + substep
  labels; migrate the existing hardcoded `qualityTier` hex in that file to CSS tokens
  (in-scope cleanup because the file is already being touched — test-plan.md Notes).
- Contracts: api-contract.md JobStatus (+ close pre-existing drift + version bump +
  regenerate `openapi.yml`/`openapi.json`); css-contract.md; design-tokens.md;
  business-rules.md BR-98; data-shape-contract.md.
- Tests: the 5 new test files named in `test-plan.md` Acceptance Criteria → Test
  Mapping.

### Out of Scope
See `change-request.md` `## Non-goals` and `test-plan.md` `## Out of Scope` (do not
re-derive). Specifically NOT in scope:
- Rolling / scrollback history of past segments (design.md Key Decisions: current-only).
- New endpoint or SSE/websocket transport (rejected in ADR-0010).
- Any change to critique-loop / QE **execution behavior or performance** — that is
  the sibling change `batch-critique-qe-scoring` (this change is visibility only).
- Any change to `useJobPolling.js` (fields flow through the existing 2s poll unmodified).
- Pipeline-control / override actions (display-only).
- Editing `.github/workflows/contract-driven-gates.yml` for this change's own test
  surface (ci-gates.md Q1/Q2: zero workflow edits needed). The `validate --versions`
  CI-hardening step is a SEPARATE recommendation, not this change's scope.
- Opportunistic refactoring of any touched file beyond the specific edits below.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | backend/schema | Add 5 optional/nullable fields to `JobStatus` (`current_stage`, `current_segment_source`, `current_segment_draft`, `current_segment_qe_score`, `current_segment_adopted`) with default `None` | backend-engineer |
| IP-2 | backend/state | Add one mutable `current_segment` struct field to `JobRecord`; widen the callback lambda to also write the struct; track per-phase throughput timestamps for ETA | backend-engineer |
| IP-3 | backend/producer | In the critique loop, emit the structured snapshot through the widened `status_callback` at each stage transition (translate → critique → qe-score → adopt) as a cheap reference assignment | backend-engineer |
| IP-4 | backend/route+ETA | Populate the 5 new response fields from `JobRecord`; replace the single-phase ETA calc with the two-phase heuristic (BR-98) | backend-engineer |
| IP-5 | contracts/api | Add the 5 new rows + close pre-existing `status_detail`/`layout_viz_available` drift in api-contract.md JobStatus; minor version bump; regenerate `openapi.yml` + `openapi.json` | backend-engineer |
| IP-6 | contracts/data+business | Add data-shape-contract.md optional-columns entry (5 fields); add BR-98 (`eta-two-phase-pipeline`) to business-rules.md | backend-engineer |
| IP-7 | frontend/component | Add conditionally-rendered `StageDetailPanel`/`StageBadge` in `TranslationProgress.jsx` consuming the new fields; migrate existing `qualityTier` hex to tokens | frontend-engineer |
| IP-8 | frontend/i18n | Add translate/critique/qe-score/adopt stage-label strings to `zh-TW.js` and `en.js` | frontend-engineer |
| IP-9 | contracts/css | Add StageDetailPanel/StageBadge component-rules row (css-contract.md, JudgePanel precedent) + `--color-stage-*` tokens (design-tokens.md) | frontend-engineer |
| IP-10 | tests | Author the 5 test files per test-plan.md mapping | backend-engineer (backend 4) / frontend-engineer (TranslationProgress.test.jsx) |
| IP-11 | backend/schema | Add 3 more optional/nullable `JobStatus` fields (`current_segment_judge_tier` [enum `高`/`中`/`低`\|null], `current_segment_judge_attempt` [int\|null], `current_segment_judge_substep` [`"scoring"`/`"retranslating"`\|null], all default `None`) and add `judge` to the `current_stage` enum — 8 new fields total (extends IP-1) | backend-engineer |
| IP-12 | backend/judge-producer | Add an additive OPTIONAL snapshot callback param (default `None`) to `run_judge_loop` (quality_judge.py L278); thread it through `_run_judge_loop_impl` (L319) into the per-block loop, invoking it at the scoring sub-step (per block, with `attempt`=`iteration+1` and `substep="scoring"`) and the retranslating sub-step (`substep="retranslating"`); each invocation must be fail-soft (try/except around the call) so a raising callback cannot break the judge loop | backend-engineer |
| IP-13 | backend/state+wiring | Extend `JobRecord.current_segment` with the judge fields; at the judge call site (job_manager.py L472-518) pass a snapshot callback into `run_judge_loop` that writes `stage="judge"`/tier/attempt/`substep="scoring"` onto the struct, and in the existing `_translate_fn` closure (L493) write `substep="retranslating"`/attempt from `_judge_retranslate_count`; record a judge-phase start timestamp + iteration counters for the phase-3 ETA (extends IP-2) | backend-engineer |
| IP-14 | backend/route+ETA | Populate the 3 new judge response fields from `JobRecord`; extend the ETA calc with the phase-3 (judge) term per BR-98, omitting phase-3 (term=0) when `JUDGE_ENABLED=false` OR winning provider is `deepseek` (BR-97) (extends IP-4) | backend-engineer |
| IP-15 | contracts | api-contract.md JobStatus +3 judge fields + `judge` enum value + regenerate `openapi.yml`/`openapi.json`; business-rules.md rename BR-98 → `eta-multi-phase-pipeline` + add phase-3 term & BR-97 omission; data-shape-contract.md add the 3 judge fields (incl. enum-string `current_segment_judge_tier`); design-tokens.md add `--color-stage-judge` + judge-tier (高/中/低) tokens; css-contract.md add judge rendering + visibility rule (extends IP-5/IP-6/IP-9) | backend-engineer (api/data/business) / frontend-engineer (css/tokens) |
| IP-16 | frontend/component+i18n | Extend the EXISTING `StageDetailPanel`/`StageBadge` (IP-7 — do NOT add a new component) to render the judge stage: tier badge (高/中/低, reusing/paralleling the migrated `qualityTier` tokens), attempt counter (`N`/`JUDGE_MAX_ITERATIONS`), scoring-vs-retranslating substep label; null-tolerant when judge fields absent; add `judge` + substep (scoring/retranslating) labels to zh-TW.js/en.js (extends IP-7/IP-8) | frontend-engineer |
| IP-17 | tests | Rename `tests/test_eta_two_phase_heuristic.py` → `tests/test_eta_multi_phase_heuristic.py` (+ phase-3 cases); extend `test_jobstatus_stage_detail.py` (judge enum + 3 fields + null), `test_job_manager_current_segment.py` (judge snapshot writes), `TranslationProgress.test.jsx` (judge render + null-tolerance); add new `tests/test_quality_judge_snapshot_callback.py` (None=no-op / invocation-shape / fail-soft raising callback) — see test-plan.md AC-9 | backend-engineer (backend) / frontend-engineer (jsx) |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | `## Affected Components` table | authoritative per-file change list + line ranges |
| design.md | `## Key Decisions` (current-only; payload-widening; ETA prose) | implementation constraints |
| design.md | `## Contract Updates` | exact contract edits (do not re-derive) |
| design.md | `## Open Risks` (sequencing; forwarder read-scope) | rebase/CER constraints |
| `docs/adr/0010-progress-detail-poll-piggyback.md` | full ADR | poll-piggyback / single-snapshot rationale |
| agent-log/contract-reviewer.yml | `contract-authority`, `pre-existing-drift`, `compatibility-precedent`, `css-conventions` | schema authority, drift to close, additive precedent |
| test-plan.md | Acceptance Criteria → Test Mapping | tests to write/run |
| test-plan.md | Notes / Anti-tautology | mock-boundary + anti-tautology rules |
| ci-gates.md | Required Gates table + Q1–Q4 | verification commands; zero-workflow-edit fact |
| change-request.md | `## Non-goals`, `## Constraints` | out-of-scope + STOP boundary |
| change-classification.md | `## Inferred Acceptance Criteria` | AC-1…AC-8 definitions |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| `app/backend/api/schemas.py` | edit `JobStatus` (L23-48) | add the 5 core + **3 judge** optional/nullable fields (`current_segment_judge_tier`/`_attempt`/`_substep`), default `None`; `current_stage` enum gains `judge`; do NOT rename/remove/retype any existing field (AC-1, AC-2, AC-9). Insert after existing `warnings` (L48) (IP-1, IP-11) |
| `app/backend/services/job_manager.py` | edit `JobRecord` (~L80) + callback lambda (~L388) + **judge call site (L472-518)** | add one mutable `current_segment` struct field (holds stage/source/draft/qe_score/adopted **+ judge_tier/judge_attempt/judge_substep**); widen the callback so it also writes the struct; add per-phase throughput timestamps (translate / critique / **judge**) for ETA. At L472-518: pass a snapshot callback into `run_judge_loop` that writes `stage="judge"`/tier/attempt/`substep="scoring"`; in the existing `_translate_fn` closure (L493) write `substep="retranslating"` + attempt from `_judge_retranslate_count[0]`. Snapshot is O(1) memory, one reference swap — never a list/append (AC-6, AC-8, AC-9) (IP-2, IP-13) |
| `app/backend/services/quality_judge.py` | edit `run_judge_loop` (L278) + `_run_judge_loop_impl` (L319) | add an additive OPTIONAL `snapshot_cb=None` param on `run_judge_loop`, forward it into `_run_judge_loop_impl`; convert the per-block scoring comprehension (L359-362) to an explicit loop so the callback fires per block **before/around each `self.evaluate`** with `(block_id, attempt=iteration+1, substep="scoring")`; fire it again in the retranslate loop (L424-438) with `substep="retranslating"`. Wrap EVERY callback call in try/except (fail-soft — a raising callback must not abort the loop, matching this repo's judge fail-soft pattern; the whole loop is already inside the L298 exception boundary). Default `None` = complete no-op (AC-9) (IP-12) |
| `app/backend/services/translation_service.py` | edit critique loop (~L351-417) | at each stage transition emit the structured snapshot via the widened `status_callback` (source/draft already in hand; score from `_critique_gate_adopt`). Reference assignment only — no expensive synchronous work (AC-6). **Coordinate with `batch-critique-qe-scoring` — see Known Risks; the snapshot hook must map onto the final loop shape.** |
| `app/backend/api/routes.py` | edit job-status handler (~L290-371) | populate the 5 core + 3 judge response fields from `JobRecord.current_segment`; replace single-phase ETA (~L318-320) with the **multi-phase** heuristic (phase-1 translate / phase-2 critique+QE / phase-3 judge) per design.md Key Decisions / BR-98. Phase-3 term = 0 when `JUDGE_ENABLED=false` OR winning provider is `deepseek` (BR-97). Fields null in legitimate cases (job just started; `CRITIQUE_LOOP_ENABLED`/`QE_ENABLED`/`JUDGE_ENABLED` false; deepseek provider; non-judge stage; mid-transition) (IP-4, IP-14) |
| `app/frontend/src/components/domain/TranslationProgress.jsx` | edit (component 10-85; `qualityTier` 3-8) | add conditionally-rendered `StageDetailPanel`/`StageBadge` consuming the new fields; render nothing when no current-segment detail (AC-7); signal ongoing work when `segments_done==total` but stage is critique (AC-4); migrate `qualityTier` hardcoded hex to CSS tokens. **Judge stage (IP-16): same panel renders tier badge (高/中/低, reuse/parallel the migrated `qualityTier` tokens), attempt counter `N`/`JUDGE_MAX_ITERATIONS`, scoring/retranslating substep label; null-tolerant when the 3 judge fields are absent (older job / non-judge stage) (AC-9).** Rendered via `pages/TranslatePage.jsx` L327 (no structural change to TranslatePage expected beyond passing existing job status through) |
| `app/frontend/src/hooks/useJobPolling.js` | **no change** | new fields flow through existing `fetchJobStatus` poll unmodified |
| `app/frontend/src/i18n/zh-TW.js`, `app/frontend/src/i18n/en.js` | edit | add translate/critique/qe-score/adopt **+ judge** stage-label strings **+ judge substep labels (scoring/retranslating)** (IP-8, IP-16) |
| `contracts/api/api-contract.md` | edit JobStatus schema | add **8** rows (5 core + 3 judge) + `judge` enum value on `current_stage` + `status_detail`/`layout_viz_available` drift rows; minor version bump. NOTE: `pre-tool-use-contract-write.sh` may block Edit on this file — use the `cdd-kit contract` CLI for schema fields (pass ALL fields in one call) and Bash for frontmatter/prose per CLAUDE.md promoted learnings |
| `contracts/api/openapi.yml`, `contracts/api/openapi.json` | regenerate | `cdd-kit openapi export --out contracts/api/openapi.yml`; must match or export-check gate fails |
| `contracts/css/css-contract.md` | edit | add StageDetailPanel/StageBadge component-rules row (JudgePanel precedent L25-32) incl. "renders nothing when no detail" rule; colors via CSS vars only |
| `contracts/css/css-contract.md` (judge rule) | edit | add judge-stage rendering + "renders nothing when no detail" visibility rule onto the StageDetailPanel/StageBadge row (IP-9/IP-15) |
| `contracts/css/design-tokens.md` | edit | add `--color-stage-translate/-critique/-qe/-adopt/**-judge**` tokens + **judge-tier (高/中/低) tokens** (reuse/parallel the migrated `qualityTier` colors); no hardcoded hex (IP-9, IP-15) |
| `contracts/business/business-rules.md` | edit | add/rename BR-98 → **`eta-multi-phase-pipeline`** (next free number after BR-97), per design.md ETA prose, including the phase-3 (judge) term and its `JUDGE_ENABLED=false`/`deepseek` (BR-97) omission (IP-6, IP-15) |
| `contracts/data/data-shape-contract.md` | edit | add optional-columns entry for **all 8** fields (5 core + 3 judge incl. enum-string `current_segment_judge_tier`) (provider/warnings precedent L31-43), documenting null cases + backend-only origin (IP-6, IP-15) |
| `tests/test_jobstatus_stage_detail.py` | new (+judge) | AC-1/AC-2/AC-7 **+ AC-9** (`current_stage="judge"` enum, 3 judge-field shape, judge fields null outside judge stage) — extend `tests/test_jobstatus_download_url.py::_make_job()` mock shape, do not invent a parallel one |
| `tests/test_eta_multi_phase_heuristic.py` | new (**rename** from `test_eta_two_phase_heuristic.py`) | AC-5 phase-1/phase-2 cases carry over unchanged; **AC-9** adds phase-3 (judge) cases: max-iterations estimate before observed, blended once observed, omit when `JUDGE_ENABLED=false`, omit when winning provider is `deepseek` (BR-98) |
| `tests/test_job_manager_current_segment.py` | new (+judge) | AC-6/AC-8 — reference-assignment overhead + overwrite-not-append; **AC-9** — judge snapshot written onto `JobRecord` at both scoring and retranslating sub-steps |
| `tests/test_quality_judge_snapshot_callback.py` | **new** | AC-9 — `run_judge_loop` optional snapshot callback: `None`=complete no-op; invoked at scoring + retranslating sub-steps with attempt index; **a raising callback must NOT break the judge loop (fail-soft)** |
| `tests/test_translation_service_stage_snapshot.py` | new | AC-1 integration — call `translate_texts()` (NOT `translate_document()`); mock only the LLM client (`patch.object`, collection-time ref) |
| `app/frontend/src/components/domain/TranslationProgress.test.jsx` | new (+judge) | AC-3/AC-4/AC-7 — render, stage-label mapping, no-hardcoded-hex static assertion; **AC-9** — judge tier badge/attempt counter/substep label render + null-tolerance when judge fields absent / non-judge stage / older job |

## Contract Updates
Perform exactly these; do not restate full prose (design.md `## Contract Updates`,
contract-reviewer.yml).
- **API:** `contracts/api/api-contract.md › Schemas › JobStatus` — add the **8** new
  optional fields (5 core + 3 judge) + the `judge` value on the `current_stage` enum,
  AND close pre-existing drift by adding `status_detail` + `layout_viz_available` rows;
  minor version bump; regenerate `openapi.yml` + `openapi.json`. api-contract.md is
  authoritative; openapi.* are generated exports.
- **CSS/UI:** `contracts/css/css-contract.md` — StageDetailPanel/StageBadge
  component-rules row (JudgePanel precedent) + explicit visibility rule + **judge-stage
  rendering (tier badge / attempt / substep)**.
- **Env:** none.
- **Data shape:** `contracts/data/data-shape-contract.md › Optional Columns` — new
  entry for the **8** current-segment fields (incl. enum-string `current_segment_judge_tier`)
  (provider/warnings precedent), documenting null cases + backend-only origin.
- **Business logic:** `contracts/business/business-rules.md` — add/rename BR-98 to
  **`eta-multi-phase-pipeline`** per the design.md ETA heuristic, including the phase-3
  (judge) term and its `JUDGE_ENABLED=false`/`deepseek` (BR-97) omission.
- **CI/CD:** none for this change's own surface (ci-gates.md Q1/Q2/Q4). The
  `cdd-kit validate --versions` CI step is a separate recommendation, NOT part of
  this change.
- **Design tokens:** `contracts/css/design-tokens.md` — add `--color-stage-*` tokens
  (incl. `--color-stage-judge`) + **judge-tier (高/中/低) tokens** (reuse/parallel the
  migrated `qualityTier` colors).

## Test Execution Plan
Required phases (floor): `collect`, `targeted`, `changed-area`; add `contract`
(OpenAPI export-check + additive-compat) and `quality` per the ladder in
`test-plan.md` / `references/sdd-tdd-policy.md`. Evidence generated with
`cdd-kit test run`; the gate validates `test-evidence.yml`. Full mapping lives in
`test-plan.md` Acceptance Criteria → Test Mapping — the table below is the
selector fallback only.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_jobstatus_stage_detail.py | new fields present + correct stage enum values when populated |
| AC-1 (integration) | tests/test_translation_service_stage_snapshot.py | callback receives distinct stage/source/draft/score/adopted at each transition |
| AC-2 | tests/test_jobstatus_stage_detail.py | existing fields unchanged when new fields absent |
| AC-2 (contract) | cdd-kit openapi export --check --out contracts/api/openapi.yml | exit 0 (export fresh) |
| AC-3 | app/frontend/src/components/domain/TranslationProgress.test.jsx | StageDetailPanel renders content; badge label matches stage |
| AC-4 | app/frontend/src/components/domain/TranslationProgress.test.jsx | in-progress indicator when segments_done==total but stage is critique |
| AC-5 | tests/test_eta_two_phase_heuristic.py | translate-only, blended, max-iterations-factor, and disabled-critique cases all correct |
| AC-6 | tests/test_job_manager_current_segment.py | snapshot capture is reference assignment (negligible overhead) |
| AC-7 | tests/test_jobstatus_stage_detail.py | fields null when job just started / critique+QE disabled |
| AC-7 (resilience) | app/frontend/src/components/domain/TranslationProgress.test.jsx | no throw when new fields absent/partial mid-transition |
| AC-8 | tests/test_job_manager_current_segment.py | snapshot overwritten (not appended) across calls |
| AC-9 (schema) | tests/test_jobstatus_stage_detail.py | `current_stage` includes `judge`; 3 judge fields present with correct shape when judge active; judge fields null outside judge stage |
| AC-9 (wiring) | tests/test_job_manager_current_segment.py | judge snapshot written onto `JobRecord` at scoring AND retranslating sub-steps |
| AC-9 (ETA) | tests/test_eta_multi_phase_heuristic.py | phase-3 max-iterations estimate / blended-once-observed / omit when disabled / omit when provider is deepseek |
| AC-9 (callback) | tests/test_quality_judge_snapshot_callback.py | `None`=no-op; invoked at both sub-steps with attempt index; raising callback does not break the loop |
| AC-9 (frontend) | app/frontend/src/components/domain/TranslationProgress.test.jsx | judge tier badge/attempt/substep render; no throw when judge fields absent / non-judge stage / older job |

Anti-tautology (test-plan.md Notes): assert exact field VALUES not mere presence;
AC-8 calls the widened callback 3× and asserts only the last snapshot survives.
AC-9 callback fail-soft test must use a callback that actually raises and assert the
judge loop still returns a valid `JudgeResult` (not merely that no exception surfaced).
Mock boundary: HTTP tests mock `app.backend.api.routes.job_manager` (consumer
binding); integration test mocks only the LLM client — never internal
`translation_service` helpers.

## Handoff Constraints
- **STOP conditions:** Do NOT begin implementation until the user explicitly
  approves in a later session (change-request.md Constraints). If that approval is
  absent, report `blocked` and do nothing further.
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this
  plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report
  `blocked`.
- Keep implementation within the file-level plan. If a forwarder that *constructs*
  the `status_callback` payload is found (design.md Open Risks), it is outside
  current Allowed Paths — file a Context Expansion Request before editing; do not
  widen scope silently.
- Backend and frontend test files land under the existing blanket pytest / `npm
  test` gates automatically — no workflow edit (ci-gates.md Q1/Q2).

## Known Risks
- **Sequencing with `qa-pipeline-consolidation`** (judge-phase amendment): this change
  makes a judge hang OBSERVABLE (`judge · block N · attempt K · scoring/retranslating`
  stays static-but-visible when stuck); it does NOT fix it. The sibling change
  `qa-pipeline-consolidation` adds the missing judge-loop cancellation check + cloud-client
  total-timeout guard, and touches the SAME `quality_judge.py` `run_judge_loop` /
  `job_manager.py` L472-518 judge call site this amendment edits — the same class of
  sequencing/rebase risk this plan already carries with `batch-critique-qe-scoring` on the
  critique-loop region. **Recommended: coordinate landing order (ideally land or rebase this
  visibility change against `qa-pipeline-consolidation`'s cancellation/timeout edits so the
  additive snapshot callback and the new cancellation checks are threaded through the same
  loop revision), and do NOT couple the two changes.** (Per the launch instruction this
  planner did NOT read `specs/changes/qa-pipeline-consolidation/*` — it is a just-scaffolded
  empty-template sibling and cross-change reads are forbidden; this note rests solely on the
  task summary. Re-verify the exact seams when that change's design lands.)
- **Judge callback fail-soft is mandatory, not optional** (test-plan.md AC-9 resilience):
  the snapshot callback fires on the hot judge path around a potentially-stuck `evaluate()`
  call; wrap every invocation in try/except so a raising callback (or a callback that blocks
  briefly) can never abort the judge loop — matching this repo's established judge fail-soft
  pattern (the loop already sits inside the L298 exception boundary, but the callback must be
  guarded independently so a bug in the wiring cannot degrade judging).
- **Sequencing with `batch-critique-qe-scoring`** (design.md Open Risks;
  change-classification.md Clarifications; CER-002): that sibling change
  restructures the SAME `translation_service.py` critique-loop region into
  round-based batches. **Recommended constraint: land `batch-critique-qe-scoring`
  first, or explicitly coordinate/rebase**, then design the IP-3 snapshot hook
  against the final batched loop shape so the "current segment" concept still maps
  cleanly. Do NOT collapse the two changes. (This planner did not read that sibling
  change's source per the task's hard-forbidden-path instruction; this constraint
  rests on the summaries in THIS change's change-request.md `## Known Context` and
  design.md `## Open Risks`.)
- **Callback-payload read-scope** (design.md Open Risks): widening the
  `status_callback` payload was verified to touch only `translation_service.py` +
  `job_manager.py` because orchestrator/processors merely forward the callable. If
  implementation finds a forwarder that constructs the payload, CER required before edit.
- **Contract-write hook friction:** `pre-tool-use-contract-write.sh` may block Edit
  on `contracts/api/api-contract.md`; use `cdd-kit contract` CLI (all schema fields
  in one call) + Bash for frontmatter/prose (CLAUDE.md promoted learnings).
- **OpenAPI staleness:** forgetting `cdd-kit openapi export` after the api-contract
  edit fails the export-check gate — regenerate both `openapi.yml` and `openapi.json`.
- **CI version-bump gap** (ci-gates.md Q3): `cdd-kit validate --versions` currently
  runs only in the local, bypassable pre-commit hook, not in CI. The api-contract
  version bump this change requires is therefore not server-side enforced until the
  recommended CI step is separately approved. Informational — not this change's scope.
