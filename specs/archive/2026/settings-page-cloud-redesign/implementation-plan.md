---
change-id: settings-page-cloud-redesign
schema-version: 0.1.0
last-changed: 2026-06-20
---

# Implementation Plan: settings-page-cloud-redesign

## Summary
Replace the Ollama-centric SettingsPage with a cloud-provider control surface and add three additive backend endpoints (`GET /api/providers/health`, `GET /api/providers/models`, `POST /api/providers/test-translation`). The frontend rewrite shows PANJIT/DeepSeek health badges, per-provider model lists, a DeepSeek API-key form (localStorage-only), and a single-sentence test-translation panel with per-model result cards (translation, latency, optional COMET score). The DeepSeek key is owned by the browser, sent per-request in the body, and the backend never reads it from `.env`, never persists it, and never logs it. Authoritative constraints: design.md Decisions 1-3; contract shapes in `contracts/data/data-shape-contract.md ## Provider API Response Shapes`; BR-63/BR-64/BR-65; `contracts/env/env-contract.md ## Secret Policy`; api-contract Endpoint Notes for the three routes. Owners follow this plan and report `blocked` rather than inferring scope from chat. Out of scope: editing/adding models (providers.yml stays admin-managed), any job_id/BackgroundTasks path, live `/v1/models` calls, persisting the DeepSeek key server-side, and any change to existing endpoints/response shapes.

## Backend Tasks (owner: backend-engineer)
Edit targets: `app/backend/api/schemas.py`, `app/backend/api/routes.py`. Reuse (no change): `app/backend/clients/openai_compatible_client.py`, `app/backend/services/quality_evaluator.py`, `app/backend/config.py`.

1. **Add Pydantic schemas** in `app/backend/api/schemas.py` matching the contract field tables exactly (`## Provider API Response Shapes`):
   - `TestTranslationRequest`: `text:str`, `src_lang:str`, `targets:List[str]`, `profile:Optional[str]=None`, `models:Optional[List[str]]=None`, `deepseek_api_key:Optional[str]=None`.
   - `ProviderHealthItem`: `provider:str`, `status:str`, `latency_ms:Optional[float]=None` (omit field when `not_configured`; use `exclude_none` / model construction without the field).
   - `ProviderModelEntry`: `provider:str`, `translate_model:Optional[str]=None`, `long_doc_model:Optional[str]=None`.
   - `TestTranslationResult`: `model_id:str`, `provider:str`, `duration_ms:float`, `translation:Optional[str]=None`, `comet_score:Optional[float]=None`, `error:Optional[str]=None`. `comet_score` must be OMITTED (not null) when `QE_ENABLED=False` — serialize with `exclude_none=True` so omission holds.

2. **`GET /providers/health`** in `routes.py` (query param `deepseek_api_key: Optional[str] = None`) — BR-63, design Decision 3:
   - For each enabled provider in `_providers_config` (already loaded at module init via `load_providers_config()`): build an `OpenAICompatibleClient` and time a wall-clock probe around `client.health()` (issues one `GET /v1/models`). PANJIT uses `verify_ssl=False`. Record `latency_ms`; non-200/exception → `status="offline"`.
   - DeepSeek: probe only when `deepseek_api_key` is non-empty; otherwise emit `status="not_configured"` with `latency_ms` omitted and make NO network call.
   - Return `List[ProviderHealthItem]`.

3. **`GET /providers/models`** in `routes.py` — BR-63, design Decision 3:
   - Read each provider entry's `models` map from in-memory `_providers_config` (`models.translate` → `translate_model`, `models.long_doc` → `long_doc_model`). NO live `/v1/models` call.
   - Return `List[ProviderModelEntry]` (omit `long_doc_model` when absent, e.g. deepseek).

4. **`POST /providers/test-translation`** in `routes.py`, `async def`, body `TestTranslationRequest` — BR-64, BR-65, design Decision 2:
   - Resolve the model slots to run (requested `models` filtered to enabled providers; default = all enabled). PANJIT always eligible; DeepSeek slot eligible only when `req.deepseek_api_key` is present and non-empty.
   - Per slot build a coroutine that constructs the right client (PANJIT from `_providers_config` + `verify_ssl=False`; DeepSeek from `_providers_config` base_url + the per-request key) and calls `translate_once(text, tgt, src_lang)` for each target. Time each with wall-clock `duration_ms`.
   - Fan out with `asyncio.gather(*coros, return_exceptions=True)` — wrap blocking `requests`-based client calls via `asyncio.to_thread`. A raised exception / non-ok result becomes a `TestTranslationResult` with populated `error`; never collapse to a 500. Always HTTP 200 when the body parses.
   - DeepSeek with absent/blank key → result `error="DeepSeek API key not provided"`, no network call (BR-65).
   - COMET: when `QE_ENABLED=True`, for each successful result call `quality_evaluator.load_model(QE_MODEL_NAME, QE_DEVICE)` then `score_blocks(model, [(text, translation)], QE_DEVICE)` and set `comet_score` to the single returned score (empty list → leave omitted). When `QE_ENABLED=False`, omit `comet_score` entirely.
   - SECURITY: never log `deepseek_api_key`; do not write it to any module/global state; discard after the request.

