# Archive — term-extraction-db-first

## Change Summary

Replaced the Ollama-based Phase 0 term extraction with a DB-first flow using PANJIT embeddings. Source segments are vectorised via `Qwen3-Embedding-8B` on the PANJIT endpoint (`POST {PANJIT_LLM_BASE_URL}/v1/embeddings`); if any approved term's embedding exceeds the cosine similarity threshold (default 0.75), matched terms are injected into the system prompt via `build_terminology_block()` without any extraction LLM call. On DB miss, PANJIT `gemma4:latest` is called for extraction, new terms are saved to `term_db`, then injected. Embedding API failures are non-fatal: injection is skipped and translation continues normally. `localhost:11434` (Ollama) is no longer referenced in the translation extraction path.

## Final Behavior

- **Phase 0 DB hit**: cosine similarity ≥ `TERM_EMBEDDING_THRESHOLD` (default 0.75) → terms injected from DB into system prompt; no PANJIT extraction LLM call made.
- **Phase 0 DB miss**: PANJIT `gemma4:latest` called for extraction → terms saved → terms injected.
- **Embedding API failure** (ConnectionError / Timeout / 5xx / SSLError): exception caught in `embed()`; non-fatal; injection skipped; WARNING logged; translation proceeds.
- **`extraction_only` mode**: unchanged — still calls the extraction LLM directly, DB-first shortcut not applied.
- **Ollama**: `OLLAMA_BASE_URL` not referenced in the term extraction path.

## Final Contracts Updated

| file | section | change |
|---|---|---|
| contracts/env/env-contract.md | Env variable table | 3 new rows: TERM_EMBEDDING_MODEL, TERM_EMBEDDING_THRESHOLD, TERM_EXTRACTION_MODEL; schema-version 0.6.0→0.7.0; PANJIT_LLM_BASE_URL row updated with SSL transport note |
| contracts/env/.env.example.template | Term extraction section | 3 commented entries for the new vars |
| contracts/env/env.schema.json | properties | 3 new properties: TERM_EMBEDDING_MODEL, TERM_EMBEDDING_THRESHOLD (pattern), TERM_EXTRACTION_MODEL |
| contracts/business/business-rules.md | BR-62 + Table R | BR-62 (DB-first flow rule); Table R (11-row decision table); schema-version 0.13.0→0.14.0 |
| contracts/data/data-shape-contract.md | Term DB — Embedding Similarity Query | `get_similar_terms_by_embedding()` function contract, nullability rules; schema-version 0.8.0→0.9.0 |
| contracts/api/api-inventory.md | Outbound Integrations (PANJIT) | 2 rows: POST /v1/embeddings and POST /v1/chat/completions as outbound integrations; schema-version 0.2.0→0.3.0 |

## Final Tests Added / Updated

| file | new tests | coverage |
|---|---|---|
| tests/test_term_extractor.py | 18 new | AC-1,2,3,4,5,6,7,8 unit |
| tests/test_term_db.py | 4 new | AC-5,6 DB cosine math |
| tests/test_env_contract.py | 6 new | AC-5 env schema + config wiring |
| tests/test_term_extractor_resilience.py | 13 new | AC-3 (all 4 network failure modes) + 9 data-boundary |
| tests/test_orchestrator_phase0.py | 3 new | AC-1 integration: hook wiring, PANJIT config threading, disabled-PANJIT path |
| **Total** | **764 passed, 4 skipped, 0 failed** | — |

## Final CI/CD Gates

Gates promoted to `.github/workflows/contract-driven-gates.yml`:
- `dead-import-assertion` — no pgvector/chromadb/faiss/hnswlib in term_extractor.py
- `dead-reference-ollama` — OLLAMA_BASE_URL absent from term_extractor.py
- `env-sync-panjit-embedding` — TERM_EMBEDDING_* vars in .env.example.template + env.schema.json
- `targeted-term-tests` — pytest tests/test_term_extractor.py + test_term_db.py + test_env_contract.py
- Active `cdd-kit gate term-extraction-db-first` (→ reverted to no-op after archive)

## Production Reality Findings

1. **Lazy import binding in orchestrator**: `run_phase0_multi` is imported inside `process_files` (not at module level), so patching `app.backend.processors.orchestrator.run_phase0_multi` fails with AttributeError at patch time. Must patch at `app.backend.services.term_extractor.run_phase0_multi` (definition module). Evidence: `agent-log/e2e-resilience-engineer.yml`.
2. **Class-level patch self-arg**: Patching `OpenAICompatibleClient.embed` with a plain function passes `self` as first arg. Use `MagicMock(side_effect=...)` to avoid positional arg confusion.
3. **Env-var name drift**: initial `ci-gates.md` used stale names (`PANJIT_EMBEDDING_MODEL`, `TERM_SIMILARITY_THRESHOLD`); corrected to contract names before workflow promotion. Evidence: `agent-log/implementation-planner.yml` Known Risks #1.
4. **QA weakened AC-1 integration assertion**: `test_phase0_hook_injects_term_table` asserts `segments` kwarg rather than the full `system_prompt` table text. Deferred to follow-up (see below).

## Lessons Promoted to Standards

1. **CLAUDE.md mock.patch entry updated** — merged lazy-import case into existing entry: "patch at the definition module when the import is lazy (inside-function); no consumer-module binding exists at patch time." Evidence: `agent-log/e2e-resilience-engineer.yml` fix-notes. New pointer: `tests/test_orchestrator_phase0.py` (lazy-import pattern).

2. **contracts/env/env-contract.md §Deployment Sync Policy — new sentence added** — Gate grep commands in `ci-gates.md` must use exact canonical var names; stale patterns pass silently. Schema-version bumped 0.7.0→0.8.0. Evidence: `agent-log/implementation-planner.yml` Known Risks #1 (stale `PANJIT_EMBEDDING_MODEL`/`TERM_SIMILARITY_THRESHOLD` in ci-gates.md draft).

## Follow-up Work

- **AC-1 integration assertion tightening**: `test_phase0_hook_injects_term_table` does not assert `client.system_prompt` contains the Markdown terminology table — only the segments argument is checked. QA signed off approved-with-risk. Follow-up: update test to assert table text in system_prompt before next change that modifies the injection seam.
- **`extraction_only` Ollama path**: the legacy path (Ollama) remains for `extraction_only` mode. When Ollama is fully removed from the stack, that path will need replacement.
- **AC-1 integration assertion ID drift**: test-plan.md AC-3 IDs use `test_embedding_*` but delivered tests use `test_embed_*`. Reconcile at next test-plan review.
- **tasks.yml 3.4 misclassified as skipped** (corrected to done before commit): data-boundary tests were delivered but the task was initially marked skipped. Watch for this pattern when backend-engineer delivers data-boundary coverage without a separate e2e phase.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
