---
change-id: context-prefix-bleed-fix
schema-version: 0.1.0
last-changed: 2026-07-08
---

# Implementation Plan: context-prefix-bleed-fix

## Objective
Stop preceding-segment source text from bleeding into a segment's translation.
Route the BR-78 sliding-context window **out of the translatable user payload and
into the LLM client's system channel**: `translate_once` gains an additive optional
`system_context` kwarg, each client places it in the system message (OpenAI) /
`system` field (Ollama), `translate_merged_paragraphs` passes context via that kwarg
instead of gluing `prefix + text`, and `build_context_prefix` returns a raw
system-channel reference block (no user-glue framing). Bug-fix lane: RED repro before
fix, GREEN after, with the real 8D 3-point fixture. This is step 1 of a 3-step
prompt realignment; steps 2 (cloud doc-summary) and 3 (JSON I/O) are NOT in scope.

## Execution Scope

### In Scope
- Additive `system_context: Optional[str] = None` on the `LLMClient` Protocol and both
  client implementations (`openai_compatible_client`, `ollama_client`) — added AFTER
  `cancel_event`, default `None`.
- OpenAI client: prepend a leading `{"role":"system"}` message when `system_context` is set.
- Ollama client (parity, runtime-unused): merge `system_context` into the payload `system` field.
- `translate_merged_paragraphs`: stop concatenating the prefix onto `text`; pass the
  context via `system_context=`; preserve the short-token bypass.
- `build_context_prefix`: repurpose to return the reference-block content string for the
  system channel; drop the literal `"Context (do not translate):"` user-glue label.
- NEW RED/GREEN repro test `tests/test_context_prefix_bleed.py` (8D 3-point fixture).
- Update the test doubles / assertions the additive kwarg + new return shape break
  (see Required Changes IP-6..IP-9).

### Out of Scope (non-goals — do NOT do these)
- `_detect_document_context` cloud doc-summary enablement (change-request Non-goals; step 2).
- JSON structured translation I/O `{"text":…}`→`{"translation":…}` (step 3).
- Any Office (docx/pptx/xlsx) output-mode, judge, QE/COMET, or layout change.
- Threading context up through `pdf_processor` direct `translate_once` call sites
  (CER-001 pending / out of scope) — do NOT touch `tests/test_pdf_layout_table_fixes.py` fakes.
- Any `config.py` value change — `CONTEXT_WINDOW_SEGMENTS=2`, `CONTEXT_MAX_CHARS=300` retained.
- No opportunistic refactor of `translation_service.py` (in read scope only; no change).

## Required Changes
| id | area | required action | owner agent |
|---|---|---|---|
| IP-1 | client protocol | Add `system_context: Optional[str] = None` (after `cancel_event`) to `LLMClient.translate_once` (`base_llm_client.py`, method lines 23-39) + docstring note. | bug-fix-engineer |
| IP-2 | OpenAI client (live) | Thread `system_context` through `translate_once` (279-300) → `_post_completion` (168-221) → `_build_messages` (111-112); `_build_messages` prepends `{"role":"system","content":system_context}` before the user message when present, else unchanged single user message. | bug-fix-engineer |
| IP-3 | Ollama client (parity) | Add `system_context` to `translate_once` (442-477); after `_build_single_translate_payload` (398-411) merge context into the payload `system` field (combine with any existing `self.system_prompt`-derived value). See design pseudocode. | bug-fix-engineer |
| IP-4 | prompt assembly | `translate_merged_paragraphs` (`translation_helpers.py`, 133-196; hot lines 176-185): stop `prompted_text = prefix + text`; pass `text` unmodified as `text=` and the prefix as `system_context=(ctx or None)`, gated by the same short-token bypass (`len(text.strip()) > 4`). `on_segment_done(text, translated)` already records raw segment — leave. | bug-fix-engineer |
| IP-5 | BR-78 context builder | `build_context_prefix` (`context_prompts.py`, 262-297): return the reference-block content string for the system channel (reworded label, e.g. "Previous segments — reference only, do NOT translate or repeat:\n<segs>"), WITHOUT the `"Context (do not translate):"` user-glue framing; still `""` when `n_context<=0` or `current_idx==0`; window/truncation logic unchanged. Exact new label per design.md "What `build_context_prefix` returns after the fix". | bug-fix-engineer |
| IP-6 | repro test (NEW) | Author `tests/test_context_prefix_bleed.py` per test-plan node list (7 nodes). Fake `LLMClient` echoes/translates exactly the `text` it receives and records `system_context` separately; driven through `translate_merged_paragraphs` with the 8D fixture. RED pre-fix, GREEN post-fix. | bug-fix-engineer |
| IP-7 | existing regression | `tests/test_context_window_segments.py`: relocate payload assertions from `payload["prompt"]` to `payload["system"]` AND update every `"Context (do not translate):"` literal to the new label. See File-Level Plan for the exact node list — more than the 2 in test-plan's Test Update Contract. | bug-fix-engineer |
| IP-8 | protocol-sig test | `tests/test_llm_client_protocol.py::TestProtocolDefinition::test_protocol_method_signatures` (line 44): append `"system_context"` to the expected params list. NOTE: file is in test-strategist's manifest packet, NOT bug-fix-engineer's — see Known Risks. | test-strategist |
| IP-9 | new client-contract tests | Author `tests/test_openai_compatible_client.py::TestSystemContextChannel::test_system_context_prepended_as_leading_system_message` and `tests/test_ollama_client_dynamic_strategy.py::test_system_context_merged_into_system_field` (AC-4). Both files are in test-strategist's packet. | test-strategist |
| IP-10 | BR-78 contract | ALREADY APPLIED — `contracts/business/business-rules.md` BR-78 + Table V reworded, `schema-version: 0.25.1`. Verify only; do NOT re-edit. | contract-reviewer |

