---
change-id: p1-observability-metrics
schema-version: 0.1.0
last-changed: 2026-06-17
---

# Implementation Plan: p1-observability-metrics

## Objective
Ship a net-new, unauthenticated `GET /api/metrics` endpoint backed by an in-process counter module that tracks five flat counters, updated by additive increment hooks at the translation and font-load call sites. Existing path behavior is unchanged except for counter side effects.

## Execution Scope

### In Scope
- New counter module `app/backend/services/metrics.py` (module-level singleton: increment fns, `reset()` for tests, dict `snapshot()`).
- New `GET /api/metrics` route in `app/backend/api/routes.py` returning a `MetricsResponse` Pydantic model.
- New `MetricsResponse` model in `app/backend/api/schemas.py` (five fields per api-contract Schemas).
- Additive increment hooks in `translation_service.py` (count + latency + provider failure) and `pdf_generator.py` (font cache hit/miss).
- New tests: `tests/test_metrics_counters.py`, `tests/test_metrics_endpoint.py`.
- Regenerate `contracts/api/openapi.yml`.

### Out of Scope
- See change-classification.md / change-request.md "Non-goals": persistence/time-series, authentication, external metrics service, historical trend, frontend display, thread-safety (test-plan Out of Scope), live-provider E2E.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | services | Create `metrics.py` counter singleton (BR-20..24) | backend-engineer |
| IP-2 | api/schemas | Add `MetricsResponse` (5 fields) | backend-engineer |
| IP-3 | api/routes | Add `GET /api/metrics` returning snapshot | backend-engineer |
| IP-4 | translation_service | Hook count+latency+failure around provider calls | backend-engineer |
| IP-5 | renderers | Hook font cache hit/miss at `_load_font_buffer` call site | backend-engineer |
| IP-6 | tests | Write `test_metrics_counters.py` + `test_metrics_endpoint.py` | backend-engineer |
| IP-7 | contracts | Run `cdd-kit openapi export --out contracts/api/openapi.yml` | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| test-plan.md | AC→test mapping; Test Families | tests to write/run |
| ci-gates.md | Required Gates table; OpenAPI Regeneration Requirement | verification commands |
| contracts/api/api-contract.md | Endpoints row `/api/metrics` (line 44); `### MetricsResponse` (lines 217-224) | response shape, no-auth |
| contracts/business/business-rules.md | BR-20..BR-24; Table E (lines 35-88) | counter semantics |
| change-classification.md | Inferred AC-1..AC-7; Non-goals | scope boundaries |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| app/backend/services/metrics.py | create | singleton counters + `record_translation(latency_ms)`, `record_provider_failure()`, `record_font_cache_hit/miss()`, `snapshot()->dict`, `reset()`. Latency mean per BR-22 incremental formula; 0.0 float when count 0. |
| app/backend/api/schemas.py | edit | add `MetricsResponse(BaseModel)`: `translation_count:int`, `translation_latency_mean_ms:float`, `provider_failure_count:int`, `font_cache_hits:int`, `font_cache_misses:int`. |
| app/backend/api/routes.py | edit | add `@router.get('/metrics', response_model=MetricsResponse)` returning `metrics.snapshot()`; import schema + metrics module. |
| app/backend/services/translation_service.py | edit | wrap each provider call (per-text `client.translate_once` ~line 187; batch results loop ~line 171) — measure wall-clock ms, `record_translation` once per completed call (success or failure, BR-21), `record_provider_failure` on failure (BR-23). Do not change return values or control flow. |
| app/backend/renderers/pdf_generator.py | edit | at `_load_font_buffer(font_file)` call (~line 458) detect hit vs miss via `_load_font_buffer.cache_info()` hits delta around the call (BR-24, exactly one counter per access); record accordingly. |
| tests/test_metrics_counters.py | create | 14 unit tests per test-plan AC-3/4/5/6 rows; reset singleton each case via `reset()`/monkeypatch. |
| tests/test_metrics_endpoint.py | create | contract + integration per test-plan AC-1/2/3/7 rows; FastAPI `TestClient`; mock at HTTP/requests boundary, not `translate_texts`. |

## Contract Updates

- API: api-contract.md endpoint row + `MetricsResponse` already present (lines 44, 217-224) — implement to match; no edit expected unless drift. Regenerate `contracts/api/openapi.yml` (IP-7).
- CSS/UI: none.
- Env: none.
- Data shape: none (response is an API-contract concern, not persisted).
- Business logic: implement to BR-20..24 + Table E; no contract text edit expected.
- CI/CD: none (existing gates apply per ci-gates.md).

## Test Execution Plan

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1, AC-2 | tests/test_metrics_endpoint.py | 200 + JSON with five keys, correct types |
| AC-3 | tests/test_metrics_counters.py | count +1 and incremental mean per BR-22 |
| AC-4 | tests/test_metrics_counters.py | failure +1 per failed attempt (chain of 3 → +3); success unchanged |
| AC-5 | tests/test_metrics_counters.py | hit/miss, exactly one per access |
| AC-6 | tests/test_metrics_counters.py | all zero at init; mean 0.0 float; no external IO |
| AC-7 | tests/test_metrics_endpoint.py | existing translation/font-load behavior unchanged |

Required `cdd-kit test run` phases: `collect`, `targeted`, `changed-area`, `contract`. `full` runs as CI smoke (informational `full-regression`, ci-gates.md). The selector reads the `test file / command` column above when test-plan.md lacks a mapping; full ladder lives in test-plan.md and references/sdd-tdd-policy.md.

## Implementation Constraints

- `metrics.py` must be importable with zero side effects (no IO, no env reads, no logging on import); counters initialize to zero at module load (BR-20, AC-6).
- Increment functions must be no-op safe and never raise — instrumentation must not alter or break existing translation/font-load behavior (AC-7); do not let a hook swallow the original call's exceptions.
- `reset()` is a test-only helper; do NOT call it from production code (routes, services, renderers).
- Counters are in-process memory only — no file/db/network read or write (AC-6, BR-20).
- After implementing the endpoint and before running the gate, run `cdd-kit openapi export --out contracts/api/openapi.yml` and commit the result in the same change; the `openapi-sync` gate fails if `openapi.yml` is stale (ci-gates.md, CLAUDE.md learnings).

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.

## Known Risks

- Latency-mean attribution (BR-22): both per-text (`translate_once`) and batch (`translate_blocks_batch`) paths exist; ensure `record_translation` fires once per completed provider call in whichever path executes, without double counting.
- Provider failure per-attempt (BR-23, Table E): failures inside a fallback chain increment once per failed attempt — hook at the provider-call boundary, not once per `translate_texts` invocation.
- Font hit/miss detection relies on `_load_font_buffer.cache_info()`; read the delta atomically around the single call so exactly one counter increments (BR-24).
- openapi.yml staleness is the highest-likelihood gate failure (ci-gates.md) — regenerate after the endpoint exists.
