# Current Behavior: Phase 0 Term Extraction

## Overview
Phase 0 runs before translation to extract domain terminology, translate it, store
it in the term DB, and inject matched terms into the LLM system prompt. Today it is
hard-wired to the local Ollama GPU endpoint and always calls an LLM, even when the
term DB already covers the document.

## `run_phase0_multi()` (term_extractor.py:401)
- Constructs `TermExtractor(model=DEFAULT_MODEL, base_url=base_url)`.
  - `DEFAULT_MODEL = "qwen3.5:9b"` (config.py:25).
  - `base_url` defaults to `OLLAMA_BASE_URL` = `http://localhost:11434` (config.py:26).
- Step 1: `extract_from_segments(segments, domain)` — one LLM call per segment
  (`_call`, term_extractor.py:232) via `POST {base_url}/api/generate` (Ollama native
  streaming format, `think=False`, `num_ctx=4096`). This is the first of the two
  LLM passes over the same source text.
- Steps 2-4: per target language, `term_db.get_unknown()` filters candidates already
  stored (exact `source_text/target_lang/domain` match), then `translate_unknown()`
  calls Ollama again in batches of 25 and writes new `Term` rows via `term_db.insert`.
- `finally: extractor.unload()` (term_extractor.py:274) frees VRAM with
  `keep_alive=0`, `options={"num_gpu": 99}`.
- On any exception the whole phase is swallowed (logged non-fatal) and translation
  proceeds with whatever the DB already holds.

## GPU consumer
- The only GPU consumer in the translation path is this Ollama endpoint: every
  extraction + term-translation call hits `localhost:11434` with `num_gpu:99`,
  occupying local VRAM. The translation itself runs separately on PANJIT cloud, so
  the same source text is sent to an LLM twice (extract on Ollama, translate on
  cloud).

## Where `_phase0_hook` is called (orchestrator.py)
- Defined at orchestrator.py:587 inside `process_files`, only when `term_db` is not
  None and `extraction_only` is False.
- Passed as `pre_translate_hook=_phase0_hook` into every processor:
  `translate_docx` (655, 685), `translate_pptx`, etc. (703, 716, 732). Processors
  invoke it with their actual de-duplicated segments before translating.
- The hook calls `run_phase0_multi(..., model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL)`
  (orchestrator.py:590-601).
- `extraction_only` mode has a separate direct call at orchestrator.py:568 using
  2K-char chunks; it does NOT use the hook.

## Where terms are injected into the system prompt
- After `run_phase0_multi` returns, the hook retrieves injection-safe terms with
  `term_db.get_document_terms(lang, domain, extracted_source_texts)`
  (orchestrator.py:614) — status `approved` (plus high-confidence unverified when
  `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED` is set).
- Terms are budget-capped (`_cap_terms_by_budget`) and formatted by
  `build_terminology_block()` (translation_strategy.py:323) into a Markdown table,
  appended to `client.system_prompt` (orchestrator.py:627-633). This is the
  LLM-side glossary injection seam.

## Relevant config today
- `OLLAMA_BASE_URL`, `DEFAULT_MODEL`, `OLLAMA_NUM_GPU` (config.py:25-50).
- `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED`, `TERM_INJECT_CONF_THRESHOLD` (config.py:199-200).
- PANJIT provider config lives in providers.yml (`base_url: ${PANJIT_LLM_BASE_URL}`,
  `api_key: ${PANJIT_API}`, `tls_verify: false`).
