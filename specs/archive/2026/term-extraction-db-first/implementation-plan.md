---
change-id: term-extraction-db-first
schema-version: 0.1.0
last-changed: 2026-06-20
---

# Implementation Plan: term-extraction-db-first

## Objective
Convert Phase 0 term extraction from an always-on local-Ollama LLM pass to a
DB-first, embedding-gated flow. For each translation document: embed the source
segments via the PANJIT `/v1/embeddings` endpoint, cosine-match against term DB
rows in-process, and inject hits (similarity ≥ threshold) through the existing
`build_terminology_block()` seam. On DB miss, call the PANJIT `/v1/chat/completions`
extraction model (`gemma4:latest`), persist new terms, then inject. The local
Ollama GPU dependency is removed from the translation path. Embedding-API failure
is non-fatal: skip injection, translation proceeds. `extraction_only` mode and the
term_db CRUD API are unchanged.

## Execution Scope

### In Scope
- `config.py`: add `TERM_EMBEDDING_MODEL`, `TERM_EMBEDDING_THRESHOLD`,
  `TERM_EXTRACTION_MODEL` constants (env-backed).
- `openai_compatible_client.py`: add `embed(texts)` + `_embeddings_url()`.
- `term_db.py`: add `get_similar_terms_by_embedding()` (in-process cosine, no
  vector DB).
- `term_extractor.py`: replace the Ollama `_call`/`unload` extraction path in
  `run_phase0_multi` with the DB-first flow (embed → cosine-match → conditional
  PANJIT extraction → save). Drop `OLLAMA_BASE_URL` from the translation path.
- `orchestrator.py` `_phase0_hook` (~585-633): stop passing
  `base_url=OLLAMA_BASE_URL`; pass PANJIT embedding/extraction config instead.
  Injection block at 620-633 reused unchanged.
- Tests per `test-plan.md` mapping table.

### Out of Scope
- `extraction_only` mode (orchestrator.py:~636 and the direct call at ~568) — must
  keep calling the extraction LLM and must NOT inject (AC-7).
- term_db CRUD API (`insert`, `get_unknown`, `get_document_terms`, etc.) — signatures
  unchanged (AC-7).
- Embedding-vector persistence / pgvector / chromadb / faiss / hnswlib (AC-6;
  hard constraint).
- Wikidata lookup; frontend; `providers.yml` routing.
- `.github/workflows/contract-driven-gates.yml` — deferred to gate-promotion step;
  do NOT edit in this change (see ci-gates.md §Deferred / §Promotion Policy).
- Do not opportunistically refactor `term_audit.py`, `model_router.py`, or the
  injection seam.

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | config | Add `TERM_EMBEDDING_MODEL` (`Qwen3-Embedding-8B`), `TERM_EMBEDDING_THRESHOLD` (`0.75`, float), `TERM_EXTRACTION_MODEL` (`gemma4:latest`) as env-backed constants near existing `TERM_INJECT_*` (config.py:199-200). | backend-engineer |
| IP-2 | embedding client | Add `embed(texts: list[str]) -> list[list[float]]` + `_embeddings_url()` to `OpenAICompatibleClient` POSTing `{base_url}/v1/embeddings`; parse `data[].embedding`; reuse `self._session` (carries `verify_ssl`), `self._auth_headers`, `self._timeout`, payload `{"model": ..., "input": texts}`. | backend-engineer |
| IP-3 | term DB query | Add `get_similar_terms_by_embedding(query_vectors, target_lang, domain, threshold, embed_fn) -> list[Term]`: load candidate term rows, embed their `source_text` via the injected `embed_fn`, compute cosine in NumPy, return rows whose max similarity ≥ threshold. No schema change; no persisted vectors. | backend-engineer |
| IP-4 | Phase 0 driver | Rewrite `run_phase0_multi` to the DB-first flow: build a PANJIT client (embedding + extraction), embed segments, call `get_similar_terms_by_embedding`; on any hit → skip the extraction LLM call; on miss (no term ≥ threshold) → run extraction via PANJIT `/v1/chat/completions` (`TERM_EXTRACTION_MODEL`) → `term_db.insert`. Remove Ollama `_call`/`unload`/`base_url`/`OLLAMA_BASE_URL` from this path. Keep `run_phase0_multi` return-dict shape (incl. `extracted_source_texts`). Embedding failure → log non-fatal, return without injecting (no raise). | backend-engineer |
| IP-5 | orchestrator hook | In `_phase0_hook` (orchestrator.py:585-605) drop `model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL`; pass PANJIT embedding/extraction config (the new config constants + PANJIT base_url/key/tls_verify resolved from the active provider). Leave injection block (620-633) and the `extraction_only` branch untouched. | backend-engineer |
| IP-6 | unit/static tests | Implement/extend tests per test-plan.md table (test_term_extractor.py, test_term_db.py, test_env_contract.py); mock at consumer-bound name; selection-style assertions; static greps via `Path(__file__).parent.parent`. | backend-engineer |
| IP-7 | resilience/data-boundary/integration tests | New `tests/test_term_extractor_resilience.py` + `tests/test_orchestrator_phase0.py` per test-plan.md; call `run_phase0_multi` / `_phase0_hook` directly (no `translate_document()` / `process_files` wrapper). | e2e-resilience-engineer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | "Key Decisions" (DB-first gating, per-segment embedding, on-the-fly cosine, embedding-failure-skips-injection, config placement) | implementation constraints |
| design.md | "Affected Components" table | file targets + nature of change |
| change-classification.md | "Inferred Acceptance Criteria" AC-1..AC-8 | acceptance mapping |
| test-plan.md | "Acceptance Criteria → Test Mapping" table | tests to write/run + node ids |
| test-plan.md | "Test Families Required" + "Notes" | mock-binding, tautology-guard, static-path rules |
| test-plan.md | "Test Update Contract" | `test_run_phase0_normal_flow` must be updated to PANJIT shape |
| ci-gates.md | "Required Gates for This Change" table | verification commands |
| ci-gates.md | §Deferred / §Promotion Policy | do NOT edit the workflow file in this change |
| contracts/env/env-contract.md:40-42 | TERM_EMBEDDING_MODEL / TERM_EMBEDDING_THRESHOLD / TERM_EXTRACTION_MODEL rows | canonical env var names + defaults |
| contracts/business/business-rules.md | BR-62 + Table R | decision-table conformance |
| contracts/data/data-shape-contract.md | `get_similar_terms_by_embedding()` semantics | DB query contract |
| contracts/api/api-inventory.md | PANJIT `/v1/embeddings`, `/v1/chat/completions` outbound rows | request-shape conformance |

