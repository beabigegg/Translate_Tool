---
change-id: p1-llm-client-abstraction
schema-version: 0.1.0
last-changed: 2026-06-17
---

# QA Report: p1-llm-client-abstraction

## Pre-existing Failures (baseline-confirmed)

All failures below confirmed pre-existing via `git stash` + `pytest` on the baseline commit `d45eaa1` on 2026-06-17.

### PF-1: test_refined_output_not_written_to_cache

| field | value |
|---|---|
| test id | `tests/test_hy_mt_quality_refinement.py::TestTranslateTextsRefinePhase::test_refined_output_not_written_to_cache` |
| baseline evidence | Fails on baseline: `AssertionError: assert 'refined result not for cache' not in (...)` |
| why outside scope | Test asserts refined output is not cached (A.7.6 policy). Production code lines 267-270 intentionally caches refined results ("Cache the final refined result for future runs"). Policy mismatch predates this change; `p1-llm-client-abstraction` does not modify cache-write logic. |
| owner | Unassigned — whoever added refined-result caching to `translation_service.py`. |
| follow-up | Decide A.7.6 policy (no refined-cache write) vs current code; align test or code in a separate change. |

### PF-2: test_runtime_options_override_is_merged

| field | value |
|---|---|
| test id | `tests/test_ollama_client_dynamic_strategy.py::test_runtime_options_override_is_merged` |
| baseline evidence | Fails on baseline with `AttributeError` or `AssertionError` (confirmed via stash run) |
| why outside scope | Unrelated to LLMClient Protocol; this tests `OllamaClient.set_runtime_options_override` method. Pre-existing failure not caused by this change. |
| owner | Unassigned |
| follow-up | Fix in a separate change targeting `ollama_client.py` runtime-options logic. |

### PF-3 through PF-7: test_term_db.py failures

| field | value |
|---|---|
| test ids | `tests/test_term_db.py::test_overwrite_strategy`, `test_merge_higher_confidence_wins`, `test_merge_lower_confidence_keeps_existing`, `test_increment_usage`, `test_get_top_terms_ordered_by_usage`, `test_import_skip_preserves_existing` |
| baseline evidence | All fail on baseline with `IndexError: list index out of range` |
| why outside scope | Term database tests entirely unrelated to LLMClient Protocol abstraction. Pre-existing failures not caused by this change. |
| owner | Unassigned |
| follow-up | Fix in a separate change targeting the term database module. |

## Also Pre-existing: Collection Errors

| test file | error |
|---|---|
| `tests/test_model_config_api.py` | `RuntimeError: starlette.testclient requires httpx2` |
| `tests/test_term_api.py` | `RuntimeError: starlette.testclient requires httpx2` |

Not caused by this change; pre-existing environment issue.

## In-scope Failures

None. All `tests/test_llm_client_protocol.py` tests pass. All five regression test files listed in test-plan.md pass (one pre-existing failure in `test_hy_mt_quality_refinement.py` is documented above as PF-1).
