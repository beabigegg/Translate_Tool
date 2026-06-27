---
change-id: wire-context-segments
schema-version: 0.1.0
last-changed: 2026-06-27
risk: medium
tier: 0
---

# Test Plan: wire-context-segments

## Acceptance Criteria → Test Mapping

| criterion id | test family | test file path | tier |
|---|---|---|---|
| AC-1 | unit | tests/test_context_window_segments.py::test_build_context_prefix_includes_n_preceding | 0 |
| AC-1 | unit | tests/test_context_window_segments.py::test_build_context_prefix_capped_at_n | 0 |
| AC-1 | unit (wiring) | tests/test_context_window_segments.py::test_prompt_payload_contains_neighbor_text_at_call_boundary | 0 |
| AC-2 | unit | tests/test_context_window_segments.py::test_build_context_prefix_truncated_to_max_chars | 0 |
| AC-2 | unit | tests/test_context_window_segments.py::test_build_context_prefix_truncates_from_oldest_end | 0 |
| AC-3 | unit | tests/test_context_window_segments.py::test_build_context_prefix_zero_n_returns_empty | 0 |
| AC-3 | unit (wiring) | tests/test_context_window_segments.py::test_prompt_payload_has_no_context_prefix_when_n_zero | 0 |
| AC-4 | unit | tests/test_context_window_segments.py::test_context_prefix_header_not_present_in_translated_output | 0 |
| AC-5 | unit | tests/test_context_window_segments.py::test_build_context_prefix_empty_at_first_segment | 0 |
| AC-5 | unit | tests/test_context_window_segments.py::test_build_context_prefix_uses_available_neighbors_at_last_segment | 0 |
| AC-6 | data-boundary | tests/test_context_window_segments.py::test_context_constants_are_imported_in_pipeline | 0 |

## Test Families Required

| family | tier | notes |
|---|---|---|
| unit | 0 | Pure function tests for `build_context_prefix()` in `context_prompts.py` |
| unit (wiring) | 0 | Mock at `_call_ollama` HTTP boundary; capture `payload["prompt"]`; assert specific neighbor text appears |
| data-boundary | 0 | Positive grep: `CONTEXT_WINDOW_SEGMENTS` referenced in `app/` outside `config.py` |

## Test Execution Ladder

| phase | required | command source | max failures | result artifact |
|---|---:|---|---:|---|
| collect | yes | cdd-kit test select | 1 | test-runs/<run-id>/summary.json |
| targeted | yes | cdd-kit test select | 1 | test-evidence.yml |
| changed-area | yes | cdd-kit test select | 1 | test-evidence.yml |
| contract | if affected | cdd-kit validate | 1 | test-evidence.yml |
| quality | if configured | ci-gates.md | 1 | test-evidence.yml |
| full | final/CI | cdd-kit test run --phase full | 1 | test-evidence.yml |

## Test Update Contract

| existing test | action | reason |
|---|---|---|
| tests/test_dead_references.py | extend | Add `test_context_constants_not_dead` as positive-grep pattern if kept in that file; AC-6 currently placed in test_context_window_segments.py |

## Stop Rules

- Do not run broad pytest before targeted and changed-area phases pass.
- Do not investigate more than the first failure per phase.
- Do not classify any failure as known, pre-existing, waived, or allowed.
- If full suite fails, record the first failure and block the gate.

## Out of Scope

- End-to-end file translation (DOCX/PDF/PPTX); context prefix correctness is provable at unit level
- LLM translation quality improvement measurement with vs without context
- OpenAI-compatible client; unless explicitly extended in scope
- Stress / soak; AC-2 char cap bounds the only load-relevant variable

## Notes

**Mock boundary**: `patch.object(client_instance, "_call_ollama", return_value=(True, "ok"))` — `payload["prompt"]` in each captured call contains the full built prompt. Do NOT mock `translate_once`, `translate_batch`, or `translate_blocks_batch` — those produce the tautological call-wiring anti-pattern.

**Wiring test shape** (AC-1 wiring): `texts = ["Segment A.", "Segment B.", "Segment C."]`; real `OllamaClient`; patch `_call_ollama`; call `translate_blocks_batch(texts, ...)`; assert the captured prompt for "Segment B." contains the LITERAL string "Segment A." — selection test, not count test.

**Pure function home**: `build_context_prefix(segments, current_idx, n_context, max_chars) -> str` in `app/backend/services/context_prompts.py` (leaf module, no circular imports).

**AC-6 test shape**: subprocess grep for `CONTEXT_WINDOW_SEGMENTS` in `app/` excluding `config.py`; assert `returncode == 0` (constant IS referenced). Inverse of `test_dead_references.py` pattern.
