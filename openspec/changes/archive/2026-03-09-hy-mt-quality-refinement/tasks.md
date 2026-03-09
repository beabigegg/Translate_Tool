## Plan C: HY-MT System Prompt Naturalness (quick win, no deps)

- [x] C.1 Add naturalness output rule to `_build_system_prompt()` in `translation_profiles.py`
      — append rule 6: "Prefer natural, idiomatic phrasing in the target language over literal or word-for-word translation."
- [x] C.2 Improve `register_tone` for `technical_process`, `business_finance`, `marketing_pr` profiles
      — add: "Avoid calque or word-for-word rendering; use phrasing natural to a native speaker of the target language."
- [x] C.3 Improve `_build_translation_dedicated_prompt()` non-Chinese direction in `ollama_client.py`
      — from: `"Translate the following segment into {target_language}, without additional explanation."`
      — to: `"Translate the following segment into {target_language}. Prefer natural, idiomatic phrasing over literal translation. Output only the translation."`

## Plan A: Cross-Model Refinement (VRAM-safe two-phase design)

### A.1 — Dual-input labeled refine prompt (ollama_client.py)
- [x] A.1.1 Update `_build_refine_prompt()` to use labeled source/draft sections:
      ```
      [SOURCE]: {source_text}
      [DRAFT]: {draft}

      Corrected {target_language}:
      ```
- [x] A.1.2 Add `_build_refine_system_prompt(target_language: str, profile_id: str) -> str`
      — maps (lang, profile) → domain+persona system prompt
      — `technical_process` → "You are a senior {lang nationality} process/manufacturing engineer at a discrete component plant reviewing a machine-translated SOP/maintenance manual draft..."
      — includes 4 rules: (1) verify terminology vs source, (2) correct literal renderings to industrial terms, (3) SOP-register formality, (4) output-only final corrected text
      — other profiles → generic manufacturing persona for that language
      — supported languages initially: Vietnamese, Japanese, German, Korean; fallback: English persona

### A.2 — Config flag (config.py)
- [x] A.2.1 Add `CROSS_MODEL_REFINEMENT_ENABLED = os.environ.get("CROSS_MODEL_REFINEMENT_ENABLED", "1").lower() in ("1", "true", "yes")`

### A.3 — RouteGroup carries refine_model (model_router.py)
- [x] A.3.1 Add `refine_model: Optional[str] = None` to `RouteGroup` dataclass
- [x] A.3.2 Set `refine_model = DEFAULT_MODEL` for HY-MT and TranslateGemma routing entries in `resolve_route_groups()`
- [x] A.3.3 `Qwen` group and manual profile override group keep `refine_model = None`

### A.4 — Two-phase translate_texts() (translation_service.py)
- [x] A.4.1 Add `refine_client: Optional[OllamaClient] = None` parameter to `translate_texts()`
- [x] A.4.2 Phase 1: translate all targets with `client` — no change to existing loop
- [x] A.4.3 Phase 2: after Phase 1 loop, if `refine_client` and `CROSS_MODEL_REFINEMENT_ENABLED`:
      a) call `client.unload_model()` — **explicit HY-MT evict before Qwen load**
      b) for each tgt, for each text where `len(text) >= REFINEMENT_MIN_CHARS` and `(tgt, text)` in tmap:
         call `refine_client.refine_translation(text, tmap[(tgt, text)], tgt, src_lang)`
         update tmap on `ok=True`; keep draft on failure
      c) do NOT write refined translations to cache
- [x] A.4.4 Cache hits: exclude cached segments from Phase 2 refinement (track `cached_keys` set per tgt)

### A.5 — process_files creates domain-aware refine client (orchestrator.py)
- [x] A.5.1 Add `refine_model: Optional[str] = None` parameter to `process_files()`
- [x] A.5.2 If `refine_model` and `CROSS_MODEL_REFINEMENT_ENABLED`:
      a) call `_build_refine_system_prompt(targets[0], profile_id)` to get persona prompt
      b) construct `refine_client = OllamaClient(model=refine_model, model_type="general", system_prompt=refine_system_prompt)`
- [x] A.5.3 Pass `refine_client` to all `translate_texts()` calls within `process_files()` (via docx/pptx/xlsx processors)

### A.6 — job_manager passes refine_model (job_manager.py)
- [x] A.6.1 Pass `group.refine_model` into `process_files()` call inside `_run_job()`

### A.7 — Tests
- [x] A.7.1 `_build_refine_system_prompt("Vietnamese", "technical_process")` contains persona + 4 rules
- [x] A.7.2 `_build_refine_prompt()` uses `[SOURCE]:` / `[DRAFT]:` / `Corrected {lang}:` format
- [x] A.7.3 `resolve_route_groups(["Vietnamese"])` → HY-MT group with `refine_model=DEFAULT_MODEL`
- [x] A.7.4 `resolve_route_groups(["English"])` → Qwen group with `refine_model=None`
- [x] A.7.5 `translate_texts()` calls `client.unload_model()` before first `refine_client` call (mock assert)
- [x] A.7.6 `translate_texts()` does NOT update cache for refined output
- [x] A.7.7 `translate_texts()` skips Phase 2 when `CROSS_MODEL_REFINEMENT_ENABLED=False`

## Validation

- [ ] V.1 E2E test: translate Vietnamese document; backend log shows `[REFINE]` entries with Qwen
- [ ] V.2 Verify no OOM: check Ollama logs confirm HY-MT unloaded before Qwen loads
- [ ] V.3 Verify English-only job has no refine pass
- [ ] V.4 Verify `CROSS_MODEL_REFINEMENT_ENABLED=0` skips all refinement
- [ ] V.5 Quality spot-check: compare HY-MT-only vs HY-MT+Qwen-refine for 5 representative segments
