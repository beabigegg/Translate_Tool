---
change-id: nontranslatable-segment-guard
schema-version: 0.1.0
last-changed: 2026-07-08
risk: medium
tier: 2
---

# Test Plan: nontranslatable-segment-guard

## Acceptance Criteria → Test Mapping
| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_nontranslatable_segment_guard.py::TestTrivialPassthrough::test_pure_number_not_called_output_equals_source | 0 |
| AC-1 | unit | tests/test_nontranslatable_segment_guard.py::TestTrivialPassthrough::test_punctuation_only_not_called_output_equals_source | 0 |
| AC-1 | unit | tests/test_nontranslatable_segment_guard.py::TestTrivialPassthrough::test_whitespace_only_not_called_output_equals_source | 0 |
| AC-1 | unit | tests/test_nontranslatable_segment_guard.py::TestTrivialPassthrough::test_already_target_language_token_not_called_output_equals_source | 0 |
| AC-1 | unit | tests/test_nontranslatable_segment_guard.py::TestTrivialPassthrough::test_very_short_single_token_not_called_output_equals_source | 0 |
| AC-2 | unit | tests/test_nontranslatable_segment_guard.py::TestRefusalOutputGuard::test_ask_back_reply_source_written_not_meta_string | 0 |
| AC-2 | unit | tests/test_nontranslatable_segment_guard.py::TestRefusalOutputGuard::test_question_back_reply_source_written_not_meta_string | 0 |
| AC-2 | unit | tests/test_nontranslatable_segment_guard.py::TestRefusalOutputGuard::test_language_detection_note_reply_source_written_not_meta_string | 0 |
| AC-3 | unit | tests/test_nontranslatable_segment_guard.py::TestRefusalDetectorNegative::test_genuine_translation_containing_question_mark_is_not_suppressed | 0 |
| AC-3 | unit | tests/test_nontranslatable_segment_guard.py::TestRefusalDetectorNegative::test_genuine_translation_reading_like_a_note_is_not_suppressed | 0 |
| AC-4 | unit | tests/test_nontranslatable_segment_guard.py::TestConservativePassthrough::test_genuine_sentence_is_sent_to_client_and_translated | 0 |
| AC-1,2,4 | integration | tests/test_nontranslatable_segment_guard.py::TestTranslateMergedParagraphsEndToEnd::test_trivial_and_refusal_and_normal_segments_in_one_call | 1 |
| AC-6 | integration | tests/test_nontranslatable_segment_guard.py::TestReproduction8D::test_8d_trivial_segment_fixture_ask_back_fake_red_pre_fix_green_post_fix | 1 |
| AC-5 | regression | tests/test_table_recognizer.py | 1 |
| AC-5 | regression | tests/test_table_context_translation.py | 1 |
| AC-7 | contract | contracts/business/business-rules.md (Table Z, BR-107/BR-108) via `cdd-kit validate --contracts` | 1 |
| n/a | regression | tests/test_context_window_segments.py | 1 |

## Test Families Required
| family | tier | notes |
|---|---|---|
| unit | 0 | Trivial-segment classifier (pure number/punctuation/whitespace/already-target-language/short-token) and refusal detector, exercised directly against the new guard function(s) with a call-counting fake `LLMClient` — no I/O, no torch |
| integration | 1 | `translate_merged_paragraphs` (translation_helpers.py) end-to-end with a fake client covering all guard paths in one call, plus the RED→GREEN 8D reproduction fixture (AC-6) |
| regression | 1 | Existing suites that MUST stay green unmodified: table-cell BR-68 path (`test_table_recognizer.py`, `test_table_context_translation.py`, AC-5) and context-window segment building (`test_context_window_segments.py`) — proves the new guards do not touch table cells or context-prefix behavior |
| contract | 1 | BR-107/BR-108 + Table Z already present in `contracts/business/business-rules.md` (0.26.0); verified structurally by `cdd-kit validate --contracts`; the behavioral proof per Table Z's own "test id" column is the AC-1..AC-4 unit/integration tests above |

## Test Update Contract
| existing test | action | reason |
|---|---|---|
| tests/test_table_recognizer.py | none | table-cell BR-68 numeric passthrough is out of scope (AC-5); must remain green unmodified as the regression baseline |
| tests/test_table_context_translation.py | none | same — BR-68/BR-79-83 table path unaffected (AC-5) |
| tests/test_context_window_segments.py | none | context-prefix delivery (`build_context_prefix`, `system_context`) is unrelated to the trivial/refusal guards; must stay green to prove no regression on the context-window seam this change's target function shares |
| tests/test_openai_compatible_client.py | none | client `translate_once` call signature is unchanged by this fix (guards live above the client call in `translate_merged_paragraphs`); asserted implicitly by AC-1/AC-4 call-counter tests using the existing fake-client pattern |

## Out of Scope
- Table-cell path and BR-68 numeric passthrough (unchanged; regression-only, see AC-5).
- Step-2 cloud doc-summary enhancement and step-3 JSON structured I/O (separate changes).
- Office (docx/pptx/xlsx) output modes, judge loop, QE/COMET scoring, layout detection.
- Live-LLM E2E (reproduction is fake-client-only per change-request Success Criterion).
- Any new `translation_status` enum value or `data-shape-contract.md` change (default plan reuses `passthrough`/`failed`; only applies if implementation deviates — out of scope for this plan).

## Notes
- Anti-tautology (per CLAUDE.md): trivial-passthrough tests MUST use a call-counting fake and assert `call_count == 0` (never infer "not called" from empty output) AND assert the result equals the exact source string (not merely truthy/non-empty). The refusal-detector NEGATIVE case (AC-3) is mandatory — a naive "suppress anything with a question mark" fix must fail it.
- AC-6 reproduction is torch-free (no COMET/QE); still run the ladder via `conda run -n translate-tool cdd-kit test run …` per repo convention so the interpreter matches CI.
- New test file has no existing counterpart — bug-fix-engineer writes `tests/test_nontranslatable_segment_guard.py` first (RED), per bug-fix lane (change-classification.md `Bug Evidence Required`).
- Root-cause pointers for implementation: `app/backend/utils/translation_helpers.py::translate_merged_paragraphs` (lines 133-199, esp. 187-194) and `app/backend/services/translation_service.py:887` (BR-68 precedent); existing classifier `app/backend/utils/text_utils.py::should_translate` (lines 75-133) is the nearest reusable building block for the trivial-passthrough check.
