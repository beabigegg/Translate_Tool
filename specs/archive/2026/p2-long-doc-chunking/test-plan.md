---
change-id: p2-long-doc-chunking
schema-version: 0.1.0
last-changed: 2026-06-19
risk: medium
tier: 2
---

# Test Plan: p2-long-doc-chunking

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_doc_chunker.py::TestChunkerTokenCeiling::test_chunks_all_within_num_ctx_ceiling | 1 |
| AC-1 | unit | tests/test_doc_chunker.py::TestOverlapInsertion::test_adjacent_chunks_share_overlap_tokens | 1 |
| AC-2 | unit | tests/test_doc_chunker.py::TestBoundaryPriority::test_paragraph_break_preferred_over_heading | 1 |
| AC-2 | unit | tests/test_doc_chunker.py::TestBoundaryPriority::test_heading_preferred_over_sentence_when_no_paragraph | 1 |
| AC-2 | unit | tests/test_doc_chunker.py::TestBoundaryPriority::test_sentence_boundary_used_when_no_higher_priority | 1 |
| AC-2 | unit | tests/test_doc_chunker.py::TestBoundaryPriority::test_paragraph_break_preferred_over_sentence | 1 |
| AC-3 | unit | tests/test_doc_chunker.py::TestOverlapInsertion::test_first_chunk_has_zero_overlap | 1 |
| AC-3 | unit | tests/test_doc_chunker.py::TestOverlapInsertion::test_overlap_element_count_captured_at_split_time | 1 |
| AC-3 | unit | tests/test_doc_chunker.py::TestChunkerTokenCeiling::test_overlap_tokens_gte_num_ctx_raises_value_error | 1 |
| AC-3 | contract | tests/test_env_contract.py::TestEnvContractDeclared::test_chunk_overlap_tokens_declared | 1 |
| AC-4 | integration | tests/test_translation_strategy.py::test_doc2doc_calls_llm_once_per_chunk | 1 |
| AC-4 | integration | tests/test_translation_strategy.py::test_each_chunk_translation_is_independent | 1 |
| AC-5 | unit | tests/test_doc_chunker.py::test_reassembly_preserves_original_order | 1 |
| AC-5 | unit | tests/test_doc_chunker.py::test_overlap_region_not_duplicated_in_output | 1 |
| AC-5 | unit | tests/test_doc_chunker.py::test_no_element_dropped_after_reassembly | 1 |
| AC-5 | unit | tests/test_doc_chunker.py::test_no_element_appears_twice_in_reassembly | 1 |
| AC-5 | data-boundary | tests/test_doc_chunker.py::test_empty_doc_returns_unchanged | 1 |
| AC-5 | data-boundary | tests/test_doc_chunker.py::test_all_no_translate_returns_unchanged | 1 |
| AC-5 | data-boundary | tests/test_doc_chunker.py::test_atomic_oversize_element_not_dropped | 1 |
| AC-5 | data-boundary | tests/test_doc_chunker.py::test_mixed_line_endings_no_content_loss | 1 |
| AC-5 | resilience | tests/test_doc_chunker.py::test_single_chunk_failure_surfaces_error | 1 |
| AC-5 | resilience | tests/test_doc_chunker.py::test_chunk_failure_does_not_corrupt_other_chunks | 1 |
| AC-5 | resilience | tests/test_doc_chunker.py::test_failed_chunk_elements_get_br25_placeholder | 1 |
| AC-6 | unit | tests/test_doc_chunker.py::test_single_chunk_when_at_token_ceiling | 1 |
| AC-6 | unit | tests/test_doc_chunker.py::test_single_chunk_when_below_token_ceiling | 1 |
| AC-6 | integration | tests/test_translation_strategy.py::test_single_chunk_doc_produces_exactly_one_llm_call | 1 |
| AC-7 | integration | tests/test_translation_strategy.py::test_doc2doc_accepts_whole_document | 1 |
| AC-7 | integration | tests/test_translation_strategy.py::test_doc2doc_returns_same_document_instance | 1 |
| AC-7 | integration | tests/test_translation_strategy.py::test_doc2doc_chunking_transparent_to_caller | 1 |
| AC-8 | integration | tests/test_translation_strategy.py::test_translate_texts_unchanged_after_doc2doc_added | 1 |
| AC-8 | integration | tests/test_translation_strategy.py::test_doc2doc_does_not_mutate_shared_cache_state | 1 |
| AC-8 | integration | tests/test_sentence_mode_consistency.py::test_sentence_mode_backward_compat_with_chunking_change | 1 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 1 | Boundary priority, token ceiling, overlap sizing, reassembly ordering — all in new `tests/test_doc_chunker.py`; must fail before implementation |
| contract | 1 | `CHUNK_OVERLAP_TOKENS` present in `contracts/env/env-contract.md`; extend `TestEnvContractDeclared` in existing `tests/test_env_contract.py` |
| integration | 1 | Doc2Doc end-to-end with mocked LLM; AC-8 regression on `translate_texts()`; extend `tests/test_translation_strategy.py` |
| data-boundary | 1 | Empty doc, all-no-translate, atomic oversize element, mixed line endings; co-located in `tests/test_doc_chunker.py` |
| resilience | 1 | Single-chunk failure surfaced without corrupting reassembly; BR-25 placeholder on failed elements; co-located in `tests/test_doc_chunker.py` |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_sentence_mode_consistency.py | extend (add one test) | AC-8 backward-compat guard for the sentence-mode path after Doc2Doc is wired |
| tests/test_env_contract.py::TestEnvContractDeclared | extend (add one test) | AC-3 requires `CHUNK_OVERLAP_TOKENS` declared in env-contract |

## Out of Scope

- E2E / HTTP tests — Doc2Doc is an internal service method, not a new HTTP endpoint
- Visual / rendering tests — no renderer surface touched by this change
- Stress / soak — single LLM call per chunk; not a load surface at Tier 2
- Monkey / fuzz — not required at this tier per change-classification.md
- Serialization of `ChunkRecord` — chunk IR is never serialized (data-shape-contract §Chunk Representation)

## Notes

- Mock boundary: patch `app.backend.utils.translation_helpers.translate_blocks_batch` (LLM network boundary), matching the pattern in `test_sentence_mode_consistency.py`. Do not mock internal chunker methods.
- All tests in `tests/test_doc_chunker.py` are TDD stubs: the file does not exist at plan-write time and must fail before `doc_chunker.py` is implemented.
- BR-47–BR-53 and Table O in `business-rules.md` are the normative behavioral spec; each test maps to at least one Table O row.
- `test_overlap_ge_num_ctx_raises_value_error` covers both the `data-shape-contract §Invalid-data behavior` row and BR-49.
