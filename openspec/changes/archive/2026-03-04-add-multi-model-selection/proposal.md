# Change: Add Multi-Model Translation Selection

## Why
The tool currently only supports general-purpose LLMs (qwen3.5:4b) which require elaborate system prompts and prompt engineering to perform translation. Dedicated translation models like HY-MT1.5-7B (Tencent's WMT25 champion) deliver higher translation quality with simpler fixed-template prompts but use a completely different prompt format and inference parameter set. Users need the ability to choose between model types based on their quality, speed, and language coverage needs.

## What Changes
- Introduce a `ModelType` concept (`"general"` | `"translation"`) that determines prompt building strategy and inference parameters
- Add `model_type` field to `TranslationProfile` dataclass
- Add HY-MT1.5 dedicated translation prompt builders in `OllamaClient` (fixed templates, no system prompt)
- Add model-type-aware inference parameters (HY-MT uses top_k/top_p/repeat_penalty/temperature instead of frequency_penalty)
- Add per-model-type `num_ctx` defaults in `MODEL_TYPE_OPTIONS` (general: 4096, translation: 3072) to fit 8GB VRAM budget
- Add HY-MT profile ("hymt") to the profile registry
- For translation-dedicated models, skip merged-paragraph marker-based batching (HY-MT does not understand `<<<SEG_N>>>` markers) and fall back to individual segment translation
- Update frontend to group profiles by model type with two visual sections
- Pass `model_type` through the full pipeline: API → job_manager → orchestrator → OllamaClient
- Move runtime tuning defaults (OLLAMA_NUM_CTX, OLLAMA_NUM_GPU, OLLAMA_KV_CACHE_TYPE) from `translate_tool.sh` into `MODEL_TYPE_OPTIONS` in `config.py`; shell script retains only service management and WSL/URL detection

## Impact
- Affected specs: `translator-core` (batch translation, model type system, frontend UI profile grouping), `translation-backend` (model selection, HY-MT profile, prompt building, VRAM runtime tuning), `translation-profiles` (profile definition adds model_type field and hymt entry, API endpoint adds model_type to response)
- Affected code: `config.py`, `translation_profiles.py`, `ollama_client.py`, `translation_helpers.py`, `routes.py`, `schemas.py`, `job_manager.py`, `orchestrator.py`, `App.jsx`, `translate_tool.sh`
- Proposal precedence: this change supersedes the earlier model baseline from archived change `2026-03-04-add-translation-profiles`; default general profile model remains `qwen3.5:4b` due current VRAM constraints
- No breaking changes to existing general-purpose model behavior
- Cache keys extended for new model types (backward compatible — existing cache entries remain valid)
- All prompts (system prompts and fixed templates) use English uniformly
