# Change Request

## Original Request
Fix a translation-output bug where a **body (non-table) segment** that is trivial or
non-translatable causes the cloud model (PANJIT gpt-oss) to reply with a META/REFUSAL
response — e.g. "Could you please provide the text you'd like translated?" — and that
reply is written verbatim into the output document.

Reproduced today in the 8D PDF English run (task `42265c0b…`): an output block
"Could you please provide the text you'd like translated?" replaced a trivial segment
(an already-English label / lone token). The translation cache is empty (no
`~/.translate_tool/cache/translations.db`), so it is a **LIVE** model reply, not a
poisoned cache. It is **PRE-EXISTING** (the July-2 `translator.log` shows the same class
of reply "Please provide the text you would like translated" on a different doc/model,
before any recent change) and is **NOT** caused by `context-prefix-bleed-fix` (verified:
`translation_helpers.py:188` always sends the real segment as the user payload;
`openai_compatible_client._build_messages` always includes it).

## Root cause
Table cells already get a non-translatable passthrough (BR-68, `translation_service.py:887`
— `is_numeric` cells → `translation_status="passthrough"`, `translated_content=content`).
But **body segments** on the `translate_merged_paragraphs` → `client.translate_once` path
have **no** equivalent non-translatable passthrough, and there is **no output-side guard**
to reject/repair a model meta/refusal reply. So a trivial segment is sent to the LLM, the
LLM asks back, and the ask-back string is stored as the "translation."

## Desired behavior
- **(a) INPUT guard** — trivial / non-translatable body segments (pure numbers,
  punctuation-only, already-target-language, very short single tokens) are passed through
  untranslated (output = source) **without an LLM call**, mirroring the table BR-68
  passthrough.
- **(b) OUTPUT guard** — if a translation reply is detected as a meta/refusal ("provide
  the text…", a question-back, a language-detection/notes remark), fall back to the source
  text (or mark the segment failed) instead of writing the meta reply into the output.

## Success Criterion
- For a trivial segment, the LLM client is **NOT** called and the result equals the source.
- Given a fake client that returns a meta/refusal string, the pipeline writes the **source**
  (not the meta string) into results.
- Reproduced RED before / GREEN after with fakes, using the real 8D trivial segments as
  fixture; no live LLM needed.

## Non-goals
- The table-cell path (already has BR-68 numeric passthrough) — do not touch.
- Step-2 cloud doc-summary enhancement and step-3 JSON structured I/O (separate changes).
- Any change to Office (docx/pptx/xlsx) output modes, judge, QE, or layout.

## Constraints
- Behavior-changing bug-fix (bug-fix lane): reproduction RED before fix, GREEN after.
- Passthrough must be conservative — never drop or alter genuinely translatable content.
  Prefer under-passing-through (translate) over over-passing-through (skip real text).
- The meta/refusal detector must be precise (avoid false positives that suppress a real
  translation that happens to contain a question mark).

## Known Context
- Providers: PANJIT / DeepSeek (cloud) only; Ollama never used.
- Live body path: `translate_texts`/pdf_processor → `translate_blocks_batch` →
  `translate_merged_paragraphs` (`translation_helpers.py`) → `client.translate_once`.
- Existing precedent: table BR-68 numeric passthrough (`translation_service.py:887`), and a
  client-side short-token bypass referenced in `translation_helpers.py:182` comment.
- Reproduction fixture: trivial segments from the 8D PDF
  (`docs/TEST_DOC/CS2408-0021 …P6SMBJ18CA… .pdf`) — the lone page-number, an already-English
  label, punctuation-only — plus a fake client returning the ask-back string.

## Open Questions
- Whether the passthrough heuristic and the refusal-detector should live in
  `translate_merged_paragraphs`, `translation_service`, or a shared helper — for planner/design.
- Whether a new BR is warranted (mirroring BR-68 for the body path) or the existing
  passthrough rule can be extended.

## Requested Delivery Date / Priority
Standalone bug-fix; do BEFORE resuming steps 2/3 of the translation-prompt realignment. Normal priority.
