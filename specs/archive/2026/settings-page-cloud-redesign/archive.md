# Archive: settings-page-cloud-redesign

## Change Summary

Redesigned SettingsPage from Ollama-centric VRAM/num_ctx controls to a cloud-provider settings UI. Added three new backend API endpoints (GET /providers/health, GET /providers/models, POST /providers/test-translation) and rewrote the frontend settings page to show provider status badges, model configuration, a DeepSeek API key input (localStorage-only), and a parallel test-translation panel. The change was driven by the removal of the local Ollama assumption and the need to expose cloud-provider health and model configuration to end-users.

## Final Behavior

- GET /api/providers/health: probes configured providers synchronously; PANJIT always probed; DeepSeek probed only when `X-DeepSeek-Api-Key` request header is supplied; returns `{provider, status, latency_ms}` list with `not_configured` for absent keys.
- GET /api/providers/models: returns model names from in-memory providers.yml config; no live network call.
- POST /api/providers/test-translation: fans out a short translation to selected providers via asyncio.gather + return_exceptions=True; returns per-provider `{model_id, provider, duration_ms, translation?, comet_score?, error?}` list; DeepSeek key from request body only, never from env, never logged.
- SettingsPage: shows Provider Status table (ProviderStatusBadge with online/offline/not_configured states), Model Configuration table, DeepSeek API Key section (password field, localStorage persistence, filled/empty/masked/disabled states), Test Translation panel (idle/running/done/error states with per-result success/error cards).
- VramCalculator, num_ctx, VRAM controls fully removed from SettingsPage.
- All Optional fields serialized with `response_model_exclude_none=True` — absent from JSON (not null) when no value.
- i18n: all new strings in both en.js and zh-TW.js.

## Final Contracts Updated

- `contracts/api/api-contract.md` — schema-version 0.7.0; 4 new typed schemas, 3 new endpoints, Endpoint Notes for key transport (header for GET, body for POST)
- `contracts/data/data-shape-contract.md` — schema-version 0.10.0; `## Provider API Response Shapes` section added
- `contracts/business/business-rules.md` — schema-version 0.15.0; BR-63, BR-64, BR-65 added
- `contracts/env/env-contract.md` — schema-version 0.9.0; DeepSeek localStorage-only key pattern added to Secret Policy
- `contracts/css/css-contract.md` — schema-version 0.2.0; SettingsPage, ProviderStatusBadge, DeepSeekKeyInput, TestTranslationPanel component rows added
- `contracts/api/openapi.yml` and `openapi.json` — regenerated (28 endpoints)

## Final Tests Added / Updated

- `tests/test_providers_api.py` — 24 new tests (4 classes): TestProvidersHealth (8), TestProvidersModels (4), TestProvidersTestTranslation (10), TestProvidersApiEdgeCases (2)
- Targeted run: 24/24 passed
- Changed-area run: 788 passed, 4 skipped (all existing tests green)

## Final CI/CD Gates

| gate | command | blocks |
|---|---|---|
| validate-contracts | `cdd-kit validate --contracts` | merge |
| change-gate | `cdd-kit gate settings-page-cloud-redesign` | merge |
| openapi-sync | `cdd-kit openapi export --check` | merge |
| secret-scan | grep for literal API keys | merge |
| targeted-tests | `pytest tests/test_providers_api.py` | merge |
| full-suite | `pytest tests/` | merge |

## Production Reality Findings

- QA reviewer found contract drift: api-contract.md Endpoint Notes and BR-63 documented the DeepSeek key for GET /providers/health as a "query parameter `deepseek_api_key`" but implementation used `X-DeepSeek-Api-Key` request header. Frontend and backend agreed on the header (correct per BR-65 — avoids key in access logs). Fixed before commit by updating api-contract.md Endpoint Notes and BR-63 to document the header. No runtime impact.
- Visual reviewer found SettingsPage missing `error` state for models-fetch rejection. Fixed before commit: added `modelsError` state with `var(--error)` styled paragraph. 
- Visual reviewer noted two hardcoded rem values (0.625rem dot size, 0.125rem pill padding) not in token scale — deferred; no token for these micro-sizes exists.
- Visual reviewer noted contracts/css/design-tokens.md has empty section bodies (stub). Deferred.
- `asyncio.gather` requires `return_exceptions=True` for partial-failure isolation — backend-engineer applied this; caught during implementation.
- `response_model_exclude_none=True` must be added explicitly to FastAPI route decorators when Optional fields should be absent from JSON (not null). Caught during testing when `latency_ms: null` appeared in health responses for `not_configured` providers.

## Lessons Promoted to Standards

None — all product behavior rules already promoted to contracts (BR-63/64/65, env Secret Policy, api-contract Endpoint Notes). No new cross-change agent workflow guidance.

## Follow-up Work

- `contracts/css/design-tokens.md` section bodies are empty stubs — future token-system change should populate them.
- Two hardcoded rem values in SettingsPage (line 34-35: 0.625rem dot size; line 341: 0.125rem pill padding) — no token exists for these sizes; address in a future CSS token-system change.
- Frontend E2E tests (SettingsPage.test.jsx) noted in ci-gates.md informational gates — not implemented in this change; Jest/Playwright setup is a separate tracked change if desired.

## Cold Data Warning

This archive is historical evidence. Current requirements live in contracts/ and active project guidance.
