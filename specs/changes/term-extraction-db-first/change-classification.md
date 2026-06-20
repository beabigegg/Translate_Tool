# Change Classification

## Change Types
- primary: business-logic-change, feature-enhancement
- secondary: api-integration-change, env-change, refactor

## Lane
- feature

## Risk Level
- medium

## Impact Radius
- module-level (term-extraction subsystem)

## Tier
- 2

## Architecture Review Required
- yes
- reason: Introduces a new data-flow (embedding lookup → DB hit/miss branch → LLM-side injection vs. extraction call), a new external integration seam (PANJIT embedding + extraction endpoints replacing Ollama), and an operational-risk/fallback decision (embedding-API-failure → skip injection). spec-architect must write design.md before implementation-planner runs.

## Required Artifacts

| artifact | create? |
|---|---|
| design.md | yes |
| current-behavior.md | yes |
| qa-report.md | no |
| visual-review-report.md | no |
| regression-report.md | yes |

## Required Contracts
- API: yes — api-inventory.md: document PANJIT /v1/embeddings and /v1/chat/completions as outbound integrations
- CSS/UI: no
- Env: yes — add PANJIT embedding config, extraction model name, similarity threshold, verify_ssl=False rationale; remove OLLAMA_BASE_URL from extraction path if no longer used elsewhere
- Data shape: yes — `get_similar_terms_by_embedding()` query semantics; no vector-DB; on-the-fly cosine only
- Business logic: yes — decision table: DB hit → inject + skip extraction; DB miss → PANJIT extract → save → inject; embedding failure → skip injection, continue translation
- CI/CD: no

## Required Tests
- unit: DB-hit skips extraction LLM call; DB-miss calls PANJIT then saves; embedding-failure skips injection; threshold boundary (≥0.75 hit vs <0.75 miss); build_terminology_block() produces correct Markdown table; mock at consumer-bound name; selection-style assertions
- contract: PANJIT embedding/extraction request shapes; env contract new vars; business-rule decision-table conformance
- integration: orchestrator _phase0_hook end-to-end with stubbed PANJIT (real seam, not higher-level wrapper)
- data-boundary: malformed/empty embedding responses; zero-similarity; empty term DB; oversized segment
- resilience: PANJIT endpoint unreachable/timeout/5xx/SSL → skip injection, translation completes

## Required Agents
1. `spec-architect` — design.md (data-flow, PANJIT seam, fallback, threshold config placement)
2. `contract-reviewer` — env + data-shape + business + api-inventory updates
3. `test-strategist` — test-plan.md
4. `ci-cd-gatekeeper` — ci-gates.md
5. `implementation-planner` — implementation-plan.md (after design + contracts + tests)
6. `backend-engineer` — term_extractor.py, term_db.py, orchestrator.py Phase 0 hook, PANJIT client wiring
7. `e2e-resilience-engineer` — resilience/data-boundary tests
8. `qa-reviewer` — release readiness; regression confirmation

## Inferred Acceptance Criteria
- AC-1: DB hit (≥0.75 similarity) → inject matched terms as Markdown table into system prompt; NO extraction LLM call
- AC-2: DB miss (<0.75) → call PANJIT gemma4:latest for extraction → save to DB → inject; never calls localhost:11434 (Ollama)
- AC-3: PANJIT embedding API fails → skip term injection; translation completes without raising
- AC-4: PANJIT calls use verify_ssl=False; target `{PANJIT_LLM_BASE_URL}/v1/embeddings` (Qwen3-Embedding-8B) and `/v1/chat/completions` (gemma4:latest)
- AC-5: Similarity threshold (default 0.75) is configurable; changing it changes hit/miss boundary
- AC-6: Embedding similarity computed per-segment; no vector-DB package introduced
- AC-7: extraction_only mode and term_db CRUD API unchanged
- AC-8: After change, translation path performs no local-GPU (Ollama) call; term_extractor.py no longer references OLLAMA_BASE_URL in extraction flow

## Tasks Not Applicable
- 2.2 (no CSS/UI)
- 2.6 (no CI/CD contract)
- 3.4 (no monkey/fuzz)
- 3.5 (no stress/soak)
- 4.2 (no frontend)
- 4.3 (no deploy)
- 5.1 (no UI/UX)
- 5.2 (no visual)
- 6.4 (no nightly/weekly)
