---
change-id: term-extraction-db-first
schema-version: 0.1.0
last-changed: 2026-06-20
risk: medium
tier: 2
---

# Test Plan: term-extraction-db-first

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1: DB hit ≥0.75 → no extraction call | unit | `tests/test_term_extractor.py::test_db_hit_skips_extraction_call` | 0 |
| AC-1: DB hit → system prompt contains Markdown terminology table | unit | `tests/test_term_extractor.py::test_db_hit_injects_terminology_table` | 0 |
| AC-2: DB miss → PANJIT gemma4:latest extraction called | unit | `tests/test_term_extractor.py::test_db_miss_calls_panjit_extraction` | 0 |
| AC-2: DB miss → extracted terms saved via term_db.insert | unit | `tests/test_term_extractor.py::test_db_miss_saves_extracted_terms` | 0 |
| AC-2: no call to localhost:11434 anywhere in new flow | unit | `tests/test_term_extractor.py::test_no_ollama_localhost_call` | 0 |
| AC-3: embedding ConnectionError → skip injection, translation proceeds | resilience | `tests/test_term_extractor_resilience.py::test_embedding_connection_error_skips_injection` | 0 |
| AC-3: embedding TimeoutError → skip injection, translation proceeds | resilience | `tests/test_term_extractor_resilience.py::test_embedding_timeout_skips_injection` | 0 |
| AC-3: embedding 5xx → skip injection, translation proceeds | resilience | `tests/test_term_extractor_resilience.py::test_embedding_5xx_skips_injection` | 0 |
| AC-3: no exception propagates from Phase 0 on any embedding failure | resilience | `tests/test_term_extractor_resilience.py::test_embedding_failure_does_not_raise` | 0 |
| AC-4: embedding call targets {PANJIT_LLM_BASE_URL}/v1/embeddings | unit | `tests/test_term_extractor.py::test_embedding_endpoint_url` | 0 |
| AC-4: embedding/extraction calls use verify_ssl=False | unit | `tests/test_term_extractor.py::test_calls_use_verify_ssl_false` | 0 |
| AC-5: threshold 0.5 → similarity 0.6 classified as DB hit | unit | `tests/test_term_extractor.py::test_threshold_lower_includes_term` | 0 |
| AC-5: threshold 0.9 → similarity 0.6 classified as DB miss | unit | `tests/test_term_extractor.py::test_threshold_higher_excludes_term` | 0 |
| AC-6: no pgvector/chromadb/faiss/hnswlib imported in term_extractor.py | static | `tests/test_term_extractor.py::test_no_vector_db_imports` | 0 |
| AC-6: get_similar_terms_by_embedding uses in-process cosine (no vector DB) | unit | `tests/test_term_db.py::test_get_similar_terms_by_embedding_cosine` | 0 |
| AC-7: extraction_only=True still calls extraction LLM; does not inject | unit | `tests/test_term_extractor.py::test_extraction_only_calls_llm_no_injection` | 0 |
| AC-8: OLLAMA_BASE_URL not referenced in term_extractor.py extraction flow | static | `tests/test_term_extractor.py::test_ollama_base_url_absent_from_extraction_flow` | 0 |
| Integration: _phase0_hook direct call → client.system_prompt contains term table | integration | `tests/test_orchestrator_phase0.py::test_phase0_hook_injects_term_table` | 1 |
| Data-boundary: malformed embedding response (missing `data` key) | data-boundary | `tests/test_term_extractor_resilience.py::test_malformed_embedding_missing_data_key` | 0 |
| Data-boundary: malformed embedding response (wrong vector type) | data-boundary | `tests/test_term_extractor_resilience.py::test_malformed_embedding_wrong_type` | 0 |
| Data-boundary: empty term DB → translation proceeds normally | data-boundary | `tests/test_term_extractor_resilience.py::test_empty_term_db_translation_proceeds` | 0 |
| Data-boundary: oversized segment (>32K chars) → graceful degradation | data-boundary | `tests/test_term_extractor_resilience.py::test_oversized_segment_graceful` | 0 |
| Env contract: new vars in env.schema.json | contract | `tests/test_env_contract.py` (extend existing) | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Extend `tests/test_term_extractor.py` and `tests/test_term_db.py`. Mock at consumer-bound name per CLAUDE.md: patch `app.backend.services.term_extractor.requests.post`, not `requests.post`. Selection assertions: assert extraction endpoint NOT called (AC-1) and called with `model=gemma4:latest` (AC-2). |
| static / dead-reference | 0 | Grep-based assertions inside test functions using `Path(__file__).parent.parent` for repo root (never hardcoded). Tests: vector-DB import absent; `OLLAMA_BASE_URL` absent from extraction code path. |
| resilience | 0 | New file `tests/test_term_extractor_resilience.py`. Each failure mode is a separate test. Call `run_phase0_multi` directly — NOT through `translate_document()` wrapper (wrong-entry-point tautology per CLAUDE.md). Assert no raise and downstream translation mock was still called. |
| data-boundary | 0 | Co-located in `tests/test_term_extractor_resilience.py`. Cover missing JSON keys, wrong embedding vector type, zero-row DB, segment length edge cases. |
| integration | 1 | New file `tests/test_orchestrator_phase0.py`. Extract and call `_phase0_hook` closure directly (orchestrator.py lines 587-607 setup block). Stub PANJIT at `requests.post`. Assert `client.system_prompt` contains the terminology Markdown table. Do NOT invoke full `process_files`. |
| contract | 1 | Extend `tests/test_env_contract.py`. Assert `TERM_EMBEDDING_MODEL`, `TERM_EXTRACTION_MODEL`, `TERM_SIMILARITY_THRESHOLD` are present and typed correctly in `contracts/env/env.schema.json`. |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| `tests/test_term_extractor.py::test_run_phase0_normal_flow` | update | Currently patches `TermExtractor._call` targeting Ollama `/api/generate`; must be updated to reflect PANJIT `/v1/chat/completions` after implementation. |

## Out of Scope

- Vector DB persistence (deferred; AC-6 explicitly forbids it)
- Frontend display changes
- Wikidata lookup (unchanged)
- term_db CRUD API (unchanged; `tests/test_term_db.py` existing coverage sufficient)
- Stress / soak / nightly tiers (no infra change)

## Notes

- AC-5 threshold tests must monkeypatch the constant in the consumer module (`app.backend.services.term_extractor.TERM_SIMILARITY_THRESHOLD`), not in `config.py`, to hit the real lookup branch.
- `_phase0_hook` integration test must reconstruct the closure preconditions (a `client` mock with `system_prompt`, a `term_db` fixture) rather than running `process_files` end-to-end.
- Both static tests open source files with `Path(__file__).parent.parent / "app/backend/services/term_extractor.py"` — the pattern from `tests/test_text_region_renderer.py`.
