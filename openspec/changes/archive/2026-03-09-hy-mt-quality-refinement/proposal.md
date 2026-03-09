# Proposal: HY-MT Quality Refinement

## Problem

Benchmark analysis (March 2026) and production observation reveal two distinct quality failure modes:

1. **Qwen3.5 hallucination** — the general-purpose LLM occasionally inserts content not present in the source text, especially during self-refinement. This is why `REFINEMENT_ENABLED = False`.
2. **HY-MT literal/semantic errors** — the translation-dedicated transformer lacks high-level language reasoning; it produces grammatically correct but contextually unnatural output (word-for-word mapping, awkward phrasing).

The current pipeline applies a uniform refinement strategy (disabled) and minimal prompt guidance for HY-MT, leaving both failure modes unaddressed.

## Solution

Two complementary fixes:

### Plan A — Cross-model refinement (structural fix)
After HY-MT translates a batch, pass the drafts to **Qwen as the refiner**. Qwen is an instruction-following LLM well-suited to "improve this draft" tasks; it is NOT being asked to translate from scratch (where hallucination occurs), only to polish existing output. The model swap is sequential (8GB VRAM constraint): HY-MT translates all segments → Qwen refines all segments.

This is fundamentally different from the disabled `REFINEMENT_ENABLED` path, which ran the same model (Qwen/general) as both translator and refiner. Cross-model refinement separates concerns: HY-MT handles terminology accuracy, Qwen handles semantic naturalness.

### Plan C — HY-MT system prompt naturalness (prompt fix)
Add explicit "prefer natural, idiomatic phrasing over literal translation" guidance to:
- The shared `_build_system_prompt()` output rules (affects all HY-MT profiles)
- `_build_translation_dedicated_prompt()` non-Chinese direction template
- Per-profile `register_tone` for HY-MT-routed profiles

## What Changes

- **`config.py`**: Add `CROSS_MODEL_REFINEMENT_ENABLED` flag (default `True`) and `REFINEMENT_MIN_CHARS` already exists (reuse).
- **`model_router.py`**: Add `refine_model: Optional[str]` to `RouteGroup`. HY-MT and TranslateGemma groups get `refine_model = DEFAULT_MODEL` (Qwen). Qwen group gets `refine_model = None`.
- **`orchestrator.py`**: Accept `refine_model` in `process_files()`, construct a minimal `OllamaClient` for refinement and pass to `translate_texts()`.
- **`translation_service.py`**: Accept `refine_client: Optional[OllamaClient]` in `translate_texts()`. After all segments for a target language are translated, run a batch refine pass; update `tmap` in-place. Do NOT cache refined output (avoids persisting incorrectly refined entries).
- **`translation_profiles.py`**: Add naturalness rule to `_build_system_prompt()` output rules; improve `register_tone` for `technical_process`, `business_finance`, `marketing_pr` profiles; improve `_build_translation_dedicated_prompt()` non-Chinese template.
- **`job_manager.py`**: Pass `refine_model` from `RouteGroup` into `process_files()`.

## Affected Specs

| Spec | Change Type |
|------|-------------|
| `translator-core` | MODIFIED — cross-model refinement pipeline |
| `translation-profiles` | MODIFIED — naturalness instructions |
| `translation-backend` | MODIFIED — refine_model in RouteGroup and process_files |

## Impact

- **Translation quality**: HY-MT outputs become semantically natural while retaining domain terminology accuracy.
- **Performance**: Cross-model jobs incur 1 Ollama model swap per file group (HY-MT→Qwen for refine, Qwen→HY-MT for next group). Estimated overhead: 15–30s per model swap.
- **Opt-out**: `CROSS_MODEL_REFINEMENT_ENABLED=0` env var disables cross-model refinement for time-sensitive jobs.
- **Cache neutrality**: Refinement results are not cached; only primary HY-MT translations are cached as before.
