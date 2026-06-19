---
change-id: p2-long-doc-chunking
schema-version: 0.1.0
last-changed: 2026-06-19
---

# Implementation Plan: p2-long-doc-chunking

## Objective
Add a standalone semantic document-chunking module plus a new Doc2Doc service
entry point so a `TranslatableDocument` whose source-side estimated token count
exceeds the resolved `num_ctx` ceiling is split, translated chunk-by-chunk, and
reassembled in original order without dropping, duplicating, or reordering
content. The existing per-segment `translate_texts()` path must stay
behaviorally identical (BR-53 / AC-8). Doc2Doc ships as an unwired public entry
point only; no processor/orchestrator wiring is in scope.

## Execution Scope

### In Scope
- New pure module `app/backend/services/doc_chunker.py`: `ChunkRecord` dataclass,
  token estimator, boundary-priority splitter, overlap insertion, reassembly with
  overlap de-duplication. No LLM, DB, HTTP, or file I/O.
- New `translate_document(...)` orchestration method on
  `app/backend/services/translation_service.py`.
- New `CHUNK_OVERLAP_TOKENS` constant in `app/backend/config.py` (env-backed,
  default 50).
- Env contract artifact registration for `CHUNK_OVERLAP_TOKENS` in
  `contracts/env/.env.example.template` and `contracts/env/env.schema.json`
  (the `env-contract.md` row already exists — see Source Pointers).
- TDD tests authored by test-strategist per the `test-plan.md` AC mapping.

### Out of Scope
- Wiring Doc2Doc into `orchestrator.py`, any processor (docx/pdf/pptx/xlsx), or
  any HTTP route (Decision 4). Confirmed: processors call `translate_texts()` on
  deduplicated text lists and never build a `TranslatableDocument` for the
  translation step.
- Any change to `translate_texts()` behavior, its cache key structure, prompt
  templates, or shared state (BR-53).
- Any new tokenizer dependency (`tiktoken`/model-specific). Reuse the existing
  chars/token heuristic (Decision 2).
- Serialization of `ChunkRecord`; any `TranslatableDocument.to_dict()/from_dict()`
  schema change; any persistence or migration.
- New HTTP endpoint, `api-contract.md`, or `openapi.yml` change (Doc2Doc is an
  internal method).
- Opportunistic refactor of `translation_service.py`, `translation_strategy.py`,
  or the models module beyond the additions above.

## Non-Goals (explicit)
- Do NOT make `translate_document()` a thin wrapper over a single
  `translate_texts()` call — it must produce one LLM call per chunk (AC-4 / BR-52).
- Do NOT introduce a Doc2Doc cache variant/partition or alter the per-segment
  cache key (Decision 6 / BR-53).
- Do NOT recompute the overlap drop-boundary from translated (target-side) token
  counts; drop exactly the element set captured at split time (Decision 3).
- Do NOT modify `orchestrator.py`, `routes.py`, or `schemas.py` (read-only here;
  CER-001 approved them for inspection only, not for edits).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | tests (TDD) | Author all `tests/test_doc_chunker.py` cases (new file) + extend `tests/test_translation_strategy.py`, `tests/test_env_contract.py`, `tests/test_sentence_mode_consistency.py` per the `test-plan.md` mapping. Must fail before IP-3/IP-4. | test-strategist |
