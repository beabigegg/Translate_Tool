---
change-id: wire-context-segments
schema-version: 0.1.0
last-changed: 2026-06-27
---

# Implementation Plan: wire-context-segments

## Objective

Activate the orphaned config constants `CONTEXT_WINDOW_SEGMENTS` (default 2) and
`CONTEXT_MAX_CHARS` (default 300) so that, in the default paragraph-granularity
translation path, each segment's LLM prompt is preceded by up to
`CONTEXT_WINDOW_SEGMENTS` immediately preceding segments rendered under a
`"Context (do not translate):"` block, capped at `CONTEXT_MAX_CHARS` characters,
truncated from the oldest end. `CONTEXT_WINDOW_SEGMENTS = 0` must produce prompts
byte-identical to current behavior. Implement exactly BR-78 / Decision Table V.
No new behavior beyond wiring the existing constants.

## Execution Scope

### In Scope
- New pure function `build_context_prefix(segments, current_idx, n_context, max_chars) -> str`
  in `app/backend/services/context_prompts.py` (leaf module; no `app.backend.*`
  imports — receive window/max_chars as arguments, do not import `config`).
- Wire that function into the per-segment paragraph path reached from
  `translate_blocks_batch()` (the loop in `translate_merged_paragraphs()`) in
  `app/backend/utils/translation_helpers.py`, so the context block becomes part
  of the prompt string actually sent to the LLM.
- Read `CONTEXT_WINDOW_SEGMENTS` / `CONTEXT_MAX_CHARS` from config at call time
  in `translation_helpers.py` so values are monkeypatchable (see IP-2 note).
- New test file `tests/test_context_window_segments.py` (11 functions per
  test-plan.md mapping).

### Out of Scope
- No REST/API changes, no `api/schemas.py`, no frontend, no DB/migration, no env
  vars (constants stay Python-level in `config.py`).
- Do NOT modify `app/backend/clients/base_llm_client.py` (the `LLMClient`
  Protocol) or `app/backend/clients/openai_compatible_client.py` — not in the
  allowed-paths boundary, and changing the shared `translate_once` signature
  would break the cloud client. The context must reach the LLM without altering
  the shared `translate_once(text, tgt, src_lang)` signature.
- No change to `app/backend/services/translation_service.py` — it already calls
  `translate_blocks_batch()` at three sites (lines 181, 468, 616); wiring inside
  that helper covers all of them. Read-only for understanding.
- Legacy sentence-granularity path (`BatchTranslator`) — context is wired only
  into the default `paragraph` granularity path.
- No redesign of the context system, prompt builders, or batching; do not
  opportunistically refactor `ollama_client.py` prompt builders.

## Required Changes

| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | context_prompts.py | Add pure `build_context_prefix(segments, current_idx, n_context, max_chars)`: returns `""` when `n_context <= 0` or no predecessors; else join predecessors `segments[max(0,current_idx-n_context):current_idx]`, cap combined neighbor text at `max_chars` truncating from the OLDEST end, and return a block labeled `"Context (do not translate):"`. Implements BR-78. | backend-engineer |
| IP-2 | translation_helpers.py | In `translate_merged_paragraphs()` (the per-segment loop reached by `translate_blocks_batch()` for `paragraph` granularity), compute `prefix = build_context_prefix(texts, i, config.CONTEXT_WINDOW_SEGMENTS, config.CONTEXT_MAX_CHARS)` and prepend it to the segment text passed into `client.translate_once(prefix + text, tgt, src_lang)`. Reference the two constants via module-qualified access (`from app.backend import config; config.CONTEXT_WINDOW_SEGMENTS`) so they are read at call time and are monkeypatchable; this also satisfies AC-6 positive grep (literal token appears outside `config.py`). Map results back to the ORIGINAL target index only — the prefix never becomes its own output segment. | backend-engineer |
| IP-3 | tests | Create `tests/test_context_window_segments.py` with the 11 functions named in test-plan.md (pure-function + wiring + data-boundary). Wiring tests mock at `_call_ollama` on a real `OllamaClient`; never mock `translate_once`/`translate_batch`/`translate_blocks_batch`. | backend-engineer |
| IP-4 | verify | Confirm `tests/test_dead_references.py` still passes (its grep targets removed `refine_*` symbols, unrelated) and run AC-6 positive-grep test. | backend-engineer |

## Source Artifact Pointers

| source | relevant pointer | used for |
|---|---|---|
| change-classification.md | AC-1..AC-6; "Inferred Acceptance Criteria" | behavior to implement |
| test-plan.md | AC→test mapping table; "Notes" (mock boundary, wiring shape, pure-function home) | tests to write + mock boundary |
| contracts/business/business-rules.md | BR-78; Decision Table V (lines 359-367) | implementation constraint (read-only context, cap, oldest-end truncation, =0 disable) |
| context-manifest.md | Allowed Paths | read/write boundary |
| ci-gates.md | Required Gates table | PR gate names (no new workflow) |

## File-Level Plan

| path or glob | action | notes |
|---|---|---|
| app/backend/services/context_prompts.py | edit (add function) | Append `build_context_prefix(...)` near other block builders; leaf module — no `config` import; window/max_chars are parameters |
| app/backend/utils/translation_helpers.py | edit | Add `from app.backend import config`; wire prefix into `translate_merged_paragraphs()` per-segment loop (≈ lines 166-185); call `build_context_prefix` from `context_prompts` |
| tests/test_context_window_segments.py | create | 11 functions per test-plan.md mapping |
| app/backend/config.py | no change | constants already defined at lines 104-105; do not edit |
| app/backend/services/translation_service.py | no change | already calls `translate_blocks_batch` |
| app/backend/clients/ollama_client.py | no change (read-only) | `_call_ollama` is the mock boundary; do not alter prompt builders or `translate_once` signature |

