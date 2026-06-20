---
change-id: settings-page-cloud-redesign
schema-version: 0.1.0
last-changed: 2026-06-20
risk: medium
tier: 2
---

# Test Plan: settings-page-cloud-redesign

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 (VRAM removal) | e2e / visual | app/frontend/src/pages/__tests__/SettingsPage.test.jsx | 1 |
| AC-2 (provider status badges) | e2e | app/frontend/src/pages/__tests__/SettingsPage.test.jsx | 1 |
| AC-3 (health online) | unit | tests/test_providers_api.py::TestProvidersHealth::test_health_panjit_online | 0 |
| AC-3 (health offline) | unit | tests/test_providers_api.py::TestProvidersHealth::test_health_panjit_offline | 0 |
| AC-3 (health not_configured) | unit | tests/test_providers_api.py::TestProvidersHealth::test_health_deepseek_not_configured_when_no_key | 0 |
| AC-3 (health deepseek with key) | unit | tests/test_providers_api.py::TestProvidersHealth::test_health_deepseek_online_when_key_supplied | 0 |
| AC-3 (health list shape) | unit | tests/test_providers_api.py::TestProvidersHealth::test_health_returns_list | 0 |
| AC-3 (models list) | unit | tests/test_providers_api.py::TestProvidersModels::test_models_returns_provider_list | 0 |
| AC-3 (models translate_model) | unit | tests/test_providers_api.py::TestProvidersModels::test_models_includes_translate_model_from_config | 0 |
| AC-3 (models config=None) | resilience | tests/test_providers_api.py::TestProvidersModels::test_models_graceful_when_config_none | 0 |
| AC-4 (localStorage key pattern) | e2e | app/frontend/src/pages/__tests__/SettingsPage.test.jsx | 1 |
| AC-5 (DeepSeek disabled no key) | e2e | app/frontend/src/pages/__tests__/SettingsPage.test.jsx | 1 |
| AC-6 (PANJIT success) | unit | tests/test_providers_api.py::TestProvidersTestTranslation::test_test_translation_panjit_success | 0 |
| AC-6 (DeepSeek no key error) | unit | tests/test_providers_api.py::TestProvidersTestTranslation::test_test_translation_deepseek_no_key_returns_error_slot | 0 |
| AC-6 (partial failure isolated) | resilience | tests/test_providers_api.py::TestProvidersTestTranslation::test_test_translation_partial_failure_isolated | 0 |
| AC-6 (COMET enabled) | unit | tests/test_providers_api.py::TestProvidersTestTranslation::test_test_translation_comet_score_present_when_qe_enabled | 0 |
| AC-6 (COMET absent when disabled) | unit | tests/test_providers_api.py::TestProvidersTestTranslation::test_test_translation_comet_score_absent_when_qe_disabled | 0 |
| AC-7 (cost-guard no network call) | unit | tests/test_providers_api.py::TestProvidersTestTranslation::test_test_translation_deepseek_no_key_returns_error_slot | 0 |
| AC-7 (key not logged) | unit | tests/test_providers_api.py::TestProvidersTestTranslation::test_test_translation_deepseek_key_is_not_logged | 0 |
| AC-8 (missing text → 422) | data-boundary | tests/test_providers_api.py::TestProvidersTestTranslation::test_test_translation_missing_text_field_returns_422 | 0 |
| AC-8 (missing targets → 422) | data-boundary | tests/test_providers_api.py::TestProvidersTestTranslation::test_test_translation_missing_targets_returns_422 | 0 |
| AC-8 (ProviderHealthItem shape) | contract | tests/test_providers_api.py::TestContractShapes::test_health_response_shape_matches_contract | 0 |
| AC-8 (ProviderModelEntry shape) | contract | tests/test_providers_api.py::TestContractShapes::test_models_response_shape_matches_contract | 0 |
| AC-8 (TestTranslationResult shape) | contract | tests/test_providers_api.py::TestContractShapes::test_test_translation_result_shape_matches_contract | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | All 3 new backend endpoints; mocked OpenAICompatibleClient |
| contract | 0 | Field presence/type assertions vs. data-shape-contract.md shapes |
| data-boundary | 0 | 422 on missing required fields |
| resilience | 0 | Partial fan-out failure → HTTP 200 with mixed results; config=None → [] |
| e2e | 1 | SettingsPage VRAM removal, status badges, localStorage key form, disabled state |
| visual | 1 | Redesigned page states — evidence in visual-review-report.md |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| (none) | — | New file only; no existing tests cover these routes |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope
- Live network calls to PANJIT or DeepSeek (all tests mock at OpenAICompatibleClient boundary)
- Stress/soak (single-sentence synchronous; per change-classification.md §Tasks Not Applicable)
- OpenAPI export correctness (gate: `cdd-kit openapi export --check` in ci-gates.md)

## Notes
- Mock target: `app.backend.api.routes._providers_config` and `app.backend.api.routes.OpenAICompatibleClient`.
- `comet_score` must be absent (not null) when QE_ENABLED=False — asserted as `"comet_score" not in result`.
- Key-logging test captures root logger output and asserts the literal key string never appears.
- AC-1/AC-2/AC-4/AC-5 are frontend-only; their contract surface is covered by AC-3/AC-6/AC-7/AC-8 backend tests.