| IP-2 | config + env | Add `CHUNK_OVERLAP_TOKENS = int(os.environ.get("CHUNK_OVERLAP_TOKENS", "50"))` to `config.py`; register the var in `.env.example.template` and `env.schema.json`. | backend-engineer |
| IP-3 | new module | Implement `doc_chunker.py`: `ChunkRecord`, token estimator, single-chunk fast path (BR-52), boundary-priority splitter (BR-50), overlap (BR-47) with `overlap_element_count` captured at split, atomic-oversize handling (BR-48), ceiling enforcement (BR-49), `ValueError` when `CHUNK_OVERLAP_TOKENS >= num_ctx`, reassembly + overlap de-dup (Reassembly contract). | backend-engineer |
| IP-4 | service entry point | Implement `translate_document(doc, targets, src_lang, client, ...) -> TranslatableDocument` on `translation_service.py`: build chunks, translate each chunk via the per-chunk primitive, set `translated_content` in place, apply BR-25 placeholder + surface failure on chunk failure (BR-51), return the same instance. | backend-engineer |
| IP-5 | contract conformance | Verify env / data-shape / business contract text matches the implemented `ChunkRecord` fields, Doc2Doc signature, and reassembly behavior. | contract-reviewer |
| IP-6 | release readiness | Run the test ladder; confirm AC-8 regression on `translate_texts()`; confirm `cdd-kit gate` is green. | qa-reviewer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | Decisions 1-6; Open Risks | module boundary, token heuristic, overlap de-dup, Doc2Doc shape, failure handling, cache constraint |
| test-plan.md | AC → test mapping table; Notes (mock boundary) | tests to write/run; patch target |
| ci-gates.md | Required Gates table; "Test coverage provided by Tier 1" | verification commands |
| business-rules.md | BR-47..BR-53; Table O; Table F (BR-25 format) | per-chunk behavior + failure placeholder |
| data-shape-contract.md | §Chunk Representation; §Doc2Doc; §Reassembly contract; §Invalid-data behavior | `ChunkRecord` fields, entry-point contract, de-dup rule, edge cases |
| env-contract.md | `CHUNK_OVERLAP_TOKENS` row (line 36) | env var spec (default 50, positive int, non-secret) |
| config.py | `GENERAL_NUM_CTX`/`TRANSLATION_NUM_CTX` (lines 33-34); `len(text)/2.5` heuristic precedent | resolved `num_ctx` source; chars/token divisor precedent |

## File-Level Plan
(Ordered: new files first, then modified files.)

| path or glob | action | notes |
|---|---|---|
| `tests/test_doc_chunker.py` | create | All unit / data-boundary / resilience cases from test-plan.md (AC-1,2,3,5,6). TDD: must fail before IP-3. |
| `app/backend/services/doc_chunker.py` | create | Pure module. `ChunkRecord` fields exactly: `chunk_index:int`, `token_span:tuple[int,int]`, `elements:list[TranslatableElement]` (same object refs — no deep copy), `overlap_tokens:int`. Track `overlap_element_count` internally for reassembly. Named chars/token divisor constant (~2.5, tunable). `ValueError` if `CHUNK_OVERLAP_TOKENS >= num_ctx` at init. Never imports LLM/DB/HTTP. |
| `app/backend/config.py` | modify | Add `CHUNK_OVERLAP_TOKENS` near the batching block (~line 97). Default 50, env-backed. |
| `app/backend/services/translation_service.py` | modify | Add `translate_document(...)`. Reuse the existing per-chunk primitive (`translate_blocks_batch` is already imported / used by `translate_texts`). Do NOT touch `translate_texts()`. NOTE: code-map is stale for this file (see Known Risks) — read current source before editing. |
| `contracts/env/.env.example.template` | modify | Add `CHUNK_OVERLAP_TOKENS=50` row. |
| `contracts/env/env.schema.json` | modify | Add `CHUNK_OVERLAP_TOKENS` (positive integer, default 50, non-secret). |
| `tests/test_translation_strategy.py` | modify | Add Doc2Doc integration tests (AC-4, AC-6, AC-7, AC-8). Mock boundary: patch `app.backend.utils.translation_helpers.translate_blocks_batch`. |
| `tests/test_env_contract.py` | modify | Extend `TestEnvContractDeclared` with `test_chunk_overlap_tokens_declared` (AC-3). |
| `tests/test_sentence_mode_consistency.py` | modify | Add `test_sentence_mode_backward_compat_with_chunking_change` (AC-8). |

## Contract Updates
- API: none (internal method; no `api-contract.md` / `openapi.yml` change).
- CSS/UI: none.
- Env: `CHUNK_OVERLAP_TOKENS` — `env-contract.md` row already present (line 36);
  add matching entries to `.env.example.template` and `env.schema.json` only.
- Data shape: `ChunkRecord` + Doc2Doc + Reassembly sections already authored in
  `data-shape-contract.md` (§Chunk Representation onward); implementation must
  conform, not edit (contract-reviewer verifies — IP-5).
- Business logic: BR-47..BR-53 + Table O already authored; implementation must
  conform. No edit expected.
- CI/CD: none (`.github/workflows/contract-driven-gates.yml` already updated per
  ci-gates.md §Workflow Changes; do not re-edit).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 token ceiling | tests/test_doc_chunker.py | every chunk (incl. overlap) ≤ num_ctx |
