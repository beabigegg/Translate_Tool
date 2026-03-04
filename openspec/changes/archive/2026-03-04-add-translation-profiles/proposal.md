# Change: Add Translation Profile Presets and Switch to Qwen 3.5 9B

## Why
The current system hardcodes `translategemma:12b` as the only model and provides no way to customize translation style for different industries or document types. Switching to `qwen3.5:9b` (a general-purpose LLM with 128K native context, 18T training tokens, and official Vietnamese support) provides better CJK tokenization, lower VRAM usage, and faster inference. Adding domain-specific "translation profiles" with tailored system prompts enables users to select the optimal translation style for their document type (e.g., semiconductor FMEA vs. legal contracts).

## What Changes
- **BREAKING**: Default model changes from `translategemma:12b` to `qwen3.5:9b`
- Add a `TranslationProfile` system with 7 presets: General, Government, Semiconductor, FAB, Manufacturing, Financial, Legal
- Add Ollama `system` prompt support to `OllamaClient` (currently only `prompt` is sent)
- Tune runtime defaults for RTX 4060 8GB-class GPUs to operate near VRAM limits while preserving long-text coherence:
  - `OLLAMA_NUM_CTX` default to `5120`
  - `DEFAULT_READ_TIMEOUT_S` default to `360`
  - `MAX_PARAGRAPH_CHARS` default to `2400`
  - `MAX_MERGE_SEGMENTS` default to `12`
- Update startup script (`translate_tool.sh`) to set these runtime env defaults when unset, while preserving user overrides
- Add `GET /api/profiles` endpoint to serve available profiles
- Add `profile` parameter to `POST /api/jobs` endpoint
- Add profile selector UI in frontend (always visible, not in collapsible settings)
- Auto-detect source language as new default (Qwen can infer source language, unlike TranslateGemma)
- Smart-skip via system prompt: if text is already in target language, return unchanged
- Cache keys differentiate by profile to prevent cross-profile contamination
- Existing `translategemma` prompt paths retained internally as code-level fallback (profile-internal, not user-facing)
- **Cross-proposal note**: `add-image-ocr-translation` assumes TranslateGemma:12b VRAM budget; that proposal should be updated to use profile-based model selection after this change lands. Recommend pending `add-image-ocr-translation` until this proposal is applied.

## Impact
- Affected specs: `translation-backend` (model change, system prompt), new `translation-profiles` capability, new `frontend-ui` capability
- Affected code:
  - `app/backend/translation_profiles.py` (new)
  - `app/backend/config.py` (DEFAULT_MODEL)
  - `app/backend/clients/ollama_client.py` (system prompt support)
  - `translate_tool.sh` (runtime env defaults for 8GB VRAM tuning)
  - `app/backend/api/routes.py` (new endpoint + profile param)
  - `app/backend/api/schemas.py` (new response model)
  - `app/backend/services/job_manager.py` (threading profile params)
  - `app/backend/processors/orchestrator.py` (threading profile params)
  - `app/backend/services/translation_service.py` (cache key adjustment)
  - `app/frontend/src/api.js` (fetchProfiles)
  - `app/frontend/src/App.jsx` (profile selector UI)