## Source Artifact Pointers
| source | relevant pointer | used for |
|---|---|---|
| design.md | "The `translate_once` seam (Decision (b))" — signature delta + per-client pseudocode | exact seam shape (IP-1..IP-4) |
| design.md | "What `build_context_prefix` returns after the fix" | new return shape (IP-5) |
| design.md | "Test doubles to update (same change)" | which fakes break / which do not |
| change-request.md | Root cause + Non-goals + Known Context (live path) | scope + non-goals |
| test-plan.md | "Acceptance Criteria → Test Mapping" (AC-1..AC-7) + "Test Update Contract" | test node ids to write/update |
| test-plan.md | "Test Execution Ladder" | bounded ladder phases |
| ci-gates.md | "Required Gates" table + "Merge Eligibility Decision" | verification commands / gate policy |
| contracts/business/business-rules.md | BR-78 + Table V (0.25.1, applied) | behavior contract (read-only) |
| docs/adr/0016-context-out-of-band-system-channel.md | protocol-boundary decision | rationale (read-only) |

## File-Level Plan
| path or glob | action | notes |
|---|---|---|
| app/backend/clients/base_llm_client.py | edit | `translate_once` Protocol sig (23-39): add `system_context: Optional[str] = None` after `cancel_event`; extend docstring. `Optional` already imported. |
| app/backend/clients/openai_compatible_client.py | edit | `_build_messages` (111-112): add optional `system_context` param, prepend system message when set. `_post_completion` (168): accept + forward `system_context` to `_build_messages` in the `messages` payload build. `translate_once` (279-300): accept `system_context`, pass to `_post_completion`. |
| app/backend/clients/ollama_client.py | edit | `translate_once` (442-477): accept `system_context`, merge into payload `system` after `_build_single_translate_payload`. Payload built via `_build_single_translate_payload`→`_build_payload`/`_build_no_system_payload` (398-411, 215-227) — merge into `payload["system"]` post-build, do not rewrite the branch logic. |
| app/backend/utils/translation_helpers.py | edit | `translate_merged_paragraphs` (176-185): replace prefix-glue with `system_context=(ctx or None)`; keep `len(text.strip()) > 4` bypass; `text=` is now the raw segment. |
| app/backend/services/context_prompts.py | edit | `build_context_prefix` (262-297): new return shape + docstring; drop `"Context (do not translate):"` framing; `""` guard unchanged; truncation `context[-max_chars:]` unchanged. |
| app/backend/services/translation_service.py | no change | In read scope for verification only (protocol-conformance test reads it). Do NOT edit. |
| app/backend/config.py | no change | `CONTEXT_WINDOW_SEGMENTS=2` (124), `CONTEXT_MAX_CHARS=300` (125) retained; read-only confirm. |
| contracts/business/business-rules.md | no change | BR-78 + Table V already reworded (0.25.1). Do NOT re-edit. |
| tests/test_context_prefix_bleed.py | create | NEW — 7 nodes per test-plan AC-1..AC-6 mapping; 8D 3-point fixture; torch-free. |
| tests/test_context_window_segments.py | edit | Update ALL header-literal + prompt-field assertions: `test_prompt_payload_contains_neighbor_text_at_call_boundary` (100,106 → assert neighbor in `payload["system"]`, target still in `payload["prompt"]`); `test_context_prefix_header_not_present_in_translated_output` (201); `test_build_context_prefix_includes_n_preceding` (62); `test_build_context_prefix_truncated_to_max_chars` (122-127, header/body-length logic); `test_build_context_prefix_uses_available_neighbors_at_last_segment` (222); `test_prompt_payload_has_no_context_prefix_when_n_zero` (174 → new-label absent). Keep pure-function `includes_n`/`capped_at_n`/`truncates_from_oldest_end`/`empty_at_first`/`zero_n_returns_empty` selection assertions (S0-absent / newest-present) intact. |
| tests/test_llm_client_protocol.py | edit | Line 44: append `"system_context"` to expected params list (IP-8; test-strategist packet). |
| tests/test_openai_compatible_client.py | edit | Add `TestSystemContextChannel` (IP-9; test-strategist packet). Existing classes stay green. |
| tests/test_ollama_client_dynamic_strategy.py | edit | Add `test_system_context_merged_into_system_field` (IP-9; test-strategist packet). Existing 3 tests stay green. |