| AC-2 boundary priority | tests/test_doc_chunker.py | paragraph>heading>sentence selection honored |
| AC-3 overlap config + ValueError | tests/test_doc_chunker.py; tests/test_env_contract.py | default 50 applied; env override honored; `CHUNK_OVERLAP_TOKENS>=num_ctx` raises ValueError; env var declared |
| AC-4 one LLM call per chunk | tests/test_translation_strategy.py | mocked primitive invoked once per chunk, independently |
| AC-5 reassembly integrity | tests/test_doc_chunker.py | original order; overlap de-duped; no drop/dup; failure surfaced + BR-25 placeholder |
| AC-6 single-chunk path | tests/test_doc_chunker.py; tests/test_translation_strategy.py | ≤ceiling → exactly 1 chunk / 1 LLM call |
| AC-7 transparent Doc2Doc | tests/test_translation_strategy.py | accepts whole doc; returns same instance; no caller pre-split |
| AC-8 translate_texts unchanged | tests/test_translation_strategy.py; tests/test_sentence_mode_consistency.py | identical behavior; no shared cache-state mutation |

TDD execution ladder (`cdd-kit test` phases; floor: collect → targeted →
changed-area → full):
1. `collect` — discover all tests including the new `tests/test_doc_chunker.py`
   stubs; confirm they are collected and RED before any implementation.
2. `targeted` — run the new/extended tests for the AC under work; keep RED until
   the matching implementation lands, then GREEN.
3. `changed-area` — run the `tests/` files touched by this change
   (`test_doc_chunker.py`, `test_translation_strategy.py`, `test_env_contract.py`,
   `test_sentence_mode_consistency.py`).
4. `full` (Tier 2 trigger applies) — `pytest tests/ -q --tb=short` (full
   regression gate per ci-gates.md) to confirm AC-8 / BR-53 no-regression across
   the suite. Implementation agents produce `test-evidence.yml` via
   `cdd-kit test run`; the gate validates it.

Contract + quality phases ride the existing `cdd-kit validate --contracts` and
`cdd-kit gate p2-long-doc-chunking` gates in `contract-and-fast-tests`.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- TDD-first: the tests in `tests/test_doc_chunker.py` must exist and FAIL before
  `doc_chunker.py` / `translate_document()` are implemented.
- Mock boundary is fixed: patch
  `app.backend.utils.translation_helpers.translate_blocks_batch`; do NOT mock
  internal chunker methods (test-plan.md Notes).
- BR-25 placeholder format is exactly `[Translation failed|{tgt}] {text}`
  (business-rules.md Table F) — reuse, do not invent a new format.
- `ChunkRecord.elements` must hold the same `TranslatableElement` object
  references as the parent document — no deep copy (data-shape contract).
- `translate_document` mutates in place and returns the same instance
  (data-shape Doc2Doc contract).
- No new top-level packages; `doc_chunker.py` stays under
  `app/backend/services/` and imports no LLM/DB/HTTP.
- Do not re-copy full design, test strategy, CI policy, or contract prose into
  this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and
  report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion
  Request is approved.

## Known Risks
- `.cdd/code-map.yml` is STALE for `app/backend/services/translation_service.py`:
  the map shows ~271 lines and imports `OllamaClient`, but the live file is 431
  lines, imports `LLMClient` from `app.backend.clients.base_llm_client`, and
  already contains the critique-loop + glossary blocks. Backend-engineer MUST
  read the current source (already in allowed paths) before editing and not rely
  on the map's line ranges. Recommend running `cdd-kit code-map` to refresh.
- Per-chunk translation uses `translate_blocks_batch` (already used inside
  `translate_texts` under `SENTENCE_MODE`). Confirm the primitive's current
  signature against live source; the integration mock patches it at the
  `app.backend.utils.translation_helpers` module path.
- Token estimation is a coarse chars/token heuristic; `overlap_element_count`
  may be off by one element vs. an exact tokenizer. Mitigated by capturing the
  duplicated element set at split time so source/target estimates never disagree
  on reassembly. Data-boundary tests (atomic oversize, single-chunk-at-ceiling,
  mixed line endings, empty doc) must exercise the boundary.
- Watch `cdd-kit gate` tier-floor false-positives on env/"endpoint"/"integration"
  vocabulary; use `tier-floor-override` with written rationale if the gate forces
  a spurious tier (per the change-classification note).
