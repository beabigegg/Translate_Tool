## 1. Backend — Profile System
- [x] 1.1 Create `app/backend/translation_profiles.py` with `TranslationProfile` dataclass, 7 profile definitions (general, government, semiconductor, fab, manufacturing, financial, legal), `get_profile()`, and `list_profiles()`
- [x] 1.2 Write detailed system prompts for each profile following the structure: role declaration → terminology guidance with domain-specific terms → register/tone → output rules → numerical/code preservation → smart-skip rule ("If the input text is already entirely in the target language, return it unchanged without modification.")
- [x] 1.3 Update `app/backend/config.py`: change `DEFAULT_MODEL` to `"qwen3.5:9b"`
- [x] 1.4 Update `app/backend/config.py` runtime defaults for 8GB VRAM tuning:
  - `OLLAMA_NUM_CTX` default: `5120`
  - `DEFAULT_READ_TIMEOUT_S` default: `360`
  - `MAX_PARAGRAPH_CHARS` default: `2400`
  - `MAX_MERGE_SEGMENTS` default: `12`

## 2. Backend — Ollama Client Prompt Architecture
- [x] 2.1 Add `system_prompt` and `profile_id` params to `OllamaClient.__init__`, store as instance attributes
- [x] 2.2 Add `_build_payload(prompt)` helper that returns `{"model", "prompt", "options"}` and conditionally includes `"system"` when `self.system_prompt` is set
- [x] 2.3 Add `_build_user_prompt(text, tgt, src_lang)` for the system-prompt path — produces language direction + source text only (no persona/domain instructions, those live in the system prompt). When `src_lang` is `"auto"` or empty, use `"Translate to {tgt}:"` (omit source); otherwise use `"Translate from {src} to {tgt}:"`
- [x] 2.4 Add `_build_batch_user_prompt(texts, tgt, src_lang)` for the system-prompt batch path — produces segments with `<<<SEG_N>>>` markers, language direction, and output format instructions only. Same auto-detect direction logic as 2.3
- [x] 2.5 Update `_build_translategemma_prompt` and `_build_generic_prompt` to treat `src_lang="auto"` the same as `None` (fall back to `"English"`)
- [x] 2.6 Refactor `translate_once` with profile-internal branching: if `"translategemma"` in `self.model` → `_build_translategemma_prompt` (no system field, ignore system_prompt); elif `self.system_prompt` → `_build_user_prompt` + `_build_payload` (with system); else → `_build_generic_prompt` + `_build_payload`
- [x] 2.7 Refactor `_translate_chunked`, `_translate_with_extended_retry` to use the same three-way branching via `_build_payload()`
- [x] 2.8 Refactor `translate_batch` to use `_build_batch_user_prompt` for system-prompt path, existing builders for other paths, all via `_build_payload()`
- [x] 2.9 Add `cache_model_key` property returning `"{model}::{profile_id}"` when profile_id is set, else just `model`

## 3. Backend — Cache Compatibility
- [x] 3.1 Update `TranslationCache.clear(model=...)` to use `WHERE LOWER(model) = ? OR LOWER(model) LIKE ?` with params `(model.lower(), f"{model.lower()}::%")` to safely delete exact model + all `::` profile variants without false positives
- [x] 3.2 Update `translation_service.py`: replace `client.model` with `client.cache_model_key` at all cache call sites (get_batch, put_batch entries, individual put)

## 4. Backend — API Layer
- [x] 4.1 Add `ProfileItem` Pydantic model to `app/backend/api/schemas.py` (fields: `id`, `name`, `description`)
- [x] 4.2 Add `GET /api/profiles` endpoint to `app/backend/api/routes.py`, returning `List[ProfileItem]` (bare JSON array, no wrapper)
- [x] 4.3 In `POST /api/jobs`: replace `model: Optional[str] = Form(None)` with `profile: Optional[str] = Form(None)` — remove the `model` parameter entirely
- [x] 4.4 Resolve profile in `create_job` route handler via `get_profile(profile_id)` and pass resolved `model`, `system_prompt`, `profile_id` to `job_manager.create_job`

## 5. Backend — Pipeline Threading & Logging
- [x] 5.1 Update `job_manager.py`: replace `model` param with `system_prompt` and `profile_id` in `create_job()` (model comes from profile resolution in the route handler), pass all three through `_run_job()` → `process_files()`
- [x] 5.2 Update `job_manager.py`: extend `[CONFIG]` log line to include `model=` and `profile=` fields
- [x] 5.3 Update `orchestrator.py`: add `system_prompt` and `profile_id` params to `process_files()`, pass to `OllamaClient` constructor

## 6. Frontend
- [x] 6.1 Add `fetchProfiles()` to `app/frontend/src/api.js`
- [x] 6.2 In `App.jsx`: remove hardcoded model, add `profiles`/`selectedProfile` state, fetch profiles on mount with fallback to `[{id: "general", name: "通用翻譯", description: "General translation"}]`
- [x] 6.5 In `App.jsx`: change `srcLang` default from `"English"` to `"auto"`, add "Auto-detect (自動偵測)" as the first option in source language selector
- [x] 6.3 In `App.jsx`: add profile selector card (always visible, above Advanced Settings, radio buttons with name + description), using existing `.radio-group` / `.radio-option` CSS patterns
- [x] 6.4 In `App.jsx`: update `handleSubmit` to send `profile` field instead of `model`

## 7. Update OpenSpec Project Context
- [x] 7.1 Update `openspec/project.md` to reflect `qwen3.5:9b` as default model and profile system

## 8. Runtime Bootstrap Script
- [x] 8.1 Update `translate_tool.sh` to set default runtime env vars when unset:
  - `OLLAMA_NUM_CTX=5120`
  - `OLLAMA_NUM_GPU=99`
  - `TRANSLATE_CONNECT_TIMEOUT=15`
  - `TRANSLATE_READ_TIMEOUT=360`
- [x] 8.2 Ensure `translate_tool.sh` preserves explicit user-provided env values (do not overwrite pre-set values)

## 9. Verification
- [x] 9.1 Start backend, verify `GET /api/profiles` returns 7 profiles with id, name, description
- [ ] 9.2 Start frontend, verify profile selector renders with "general" selected by default
- [ ] 9.3 Submit translation with "general" profile — verify success and clean output (no markdown, no commentary)
- [ ] 9.4 Submit same text with "semiconductor" profile — verify cache miss and domain-appropriate translation (semiconductor terminology used correctly)
- [x] 9.5 Verify logs show `[CONFIG] model=qwen3.5:9b, profile=semiconductor` in job log
- [x] 9.6 Verify `DELETE /api/cache?model=qwen3.5:9b` clears entries for all profile variants
- [x] 9.7 Verify translategemma internal compatibility: if a profile's model field contains "translategemma", no `system` field in Ollama payload
- [x] 9.10 Verify auto-detect source language: submit with src_lang="auto", confirm prompt uses "Translate to {tgt}:" without source language
- [ ] 9.11 Verify smart-skip: submit text already in target language, confirm model returns it unchanged
- [ ] 9.8 On RTX 4060 8GB testbed, verify `OLLAMA_NUM_CTX=5120` runs stably without repeated unload/reload or RAM spill slowdown for representative long-document jobs
- [ ] 9.9 Verify fallback guidance: reducing `OLLAMA_NUM_CTX` from `5120` to `4608` resolves instability on tighter VRAM environments
