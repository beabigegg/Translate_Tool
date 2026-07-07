---
change-id: batch-critique-qe-scoring
schema-version: 0.1.0
last-changed: 2026-07-07
risk: medium
tier: 2
---

# Test Plan: batch-critique-qe-scoring

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 (parity: identical draft-vs-revised choices) | integration | tests/test_critique_loop_batching.py::test_batched_loop_matches_per_segment_adoption_parity | 1 |
| AC-2 (score_blocks ≤ CRITIQUE_MAX_ITERATIONS calls) | integration | tests/test_critique_loop_batching.py::test_score_blocks_call_count_bounded_by_iterations_not_segment_count | 1 |
| AC-3 (tie keeps draft — index mapping) | unit | tests/test_critique_gate.py::test_batched_round_scores_map_to_correct_segment_index | 0 |
| AC-3 (tie keeps draft — integration) | integration | tests/test_critique_loop_batching.py::test_tie_score_keeps_draft_in_batched_round | 1 |
| AC-4 (":c" cache key unchanged; cached segments skip before round work) | integration | tests/test_critique_loop_batching.py::test_cached_segments_excluded_from_round_batch | 1 |
| AC-5 (per-segment exception isolation within a round) | resilience | tests/test_critique_loop_batching.py::test_segment_exception_in_round_does_not_abort_other_segments | 1 |
| AC-5 (per-segment timeout isolation within a round) | resilience | tests/test_critique_loop_batching.py::test_segment_timeout_in_round_does_not_abort_other_segments | 1 |
| AC-6 (COMET OOM ladder 8/4/1 functions with batched input) | resilience | tests/test_quality_evaluation.py::test_cuda_oom_ladder_functions_with_larger_batched_blocks_list | 1 |
| AC-7 (env/config-default unchanged) | unit | tests/test_critique_loop_batching.py::test_critique_config_defaults_unchanged_after_batching | 0 |
| AC-7 (no API/schema/CSS drift) | contract | ci-gates.md: contract conformance gate (`cdd-kit validate --contracts`) | 0 |
| AC-8 (VRAM bound unaffected by batched list length) | unit | tests/test_quality_evaluation.py::test_score_blocks_batch_size_param_unaffected_by_input_list_length | 0 |
| metrics-counter parity (BR-46, contract-reviewer rec.) | integration | tests/test_critique_loop_batching.py::test_critique_loop_invocation_and_iteration_counters_match_baseline | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | `_critique_gate_adopt` index-mapping, `score_blocks` batch_size invariance, config-default assertions — mocked, no I/O |
| integration | 1 | End-to-end `translate_texts()` (client + cache mocked) proving round-based batching parity, call-count reduction, cache-skip, metrics-counter parity — the PR-required critical path, since correctness here is the entire point of the change |
| resilience | 1 | Per-segment exception/timeout isolation inside a batched round; COMET OOM ladder under a larger batched blocks list |
| stress (consideration only, not required) | 3 | Wall-clock micro-benchmark of reduced Lightning Trainer instantiations — supporting evidence for the change's motivation, not a merge gate |

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

## Test Update Contract

No existing test's expected behavior changes — the refactor is behavior-preserving
by design (AC-1). All rows above are new tests or extensions of existing coverage
in `tests/test_critique_gate.py` / `tests/test_quality_evaluation.py`; none of the
existing assertions in those files need to change or be deleted.

| existing test | action | reason |
|---|---|---|
| (none) | n/a | parity is the acceptance criterion; no prior test's expected outcome changes |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- Full VRAM/GPU peak-memory profiling (needs real CUDA hardware + soak run; the
  batch_size-invariance unit test stands in for this at Tier 2).
- Wall-clock benchmark as a blocking gate (classification: "consideration only").
- `job_manager.py:423` end-of-file QE scoring call site — explicit non-goal,
  already batched, untouched by this change.
- QE model/checkpoint changes; `CRITIQUE_MAX_ITERATIONS` / `CRITIQUE_LOOP_ENABLED`
  / `CRITIQUE_TIMEOUT_SECONDS` default changes; early-exit-on-adoption logic — all
  explicit non-goals.
- E2E, visual, fuzz/monkey, soak — none required per change-classification.

## Notes

- New file `tests/test_critique_loop_batching.py` follows the
  `tests/test_translate_document_parity.py` / `tests/test_glossary_enforcement.py`
  pattern: call `translate_texts()` with a mocked `LLMClient` and mocked
  `get_cache` / `quality_evaluator.score_blocks`, patching
  `CRITIQUE_LOOP_ENABLED` / `CRITIQUE_MAX_ITERATIONS` on the
  `translation_service` consumer module.
- AC-1 parity baseline is a fixed, scripted per-segment/per-round QE score
  sequence shared by both the expected-outcome table and the batched call —
  not a live diff against removed code.
- Extend `tests/test_critique_gate.py` and `tests/test_quality_evaluation.py`
  rather than duplicating adoption-rule or OOM-ladder coverage already there.
- Anti-tautology: assert exact adopted-text identity per segment and exact
  `score_blocks` / `record_critique_iteration` call args/counts, never just
  "no exception raised" or job completion.