## Implementation Sequence

1. IP-1: add `build_context_prefix()` to `context_prompts.py`; get the pure-function
   unit tests (AC-1, AC-2, AC-3 `_zero_n_returns_empty`, AC-5) green first.
2. IP-2: wire it into `translate_merged_paragraphs()` in `translation_helpers.py`
   using module-qualified `config.CONTEXT_WINDOW_SEGMENTS` / `config.CONTEXT_MAX_CHARS`.
3. IP-3: write the wiring tests (AC-1 wiring, AC-3 wiring, AC-4) and the AC-6
   data-boundary positive grep; confirm `_call_ollama`-boundary tests pass.
4. IP-4: run the test ladder (below) and `tests/test_dead_references.py`.

## Contract Updates

- API: none
- CSS/UI: none
- Env: none
- Data shape: none
- Business logic: BR-78 + Decision Table V already authored in
  `contracts/business/business-rules.md` (tasks.yml 2.5 done). Implementation
  must conform; do not re-edit the contract.
- CI/CD: none

## Test Execution Plan

Required phases (floor): `collect`, `targeted`, `changed-area`. Add `contract`
(business-rule affected) per test-plan.md ladder. Generate evidence with
`cdd-kit test run`; full ladder lives in test-plan.md / references/sdd-tdd-policy.md.

| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_context_window_segments.py::test_build_context_prefix_includes_n_preceding | prefix contains up to N predecessors |
| AC-1 | tests/test_context_window_segments.py::test_build_context_prefix_capped_at_n | at most N predecessors included |
| AC-1 (wiring) | tests/test_context_window_segments.py::test_prompt_payload_contains_neighbor_text_at_call_boundary | captured `payload["prompt"]` for "Segment B." contains literal "Segment A." |
| AC-2 | tests/test_context_window_segments.py::test_build_context_prefix_truncated_to_max_chars | combined context length ≤ CONTEXT_MAX_CHARS |
| AC-2 | tests/test_context_window_segments.py::test_build_context_prefix_truncates_from_oldest_end | newest predecessor text retained; oldest trimmed |
| AC-3 | tests/test_context_window_segments.py::test_build_context_prefix_zero_n_returns_empty | returns "" |
| AC-3 (wiring) | tests/test_context_window_segments.py::test_prompt_payload_has_no_context_prefix_when_n_zero | prompt has no "Context (do not translate):"; identical to pre-change |
| AC-4 | tests/test_context_window_segments.py::test_context_prefix_header_not_present_in_translated_output | returned translation excludes the context header |
| AC-5 | tests/test_context_window_segments.py::test_build_context_prefix_empty_at_first_segment | first segment → "" , no error |
| AC-5 | tests/test_context_window_segments.py::test_build_context_prefix_uses_available_neighbors_at_last_segment | uses only available predecessors |
| AC-6 | tests/test_context_window_segments.py::test_context_constants_are_imported_in_pipeline | positive grep: `CONTEXT_WINDOW_SEGMENTS` referenced in `app/` outside `config.py` (returncode 0) |

## Handoff Constraints

- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved.
- Anti-patterns to avoid (CLAUDE.md learnings): (a) tautological call-wiring — do
  NOT mock `translate_once`/`translate_batch`/`translate_blocks_batch`; mock only
  `_call_ollama` on a real `OllamaClient`. (b) Wiring tests must be SELECTION
  tests — assert the specific literal neighbor text ("Segment A.") appears, not a
  count. (c) For `_call_ollama` patching use `patch.object(client_instance, "_call_ollama", ...)`
  (instance-level, collection-safe), per the `mock.patch` target learning. (d)
  AC-6/dead-reference grep tests derive repo root via `Path(__file__).parent.parent`,
  never hardcoded paths.
- Backward-compat guarantee (AC-3): with `CONTEXT_WINDOW_SEGMENTS = 0`,
  `build_context_prefix` returns `""` and `translate_merged_paragraphs` passes the
  unmodified `text` to `translate_once`, so the prompt is byte-identical to today.

## Known Risks

- Tier/risk mismatch across artifacts: change-classification.md and tasks.yml say
  Tier 2 / medium; test-plan.md frontmatter says tier 0 / low. Individual test
  families being Tier 0 is consistent with a Tier-2 change; treat the change as
  Tier 2 for the gate. Flag to the orchestrator if the gate enforces a different
  floor.
- AC-4 read-only guarantee is enforced by the `"Context (do not translate):"`
  instruction in the prompt plus the fact that the prefix is never mapped to an
  output segment — it is not a hard parse-time guarantee. This matches BR-78's
  intent and the test-strategist's prepend-into-prompt design (context becomes
  part of the prompt string sent to `_call_ollama`). The default behavior of
  every translation changes (ships with N=2), per classification rationale.
- Monkeypatch reliability: tests must patch the names where the code reads them.
  Plan specifies module-qualified `config.CONTEXT_WINDOW_SEGMENTS` access so
  `monkeypatch.setattr(config, "CONTEXT_WINDOW_SEGMENTS", 0)` is honored at call
  time; if the engineer instead imports the names at module top, the n=0 wiring
  test must patch them in the `translation_helpers` namespace.
- `.cdd/code-map.yml` was not consulted for this plan (paths were located directly
  from the manifest's allowed source files, all read within budget); precise line
  ranges above came from direct reads, not the map.
