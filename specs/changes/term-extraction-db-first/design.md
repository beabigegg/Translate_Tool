# Design: term-extraction-db-first

## Summary
Phase 0 term extraction moves from an always-on local-Ollama LLM pass to a DB-first
flow. For each translation document we embed the source segments via the PANJIT
`Qwen3-Embedding-8B` endpoint, compute cosine similarity in-process against embedded
DB terms, and inject any matches (≥ threshold) through the existing
`build_terminology_block()` seam. Only when the DB is sparse for the document do we
call a lightweight PANJIT extraction LLM (`gemma4:latest`) to mint new terms, persist
them, and inject. The local Ollama GPU dependency is removed from the translation
path; the extraction LLM and embedding model both run on PANJIT cloud over the
existing self-signed TLS (`verify_ssl=False`). Embedding-API failure is non-fatal:
term injection is skipped and translation proceeds. `extraction_only` mode and the
term_db CRUD API are unchanged.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Phase 0 driver | `app/backend/services/term_extractor.py` | Replace Ollama `_call`/`unload` extraction path with DB-first flow: embed segments, cosine-match DB, conditional PANJIT extraction. `run_phase0_multi` signature kept; `base_url`/`OLLAMA_BASE_URL` dropped from translation path. |
| Term DB query | `app/backend/services/term_db.py` | Add `get_similar_terms_by_embedding()` (on-the-fly cosine over candidate term rows). No schema change; embeddings not persisted in v1. |
| Phase 0 hook wiring | `app/backend/processors/orchestrator.py` (~553-635) | Hook stops passing `base_url=OLLAMA_BASE_URL`; passes PANJIT embedding/extraction config instead. Injection block (627-633) reused unchanged. |
| Embedding client | `app/backend/clients/openai_compatible_client.py` | Add a thin `embed(texts)` method targeting `/v1/embeddings`; or a small dedicated embeddings helper. Existing chat client only does `/v1/chat/completions`. |
| Config | `app/backend/config.py` + `.env` | Add `TERM_EMBEDDING_MODEL` (`Qwen3-Embedding-8B`), `TERM_EXTRACTION_MODEL` (`gemma4:latest`), `TERM_SIMILARITY_THRESHOLD` (0.75). Reuse `PANJIT_LLM_BASE_URL`/`PANJIT_API`/`tls_verify`. |

## Key Decisions
- **DB-first, embedding-gated extraction**: embed source segments, cosine-match DB
  terms, inject hits, and only call the extraction LLM on miss. Rationale: eliminates
  the redundant second LLM pass over the same text when the DB already covers the
  document; removes local GPU from the translation path.
  → Rejected: keep Ollama extraction always-on — it is the cost this change exists to remove.
- **Per-segment embedding** (matches `run_phase0_multi`'s existing `segments`
  argument). Rationale: segments are already the unit processors hand to the hook;
  per-segment vectors give finer match granularity and keep each request inside the
  embedding context window. → Rejected: whole-document single embedding — blurs many
  terms into one vector, poor match precision, and risks exceeding context for long docs.
- **On-the-fly cosine in Python, no vector DB**. Rationale: the term DB is small
  (SQLite, document-scoped candidate sets), v1 must ship without new infrastructure,
  and a hard constraint forbids `pgvector`/`chromadb`/`faiss`. Cosine over a handful
  of candidate vectors is trivial in NumPy (already a transitive dependency).
  → Rejected: vector DB — disproportionate operational and packaging cost for the
  data volume; explicitly out of scope (persistence deferred to a later change).
- **PANJIT embedding endpoint**: `POST {PANJIT_LLM_BASE_URL}/v1/embeddings`, model
  `Qwen3-Embedding-8B`, `verify_ssl=False` (self-signed internal cert, same as the
  chat client). **Extraction endpoint**: `POST {PANJIT_LLM_BASE_URL}/v1/chat/completions`,
  model `gemma4:latest`.
- **`gemma4:latest` for extraction, not `gpt-oss:120b`**: term extraction is an
  NER-style task; an 8B model is fast and sufficient, and the heavy model is reserved
  for translation. → Rejected: `gpt-oss:120b` — needless latency/cost for NER.
- **Reuse the injection seam unchanged**: matched terms still flow through
  `get_document_terms()` budget-capping → `build_terminology_block()` →
  `client.system_prompt` (orchestrator.py:614-633). No post-process string
  replacement. → Rejected: regex/post-process glossary substitution — brittle,
  ignores morphology/context, and abandons the LLM-side approach already validated by
  `term_audit.py`.
- **Embedding failure → skip injection, continue translation** (load-bearing safety
  property). Phase 0 is non-fatal: an unreachable/timeout/5xx/SSL error on the
  embedding call must not raise into the translation path. Chosen over "fall back to
  LLM extraction" because the fallback would re-introduce latency/cost on the exact
  failure where the network is already degraded.
- **Config placement**: model names + threshold + SSL flag as `config.py` constants
  backed by env vars (consistent with existing `TERM_INJECT_*`). PANJIT base_url/key/
  `tls_verify` stay in `providers.yml`; the embedding model is a term-subsystem
  tunable, not a routing concern, so it does not belong in `providers.yml` routing.

## Migration / Rollback
No data migration: the `terms` table schema is unchanged and embeddings are computed
on the fly (not persisted). Rollback is a code revert of `term_extractor.py` and the
orchestrator Phase 0 hook (restore `base_url=OLLAMA_BASE_URL` and the Ollama `_call`
path); the term DB written under the new flow remains fully valid for the old flow.
The new config constants are additive and inert when the old code is restored.

## Open Risks
- Embedding-match recall depends on what DB rows we embed per call. v1 embeds the
  candidate term set on the fly each request — acceptable for small DBs but O(terms)
  cost per document; flagged for the deferred persistence change.
- `Qwen3-Embedding-8B` response shape (`data[].embedding`) and `gemma4:latest`
  availability on the PANJIT endpoint must be confirmed by integration tests against
  a stubbed seam; contract-reviewer should record both in `api-inventory.md`.
- Removing `OLLAMA_BASE_URL` from the extraction path: verify no other translation
  caller depends on Phase 0 loading Ollama (grep confirms `layout_assist_only` is the
  remaining Ollama role in providers.yml — independent).
