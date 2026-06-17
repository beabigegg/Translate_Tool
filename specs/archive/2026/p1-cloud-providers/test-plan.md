---
change-id: p1-cloud-providers
schema-version: 0.1.0
last-changed: 2026-06-17
risk: high
tier: 1
---

# Test Plan: p1-cloud-providers

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | contract | tests/test_llm_client_protocol.py | 0 |
| AC-1 | unit | tests/test_openai_compatible_client.py | 0 |
| AC-2 | unit | tests/test_openai_compatible_client.py | 0 |
| AC-3 | unit | tests/test_openai_compatible_client.py | 0 |
| AC-3 | data-boundary | tests/test_openai_compatible_client.py | 0 |
| AC-4 | unit | tests/test_model_router.py | 0 |
| AC-5 | resilience | tests/test_provider_fallback.py | 1 |
| AC-5 | integration | tests/test_provider_fallback.py | 1 |
| AC-6 | unit | tests/test_provider_fallback.py | 1 |
| AC-6 | contract | tests/test_llm_client_protocol.py | 0 |
| AC-7 | contract | tests/test_model_config_api.py | 1 |
| AC-8 | contract | tests/test_llm_client_protocol.py | 0 |

### Test names per file

**tests/test_openai_compatible_client.py** (new)
- `TestProtocolConformance::test_openai_compatible_client_satisfies_protocol`
- `TestProtocolConformance::test_openai_compatible_client_isinstance_llm_client`
- `TestTranslateOnce::test_successful_translation_returns_ok_true`
- `TestTranslateOnce::test_http_error_returns_ok_false`
- `TestTranslateOnce::test_connection_timeout_returns_ok_false`
- `TestTranslateBatch::test_batch_calls_translate_once_sequentially`
- `TestTranslateBatch::test_batch_partial_failure_returns_ok_false`
- `TestRefineTranslation::test_refine_returns_ok_true_on_success`
- `TestHealth::test_health_probe_reachable_returns_true`
- `TestHealth::test_health_probe_unreachable_returns_false`
- `TestListModels::test_list_models_returns_list_of_strings`
- `TestUnload::test_unload_is_noop_returns_true`
- `TestConfigLoading::test_providers_yml_env_var_interpolation`
- `TestConfigLoading::test_missing_providers_yml_falls_back_to_ollama`
- `TestConfigLoading::test_malformed_providers_yml_falls_back_to_ollama`
- `TestConfigLoading::test_unresolved_env_var_disables_provider`
- `TestConfigLoading::test_all_providers_disabled_falls_back_to_ollama`
- `TestSecretHandling::test_literal_api_key_not_emitted_in_request`

**tests/test_model_router.py** (extend existing)
- `TestConfigDrivenRouting::test_resolve_route_uses_providers_yml`
- `TestConfigDrivenRouting::test_hardcoded_routing_table_removed`
- `TestConfigDrivenRouting::test_default_route_from_config`
- `TestConfigDrivenRouting::test_provider_field_present_in_route_decision`

**tests/test_model_config_api.py** (extend existing)
- `test_route_info_response_includes_provider_field`
- `test_route_info_provider_matches_routing_decision`

**tests/test_provider_fallback.py** (new)
- `TestFallbackChain::test_primary_offline_falls_back_to_next`
- `TestFallbackChain::test_primary_timeout_falls_back_to_next`
- `TestFallbackChain::test_primary_auth_failure_falls_back_to_next`
- `TestFallbackChain::test_all_providers_fail_job_fails`
- `TestFallbackChain::test_first_success_wins_chain_stops`
- `TestProviderAttribution::test_winning_provider_recorded_on_job_status`
- `TestProviderAttribution::test_fallback_provider_recorded_not_primary`
- `TestProviderAttribution::test_no_provider_recorded_when_job_fails`
- `TestJobStatusShape::test_job_status_provider_field_is_optional_str`
- `TestJobStatusShape::test_job_status_provider_field_defaults_to_none`

**tests/test_llm_client_protocol.py** (extend existing)
- `TestOpenAICompatibleClientConformance::test_openai_compatible_client_satisfies_protocol`
- `TestOpenAICompatibleClientConformance::test_openai_compatible_client_isinstance_llm_client`
- `TestJobStatusProviderField::test_job_status_schema_has_provider_field`
- `TestJobStatusProviderField::test_job_status_provider_defaults_to_none`

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | OpenAICompatibleClient methods, config loading, env interpolation, model_router config-driven path |
| contract | 0 | LLMClient Protocol conformance for OpenAICompatibleClient; JobStatus schema shape |
| integration | 1 | Fallback chain end-to-end with mocked HTTP; provider attribution written to JobStatus |
| resilience | 1 | Primary offline / timeout / auth-failure triggers fallback; winning provider recorded |
| data-boundary | 0 | Malformed/missing providers.yml; unresolved env var disables provider; JobStatus provider=None default |

## Test Execution Ladder

| phase | command |
|---|---|
| collect | `pytest --collect-only tests/test_openai_compatible_client.py tests/test_provider_fallback.py tests/test_model_router.py tests/test_model_config_api.py tests/test_llm_client_protocol.py` |
| targeted | `pytest tests/test_openai_compatible_client.py tests/test_provider_fallback.py` |
| changed-area | `pytest tests/test_openai_compatible_client.py tests/test_provider_fallback.py tests/test_model_router.py tests/test_model_config_api.py tests/test_llm_client_protocol.py` |
| contract | `pytest tests/test_llm_client_protocol.py` |
| full | `pytest tests/` |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_model_router.py (all TestResolveRoute / TestGetRouteInfo cases) | update | hardcoded _ROUTING_TABLE removed; routing now reads ProviderConfig from providers.yml (AC-4) |
| tests/test_model_config_api.py | update | /route-info response gains provider field (AC-7) |
| tests/test_llm_client_protocol.py | extend | add OpenAICompatibleClient conformance class + JobStatus provider field class (AC-1, AC-6) |

## TDD Order

Backend-engineer must write failing tests in `targeted` + `changed-area` phases before any implementation. Resilience and data-boundary tests are part of `targeted` — they must exist and fail before `openai_compatible_client.py`, `config.py` changes, or `model_router.py` refactor are written.

## Out of Scope

- Real HTTP calls to Panjit or DeepSeek endpoints (all tests use mocked HTTP at the `requests` boundary)
- E2E browser or UI tests
- Stress, soak, and monkey tests
- `DeepLClient` (P3-8 scope)
- Per-language precise routing rules (`p1-provider-routing` scope)
- Observability metrics (`p1-observability-metrics` scope)

## Notes

- `tests/test_llm_client_protocol.py` already exists; extend with new classes, do not duplicate.
- Mock at `requests.Session.post/get` boundary only — never mock internal `OpenAICompatibleClient` methods.
- `JobStatus.provider` is additive optional; backward-compatibility (default `None`) is a required assertion.
- `providers.yml` loading tests must cover file-absent and file-malformed paths to satisfy the rollback guarantee in design.md.