## Contract Updates
- API: none.
- CSS/UI: none.
- Env: none (`CONTEXT_WINDOW_SEGMENTS`/`CONTEXT_MAX_CHARS` values unchanged).
- Data shape: none.
- Business logic: `contracts/business/business-rules.md` BR-78 + Table V — ALREADY APPLIED (0.25.1); verify only, do not re-edit.
- CI/CD: none (ci-gates.md "New Workflow Changes: None"; existing `contract-and-fast-tests` auto-collects the new/edited tests).

## Test Execution Plan
| acceptance criterion | test file / command | expected signal |
|---|---|---|
| AC-1 | tests/test_context_prefix_bleed.py::test_build_context_prefix_returns_system_channel_block_no_user_glue | new-label block returned; no `"Context (do not translate):"` |
| AC-1 | tests/test_context_prefix_bleed.py::test_translate_merged_paragraphs_user_payload_excludes_neighbor_segments | `text=` handed to `translate_once` for seg N excludes verbatim seg N-1/N-2 |
| AC-2 | tests/test_context_prefix_bleed.py::test_fake_client_no_bleed_returns_only_target_segment_8d_fixture | fake echo-translator returns only seg N (no points 1+2 bleed) |
| AC-3 | tests/test_context_prefix_bleed.py::test_fake_client_no_bleed_returns_only_target_segment_8d_fixture | RED pre-fix / GREEN post-fix (same node, bug-fix repro==regression) |
| AC-4 | tests/test_context_prefix_bleed.py::test_neighbor_text_appears_only_in_system_context_never_in_translated_output | neighbor text only in captured `system_context`, never in output |
| AC-4 | tests/test_openai_compatible_client.py::TestSystemContextChannel::test_system_context_prepended_as_leading_system_message | leading `role:"system"` message present when `system_context` set |
| AC-4 | tests/test_ollama_client_dynamic_strategy.py::test_system_context_merged_into_system_field | context merged into payload `system` field |
| AC-5 | tests/test_context_prefix_bleed.py::test_br78_context_delivered_out_of_band_not_in_translatable_payload | BR-78 out-of-band assertion |
| AC-6 | tests/test_context_prefix_bleed.py::test_context_window_segments_and_max_chars_constants_unchanged | constants == 2 / 300 |
| AC-7 | tests/test_llm_client_protocol.py::TestProtocolDefinition::test_protocol_method_signatures | params list includes `system_context` |
| AC-7 | tests/test_context_window_segments.py | payload/header assertions relocated, all green |

Required ladder floor (test-plan "Test Execution Ladder"): `collect`, `targeted`,
`changed-area`, plus `contract` (business-rules touched — AC-5/AC-7). Generate evidence
with `cdd-kit test run --phase <p>`, scoped to the NEW/edited node-ids
(`tests/test_context_prefix_bleed.py`, edited `tests/test_context_window_segments.py`,
`tests/test_llm_client_protocol.py`, and the new client-contract nodes). Run under
`conda run -n translate-tool cdd-kit test run …` per CLAUDE.md (QE-adjacent collection
hard-errors on missing torch outside the env; the core repro file itself is torch-free).
Do not restate the full ladder — see test-plan.md / references/sdd-tdd-policy.md.

## Bug-Fix Lane TDD Sequence (bug-fix-engineer)
1. **RED**: write `tests/test_context_prefix_bleed.py` (8D 3-point fixture; fake client
   echoes the `text` it is asked to translate, captures `system_context` separately).
   On CURRENT code the neighbor points bleed into the target segment's `text=`/output →
   the no-bleed assertions FAIL. Record the failed run per ADR 0006 §6/§7.
