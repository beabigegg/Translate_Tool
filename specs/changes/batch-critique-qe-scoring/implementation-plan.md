---
change-id: batch-critique-qe-scoring
schema-version: 0.1.0
last-changed: 2026-07-07
---

# Implementation Plan: batch-critique-qe-scoring

> **IMPLEMENTATION IS DEFERRED.** This is a planning-only artifact. Per
> `change-request.md` §Non-goals and §Constraints ("STOP after
> implementation-plan.md is ready"), NO product code in `app/backend/`, no test
> file, and no workflow file may be touched until the user explicitly approves
> this plan in a later, separate session. The `backend-engineer`,
> `e2e-resilience-engineer`, and `qa-reviewer` are NOT to be commissioned in
> this pass.

## Objective

Restructure the critique-loop QE (COMET) scoring in
`app/backend/services/translation_service.py` from a **per-segment inner loop**
(where `score_blocks()` is invoked once per `(segment, iteration)` — up to
`CRITIQUE_MAX_ITERATIONS` × segment-count times) into a **round-based loop**
(where each of `CRITIQUE_MAX_ITERATIONS` rounds revises all pending segments,
then issues exactly ONE batched `score_blocks()` call for that round, then
applies per-segment adoption). The refactor must be **behavior-preserving**:
every segment's adopted draft-vs-revised choice is identical to today's, but
the number of Lightning Trainer instantiations drops from
`O(segments × iterations)` to `O(iterations)`.

## Execution Scope

### In Scope
- `app/backend/services/translation_service.py`: replace the nested
  per-segment/per-iteration critique loop (lines ~354-421) with a round-based
  loop; adapt `_critique_gate_adopt` (lines ~59-96) or add a batched adoption
  helper so QE scoring is issued once per round across all pending segments.
- `app/backend/services/quality_evaluator.py`: `score_blocks()` (lines ~74-125)
  is **not modified internally**; the change only passes it a longer `blocks`
  list. The implementer must confirm the OOM ladder (8→4→1 +
  `torch.cuda.empty_cache()`) still functions unchanged under the larger input
  and that scores come back in input order, one per block.
- The required contract update to `contracts/data/data-shape-contract.md`
  (see §Contract Updates).
- New/extended tests per `test-plan.md` (see §Test Execution Plan).

### Out of Scope
See `change-request.md` §Non-goals (authoritative). In particular:
- No change to the QE model/checkpoint or its scoring semantics.
- No change to `CRITIQUE_MAX_ITERATIONS`, `CRITIQUE_LOOP_ENABLED`, or
  `CRITIQUE_TIMEOUT_SECONDS` defaults (`config.py:139-141`).
- No early-exit-on-non-adoption logic — all iterations still run
  unconditionally, just batched.
- No touching the job-level end-of-file QE call site (`job_manager.py:423`).
- No API / env / UI / data-IR / CI-workflow change (`change-classification.md`
  §Required Contracts — all "none" except the data-shape doc row below).

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | translation_service.py critique loop | Invert loop nesting to round-based: outer loop over `CRITIQUE_MAX_ITERATIONS` rounds; per round, (a) generate revisions for all still-pending segments, (b) build one batched `(src,draft)/(src,revised)` pair list, (c) issue ONE `score_blocks()`, (d) apply per-segment adoption by index, (e) carry adopted draft into next round. Preserve pre-loop cache-skip filter and failure-placeholder skip. | backend-engineer (deferred) |
| IP-2 | translation_service.py adoption | Add a batched adoption path that reuses the strict-greater-than / tie-keeps-draft rule from `_critique_gate_adopt` but consumes a batched score list mapped back to segment index (see §Timeout & Exception Isolation). Keep the single-pair `_critique_gate_adopt` for the heuristic/QE-unavailable fallback semantics. | backend-engineer (deferred) |
| IP-3 | quality_evaluator.py | No internal edit. Verify `score_blocks()` returns scores in input order (one per block) and that the OOM ladder still exercises correctly with a 2N-length list; add regression coverage per test-plan. | backend-engineer (deferred) |
| IP-4 | metrics parity | Preserve `record_critique_loop_invocation()` (once) and `record_critique_iteration(total)` accounting so `critique_loop_invocations` / `critique_iterations_total` counters match the pre-refactor baseline (BR-46). | backend-engineer (deferred) |
| IP-5 | contracts/data/data-shape-contract.md | Rewrite the "Critique gate usage" row (lines ~782-787), currently documenting a two-element `score_blocks()` call, to describe the batched multi-segment call shape; bump `schema-version` and add a CHANGELOG entry (`validate_contract_versions.py` enforces both). | backend-engineer (deferred) |
| IP-6 | tests | Author `tests/test_critique_loop_batching.py` and extend `tests/test_critique_gate.py` / `tests/test_quality_evaluation.py` per `test-plan.md`. | backend-engineer + e2e-resilience-engineer (deferred) |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-request.md | §Non-goals, §Constraints ("Constraints to preserve") | scope boundary, STOP condition |
| change-classification.md | §Inferred Acceptance Criteria (AC-1..AC-8) | criteria to satisfy |
| test-plan.md | §Acceptance Criteria → Test Mapping (full AC→test table) | tests to write/run |
| ci-gates.md | §Required Gates table; §Workflow Changes Required When Implementation Lands | verification commands / gate policy |
| agent-log/contract-reviewer.yml | `scheduled-contract-update` → `contracts/data/data-shape-contract.md:782-787`; BR-89/BR-90 no-change; BR-46 metrics-counter rec | contract update task, invariant confirmation |
| contracts/business/business-rules.md | BR-89/BR-90 (adoption outcome), BR-46 (critique metrics) | adoption rule + counter parity (NO wording change) |
| design.md | not present (Tier 2, no design required) | n/a |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| `app/backend/services/translation_service.py` | modify | Restructure critique block (lines ~354-421) to round-based; add batched adoption helper alongside `_critique_gate_adopt` (~59-96). Preserve cache pre-filter (~337-352), failure-placeholder skip, `status_callback` progress text, and metrics calls (~330, ~419). |
| `app/backend/services/quality_evaluator.py` | verify only (no edit expected) | `score_blocks()` (~74-125) receives a longer list; confirm order-preserving return + OOM ladder still works. |
| `app/backend/config.py` | read only | Confirm `CRITIQUE_*` defaults unchanged (~139-141). No edit. |
| `contracts/data/data-shape-contract.md` | modify | Rewrite "Critique gate usage" row (~782-787) to batched call shape; bump `schema-version`; add CHANGELOG entry. |
| `tests/test_critique_loop_batching.py` | create | Parity, call-count bound, cache-skip, exception/timeout isolation, metrics-counter parity (per test-plan). |
| `tests/test_critique_gate.py` | modify | Add batched-round score→segment index-mapping test (AC-3). |
| `tests/test_quality_evaluation.py` | modify | Add OOM-ladder-with-larger-batch + batch_size-invariance tests (AC-6, AC-8). |

## Round-Based Design Detail (the load-bearing restructuring)

Current shape (to be replaced): `for each segment: for each iteration: generate
revision → score_blocks([(src,draft),(src,revised)]) → adopt`.

Target shape:

1. **Pre-filter (unchanged, must be preserved as-is):** before any round runs,
   skip failure placeholders and segments already in `_critiqued_keys` (the
   `:c` cache hits gathered at lines ~337-352). Only non-cached, non-failed
   segments enter the round loop. This filter must NOT be weakened — AC-4.
2. **Round loop:** `for _iter in range(max(1, CRITIQUE_MAX_ITERATIONS)):`
   - **Revision phase:** iterate the pending segments; for each, run
     `client.translate_once(...)` to produce its revision, applying the
     per-segment timeout check around THAT call (see §Timeout below). Collect,
     per pending segment, its `(src, current_draft, revised_or_None)`.
   - **Batched score phase:** for every segment that produced a valid revision
     this round, append `(src, draft)` and `(src, revised)` to one `blocks`
     list, tracking each segment's pair indices. Issue exactly ONE
     `score_blocks(model, blocks, device=...)` call.
   - **Adoption phase:** for each segment, read its two scores back by index and
     apply strict-greater-than (`revised` adopted iff `s_revised > s_draft`;
     tie keeps draft). The adopted text becomes that segment's `current_draft`
     for the next round.
   - Segments whose revision failed/timed out this round keep their current
     draft and remain eligible for subsequent rounds (matching today's
     unconditional-iteration behavior — no early exit).
3. **After all rounds:** write each segment's final `current_draft` back to
   `tmap`, persist to the `:c` cache (lines ~410-414 semantics), emit
   `record_critique_iteration(total_iters)` where `total_iters` equals the count
   of adopted-or-attempted iterations consistent with today's `_segment_iters`
   accumulation (IP-4 / BR-46 parity).

## Timeout & Exception Isolation Semantics (highest-risk detail — resolve exactly as stated)

These are the resolved decisions from `contract-reviewer.yml` and the
classifier's open design question. Implement them verbatim; do not re-decide.

- **Per-segment timeout stays on the revision call only.**
  `CRITIQUE_TIMEOUT_SECONDS` is applied ONLY around each segment's own
  `client.translate_once(...)` revision-generation call (as today at lines
  ~368-391), never around the batched `score_blocks()` call. Batching the
  scoring step therefore introduces NO new timeout-granularity gap: each
  segment's revision is still individually time-boxed. A segment whose revision
  call exceeds the timeout keeps its draft for that round and does not enter the
  round's batched score list.
- **Per-segment exception isolation within a round.** One segment's
  revision-generation exception or timeout must NOT prevent other segments in
  the same round from being revised, scored, and adopted. Wrap each segment's
  revision generation in its own try/except (mirroring today's per-segment
  `break`, now scoped to "this segment skips this round" rather than aborting a
  shared loop). Other pending segments proceed normally. — AC-5.
- **Batched score total-failure degradation.** If the single
  `score_blocks()` call returns `[]` (total failure, e.g. a non-OOM exception
  inside COMET, or OOM ladder exhausted), every pending segment in that round
  must degrade to "keep draft" — matching today's `len(_scores) >= 2` →
  else-keep-draft fallback semantics (line ~92-93). A `[]` return must NOT crash
  the round or the job; the round completes with all drafts kept.
- **QE-unavailable / heuristic fallback.** When QE is disabled or the model
  cannot load (the `except Exception` path in `_critique_gate_adopt`, lines
  ~94-96), the batched path must still fall back to the deterministic
  length-ratio/fluency heuristic per segment (AC-8), exactly as today. Preserve
  `_critique_gate_adopt`'s single-pair heuristic path for this case.

## Contract Updates

- API: none (`change-classification.md` §Required Contracts — API: none; conformance gate stays green).
- CSS/UI: none.
- Env: none — `CRITIQUE_*` defaults unchanged.
- Data shape: **REQUIRED** — rewrite `contracts/data/data-shape-contract.md`
  "Critique gate usage" row (~782-787) from the current two-element
  `score_blocks()` call description to the batched multi-segment call shape.
  Bump `schema-version` + add CHANGELOG entry (`validate_contract_versions.py`
  enforces). See `agent-log/contract-reviewer.yml`
  (`scheduled-contract-update` artifact) — do not restate the full quoted row
  here.
- Business logic: NO wording change. contract-reviewer confirmed BR-89/BR-90
  describe only the adoption outcome, not call cardinality; the refactor keeps
  them satisfied. BR-46 metrics counters must retain parity (IP-4).
- CI/CD: none — existing blanket `pytest tests/` steps already glob-cover the
  new/extended test files (`ci-gates.md` §Workflow Changes Required item 1).

## Test Execution Plan

Full AC→test mapping is authoritative in `test-plan.md` §Acceptance Criteria →
Test Mapping — do not restate it here. Required phase floor: **collect,
targeted, changed-area** (always), plus **contract** (data-shape-contract.md
changes) and **full** at CI. Implementation agents generate evidence with
`cdd-kit test run`; the gate validates `test-evidence.yml`.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (parity) | tests/test_critique_loop_batching.py::test_batched_loop_matches_per_segment_adoption_parity | identical per-segment adopted text vs. scripted baseline |
| AC-2 (call-count bound) | tests/test_critique_loop_batching.py::test_score_blocks_call_count_bounded_by_iterations_not_segment_count | `score_blocks` called ≤ CRITIQUE_MAX_ITERATIONS times |
| AC-3 (tie keeps draft, index map) | tests/test_critique_gate.py::test_batched_round_scores_map_to_correct_segment_index | correct score→segment mapping; tie keeps draft |
| AC-3 (tie integration) | tests/test_critique_loop_batching.py::test_tie_score_keeps_draft_in_batched_round | draft retained on equal scores |
| AC-4 (cache skip) | tests/test_critique_loop_batching.py::test_cached_segments_excluded_from_round_batch | `:c` cache hits never entered into any round's batch |
| AC-5 (exception isolation) | tests/test_critique_loop_batching.py::test_segment_exception_in_round_does_not_abort_other_segments | other segments still revised/scored/adopted |
| AC-5 (timeout isolation) | tests/test_critique_loop_batching.py::test_segment_timeout_in_round_does_not_abort_other_segments | timed-out segment keeps draft; others proceed |
| AC-6 (OOM ladder) | tests/test_quality_evaluation.py::test_cuda_oom_ladder_functions_with_larger_batched_blocks_list | 8→4→1 + empty_cache still exercised on 2N list |
| AC-7 (config defaults) | tests/test_critique_loop_batching.py::test_critique_config_defaults_unchanged_after_batching | CRITIQUE_* defaults unchanged |
| AC-7 (no drift) | `cdd-kit validate --contracts` | exit 0 |
| AC-8 (VRAM bound) | tests/test_quality_evaluation.py::test_score_blocks_batch_size_param_unaffected_by_input_list_length | `batch_size` arg independent of list length |
| metrics parity (BR-46) | tests/test_critique_loop_batching.py::test_critique_loop_invocation_and_iteration_counters_match_baseline | counter values match pre-refactor baseline |

## Handoff Constraints

- **Implementation is DEFERRED** — do not write or modify any `app/backend/`
  product code, test, or workflow until the user approves this plan in a later
  session (`change-request.md` §Constraints STOP condition).
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into
  this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and
  report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion
  Request is approved. If the critique loop is found to delegate to a helper
  outside the Allowed Paths (e.g. `translation_strategy.py`,
  `translation_helpers.py`), raise a Context Expansion Request rather than
  reading it ad hoc (per context-manifest.md §Context Expansion Requests note).

## Known Risks

- **Segment/index misalignment (highest risk).** Batching collapses 2 scores
  per segment into one flat list; an off-by-one in the pair-index→segment map
  silently swaps which segment's revised score is compared, changing document
  output with no error. AC-1/AC-3 parity + index-mapping tests are the guard;
  assert exact adopted-text identity per segment, not just call counts.
- **Broken failure isolation.** A shared per-round try/except that wraps the
  whole revision phase would let one segment's exception abort the round —
  violating AC-5. Each segment's revision must be individually guarded.
- **Batched `[]` degradation.** Forgetting the total-failure → keep-all-drafts
  path could crash the round instead of degrading gracefully. Covered by the
  resilience tests.
- **Metrics-counter drift.** Re-accounting `critique_iterations_total` under the
  new loop structure could diverge from baseline; BR-46 parity test guards it.
- **Contract-version gate.** Editing the data-shape-contract row without bumping
  `schema-version` / adding a CHANGELOG entry will fail
  `validate_contract_versions.py`.
- **Code-map staleness note:** planning relied on direct reads of the two
  service files (lines confirmed against `contract-reviewer.yml` ground-truth);
  `.cdd/code-map.yml` was not consulted for line ranges in this pass. If line
  numbers have shifted by implementation time, re-locate by symbol name
  (`_critique_gate_adopt`, the `CRITIQUE_LOOP_ENABLED` block, `score_blocks`).
