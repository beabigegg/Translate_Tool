---
change-id: p1-provider-routing
schema-version: 0.1.0
last-changed: 2026-06-17
risk: medium
tier: 2
---

# Test Plan: p1-provider-routing

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_model_router.py::TestConfigDrivenRouting::test_hardcoded_routing_table_removed | 0 |
| AC-1 | unit | tests/test_model_router.py::TestProviderRoutingRules::test_routing_rules_key_consumed_from_config | 0 |
| AC-2 | contract | tests/test_model_router.py::TestProviderRoutingRules::test_config_only_change_routes_new_language | 0 |
| AC-3 | unit | tests/test_model_router.py::TestResolveRouteGroupsPerLanguage::test_each_target_resolved_independently | 0 |
| AC-3 | unit | tests/test_model_router.py::TestResolveRouteGroupsPerLanguage::test_first_target_not_used_for_all | 0 |
| AC-4 | unit | tests/test_model_router.py::TestResolveRouteGroupsPerLanguage::test_mixed_batch_vi_de_ko_ja_groups | 0 |
| AC-4 | unit | tests/test_model_router.py::TestResolveRouteGroupsPerLanguage::test_mixed_batch_group_models_match_rules | 0 |
| AC-5 | unit | tests/test_model_router.py::TestProviderRoutingRules::test_unlisted_language_falls_back_to_default | 0 |
| AC-5 | unit | tests/test_model_router.py::TestProviderRoutingRules::test_default_fallback_no_crash | 0 |
| AC-6 | unit | tests/test_model_router.py::TestResolveRoute | 0 |
| AC-6 | unit | tests/test_model_router.py::TestResolveRouteGroups | 0 |
| AC-6 | unit | tests/test_model_router.py::TestGreedyPreset | 0 |
| AC-6 | unit | tests/test_model_router.py::TestGetRouteInfo | 0 |
| AC-6 | unit | tests/test_model_router.py::TestConfigDrivenRouting | 0 |
| AC-6 | unit | tests/test_model_router.py::TestLegacyOllamaPath::test_provider_config_none_uses_ollama_grouping | 0 |
| AC-6 | unit | tests/test_model_router.py::TestLegacyOllamaPath::test_legacy_profile_override_non_auto_returns_none | 0 |
| AC-7 | contract | contracts/business/business-rules.md | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | All new tests in `tests/test_model_router.py`; fixture providers.yml built via `tmp_path`; never reads real `config/providers.yml` |
| contract | 1 | Assert resolved `(model, provider)` in `RouteGroup` matches fixture `routing.rules` or `routing.default`; business-rules contract updated for AC-7 |

## New Test Classes and Functions Required

All additions go in `tests/test_model_router.py`.

**TestProviderRoutingRules** (new — `routing.rules` consumed from config):
- `test_routing_rules_key_consumed_from_config` — fixture yml with `routing.rules` entries; assert `resolve_route` picks per-language rule, not the default
- `test_config_only_change_routes_new_language` — add a new language to fixture `routing.rules` only; assert it routes to that rule's model (proves AC-2 by construction)
- `test_unlisted_language_falls_back_to_default` — fixture `routing.rules` omits the target; assert result matches `routing.default`
- `test_default_fallback_no_crash` — missing language raises no exception and returns a valid `RouteGroup`

**TestResolveRouteGroupsPerLanguage** (new — per-language independent resolution):
- `test_each_target_resolved_independently` — fixture with two languages mapped to different models; assert two `RouteGroup` objects returned
- `test_first_target_not_used_for_all` — batch `["German", "Vietnamese"]`, German→model-A, Vietnamese→model-B; assert second language is NOT in German's group
- `test_mixed_batch_vi_de_ko_ja_groups` — fixture with distinct rules for vi/de/ko/ja; assert groups partition all four languages with correct model assignments
- `test_mixed_batch_group_models_match_rules` — for each group assert `group.model == fixture_rules[lang].model` for its target(s) (contract assertion)

**TestLegacyOllamaPath** (new — backward compat when `provider_config=None`):
- `test_provider_config_none_uses_ollama_grouping` — call `resolve_route_groups` without `provider_config`; assert result matches expected Ollama per-language grouping
- `test_legacy_single_language_batch` — single target, `provider_config=None`; assert one group returned
- `test_legacy_profile_override_non_auto_returns_none` — `provider_config=None`, `profile_override="general"`; assert `None`

## Fixture Shape Required

Tests exercising `routing.rules` must build a `tmp_path` providers.yml with:

```yaml
routing:
  default:
    model: <fallback-model>
    provider: <fallback-provider>
    profile: general
  rules:
    Vietnamese:
      model: <vi-model>
      provider: <vi-provider>
    Korean:
      model: <ko-model>
      provider: <ko-provider>
```

Do not reference `config/providers.yml` — it has no `routing.rules` when tests run.

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_model_router.py::TestConfigDrivenRouting::test_hardcoded_routing_table_removed | verify asserts `_OLLAMA_ROUTING_TABLE` absent, not just `_ROUTING_TABLE` | AC-1 names the correct symbol |
| tests/test_model_router.py::TestResolveRouteGroups::test_vietnamese_japanese_german_gives_one_group | keep if Ollama-path still groups these three together; update only if per-language resolution changes the expected group count | AC-3/AC-4 may split this group |

## Out of Scope

- E2E translation pipeline (orchestrator, translation_service callers)
- Cloud provider authentication or HTTP calls
- `routing.rules` schema validation enforcement
- `get_route_info` per-language behaviour (unchanged)
- Tests requiring a live Ollama or cloud endpoint

## Notes

- All tests in `tests/test_model_router.py` run with `pytest tests/test_model_router.py`; no network calls; must complete < 30 s.
- New tests must fail before implementation (TDD red phase) to qualify as gate blockers.
- Existing `TestResolveRoute`, `TestResolveRouteGroups`, `TestGreedyPreset`, `TestGetRouteInfo`, and `TestConfigDrivenRouting` must pass unchanged in intent — do not alter their assertions.
- `test_hardcoded_routing_table_removed` already exists; confirm it checks `_OLLAMA_ROUTING_TABLE` (the symbol name used in the current implementation).
