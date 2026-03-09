## Context

Two quality failure modes identified in production:
- **HY-MT**: literal translation → semantic errors (translates words, not meaning)
- **Qwen3.5**: hallucination during self-refinement (adds content not in source)

The existing `REFINEMENT_ENABLED = False` was disabled because 4B models hallucinate when refining their own output. Cross-model refinement bypasses this by separating roles: HY-MT handles terminology accuracy, Qwen handles semantic naturalness.

## Goals / Non-Goals

**Goals:**
- Improve semantic naturalness of HY-MT translations without degrading terminology accuracy
- Enable Qwen as domain-aware refiner for HY-MT/TranslateGemma primary translations
- Guarantee OOM-safe execution on 8GB VRAM hardware
- Add naturalness guidance to HY-MT system prompts as complementary fix

**Non-Goals:**
- Enable self-refinement for Qwen (hallucination risk with no quality gain)
- Real-time A/B quality scoring
- Cache refined translations (avoids persisting incorrect refinements)

## Decisions

### Decision 1: Two-phase execution with explicit HY-MT unload (VRAM safety)

`translate_texts()` executes in two strictly separated phases:

**Phase 1 — Primary translation (HY-MT loaded):**
All target languages translated sequentially by HY-MT. `tmap` accumulates all results.

**Phase 2 — Refinement (Qwen loaded):**
Only triggered when `refine_client` is provided. Before the first Qwen call, `client.unload_model()` is called explicitly to evict HY-MT from VRAM. Qwen then loads and refines ALL segments across ALL target languages in a single sweep. Qwen stays loaded until `release_resources()` is called by `job_manager` after the group completes.

```
HY-MT translate(vi, ja, de) → tmap → client.unload_model()
→ Qwen refine(vi, ja, de) from tmap → tmap_refined
→ write tmap_refined to document
```

**Why not per-segment swap:** N segments × 2 model loads = 2N VRAM evictions. With 100 segments, this means 200 Ollama model swaps — completely untenable. Two-phase means exactly **2 model loads** per file group (HY-MT once, Qwen once).

**Alternative considered:** Parallel streams — not feasible with single-GPU constraint.

### Decision 2: Domain + language-specific Qwen refiner system prompt

The Qwen refiner receives a **dynamically generated system prompt** tied to (target_language, profile_id). This is critical: a generic "improve this draft" instruction causes Qwen to hallucinate. A role-grounded persona ("You are a senior Vietnamese process engineer…") constrains Qwen to stay within domain and terminology boundaries.

System prompt template:
```
You are a senior {nationality} engineer in the {domain} department of a discrete component manufacturing plant.
Your task is to review and correct a machine-translated draft of a {document_type}.

Rules:
1. Cross-reference the [SOURCE] to verify professional terminology in the [DRAFT].
2. Correct unnatural literal renderings (e.g., "奶油" for grease → correct industrial term).
3. Ensure register matches standard SOP/work instruction formality.
4. Output ONLY the corrected {target_language}. No explanations, no dialogue.
```

User prompt format:
```
[SOURCE]: {source_text}
[DRAFT]: {hy_mt_draft}

Corrected {target_language}:
```

A `_build_refine_system_prompt(target_language, profile_id)` function maps (lang, profile) → system prompt string. This function is added to `ollama_client.py`.

**Decision 3 (superseded):** ~~"Refine client uses minimal Qwen config with no system prompt"~~ — **SUPERSEDED** by Decision 2. Generic prompts cause hallucination in refinement tasks. Domain persona constrains Qwen to the correction role.

### Decision 3: refine_model lives in RouteGroup

`RouteGroup` carries `refine_model: Optional[str]`. Routing assignments:
- `HY-MT` → `refine_model = DEFAULT_MODEL` (Qwen3.5:4b)
- `TranslateGemma` → `refine_model = DEFAULT_MODEL` (Qwen3.5:4b)
- `Qwen` → `refine_model = None` (no refinement)
- Manual profile override → `refine_model = None`

### Decision 4: Plan C targets shared builder + per-profile register_tone

`_build_system_prompt()` output rules apply to ALL profiles. Adding "Prefer natural and idiomatic phrasing over literal word-for-word translation" covers all HY-MT profiles uniformly. Per-profile `register_tone` gets a targeted naturalness sentence.

**Note:** HY-MT is a translation transformer and may not follow instruction prompts reliably. Plan C is best-effort; Plan A (cross-model refinement) is the primary quality fix.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Qwen hallucination in refine role | Domain+persona system prompt constrains Qwen to correction role, not re-translation. `refine_translation()` keeps draft on failure. |
| OOM on 8GB VRAM | Explicit `client.unload_model()` before first Qwen refine call. No simultaneous dual-model load. |
| Refinement increases job duration | 1 extra Qwen pass per file group; opt-out via `CROSS_MODEL_REFINEMENT_ENABLED=0`. |
| Refined output not cached | Intentional. HY-MT primary is cached. Future: separate refined-output cache table. |
| `_build_refine_system_prompt` coverage gaps | Start with `technical_process` (highest priority). Other profiles get generic manufacturing persona as fallback. |