5. **Register routes**: import the four new schemas in `routes.py` and add the three `@router.get/@router.post` handlers; confirm they mount under the `/api` prefix used by existing routes (health/models/etc.).

## Frontend Tasks (owner: frontend-engineer)
Edit targets: `app/frontend/src/pages/SettingsPage.jsx`, `app/frontend/src/api/system.js`, `app/frontend/src/hooks/useHealthCheck.js`, removal of `app/frontend/src/components/domain/VramCalculator.jsx`. Parity reference for Step-2 controls: `app/frontend/src/pages/TranslatePage.jsx`. Use existing `client.js` helpers (`get`, `post`).

1. **`api/system.js`**: add `getProviderHealth(deepseekKey)` → `get('/api/providers/health' + (key ? '?deepseek_api_key=' + encodeURIComponent(key) : ''))`; `getProviderModels()` → `get('/api/providers/models')`; `testTranslation(payload)` → `post('/api/providers/test-translation', JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } })` (the shared `post` does not set the header — pass it here).

2. **`hooks/useHealthCheck.js`**: make provider-aware — poll `GET /api/providers/health` and return per-provider status/latency (keep the existing interval/toast pattern but key it off provider results instead of `/api/health`). Pass the localStorage DeepSeek key so DeepSeek is probed only when set.

3. **`SettingsPage.jsx` full rewrite** (AC-1, AC-2, AC-4, AC-5):
   - REMOVE: GPU VRAM slider, num_ctx slider, all `VramCalculator` usage and its import; then delete `VramCalculator.jsx`. No orphaned import may remain (grep-verify).
   - System status block: PANJIT badge (green/red dot + `latency_ms`); DeepSeek badge — `not configured` when no localStorage key, else online/offline + latency.
   - Model list block: render `ProviderModelEntry[]` from `getProviderModels()` (translate/long_doc per provider).
   - DeepSeek key form: `type="password"` input; Save → `localStorage.setItem('deepseek_api_key', ...)`; Clear → `localStorage.removeItem`; show set/not-set status. NEVER auto-populate from any backend response — read only from localStorage (BR-65, AC-4).
   - When no key in localStorage: disable DeepSeek model options and the Run/test button for DeepSeek (AC-5).
   - Test Translation panel: text input, source/target language selectors and profile selector mirroring TranslatePage Step-2 controls, model multi-select, Run button → `testTranslation(payload)` including `deepseek_api_key` from localStorage when present. Render one result card per `TestTranslationResult`: translation, `duration_ms`, `comet_score` when present, `error` when present.
   - Keep existing default-source-language preference behavior.
   - Style new components against `contracts/css/css-contract.md` + `design-tokens.md`; add UI copy to `app/frontend/src/i18n/`.

## Contract Status
All contracts are already written (api-contract endpoints + schemas + Endpoint Notes; data-shape `## Provider API Response Shapes`; BR-63/64/65; env Secret Policy; css). Implementation must conform, not edit them. After backend route changes, run `cdd-kit openapi export --out contracts/api/openapi.yml` and commit so the `openapi --check` gate passes.

## Test Ladder
Required floor every run: `collect`, `targeted`, `changed-area`. Add `contract` (3 endpoints vs api-contract/openapi), `quality` (full suite touch), and `full` before gate. Implementation agents generate evidence via `cdd-kit test run`; the gate validates `test-evidence.yml`. Detailed mapping (per-AC test files, parallel/COMET/key-isolation cases) lives in `test-plan.md`; primary backend target `tests/test_providers_api.py` (new), plus `tests/test_quality_evaluation.py`, `tests/test_provider_fallback.py`, `tests/test_openai_compatible_client.py`, and frontend `__tests__` for SettingsPage/system.js. Config-content tests must read `config/providers.yml.example`, not the gitignored `providers.yml`.

## Acceptance Criteria Reference
AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8 — defined in `change-classification.md` (## Inferred Acceptance Criteria). Do not infer requirements outside this plan; report `blocked` if any required file, behavior, contract, or test is missing.

## Known Risks
- `comet_score` omission vs null: must serialize with `exclude_none=True`; a null leaks the field and breaks AC-6/AC-8 contract conformance.
- DeepSeek key leakage: avoid logging request bodies and avoid storing the key on any client/global; the gate and qa-reviewer check for this (BR-65).
- Blocking `requests` client inside `async` handler: wrap in `asyncio.to_thread` so `asyncio.gather` truly parallelizes and the event loop is not blocked.
- Frontend orphaned-import regression: deleting `VramCalculator.jsx` without removing every import breaks the build — grep before marking done.
- `_providers_config` may be `None` (providers.yml absent on a fresh checkout) — handlers must degrade gracefully (empty/`not_configured` results), not raise.
