# Design: p1-cloud-providers

## Summary
This change makes cloud LLM endpoints the primary translation path by adding an `OpenAICompatibleClient` (implements the existing `LLMClient` Protocol, talks OpenAI `/v1/chat/completions`) and externalizing provider/routing config from the hardcoded `model_router._ROUTING_TABLE` into a new `config/providers.yml` loaded by `config.py` with `${VAR:-default}` env interpolation. `model_router` resolves model+provider from that config instead of literals; the orchestrator constructs the right client per route group; on primary-provider failure the request walks a configured `fallback_chain`, and the provider that actually produced the result is recorded additively on `JobStatus.provider` and surfaced via `/route-info`. Ollama is demoted to a fallback / layout-assist entry (`ollama-local`) but remains the default-on path when `providers.yml` is absent or all cloud providers are disabled, keeping the change backward-compatible. This serves AC-1..AC-8 by locking the Protocol-conformant client (AC-1/2), the config schema + env interpolation (AC-3/4), the fallback semantics (AC-5), provider attribution (AC-6/7), while adding no frontend/DB changes and no new env vars beyond `.env` (AC-8).

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| OpenAICompatibleClient | `app/backend/clients/openai_compatible_client.py` (new) | New `LLMClient` Protocol impl over OpenAI-compatible chat completions |
| Clients export | `app/backend/clients/__init__.py` | Export new client |
| Provider config schema | `config/providers.yml` (new), `config/providers.yml.example` (new) | Externalized provider registry + routing + fallback_chain; example has no secrets |
| Config loader | `app/backend/config.py` | Load+parse `providers.yml`, expand `${VAR:-default}`, expose `ProviderConfig` |
| Model router | `app/backend/services/model_router.py` | Replace hardcoded `_ROUTING_TABLE` with config-driven lookup; carry provider in route decision |
| Client construction | `app/backend/processors/orchestrator.py` | Build `OpenAICompatibleClient` vs `OllamaClient` from resolved provider; fallback retry |
| Translation consumer | `app/backend/services/translation_service.py` | Unchanged Protocol consumer; receives provider-attributed client |
| Job record/state | `app/backend/services/job_manager.py` | Add `provider: str \| None`; set on successful call |
| API surface | `app/backend/api/routes.py`, `app/backend/api/schemas.py` | `/route-info` + `JobStatus` gain `provider` field |
| Contracts | `contracts/{api,env,data,business}/*` | Document `provider` field, new env vars, routing/fallback rules |

## Key Decisions
- **providers.yml schema**: top-level `providers:` (list of `{id, type, enabled, base_url, api_key, models, role?}`), `routing.rules` (ordered match list), `routing.default` (`{model, provider, profile}`), and `fallback_chain` (ordered list of provider IDs). Shape mirrors `docs/improvement-plan.md` §3.1.3 but THIS change delivers only: provider registry, single `routing.default`, and `fallback_chain`. Per-language precise routing and `src_tokens_gt` rules are declared as schema-tolerated but NOT consumed here (owned by `p1-provider-routing`); observability fields are out of scope (`p1-observability-metrics`). Rationale: lock the schema downstream changes depend on without implementing their logic.
- **Env-var interpolation**: `config.py` expands `${VAR}` and `${VAR:-default}` at load time using `os.environ.get` with the literal fallback → rejected a third-party YAML templating engine: a ~10-line regex substitution over loaded values is simpler, dependency-free, and keeps secrets in `.env` only.
- **Fallback chain semantics**: `fallback_chain` is an ordered list of provider IDs. "Primary offline" is detected at the client boundary by catching connection/timeout/auth exceptions (the Protocol's `(ok, ...)` False signal plus raised network errors). Max one attempt per provider, walked in chain order; first success wins. Provider attribution is recorded at the point of the successful call, not at routing time → rejected per-segment fallback for now: chain is evaluated per route group/job for simplicity.
- **JobStatus.provider**: additive optional `provider: str | None` on `JobRecord` (`job_manager.py`) and the API schema; set to the winning provider ID when the orchestrator's call succeeds. Backward-compatible (default `None`); consistent with AC-6.
- **OpenAICompatibleClient**: implements the six Protocol methods over HTTP via `requests` (already the project's HTTP dependency; `httpx` is not a dependency). `streaming=False` — translation output is short, so a single non-streamed chat completion is sufficient. `translate_once` → one chat completion; `translate_batch` → sequential `translate_once` calls (no OpenAI batch API); `refine_translation` → one completion with draft+source; `health`/`list_models` → `/v1/models` probe; `unload()` → no-op `(True, "no-op")` for cloud providers.
- **model_router refactor**: `resolve_route*` and `get_route_info` accept/consult a `ProviderConfig` loaded from `providers.yml` instead of module-level dict literals. The existing grouping skeleton (`RouteGroup`, insertion-order grouping, cross-model refiner) is retained; only the source of `(model, provider, profile_id, model_type)` moves from `_ROUTING_TABLE`/`_DEFAULT_ROUTE` to config lookup.
- **Rejected alternatives**: (a) dynamic YAML template engine — rejected, expand env vars in Python at load time; (b) single global client singleton — rejected, per-job/per-group provider selection is more flexible and fallback-friendly; (c) async `httpx` — rejected for now, the codebase is sync/thread-based and cloud latency (3–7s) is acceptable for an initial implementation.

## Migration / Rollback
Backward-compatibility: `ollama-local` remains an entry in `providers.yml` (role: layout-assist / fallback). If `config/providers.yml` is absent, unreadable, or every provider has `enabled=false`, `config.py`/`model_router` fall back to the current `OllamaClient`-only behavior — no job fails purely because cloud config is missing. The `provider` field defaults to `None` for pre-existing/legacy jobs, so older clients and stored job records remain valid.

Rollback: delete `openai_compatible_client.py`, revert `model_router.py` to the hardcoded table, and remove the `provider` field handling; with `providers.yml` absent the system returns to Ollama-only translation with no data migration required (the additive `provider` field is forward/backward inert).

Secret handling: `.env` stays gitignored and is the only home for `PANJIT_API` / `DEEPSEEK_API` (and base URLs). `config/providers.yml` must contain only `${VAR}` references, never literal keys; a secret-free `config/providers.yml.example` is committed as the template. Misconfiguration that leaves a key unresolved must disable that provider (not emit the literal `${VAR}` to the endpoint).

## Open Risks
- `.cdd/code-map.yml` was not consulted (presence not verified); component ranges above were grounded by direct scoped reads. If a code-map exists it should be regenerated before implementation.
- `requests`-based sync fallback means a slow/hanging primary provider consumes its full read timeout before the chain advances; timeout tuning (reuse `TimeoutConfig`) is required so fallback latency stays bounded.
- Env vars `PANJIT_LLM_BASE_URL`, `PANJIT_API`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_API`, `DEEPSEEK_ENABLED` are not yet in `contracts/env/env-contract.md`; contract-reviewer must add them before gate.
- Schema-tolerated-but-unconsumed `routing.rules` risks drift with `p1-provider-routing`; an ADR or shared schema note may be warranted if that change reinterprets the fields.