## File-Level Plan
Implement strictly in this order: config.py → openai_compatible_client.py →
term_db.py → term_extractor.py → orchestrator.py (Phase 0 hook) → tests.

| path or glob | action | notes |
|---|---|---|
| `app/backend/config.py` | edit | Add 3 constants near line 199-200. Canonical names: `TERM_EMBEDDING_MODEL`, `TERM_EMBEDDING_THRESHOLD`, `TERM_EXTRACTION_MODEL` (see Known Risks #1). |
| `app/backend/clients/openai_compatible_client.py` | edit | Add `_embeddings_url()` (alongside `_chat_completions_url` at :85) and `embed()`. Reuse `self._session` / `_auth_headers` / `_timeout`. No change to existing chat methods. |
| `app/backend/services/term_db.py` | edit | Add `get_similar_terms_by_embedding()` after `get_document_terms` (:128-159). Candidate rows follow existing status policy (approved + optional high-conf unverified). `_row_to_term` reused. |
| `app/backend/services/term_extractor.py` | edit | Rewrite `run_phase0_multi` (:401-499) DB-first; delete Ollama `_call`/`unload` from the translation path; remove `OLLAMA_BASE_URL` from this path. `extraction_only` callers must still reach the extraction LLM. |
| `app/backend/processors/orchestrator.py` | edit | `_phase0_hook` (:585-605) config wiring only. Lines 620-633 unchanged. |
| `tests/test_term_extractor.py` | edit | Extend per mapping; update `test_run_phase0_normal_flow` to PANJIT shape (Test Update Contract). |
| `tests/test_term_db.py` | edit | Add `test_get_similar_terms_by_embedding_cosine`. |
| `tests/test_env_contract.py` | edit | Assert the 3 new vars present + typed in env.schema.json. |
| `tests/test_term_extractor_resilience.py` | create | resilience + data-boundary families. |
| `tests/test_orchestrator_phase0.py` | create | integration: `_phase0_hook` direct call. |

## Contract Updates
- API: already updated — `api-inventory.md` lists PANJIT `/v1/embeddings` +
  `/v1/chat/completions` outbound. No new served route; no `openapi.yml`
  regeneration (ci-gates.md note).
- CSS/UI: none.
- Env: already updated — `env-contract.md:40-42`, `env.schema.json:128-145`,
  `.env.example.template:58-62`. Implementation must read the canonical names
  (Known Risks #1). No new contract edits expected from implementation agents.
- Data shape: already updated — `data-shape-contract.md`
  `get_similar_terms_by_embedding()` semantics. Implementation must match.
- Business logic: already updated — BR-62 + decision Table R. Implementation
  decision branches must conform.
- CI/CD: no contract edit; workflow file edit deferred (ci-gates.md §Promotion).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 (DB hit skips extraction) | `tests/test_term_extractor.py::test_db_hit_skips_extraction_call` | extraction endpoint NOT called |
| AC-1 (hit injects table) | `tests/test_term_extractor.py::test_db_hit_injects_terminology_table` | system prompt contains Markdown term table |
| AC-2 (miss calls PANJIT) | `tests/test_term_extractor.py::test_db_miss_calls_panjit_extraction` | called with `model=gemma4:latest` |
| AC-2 (miss saves) | `tests/test_term_extractor.py::test_db_miss_saves_extracted_terms` | `term_db.insert` invoked |
| AC-2 (no localhost) | `tests/test_term_extractor.py::test_no_ollama_localhost_call` | no `localhost:11434` call |
| AC-3 (failure modes) | `tests/test_term_extractor_resilience.py` | no raise; downstream translation mock still called |
| AC-4 (endpoint url) | `tests/test_term_extractor.py::test_embedding_endpoint_url` | targets `{base}/v1/embeddings` |
| AC-4 (verify_ssl) | `tests/test_term_extractor.py::test_calls_use_verify_ssl_false` | session `verify=False` |
| AC-5 (threshold) | `tests/test_term_extractor.py::test_threshold_lower_includes_term` ; `::test_threshold_higher_excludes_term` | boundary flips hit/miss |
| AC-6 (no vector DB) | `tests/test_term_extractor.py::test_no_vector_db_imports` ; `tests/test_term_db.py::test_get_similar_terms_by_embedding_cosine` | no banned import; cosine path used |
| AC-7 (extraction_only) | `tests/test_term_extractor.py::test_extraction_only_calls_llm_no_injection` | extraction called, no injection |
| AC-8 (no OLLAMA_BASE_URL) | `tests/test_term_extractor.py::test_ollama_base_url_absent_from_extraction_flow` | grep absent in extraction path |
| Integration | `tests/test_orchestrator_phase0.py::test_phase0_hook_injects_term_table` | `client.system_prompt` contains term table |
| Data-boundary | `tests/test_term_extractor_resilience.py` (malformed / empty / oversized) | graceful, no raise |
| Env contract | `tests/test_env_contract.py` | 3 new vars present + typed |

Required test phases (generate evidence via `cdd-kit test run`; gate validates
`test-evidence.yml`): `collect`, `targeted`, `changed-area`, plus `contract`
(env + business + data + api-inventory touched) and `full` (full-test-suite gate
in ci-gates.md). The selector floor falls back to this table's
`test file / command` column. Full ladder lives in test-plan.md /
references/sdd-tdd-policy.md.

### Mock-binding rule (load-bearing)
Patch at the **consumer-bound** name inside `term_extractor.py`, e.g.
`app.backend.services.term_extractor.requests.post` (or the embedding-client
symbol as imported there) — NOT `requests.post` / `httpx` at the definition path.
Python binds names at import time; patching the source path silently misses the
already-imported reference. AC-5 threshold tests monkeypatch
`app.backend.services.term_extractor.TERM_EMBEDDING_THRESHOLD`, not the
`config.py` constant.

### Tautology guard (load-bearing)
Resilience and integration tests must call `run_phase0_multi` / `_phase0_hook`
**directly**, never via `translate_document()` or `process_files`. Calling a
higher-level wrapper that does not reach the Phase 0 seam is a wrong-entry-point
tautology and passes trivially. Static tests derive repo root via
`Path(__file__).parent.parent`, never a hardcoded absolute path.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into
  this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and
  report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion
  Request is approved.
- `tasks.yml` frontmatter must carry a `tier-floor-override` with written
  rationale: the change vocabulary ("integration", "api key", "endpoint") trips
  the Tier-2 tier-floor false-positive (CLAUDE.md lesson); the real tier is 2 per
  change-classification.md and no migration / DDL is involved.

## Known Risks
1. **Env-var name drift across artifacts (resolve to contracts).** Contracts
   (source of truth) use `TERM_EMBEDDING_MODEL`, `TERM_EMBEDDING_THRESHOLD`,
   `TERM_EXTRACTION_MODEL` (`env-contract.md:40-42`, `env.schema.json:128-145`,
   `.env.example.template:58-62`). `test-plan.md` and `ci-gates.md` reference
   stale names `TERM_SIMILARITY_THRESHOLD` / `PANJIT_EMBEDDING_MODEL`.
   Implementation MUST use the contract names. The `env-sync-panjit-embedding`
   gate in ci-gates.md greps for `PANJIT_EMBEDDING_MODEL` / `TERM_SIMILARITY_THRESHOLD`
   and will NOT match the contract names — route to ci-cd-gatekeeper to correct
   the gate grep to `TERM_EMBEDDING_MODEL` / `TERM_EMBEDDING_THRESHOLD` before the
   workflow-promotion step, or that gate fails.
2. **PANJIT client construction in the Phase 0 path.** `run_phase0_multi`
   currently takes `model`/`base_url`; the new flow needs PANJIT base_url/key/
   tls_verify. Resolve from the active provider config (not hardcoded). Confirm
   the seam against model_router / providers.yml so embedding and extraction both
   reach PANJIT with `verify_ssl=False`.
3. **Cosine candidate-set cost.** v1 embeds candidate term rows on the fly per
   request (O(terms)); acceptable for small SQLite DBs, flagged for the deferred
   persistence change (design.md Open Risks).
4. **`Qwen3-Embedding-8B` / `gemma4:latest` response shapes** must be confirmed by
   the integration / data-boundary tests against the stubbed seam (`data[].embedding`;
   missing-key and wrong-type cases are in the test plan).
5. **`.cdd/code-map.yml` not consulted.** It was not present in the read scope.
   Source pointers above were derived from direct reads of allowed paths; a
   `cdd-kit code-map` refresh would let future planning avoid broad reads.
