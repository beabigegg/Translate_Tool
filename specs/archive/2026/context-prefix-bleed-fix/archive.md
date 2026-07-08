# Archive — context-prefix-bleed-fix

## Change Summary
Fixed a translation-output bug where a segment's translation contained the text of
its **preceding** segments. Root cause: `build_context_prefix` (BR-78) prepended the
previous `CONTEXT_WINDOW_SEGMENTS` (=2) raw source segments into the **translatable
user prompt** as an inline `"Context (do not translate):"` block; the client's
`"Translate the following text…"` wrapper then translated the context too, so cloud
providers (PANJIT/DeepSeek — the only providers used) leaked neighbor segments into
the output. Reproduced deterministically with the real 8D PDF
(`docs/TEST_DOC/CS2408-0021 …P6SMBJ18CA… .pdf`): the「3、」segment yielded points
1+2+3. Fix routes the preceding-segment context via the **system channel** instead of
the translatable payload. Step 1 of a 3-step translation-prompt realignment.

## Final Behavior
- `translate_once` gained an additive `system_context: Optional[str] = None` (after
  `cancel_event`). The OpenAI client prepends a `role:"system"` message when set; the
  Ollama client merges it into its payload `system` field. Default `None` preserves all
  ~15 existing call sites.
- `translate_merged_paragraphs` now passes the preceding-segments context via
  `system_context=`; the **user payload is only the target segment**.
- `build_context_prefix` returns a system-channel reference block with **no**
  "Context (do not translate):" user-glue label.
- Net effect: neighbor segments are provided to the model as reference but are never
  themselves translated or leaked into output. Config values unchanged
  (`CONTEXT_WINDOW_SEGMENTS=2`, `CONTEXT_MAX_CHARS=300`).

## Final Contracts Updated
- `contracts/business/business-rules.md` — BR-78 (`context-window-segment-prefix`) row +
  Decision Table V rows reworded to "delivered out-of-band via the system channel; never
  concatenated into the translatable user payload"; id/name unchanged;
  `schema-version` 0.25.0 → 0.25.1 (patch/fix).
- `contracts/CHANGELOG.md` — `[business 0.25.1]` entry.
- `docs/adr/0016-context-out-of-band-system-channel.md` — records the invariant
  "context never sits in the translatable user message."
- No api/env/data-shape/ci contract change.

## Final Tests Added / Updated
- `tests/test_context_prefix_bleed.py` (NEW) — RED-before/GREEN-after repro with the real
  8D 3-point fixture; a fake client echoes exactly the user `text` it is handed and records
  `system_context` separately; asserts seg3's output contains only seg3 and that seg1/seg2
  appear ONLY in the captured system_context (channel-selection, not counts).
- `tests/test_context_window_segments.py` — payload assertions moved prompt→system; literal
  "Context (do not translate):" asserts removed.
- `tests/test_llm_client_protocol.py` — `translate_once` param list updated (+`system_context`).
- `tests/test_openai_compatible_client.py` — new `TestSystemContextChannel` (leading system message).
- `tests/test_ollama_client_dynamic_strategy.py` — new system-field merge test.
- `tests/test_pdf_layout_table_fixes.py` — `_StubTableClient.translate_once` signature tolerance
  (CER-002; ignored kwargs, zero behavior change).
- Bounded ladder (collect/targeted/changed-area/contract) + full smoke all passed.

## Final CI/CD Gates
- `contract-and-fast-tests` (required) — `cdd-kit validate --contracts` + blanket `pytest tests/`
  auto-cover the new/edited tests + BR-78 edit. **Green on PR #23.**
- `full-regression` (informational) + all format/renderer gates — **green on PR #23.**
- No new workflow/job/secret. Rollback = single `git revert` or `CONTEXT_WINDOW_SEGMENTS=0`.

## Production Reality Findings
- **Design assumption disproved (CER-002):** design.md assumed "the PDF path calls
  `translate_once` directly, not via `translate_merged_paragraphs`." bug-fix-engineer found
  `_translate_pdf_to_pdf`'s body-text path DOES flow through `translate_merged_paragraphs`,
  so the additive kwarg broke `test_pdf_layout_table_fixes.py::_StubTableClient` (strict 3-arg
  `translate_once`). Fixed with signature-only tolerance (CER-002, approved). This is the
  CLAUDE.md "additive kwarg breaks test doubles" learning recurring again — grep for fakes.
- **The `<<<SEG_N>>>` marker-merge is dead code** — the live path is per-segment
  `translate_merged_paragraphs`, confirmed during diagnosis.
- qa-reviewer independently reverted the fix and confirmed 5/6 repro tests genuinely fail
  pre-fix (incl. all 3 channel-selection assertions), GREEN post-fix.

## Lessons Promoted to Standards
- **A (context-out-of-band invariant)** — do-not-promote-again: fully held by the contracts
  updated this change (`business-rules.md` BR-78 0.25.1 + Table V) and
  `docs/adr/0016-context-out-of-band-system-channel.md`. No CLAUDE.md line (would duplicate
  contract content).
- **B (additive-kwarg-breaks-test-doubles, now on `translate_once`)** — promote-to-guidance,
  FOLDED into the existing `cdd-kit:learnings` bullet (net 0 new bullets): extended the seam
  list with `LLMClient.translate_once` system_context, added the nuance "grep the WHOLE tests/
  tree — fakes hide in unexpected/'do-not-touch' files (e.g. `_StubTableClient` in
  `test_pdf_layout_table_fixes.py`, broken because the PDF path unexpectedly reaches the changed
  seam)", and appended `context-prefix-bleed-fix` to the recurrence list. No schema bump.
  Evidence: `agent-log/bug-fix-engineer.yml` + `context-manifest.md` CER-002 +
  `agent-log/qa-reviewer.yml` CER-002 adjudication + the changed test files.

## Follow-up Work
- **CER-001 (pending, out of scope):** `pdf_processor.py` has direct `translate_once` call
  sites that never received BR-78 context (before or after this fix). If step-2/step-3 want
  context on those sites, thread `system_context` up through `pdf_processor`.
- **Step 2 of the realignment:** make the one-sentence document-context summary
  (`_detect_document_context`) run on cloud providers (remove the `_cloud_client is None` skip).
- **Step 3 of the realignment:** JSON structured translation I/O (`{"text":…}`→`{"translation":…}`)
  + unify all context (style + summary) into the system channel.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active
project guidance.
