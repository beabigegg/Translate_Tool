## Context

The translation tool supports one model interaction pattern: general-purpose LLMs with system prompt + crafted user prompt. Adding HY-MT1.5 (a dedicated translation model) requires a second interaction pattern: fixed-template prompts, no system prompt, and different inference parameters. This change spans the full pipeline from frontend through API to the Ollama client.

## Goals / Non-Goals

- Goals:
  - Support two model types: general-purpose and translation-dedicated
  - Model type determines prompt strategy, inference parameters, and batch behavior
  - Clean dispatch in OllamaClient without proliferating if-else branches
  - Preserve existing general-purpose model behavior exactly
  - Extend profile system with model_type field (backward compatible default)

- Non-Goals:
  - Implementing HY-MT terminology intervention or contextual translation features (future work)
  - Auto-detecting model type from model name patterns (explicit per profile)
  - Supporting more than two model types initially

## Decisions

- **Decision: Model type lives in TranslationProfile**
  - The `model_type` field is added to the `TranslationProfile` dataclass with default `"general"` for backward compatibility
  - This means model type is resolved at profile selection time, not at OllamaClient construction time
  - Alternatives considered: (a) detect by model name pattern — fragile, breaks on custom Ollama tags; (b) separate model-type selector independent of profiles — adds UI complexity without clear benefit

- **Decision: HY-MT uses individual segment translation (no batch markers)**
  - HY-MT was not trained with `<<<SEG_N>>>` marker preservation, so merged-paragraph batching is skipped
  - In `translate_merged_paragraphs()`, when `client.model_type == "translation"`, each paragraph is translated individually
  - In `translate_batch()`, when `_is_translation_dedicated()`, fall back to per-segment translation
  - Alternative considered: test if HY-MT can handle markers — risky, untested, and model behavior is unpredictable with unseen tokens

- **Decision: Inference parameters and num_ctx stored in config dict per model type**
  - `MODEL_TYPE_OPTIONS` maps `ModelType` enum to parameter dicts including `num_ctx`
  - General: `num_ctx=4096` (~3.5GB model + ~1.5GB KV cache = ~5GB); Translation-dedicated (HY-MT 7B Q4_K_M): `num_ctx=3072` (~5.7GB model + ~0.8GB KV cache ≈ 6.5GB) — both fit 8GB VRAM
  - `_build_options()` becomes an instance method consulting `self.model_type`
  - Alternative considered: per-profile parameter overrides — over-engineering for current needs

- **Decision: All prompts and system prompts use English uniformly**
  - Both general-purpose system prompts (profiles) and translation-dedicated fixed templates use English
  - HY-MT uses a single English template for all language pairs: "Translate the following segment into {target_language}, without additional explanation."
  - Alternative considered: use Chinese template for Chinese-involved pairs (official HY-MT recommendation) — rejected for consistency and maintainability across the codebase

- **Decision: Move runtime tuning from shell script to backend config**
  - `translate_tool.sh` currently hardcodes `OLLAMA_NUM_CTX=4096`, `OLLAMA_NUM_GPU=99`, `OLLAMA_KV_CACHE_TYPE=q8_0` as exported env vars
  - These values are model-type-dependent (HY-MT needs lower `num_ctx` than qwen3.5) and belong in `MODEL_TYPE_OPTIONS`
  - Shell script retains: service management (start/stop/status), WSL auto-detection, `OLLAMA_BASE_URL`, `TRANSLATE_CONNECT_TIMEOUT`, `TRANSLATE_READ_TIMEOUT` (these are transport-level, not model-level)
  - `config.py` reads remaining env vars (`OLLAMA_NUM_GPU`, `OLLAMA_KV_CACHE_TYPE`) as global defaults; `num_ctx` comes from `MODEL_TYPE_OPTIONS` per model type
  - Alternative considered: keep all env vars in shell script — doesn't scale with multiple model types needing different `num_ctx`

## Risks / Trade-offs

- **Individual translation is slower than batched** — HY-MT translates one segment at a time instead of merging 4 paragraphs. Mitigated by HY-MT's faster per-token inference (translation-only, no reasoning overhead).
- **`_build_options()` changes from @staticmethod to instance method** — All call sites already use `self._build_options()` so no external impact. Verified no external callers exist.
- **HY-MT language coverage is narrower (33+5 vs 200+)** — Frontend could warn when selecting HY-MT with an unsupported language, but this is deferred to future work.
- **Removing OLLAMA_NUM_CTX from shell script** — Existing users who relied on the sh default `4096` will now get the same value from `config.py`. Users who set the env var manually will still be honored via `os.environ.get()` override in `config.py`.

## Open Questions

- Exact Ollama model tag for HY-MT1.5-7B:Q4_K_M (depends on user's Ollama setup — make configurable via `HYMT_DEFAULT_MODEL` constant)
