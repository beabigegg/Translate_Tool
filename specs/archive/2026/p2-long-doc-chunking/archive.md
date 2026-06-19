# Archive — p2-long-doc-chunking

## Change Summary

Added semantic chunking support so documents exceeding the LLM context window (`num_ctx`) can be translated in multiple passes without loss of content. The core module `app/backend/services/doc_chunker.py` splits a `TranslatableDocument` into `ChunkRecord` objects using a priority cascade (paragraph break > heading > sentence > hard element boundary), inserts configurable token overlap for context continuity, and reassembles the translated results with overlap de-duplication. A new `translate_document()` entry point on `translation_service.py` drives the per-chunk LLM calls; the existing `translate_texts()` path is unchanged (AC-8/BR-53). The `CHUNK_OVERLAP_TOKENS` env var (default 50) is documented in the env contract.

## Final Behavior

- Documents ≤ `num_ctx` tokens: single-chunk fast path (BR-52) — exactly one LLM call, no overhead.
- Documents > `num_ctx` tokens: split at highest-priority semantic boundary within budget, overlapping tail retained per BR-47, all chunks translated independently, reassembled with leading overlap elements dropped.
- Chunk failure (BR-51): BR-25 placeholder written to all elements in the failed chunk; `translate_document` raises `RuntimeError`; other chunks unaffected.
- Atomic oversize element (BR-48): element always starts a chunk even if it alone exceeds `num_ctx` (never dropped or truncated).
- `translate_texts()` behavior: unchanged (BR-53).
- `translate_document()`: **unwired entry point** after this change — no format processor (docx/pptx/xlsx) calls it yet; wiring is a future follow-up.

## Final Contracts Updated

- `contracts/business/business-rules.md` — schema-version 0.8.0→0.9.0; BR-47–BR-53 added; Table O (12 rows) added
- `contracts/data/data-shape-contract.md` — schema-version 0.4.4→0.5.0; ChunkRecord, Doc2Doc entry point contract, Reassembly contract, Invalid-data-behavior rows added
- `contracts/env/env-contract.md` — schema-version 0.4.1→0.5.0; CHUNK_OVERLAP_TOKENS row added
- `contracts/env/.env.example.template` — `#CHUNK_OVERLAP_TOKENS=50` appended
- `contracts/env/env.schema.json` — CHUNK_OVERLAP_TOKENS property added

## Final Tests Added / Updated

- `tests/test_doc_chunker.py` — NEW; 38+ tests: `TestChunkerTokenCeiling`, `TestBoundaryPriority` (AC-2 boundary-position assertions + `test_paragraph_break_preferred_over_heading`), `TestOverlapInsertion`, `TestReassembly`, `TestAtomicOversizeElement`, `TestDoc2DocPath`, `TestChunkFailureIsolation`, `TestTranslateTextsRegression`, `TestDataBoundary`, `TestReassemblyIntegrity`
- `tests/test_translation_strategy.py` — 8 new Doc2Doc integration tests
- `tests/test_env_contract.py` — `test_chunk_overlap_tokens_declared`
- `tests/test_sentence_mode_consistency.py` — `test_sentence_mode_backward_compat_with_chunking_change`

Full suite: 669 passed / 4 skipped / 0 failed.

## Final CI/CD Gates

| gate | tier | trigger |
|---|---:|---|
| Contract validation (`cdd-kit validate --contracts`) | 1 | push + PR |
| Change gate (`cdd-kit gate p2-long-doc-chunking`) | 1 | push + PR |
| OpenAPI sync | 1 | push + PR |
| Unit / contract / integration / data-boundary tests | 1 | push + PR |
| Full regression | 2 | PR only |
| Golden-sample regression | 2 | PR only |
| Text expansion benchmark | 2 | PR only |
| Renderer equivalence | 2 | PR only |

## Production Reality Findings

- **AC-2 initial gap** (test-strategist fix-back): `TestBoundaryPriority` originally asserted only `len(chunks) >= 2`. QA-reviewer caught this as tautological; test-strategist strengthened all three tests to assert `chunks[1].elements[overlap_element_count].element_id` and added `test_paragraph_break_preferred_over_heading`. Implementation was correct; the regression net was absent. Fixed before gate re-pass.
- **Doc2Doc unwired**: `translate_document()` has no caller in any format processor. This is intentional and documented as a follow-up.
- **Mock boundary**: tests must patch `app.backend.services.translation_service.translate_blocks_batch` (name bound at import in translation_service.py), not the utils path.

## Lessons Promoted to Standards

1. **Tautological test — selection form** (folded into existing CLAUDE.md tautological-test entry): Tests asserting count/length without asserting WHICH element was chosen pass even when selection/priority logic is broken. Assert `element_id` (or equivalent identity), not just `len(chunks)`. Evidence: `qa-reviewer.yml` AC-2 finding; `test-strategist.yml` fix-back; `tests/test_doc_chunker.py::TestBoundaryPriority` (corrected pattern).

2. **`mock.patch` binding path** (new CLAUDE.md entry): Patch must target the name bound in the **consumer** module, not the definition path — Python binds at import time. Evidence: `backend-engineer.yml` notes; `tests/test_translation_strategy.py` Doc2Doc mock pattern.

## Follow-up Work

- Wire `translate_document()` into format processors (docx/pptx/xlsx orchestrator) — new change required.
- AC-2 boundary-priority tests now assert split position; no further follow-up needed there.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
