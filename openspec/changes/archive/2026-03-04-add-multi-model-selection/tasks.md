## 1. Backend Core: Model Type System

- [ ] 1.1 Add `ModelType` enum and `MODEL_TYPE_OPTIONS` dict to `config.py` (include per-model-type `num_ctx`: general=4096, translation=3072)
- [ ] 1.2 Add `HYMT_DEFAULT_MODEL` constant to `config.py`
- [ ] 1.3 Move `OLLAMA_NUM_GPU` and `OLLAMA_KV_CACHE_TYPE` defaults into `config.py` (read from env with fallbacks: `num_gpu=99`, `kv_cache_type="q8_0"`)
- [ ] 1.4 Add `model_type` field to `TranslationProfile` dataclass in `translation_profiles.py`
- [ ] 1.5 Add `"hymt"` profile entry to `PROFILES` dict in `translation_profiles.py`

## 2. Backend: OllamaClient Multi-Model Support

- [ ] 2.1 Add `model_type` parameter to `OllamaClient.__init__()`
- [ ] 2.2 Change `_build_options()` from `@staticmethod` to instance method, dispatch by `model_type` (use `MODEL_TYPE_OPTIONS` including per-type `num_ctx`)
- [ ] 2.3 Add `_is_translation_dedicated()` method
- [ ] 2.4 Add `_build_translation_dedicated_prompt()` static method with single English template
- [ ] 2.5 Update `_build_single_translate_payload()` to dispatch to translation-dedicated prompt builder
- [ ] 2.6 Update `translate_batch()` to fall back to individual translation for translation-dedicated models
- [ ] 2.7 Update `cache_model_key` property to include model_type for non-general types

## 3. Backend: Pipeline Pass-Through

- [ ] 3.1 Add `model_type` field to `ProfileItem` in `schemas.py`
- [ ] 3.2 Update `GET /api/profiles` in `routes.py` to include `model_type` in response
- [ ] 3.3 Update `POST /api/jobs` in `routes.py` to pass `model_type` to job_manager
- [ ] 3.4 Add `model_type` parameter to `create_job()` in `job_manager.py` and pass to `process_files()`
- [ ] 3.5 Add `model_type` parameter to `process_files()` in `orchestrator.py` and pass to `OllamaClient`

## 4. Backend: Translation Helpers Guard

- [ ] 4.1 Update `translate_merged_paragraphs()` in `translation_helpers.py` to skip merging for translation-dedicated models

## 5. Frontend: Model Type UI

- [ ] 5.1 Update `App.jsx` to group profiles by `model_type` from API response
- [ ] 5.2 Render two visual sections: "通用AI翻譯" and "專業翻譯引擎"

## 6. Shell Script Cleanup

- [ ] 6.1 Remove `OLLAMA_NUM_CTX`, `OLLAMA_NUM_GPU`, `OLLAMA_KV_CACHE_TYPE` exports from `translate_tool.sh`
- [ ] 6.2 Keep `TRANSLATE_CONNECT_TIMEOUT`, `TRANSLATE_READ_TIMEOUT`, `OLLAMA_BASE_URL` in shell script (transport-level, not model-level)
- [ ] 6.3 Update shell script comment block to reflect that model-level tuning moved to `config.py`

## 7. Verification

- [ ] 7.1 Start backend, verify `GET /api/profiles` returns profiles with `model_type` field
- [ ] 7.2 Submit translation job with HY-MT profile, verify correct prompt template and inference params in logs
- [ ] 7.3 Submit translation job with general profile, verify existing behavior unchanged
- [ ] 7.4 Verify cache entries are stored with distinct keys per model type
- [ ] 7.5 Verify `OLLAMA_NUM_CTX` env var override still honored when set manually (backward compat)
