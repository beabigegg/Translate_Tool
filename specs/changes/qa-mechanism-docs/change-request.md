# Change Request

## Original Request

The QA/quality pipeline has three independent quality mechanisms, built
across separate past changes, with no single place documenting how they
relate to each other. Verified this session via direct code read (not just
agent-reported):

1. **In-line critique loop** (`translation_service.py:59-96`,
   `_critique_gate_adopt`, invoked from the loop at ~L322-421) — per-segment,
   COMET *relative* comparison: LLM revises the draft, then
   `score_blocks(model, [(src,draft),(src,revised)])` decides whether to
   adopt the revision (strictly-greater-than wins, tie keeps draft). BR-89/90.
2. **Post-job bulk COMET rescore** (`job_manager.py:418-447`) — ONE batched
   `score_blocks()` call over every block after all files are translated,
   stored in `job.quality` (`JobQualityRecord`) purely for the
   `/jobs/{id}/quality` dashboard endpoint. Never triggers re-translation.
   BR-55/56.
3. **LLM-as-judge** (`quality_judge.py:355-444`, `_run_judge_loop_impl`) — a
   separate cloud/local LLM judges each block as *absolute* 高/中/低; anything
   not 高 triggers re-translation via `translate_fn` with feedback, up to
   `JUDGE_MAX_ITERATIONS` rounds. The ONLY mechanism that actually
   re-translates based on a quality verdict. BR-72-77.

Mechanisms (1) and (3) can disagree with no documented bridging behavior:
the judge can flag 低 and re-translate a segment the critique loop already
adopted (because COMET liked the revision), discarding that earlier work —
current code has no shared state between the two. Mechanism (2) is
redundant compute layered on top of what mechanism (1) already scored
per-segment, existing purely as a dashboard number.

Additionally, `contracts/api/api-contract.md:154` (`quality_score_avg`) and
`contracts/data/data-shape-contract.md:484-501` (`JobQualityRecord`) carry no
"advisory/non-gating" language — a user reading the API docs or UI could
reasonably (and wrongly) conclude a low `quality_score_avg` already triggered
a fix, when mechanism (2) never gates anything.

## Business / User Goal

Give future readers (contributors, this same audit process next time, the
user) one place that explains why three quality mechanisms exist, what each
one actually does, and — critically — that they are independent and
non-bridged by design (or, if the sibling `br92-rescore-resolution` change
decides otherwise, documents whatever bridging was actually built). Prevent
the API/UI surface from implying a gating relationship that doesn't exist.

## Non-goals

- Not changing any of the three mechanisms' actual behavior — this change is
  contracts/documentation only. Behavior changes are the sibling changes:
  `br92-rescore-resolution` (mechanism 2's phantom rescore rule),
  `qa-judge-provider-consistency` (mechanism 3's re-translation provider),
  `qa-judge-hang-recovery` (mechanism 3's cancellation/timeout). This change
  `depends-on` all three (see `tasks.yml`) so its documentation reflects
  FINAL, post-fix behavior rather than needing a rewrite afterward.
- Not touching `batch-critique-qe-scoring`'s scope — that change's own
  design.md/business-rule updates already cover mechanism (1)'s batching;
  this change should reference, not duplicate, that work.
- Not touching `translation-progress-detail-ui`'s scope — that change's own
  design.md already documents (post-amendment) the display-layer distinction
  between mechanisms; this change is the underlying business-rule/contract
  documentation, not the UI.

## Sibling Decisions (now finalized — this change's actual input)

- **`br92-rescore-resolution`**: user confirmed **RETIRE**. BR-92 is deleted
  from `business-rules.md` (was mechanism (2)'s phantom rescore→re-translate
  claim). Mechanism (2) (`job_manager.py:418-447`, post-job bulk COMET
  rescore) is confirmed to remain permanently dashboard-only/advisory —
  there is no future bridging logic to document; this change's job is to
  make that permanence explicit in the API/data-shape surfaces.
- **`qa-judge-provider-consistency`**: new **BR-98**
  (`judge-retranslation-provider-consistency`) — mechanism (3)'s
  re-translation callback now explicitly routes through the judge's own
  cloud provider via a new `QualityJudge.translation_client` property,
  decoupled from whatever provider won main translation.
- **`qa-judge-hang-recovery`**: new **BR-99** (`judge-loop-cancellation`) and
  **BR-100** (`cloud-llm-total-duration-ceiling`) — mechanism (3) gains
  cooperative cancellation and a wall-clock ceiling; a new `judge_status`
  value `"stopped"` is added (4th enum value, alongside
  available/disabled/unavailable).

This change's three-mechanism relationship table should therefore describe:
mechanism (1) critique loop (BR-89/90, relative COMET comparison, batched
per `batch-critique-qe-scoring`), mechanism (2) dashboard-only bulk COMET
(BR-55/56, permanently advisory post-BR-92-retirement), and mechanism (3)
LLM-judge (BR-72-77, the pre-existing BR-97, and new BR-98/99/100, the only mechanism that gates
re-translation) — plus the "no bridging between (1) and (3)" disagreement
behavior originally flagged, which none of the three sibling changes
resolved (it was out of scope for all three) and remains true today.

## Constraints

- Must not restate content that already lives correctly in BR-55/56, BR-72-77,
  BR-89/90, BR-98, BR-99, BR-100 — add a short cross-referencing "how these
  relate" section/table, not a rewrite of each existing rule.
- Must add explicit "advisory/non-gating" language to the `quality_score_avg`
  and `JobQualityRecord` surfaces without changing their schema (fields,
  types, nullability) — documentation-only edit to those contract entries.
- STOP after `implementation-plan.md` — this change's "implementation" is
  itself contract/doc edits, but per this repo's established pattern, actual
  contract file edits still happen in a later, separately-approved
  implementation pass (likely `contract-reviewer`/`spec-architect` drafting
  exact wording now, actual edits applied then) — confirm with the user
  whether doc-only changes should skip the backend/frontend-engineer stop
  entirely or still defer, given `pre-tool-use-contract-write.sh`
  (`CDD_CONTRACT_WRITE_STRICT=1`) blocks direct Edit/Write on
  `contracts/api/api-contract.md` and requires the `cdd-kit contract` CLI or
  Bash string-replace instead.

## Known Context

- This change intentionally has the widest/latest dependency chain
  (`depends-on: br92-rescore-resolution, qa-judge-provider-consistency,
  qa-judge-hang-recovery` — see `tasks.yml`) so the documentation it writes
  describes final, settled behavior rather than needing revision once those
  three land.
- Source of this finding: a `spec-drift-auditor` pass this session covering
  the whole QA pipeline, cross-checked against direct reads of
  `translation_service.py`, `job_manager.py`, `quality_judge.py`, and
  `contracts/business/business-rules.md`.

## Open Questions

- Where should the "how the three mechanisms relate" note live — a new
  Decision Table in `business-rules.md` (matching the existing "Table U — LLM
  judge loop behavior" pattern at line ~357), a short prose section, or a new
  ADR? Deferred to contract-reviewer/spec-architect.
- Exact wording for the "advisory/non-gating" API/data-shape note — deferred
  to contract-reviewer.

## Requested Delivery Date / Priority

No fixed deadline. Lowest priority / last-in-sequence of the four sibling
changes (deliberately depends on the other three) — plan now, but do not
start its actual planning agents until the other three are far enough along
that their final behavior is known.
