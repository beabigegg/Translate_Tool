---
change-id: p2-prompt-fewshot-glossary
schema-version: 0.1.0
last-changed: 2026-06-19
risk: medium
tier: 2
---

# Test Plan: p2-prompt-fewshot-glossary

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_fewshot_glossary.py::TestGlossaryEnforcement | 0 |
| AC-1 | contract | tests/test_fewshot_glossary.py::TestGlossaryMatchRate | 0 |
| AC-2 | unit | tests/test_fewshot_glossary.py::TestFewShotInjection | 0 |
| AC-2 | unit | tests/test_context_prompt_i18n.py | 0 |
| AC-3 | unit | tests/test_fewshot_glossary.py::TestGlossarySourceOfTruth | 0 |
| AC-3 | unit | tests/test_term_db.py | 0 |
| AC-4 | unit | tests/test_fewshot_glossary.py::TestCritiqueLoop | 0 |
| AC-4 | integration | tests/test_hy_mt_quality_refinement.py | 1 |
| AC-5 | resilience | tests/test_fewshot_glossary.py::TestCritiqueLoopBounds | 0 |
| AC-6 | unit | tests/test_fewshot_glossary.py::TestCacheKeyGlossaryDigest | 0 |
| AC-7 | integration | tests/test_golden_regression.py | 1 |
| AC-7 | integration | tests/test_hy_mt_quality_refinement.py | 1 |
| AC-8 | unit | tests/test_metrics_counters.py | 0 |
| AC-8 | unit | tests/test_fewshot_glossary.py::TestCritiqueMetrics | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Pure-function tests; mock at LLM client boundary only |
| contract | 0 | 100% glossary-match rate asserted deterministically against in-memory TermDB |
| integration | 1 | Existing refinement + golden-regression suites must pass without modification |
| resilience | 0 | Critique-loop timeout/exception path degrades to last valid draft; job must not raise |

## New Test Class: `TestFewShotInjection` (tests/test_fewshot_glossary.py)

- `test_fewshot_examples_present_in_prompt_string`
- `test_fewshot_injected_for_every_call_including_second`
- `test_fewshot_block_contains_at_least_one_source_target_pair`
- `test_fewshot_examples_absent_when_bank_is_empty`

## New Test Class: `TestGlossaryEnforcement` (tests/test_fewshot_glossary.py)

- `test_registered_term_appears_in_output_after_substitution`
- `test_multiple_terms_all_substituted`
- `test_term_not_in_source_not_forced_into_output`
- `test_substitution_is_case_insensitive_on_source_match`

## New Test Class: `TestGlossaryMatchRate` (tests/test_fewshot_glossary.py)

- `test_match_rate_is_1_0_when_all_terms_present`
- `test_match_rate_is_0_when_no_terms_match`

## New Test Class: `TestGlossarySourceOfTruth` (tests/test_fewshot_glossary.py)

- `test_glossary_terms_sourced_from_term_db_not_hardcoded`
- `test_empty_term_db_produces_empty_glossary_block`

## New Test Class: `TestCritiqueLoop` (tests/test_fewshot_glossary.py)

- `test_critique_loop_runs_at_least_once_per_request`
- `test_revised_draft_recorded_in_tmap`

## New Test Class: `TestCritiqueLoopBounds` (tests/test_fewshot_glossary.py)

- `test_loop_stops_at_critique_max_iterations`
- `test_loop_degrades_to_last_valid_draft_on_critique_failure`
- `test_loop_degrades_to_draft_on_timeout`
- `test_job_does_not_fail_when_critique_times_out`

## New Test Class: `TestCacheKeyGlossaryDigest` (tests/test_fewshot_glossary.py)

- `test_cache_key_differs_after_glossary_state_changes`
- `test_pre_glossary_cache_entry_is_a_miss_after_term_added`

## New Test Class: `TestCritiqueMetrics` (tests/test_fewshot_glossary.py)

- `test_critique_loop_invocations_increments_per_request`
- `test_critique_iterations_total_reflects_actual_iteration_count`
- `test_glossary_match_rate_reported_in_get_metrics`
- `test_new_counters_initialize_to_zero`
- `test_new_counters_reset_via_reset_helper`

## Test Update Contract

| existing test file | action | reason |
|---|---|---|
| tests/test_metrics_counters.py | extend — add tests for `critique_loop_invocations`, `critique_iterations_total`, `glossary_match_rate` | AC-8 / BR-46 adds three counters alongside existing ones |
| tests/test_translation_strategy.py | extend — add `test_build_strategy_includes_glossary_digest_in_cache_variant` | AC-6: cache_variant must embed glossary-state digest |
| tests/test_hy_mt_quality_refinement.py | extend — add `test_critique_loop_invoked_within_translate_texts` (mock-call count ≥1) | AC-4: loop ≥1 per request, proven via mock at LLM boundary |
| tests/test_context_prompt_i18n.py | no body change; run as regression guard after new injections land | AC-2/AC-7: ensure prior prompt tests still pass |

## Out of Scope

- E2E / real-LLM calls (no Ollama available in CI)
- Frontend / API schema changes (no new endpoint per change-classification.md)
- Stress / soak tests (loop cost documented in design.md; not mandated at Tier 2)
- Data-boundary / monkey tests (no adversarial input surface per change-classification.md)
- DOCX/PPTX golden IR shape (unaffected by this change)

## Notes

- Mock at LLM client boundary (`translate_blocks_batch`, `OllamaClient`) only; do NOT mock `TermDB` reads — use an in-memory SQLite TermDB fixture (same pattern as `test_term_db.py`) so AC-3 is proven against the real read path.
- `CRITIQUE_MAX_ITERATIONS` and `CRITIQUE_TIMEOUT_SECONDS` must be patchable via `unittest.mock.patch` on the config/strategy module; tests must not rely on production defaults.
- Glossary-match enforcement is deterministic post-translation substitution (not prompt-only persuasion); `TestGlossaryEnforcement` proves substitution, not LLM output.
- Import source for new functions: `app.backend.services.context_prompts` (few-shot/glossary block builders) and `app.backend.services.translation_strategy` (critique loop + cache key).
- All new counters must satisfy BR-20: no IO on import, zero-initialized, reset()-safe.
