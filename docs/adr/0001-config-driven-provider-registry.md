# ADR 0001: Config-driven provider registry and fallback chain

## Status
proposed

## Context
Translation routing was a hardcoded `_ROUTING_TABLE` in `app/backend/services/model_router.py` and translation ran only against local Ollama via `OllamaClient`. The `p1-cloud-providers` change makes cloud LLM endpoints (Panjit, DeepSeek) the primary translation path and demotes Ollama to fallback / layout-assist. This moves a module boundary (routing knowledge leaves code and enters `config/providers.yml`) and changes an availability guarantee (a single-provider synchronous call becomes a multi-provider fallback chain). Two downstream P1 changes — `p1-provider-routing` and `p1-observability-metrics` — depend on the schema and fallback semantics locked here. A leaky Protocol or config schema would propagate to both.

## Decision
- Externalize provider/routing config to `config/providers.yml` with top-level `providers`, `routing.default`, `routing.rules`, and `fallback_chain`. Env interpolation is `${VAR:-default}`, expanded in `config.py` at load time via `os.environ.get` (no third-party templating library).
- `OpenAICompatibleClient` implements the existing `LLMClient` Protocol over OpenAI `/v1/chat/completions` using the project's existing `requests` dependency, non-streaming, sequential batch, no-op `unload()`.
- `fallback_chain` is an ordered list of provider IDs; primary-offline is detected at the client boundary (exception/timeout/auth or `(ok=False)`), max one attempt per provider, first success wins, evaluated per route group.
- The provider that produced the result is recorded additively on `JobStatus.provider` (`str | None`) and surfaced via `/route-info`.
- THIS change consumes only `routing.default` + `fallback_chain`; per-language `routing.rules` and `src_tokens_gt` matching are schema-tolerated but NOT interpreted here (reserved for `p1-provider-routing`).

## Consequences
- Routing changes no longer require code edits; provider/endpoint switching is env-driven, satisfying the externalization goal.
- Secrets stay in `.env`; `config/providers.yml` holds only `${VAR}` references and a secret-free `.example` is committed. Unresolved keys must disable the provider rather than leak `${VAR}`.
- Backward-compatible: absent/empty/all-disabled `providers.yml` falls back to Ollama-only behavior; `provider` defaults to `None`. Rollback is revert + remove `providers.yml` with no data migration.
- Downstream changes must not silently reinterpret `routing.rules` in a way that breaks the registry/fallback contract defined here; reversing config-driven routing back to a hardcoded table would regress the externalization guarantee and break both downstream changes.
- Sync `requests` fallback means a hanging primary consumes its read timeout before the chain advances; timeout tuning via `TimeoutConfig` is required to bound fallback latency. Async `httpx` was rejected for now (codebase is sync/thread-based).
