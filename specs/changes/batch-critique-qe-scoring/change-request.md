# Change Request

## Original Request

Batch the per-segment critique-loop QE (COMET) scoring calls in
`app/backend/services/translation_service.py` (`_critique_gate_adopt` /
the critique loop at `translation_service.py:354-414`) to reduce redundant
PyTorch Lightning Trainer startup overhead.

Currently `score_blocks()` is called once per (segment, iteration) — up to
3x per segment given `CRITIQUE_MAX_ITERATIONS=3` with no early-exit — and
each call re-instantiates a Lightning Trainer even though only 2 items
(draft, revised) are scored per call. Observed in production logs: every
single translated segment produces a full Lightning startup banner
("GPU available: True (cuda)", "TPU available: False", litlogger/litmodels
tips, `LOCAL_RANK` banner, "Predicting DataLoader 0") for a 2-item score,
repeated up to 3x per segment — this dominates wall-clock time on
multi-hundred-segment documents.

Proposed direction: restructure to a round-based loop — for each of the
`CRITIQUE_MAX_ITERATIONS` rounds, run revision for all pending segments
first, then issue ONE batched `score_blocks()` call across all segments'
`(src, draft)`/`(src, revised)` pairs for that round, then apply the
per-segment adoption decision, before moving to the next round.

Constraints to preserve:
- Same critique cache key scheme (`cache_model_key + ":c"`) — already-cached
  segments must continue to be skipped before any critique work runs, so no
  previously critiqued/translated document needs to be re-processed.
- Same adoption rule: adopt `revised` only if its QE score is strictly
  greater than `draft`'s — a tie keeps `draft`.
- Same per-segment exception/timeout isolation — one segment's failure must
  not abort the round for other segments (current code `break`s only that
  segment's inner loop on exception/timeout).
- Same COMET OOM retry batch-size ladder in
  `quality_evaluator.score_blocks()` (8 → 4 → 1, with `torch.cuda.empty_cache()`
  between attempts).

VRAM impact is expected to be minimal: COMET's `model.predict()` already
internally chunks the input list by its own `batch_size` parameter
regardless of the total list size passed in — so batching more segments
into one `score_blocks()` call should not materially increase peak GPU
memory, only reduce the number of Lightning Trainer instantiations.

## Business / User Goal

Reduce total translation job wall-clock time for documents with hundreds+
of segments by eliminating redundant per-segment/per-iteration Lightning
Trainer startup overhead in the critique-loop QE gate, without changing
which translations get adopted (draft vs. revised) or invalidating any
already-critiqued/cached segments.

## Non-goals

- Not changing the QE model itself (COMET/xCOMET), its checkpoint, or its
  scoring semantics.
- Not changing `CRITIQUE_MAX_ITERATIONS`, `CRITIQUE_LOOP_ENABLED`, or
  `CRITIQUE_TIMEOUT_SECONDS` default values.
- Not adding early-exit logic to stop iterating a segment once a round's
  revision isn't adopted (out of scope for this change; current code
  already runs all iterations unconditionally and this change preserves
  that behavior, just batched).
- Not touching the job-level end-of-file QE scoring call site
  (`job_manager.py:423`) — that is a separate, already-batched call site.
- Not implementing the change yet — this request is for the CDD planning
  artifacts only (classification, contracts impact, test strategy,
  implementation plan). Implementation is explicitly deferred to a later,
  separate session/approval.

## Constraints

- Must preserve existing critique cache key scheme and adoption rule
  exactly (see "Constraints to preserve" above) — behavior for previously
  processed/cached segments must be unchanged.
- Must preserve per-segment failure isolation (one segment's exception/
  timeout must not abort critique for the rest of the batch/round).
- Must preserve the existing COMET OOM retry ladder in
  `quality_evaluator.score_blocks()`.
- STOP after `implementation-plan.md` is ready — do not commission or run
  backend/frontend implementation agents, and do not modify any product
  code in `app/backend/` in this pass.

## Known Context

- Critique loop code: `app/backend/services/translation_service.py:322-421`
  (loop) and `:59-96` (`_critique_gate_adopt`).
- QE scoring service: `app/backend/services/quality_evaluator.py`
  (`score_blocks`, OOM retry ladder already added in a prior change).
- Config flags: `CRITIQUE_LOOP_ENABLED` (default true),
  `CRITIQUE_MAX_ITERATIONS` (default 3), `CRITIQUE_TIMEOUT_SECONDS`
  (default 60) — `app/backend/config.py:139-141`.
- Confirmed via live production log analysis (this session) that every
  segment's critique iteration triggers a full Lightning Trainer startup
  banner, and that this is called unconditionally up to 3x per segment
  (no early-exit on adoption outcome).
- Related prior changes (see `specs/archive/`): `p2-comet-qe` (QE shipped),
  `quality-metrics-gating` (per-segment QE critique gate, QE_ENABLED
  default true).

## Open Questions

- None blocking classification; if COMET's `predict()` internal chunking
  assumption needs verification, `spec-architect` or `contract-reviewer`
  should confirm behavior against the installed `comet` version before
  implementation-plan.md finalizes the batching approach.

## Requested Delivery Date / Priority

No fixed deadline. Priority: performance optimization, non-urgent — plan
now, implement in a later session once the user reviews this proposal.
