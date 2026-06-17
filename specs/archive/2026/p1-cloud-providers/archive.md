# Archive — p1-cloud-providers

## Change Summary

Added cloud LLM provider support by introducing `OpenAICompatibleClient` (implementing the existing `LLMClient` Protocol via OpenAI `/v1/chat/completions`), an externalized `config/providers.yml` provider registry with `${VAR:-default}` env-var interpolation, and an automatic fallback chain in the orchestrator. The hardcoded `_ROUTING_TABLE` in `model_router.py` was replaced by config-driven routing. `JobStatus.provider` and `RouteInfoEntry.provider` were added so callers can see which provider processed each job. This change unblocks `p1-provider-routing` and `p1-observability-metrics`.

## Final Behavior

- Cloud translation requests go to the primary provider in `providers.yml` (default: Panjit `gpt-oss:120b`).
- On connection / timeout / HTTP 401-403 failure the orchestrator walks the `fallback_chain` and tries the next provider; winner is recorded in `JobStatus.provider`.
- When all cloud providers are exhausted (or `providers.yml` is absent), the system falls back to Ollama-local; `JobStatus.provider` is `"ollama-local"`.
- An unresolved `${VAR}` in `providers.yml` disables that provider rather than sending the literal template string to the endpoint.
- `/api/route-info` now returns a `provider` field per route group.
- Context detection (`_detect_document_context`) always uses the Ollama client, not the active translation client, because it depends on Ollama-specific methods.

## Final Contracts Updated

| contract | version | change |
|---|---|---|
| `contracts/api/api-contract.md` | 0.1.0 → 0.2.0 | RouteInfoEntry.provider, JobStatus.provider, JobStatus.term_summary |
| `contracts/env/env-contract.md` | 0.1.0 → 0.2.0 | 5 new vars (PANJIT_LLM_BASE_URL, PANJIT_API, DEEPSEEK_BASE_URL, DEEPSEEK_API, DEEPSEEK_ENABLED); Secret Policy + Deployment Sync Policy filled |
| `contracts/data/data-shape-contract.md` | 0.1.0 → 0.2.0 | JobStatus.provider optional column |
| `contracts/business/business-rules.md` | 0.1.0 → 0.2.0 | BR-4 updated; BR-12..17 added; Table C (fallback decision table) |

Evidence path: `agent-log/backend-engineer.yml` → `contracts-touched`; `contracts/CHANGELOG.md`.

## Final Tests Added / Updated

| file | status | count | notes |
|---|---|---|---|
| `tests/test_openai_compatible_client.py` | new | 18 | Protocol conformance, translate/batch/refine, error mapping, config, secret safety |
| `tests/test_provider_fallback.py` | new | 10 | fallback chain, offline/timeout/auth-failure, attribution, data-boundary (malformed yml, DEEPSEEK_ENABLED=false) |
| `tests/test_llm_client_protocol.py` | extended | +4 | OpenAICompatibleClient conformance + JobStatus.provider shape |
| `tests/test_model_router.py` | extended | +4 | config-driven routing; hardcoded table removed |
| `tests/test_model_config_api.py` | extended | +2 | provider field on /route-info |
| `tests/fixtures/test.pdf` | new fixture | — | Enables 4 previously-skipped PDF parser integration tests |

Final result: **350 passed, 0 skipped, 0 failed**. Evidence path: `specs/changes/p1-cloud-providers/test-evidence.yml`.

## Final CI/CD Gates

- Required (Tier 1): contract-validate, change-gate, unit-tests, contract-conformance, integration, resilience, data-boundary, secret-scan
- Informational (Tier 2): full-regression, env-template-check
- Manual (Tier 5): cloud-smoke-test before first production deploy

Source: `specs/changes/p1-cloud-providers/ci-gates.md`; workflow updated in `.github/workflows/contract-driven-gates.yml`.

## Production Reality Findings

Four critical bugs were found by contract-reviewer (not by unit tests) during the implementation pass:

1. **Cloud client discarded**: `orchestrator.py` built `_cloud_client` then unconditionally reassigned `client = OllamaClient(...)`, discarding the cloud client entirely. All cloud translation silently ran on Ollama. Fixed by `client = _cloud_client if _cloud_client is not None else ollama_client`.

2. **routes.py never passed `provider_config`**: `get_route_info()` and `resolve_route_groups()` were called without the `provider_config` kwarg; `/route-info` always returned `"ollama-local"` regardless of `providers.yml`. Fixed at routes module level.

3. **Attribution false positive**: When the cloud fallback chain was exhausted and `client` fell back to `ollama_client`, `_provider_id` still held the last cloud provider ID. `winning_provider` reported `"panjit"` when Ollama actually ran. Fixed by setting `_provider_id = "ollama-local"` in the else branch.

4. **Context detection failure for cloud jobs**: `_detect_document_context` calls `client._build_no_system_payload()` and `client._call_ollama()` — methods absent on `OpenAICompatibleClient`. Caught silently; context returned `""` for all cloud-primary jobs. Fixed by always passing `ollama_client` (always built) to this function.

Additionally, `OpenAICompatibleClient` required orchestrator-compat stubs (`system_prompt`, `model_type`, `health_check()`, `_is_translation_dedicated()`, `_is_translategemma_model()`, `set_runtime_options_override()`, `set_cache_variant()`) that were not in the original spec.

A `tier-floor-override` was required: the tier-floor keyword detector matched `"api key"` (third-party env vars) and `"cache"` (translation cache) and demanded Tier 0. These are false positives; Tier 1 is correct.

## Lessons Promoted to Standards

| lesson | target | evidence path |
|---|---|---|
| `cdd-kit gate` tier-floor detector false-positive: third-party provider API key env vars (e.g. `PANJIT_API`) match keyword `"api key"` and force Tier 0 — use `tier-floor-override` with written rationale if no auth system is involved; see `contracts/env/env-contract.md` Secret Policy. | `CLAUDE.md` → Promoted Learnings (line 3 inside markers) | `specs/changes/p1-cloud-providers/agent-log/audit.yml` |

## Follow-up Work

| item | owner | priority |
|---|---|---|
| Cloud smoke test (manual, Tier 5) — sign off before first production deploy with real Panjit endpoint | platform-team | deploy gate |
| `translation_service.py:235` — residual `OllamaClient._build_refine_system_prompt` private static call; should use Protocol method | application-team | low |
| `p1-provider-routing` — now unblocked (depends on this change) | — | next |
| `p1-observability-metrics` — unblocked after `p1-provider-routing` | — | after routing |

---

*This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.*
