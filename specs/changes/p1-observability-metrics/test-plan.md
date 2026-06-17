---
change-id: p1-observability-metrics
schema-version: 0.1.0
last-changed: 2026-06-17
risk: medium
tier: 2
---

# Test Plan: p1-observability-metrics

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | contract | tests/test_metrics_endpoint.py::test_get_metrics_returns_200 | 1 |
| AC-2 | contract | tests/test_metrics_endpoint.py::test_get_metrics_response_keys_present | 1 |
| AC-2 | contract | tests/test_metrics_endpoint.py::test_get_metrics_field_types | 1 |
| AC-3 | unit | tests/test_metrics_counters.py::test_translation_count_increments_on_success | 0 |
| AC-3 | unit | tests/test_metrics_counters.py::test_latency_mean_updated_after_calls | 0 |
| AC-3 | unit | tests/test_metrics_counters.py::test_latency_mean_incremental_formula | 0 |
| AC-3 | integration | tests/test_metrics_endpoint.py::test_translation_count_reflected_in_endpoint | 1 |
| AC-4 | unit | tests/test_metrics_counters.py::test_provider_failure_count_increments_on_failure | 0 |
| AC-4 | unit | tests/test_metrics_counters.py::test_provider_failure_count_unchanged_on_success | 0 |
| AC-4 | unit | tests/test_metrics_counters.py::test_translation_count_increments_on_failure_too | 0 |
| AC-4 | unit | tests/test_metrics_counters.py::test_provider_failure_count_increments_per_attempt_in_chain | 0 |
| AC-5 | unit | tests/test_metrics_counters.py::test_font_cache_hit_increments_hits | 0 |
| AC-5 | unit | tests/test_metrics_counters.py::test_font_cache_miss_increments_misses | 0 |
| AC-5 | unit | tests/test_metrics_counters.py::test_font_cache_exactly_one_counter_per_access | 0 |
| AC-6 | unit | tests/test_metrics_counters.py::test_all_counters_initialize_to_zero | 0 |
| AC-6 | unit | tests/test_metrics_counters.py::test_latency_mean_is_float_zero_when_count_zero | 0 |
| AC-6 | unit | tests/test_metrics_counters.py::test_counters_no_external_io | 0 |
| AC-7 | integration | tests/test_metrics_endpoint.py::test_existing_translation_behavior_unchanged | 1 |
| AC-7 | integration | tests/test_metrics_endpoint.py::test_existing_font_load_behavior_unchanged | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Counter module logic in isolation; reset singleton state between tests via `monkeypatch` or an exposed `reset()` helper |
| contract | 1 | FastAPI `TestClient` against `GET /api/metrics`; assert HTTP 200, `Content-Type: application/json`, key presence, value types |
| integration | 1 | Invoke instrumented call sites with mocked HTTP boundary (requests/httpx); assert endpoint response reflects updated counters |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| (none) | — | Change is additive; no existing test expectations are modified |

## Out of Scope

- Persistence or counter recovery across process restarts (in-process only, per BR-20)
- Authentication/authorization (endpoint is intentionally unauthenticated per BR-1)
- Concurrent-write thread-safety (not required at Tier 2; defer to nightly soak if threading is later added)
- E2E tests against a live Ollama provider
- Frontend display or consumption of metrics values

## Notes

- Unit tests must reset counter state between cases; prefer a module-level `reset()` or `monkeypatch` on the singleton.
- `test_latency_mean_is_float_zero_when_count_zero` guards BR-22: value must be `0.0` (float), not `null` or missing.
- `test_provider_failure_count_increments_per_attempt_in_chain` covers the Table E edge case: a 3-provider chain with all three failing must increment by 3.
- Integration tests mock at the HTTP client boundary (requests), not at `translation_service.translate_texts`, to avoid test drift.
- All five required counter keys must be present in the response even before any calls have occurred (AC-2 + AC-6 combined).