2. **Implement** the `system_context` seam (IP-1..IP-5).
3. **GREEN**: re-run the repro node in the same phase → passes.
4. **Fix the additive-kwarg / return-shape breaks**: IP-7 (`test_context_window_segments.py`),
   IP-8 (`test_llm_client_protocol.py`), IP-9 (new client-contract tests). See Known Risks
   for the IP-8/IP-9 packet-boundary coordination.
5. **Ladder**: run `collect → targeted → changed-area → contract` under
   `conda run -n translate-tool cdd-kit test run … --phase <p>`, scoped to the new/edited
   node-ids.

### Bug-fix evidence requirement (ADR 0006 §6/§7)
`agent-log/bug-fix-engineer.yml` must carry a `bug-fix:` block whose `test-reproduced`
reproduction points at a genuinely FAILED pre-fix `cdd-kit test run`, and whose
reproduction/regression `command` equals that run's recorded command **minus runner-added
flags**. Recipe: `git stash`/restore pre-fix `context_prompts.py` + `translation_helpers.py`,
run ONLY the repro node via `cdd-kit test run --phase targeted` (captures the failed
run-dir), restore the fix, re-run that phase green.

### Constraints (repeat for the implementer)
- `system_context` is additive with default `None` — the ~15 existing positional
  `translate_once` call sites (pdf/pptx/docx/xlsx processors, translation_service critique,
  translation_verification, BatchTranslator) MUST stay untouched; only
  `translate_merged_paragraphs` passes the kwarg.
- No `config.py` value change; providers cloud-only (PANJIT/DeepSeek); Ollama edited for
  protocol parity only.
- No Office / API / UI / judge / QE / layout change.

## Handoff Constraints
- Implementation agents must not infer missing requirements from chat history.
- Do not re-copy full design, test strategy, CI policy, or contract prose into this plan; follow the source pointers above.
- If this plan omits a required file, behavior, contract, or test, stop and report `blocked`.
- Keep implementation within the file-level plan unless a Context Expansion Request is approved. CER-001 (`pdf_processor.py`) stays pending / out of scope — do not read or edit it.

## Known Risks
- **Packet boundary (IP-8/IP-9)**: `tests/test_llm_client_protocol.py`,
  `tests/test_openai_compatible_client.py`, `tests/test_ollama_client_dynamic_strategy.py`
  are in **test-strategist's** manifest Agent Work Packet, NOT bug-fix-engineer's. The
  additive-kwarg break makes `test_protocol_method_signatures` go RED once IP-1 lands, so
  the orchestrator must route IP-8/IP-9 through test-strategist (or expand bug-fix-engineer's
  packet) before bug-fix-engineer's `changed-area`/`full` phase can be green. Do not let a
  cross-packet file block bug-fix-engineer's targeted RED/GREEN — scope those phases to the
  repro node.
- **More header-literal tests than the Test Update Contract lists**: test-plan's Test Update
  Contract names only 2 nodes, but `test_context_window_segments.py` has 3 additional
  pure-function nodes asserting `"Context (do not translate):"` (lines 62, 122-127, 222) that
  the new return shape breaks. Grep the file for the literal and update ALL of them, plus the
  body-length math in `test_build_context_prefix_truncated_to_max_chars` (header length changes).
- **Ollama payload indirection**: the `system` field is built inside
  `_build_single_translate_payload`/`_build_payload`; the translategemma / `_build_no_system_payload`
  branch intentionally omits `system`. Merge `system_context` post-build and let
  `test_system_context_merged_into_system_field` pin the exact expectation; do not rewrite the
  branch logic. Ollama is runtime-unused (cloud-only) — parity only.
- **Provider residual bleed** (design Open Risks): system-vs-user separation depends on each
  provider honoring it; fallback is `system_context=None` from `translate_merged_paragraphs`
  (reduces to delete-the-prefix) and the existing `CONTEXT_WINDOW_SEGMENTS=0` kill-switch. No
  code change needed to exercise either.
- **Do-not-break list**: `test_context_prompt_i18n.py`, `test_fewshot_glossary.py`, and the
  existing classes in `test_openai_compatible_client.py` / `test_ollama_client_dynamic_strategy.py`
  reference neither the header literal nor the new kwarg (grep-confirmed) — they must stay green
  unmodified. `test_sentence_mode_consistency.py`'s positional `translate_once_side_effect`
  (line 154) is never invoked (stop_flag pre-set) so it does not break; `test_critique_loop_batching.py`
  / `test_translation_service_stage_snapshot.py` fakes flow through the critique path, not
  `translate_merged_paragraphs`, so they receive no `system_context` — verify by running them,
  do not edit.
