# Change Request

## Original Request
Fix a translation-output bug: a segment's translation contains the text of its
**preceding** segments. Reproduced on a real cloud (PANJIT) job with the 8D PDF
`docs/TEST_DOC/CS2408-0021 信和達(歐朗) P6SMBJ18CA 本體破损 -onepage.pdf`:
translating the segment "3、此失效模式内部外检有发现…A…B…C" produced Vietnamese
output for points **1 + 2 + 3** (the customer-feedback point 1 and defect point 2
were translated too).

## Root cause (code-traced + reproduced)
`build_context_prefix` (BR-78, `app/backend/services/context_prompts.py`) prepends
the previous `CONTEXT_WINDOW_SEGMENTS` (=2) **raw source segments** as an inline
`"Context (do not translate):"` block, and `translate_merged_paragraphs`
(`app/backend/utils/translation_helpers.py`) glues that prefix onto the segment
BEFORE handing it to `client.translate_once`. The client wraps the whole thing as
`"Translate the following text… Output only the translation…\n\n<prefix+segment>"`.
So the prompt carries TWO conflicting instructions — the top-level "translate the
following text" vs the inline "do not translate" — and cloud models (PANJIT /
DeepSeek; Ollama is never used here) resolve it by translating everything,
including the context. The progress snapshot records `source = raw segment` (via
`on_segment_done(text, …)`, without the prefix), so the panel shows a short source
and a long draft.

Deterministic reproduction (no live LLM needed): calling `build_context_prefix`
with the real 8D segments and `CONTEXT_WINDOW_SEGMENTS=2` yields a `prompted_text`
whose translatable body contains points 1 and 2 verbatim.

## Desired behavior
The model must translate **only the target segment**. Any surrounding context must
NOT sit inside the translatable user text — move it to the **system channel**
(aligns with the intended design of unifying context into the system message) or
otherwise structurally separate it so the model cannot translate it.

## Success Criterion
For a sequence of segments, the user/message content actually handed to the LLM as
the **to-translate** payload for segment N contains ONLY segment N (not the raw
text of preceding segments). A fake client that "translates whatever it is asked to
translate" returns only segment N's translation (no bleed). Reproduced RED before
the fix, GREEN after, using the real 8D segments as the fixture.

## Non-goals (explicitly out of scope — separate later changes)
- Making the one-sentence document-context summary (`_detect_document_context`) run
  on cloud providers — it is currently skipped by the `_cloud_client is None` guard.
  Separate enhancement (step 2 of the realignment).
- JSON structured translation I/O (`{"text":…}`→`{"translation":…}`). Separate
  enhancement (step 3).
- Any change to Office (docx/pptx/xlsx) output modes, judge, QE, or layout.

## Constraints
- Behavior-changing bug-fix (bug-fix lane): reproduction RED before fix, GREEN after.
- Do not lose the *value* of context blindly — the fix should keep context available
  to the model as reference (system channel) rather than simply deleting it, unless
  the design decides deletion is the smallest safe fix.
- BR-78 (context-window rule) contract text must be updated to reflect that
  preceding segments are no longer injected into the translatable payload.

## Known Context
- Providers: PANJIT / DeepSeek only (cloud). Ollama never used.
- `CONTEXT_WINDOW_SEGMENTS=2`, `CONTEXT_MAX_CHARS=300`, `TRANSLATION_GRANULARITY="paragraph"` (config.py).
- Live path: `translate_texts`/pdf_processor → `translate_blocks_batch` →
  `translate_merged_paragraphs` (per-segment, with `build_context_prefix`) →
  `client.translate_once`. The `<<<SEG_N>>>` marker-merge is dead code.
- Reproduction fixture: the numbered points from the 8D PDF above.

## Requested Delivery Date / Priority
Step 1 of a 3-step translation-prompt realignment; do first (active output bug). Normal priority.
