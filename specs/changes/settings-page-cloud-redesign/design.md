---
change-id: settings-page-cloud-redesign
schema-version: 0.1.0
last-changed: 2026-06-20
---

# Design: settings-page-cloud-redesign

## Architecture Summary
The Ollama-centric SettingsPage is replaced by a cloud-provider control surface backed by three additive, read/test backend endpoints. No persistence, schema, or migration is introduced. `GET /api/providers/health` probes each enabled provider for liveness+latency; `GET /api/providers/models` enumerates the static `models` map from the already-loaded `providers.yml` config; `POST /api/providers/test-translation` fans out a single sentence across selected model slots in parallel and optionally attaches COMET scores. The only security-sensitive boundary is the DeepSeek API key, which is owned entirely by the browser (localStorage) and transmitted per-request in the body — the backend never reads it from `.env` for this surface and never persists it.

## Affected Components
| component | file path | nature of change |
|---|---|---|
| Provider API routes | app/backend/api/routes.py | add 3 endpoints (health, models, test-translation) |
| API schemas | app/backend/api/schemas.py | add request/response models for the 3 endpoints |
| OpenAI-compatible client | app/backend/clients/openai_compatible_client.py | reuse `health()` probe + `complete`/translate path; accept per-request DeepSeek key |
| Quality evaluator | app/backend/services/quality_evaluator.py | reuse `load_model`/`score_blocks` (no change) |
| Provider config loader | app/backend/config.py | reuse `load_providers_config` (no change) |
| SettingsPage | app/frontend/src/pages/SettingsPage.jsx | full rewrite: health panel, model list, test panel, DeepSeek key form |
| VramCalculator | app/frontend/src/components/domain/VramCalculator.jsx | removed; drop orphaned import |
| Health hook | app/frontend/src/hooks/useHealthCheck.js | provider-aware health check |
| System API client | app/frontend/src/api/system.js | add `fetchProviderHealth`, `fetchProviderModels`, `testTranslation` |
| Contracts | contracts/api,data,business,env,css | document endpoints, shapes, orchestration rule, secret policy, styles |

## Key Decisions

### Decision 1 — DeepSeek key secret-handling
Confirmed: the DeepSeek key is user-supplied and lives only in browser `localStorage` under key `deepseek_api_key`. The frontend reads it at call time and sends it in the request **body** field `deepseek_api_key` (string) — chosen over a custom header because it avoids CORS preflight complexity for browser `fetch`. The backend uses the value only for that single request's DeepSeek client construction and discards it; it is never written to disk, never copied into an env var, and never logged. The backend MUST NOT fall back to `DEEPSEEK_API` from `.env` to satisfy a test-translation request — the developer `.env` key exists for the fallback-chain translation path only, not this UI surface. Security notes go in env-contract Secret Policy: key is client-owned, memory-only on the server, redacted from all logs and error payloads.

### Decision 2 — test-translation orchestration
Confirmed **synchronous** response: no `job_id`, no `BackgroundTasks`. A single sentence across a few model slots completes in seconds, so the deferred-job machinery (used by document translation) adds latency-budget and polling cost for no benefit. The handler builds one client per requested model slot and runs them concurrently via `asyncio.gather(..., return_exceptions=True)`. Cost-conservatism: PANJIT is free and probed unconditionally; the paid DeepSeek path is invoked **only** when a valid `deepseek_api_key` is present in the body — absent/blank key yields a per-model error result (e.g. `{"model_id": ..., "error": "deepseek_api_key required"}`) and never reaches the network. Partial failure is isolated: one model raising (network error, 401, timeout) produces a result object with a populated `error` field while every other model returns its translation normally — the fan-out never collapses to a single 500. COMET gate: each successful result calls `load_model(QE_MODEL_NAME, QE_DEVICE)` + `score_blocks` (the existing job-manager pattern) **only when `QE_ENABLED=true`**; when false the `comet_score` field is omitted entirely, not set to null.

### Decision 3 — provider health and model data source
Health: for each enabled provider, perform a lightweight liveness probe and record `latency_ms`. Reuse the existing client `health()` method, which issues a single `GET /v1/models` and returns `(ok, message)`; measure wall-clock around it. A timeout or non-200 marks the provider `offline`. PANJIT uses `verify_ssl=False` (self-signed cert). DeepSeek is only probed when a key is present; otherwise the UI shows "not configured" and the backend reports it as unconfigured rather than offline. Models: enumerated from the **in-memory `providers.yml`** config (already loaded once via `load_providers_config()` at module init) by reading each provider entry's `models` map. A live `/v1/models` network call is rejected for the model list because the static config is predictable, costs no network round-trip, does not depend on a provider's listing capability or auth, and remains queryable when a provider is offline.

## Rejected Alternatives
- **Key in custom HTTP header / backend session store** — rejected: header triggers CORS preflight friction for browser fetch; any server-side store reintroduces the persistence risk the policy explicitly forbids.
- **Async job + polling for test-translation** — rejected: single-sentence latency is acceptable synchronously; job/poll adds operational surface and client complexity for no user-visible gain.
- **Live `/v1/models` for the model list** — rejected: network cost, dependency on provider listing support and auth, and breaks when a provider is offline; static config is the durable source of truth.
- **Fail the whole fan-out on first model error** — rejected: defeats the comparison goal; per-model error isolation is required by AC-7.

## Migration / Rollback Strategy
Purely additive: three new GET/POST endpoints and a frontend rewrite, with no database, schema, contract-breaking, or env-variable changes (env change is policy-only documentation). No data migration is required. Rollback is reverting the frontend page and removing the three route handlers and their schemas; no state cleanup is needed because nothing is persisted server-side. The removed VRAM/num_ctx UI carries no backend dependency, so its deletion cannot regress translation behavior. Forward/back compatibility is unaffected because no existing endpoint or response shape is modified.
