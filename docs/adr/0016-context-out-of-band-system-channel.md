# ADR 0016: Sliding-context travels out-of-band via the LLM client system channel

## Status
proposed

## Context
BR-78's sliding-context window prepends the preceding source segments onto the
segment being translated, in the same user message that the client wraps with
"Translate the following text… Output only the translation". This puts two
conflicting instructions ("translate this" vs the inline "Context (do not
translate):") in one user payload. Cloud providers (PANJIT/DeepSeek) resolve the
conflict by translating everything, so segment N's output bleeds the verbatim
text of N-1/N-2 (reproduced on the 8D PDF job). The `translate_once` Protocol
(`base_llm_client.py`) is a shared boundary every processor depends on, and the
OpenAI-compatible client currently sends a single `role:"user"` message with no
system channel. A future engineer "simplifying" the fix by re-gluing context onto
the user text would silently reintroduce the bleed.

## Decision
Context is carried **out-of-band**, never inside the translatable user payload.
`translate_once` gains an additive `system_context: Optional[str] = None`
parameter across the Protocol and both clients; the OpenAI client emits a leading
`role:"system"` message and the Ollama client merges it into the `system` field.
`translate_merged_paragraphs` passes `build_context_prefix`'s output through that
parameter. The to-translate user payload for segment N therefore contains only
segment N. Chosen over deleting context outright because it preserves BR-78's
coherence intent and builds the exact system-channel seam the step-2 doc-summary
work reuses; deletion is retained only as a `system_context=None` fallback.

## Consequences
- Invariant future changes must not reverse: **surrounding context never sits in
  the translatable user message**; it travels via the system channel. Re-gluing
  `prefix + text` reintroduces the bleed.
- The additive kwarg breaks any test double reproducing a fixed positional
  `translate_once`; such doubles reached via the paragraph path are updated in the
  same change (`MagicMock(spec=...)` doubles are unaffected).
- BR-78 and Table V are reworded; `CONTEXT_WINDOW_SEGMENTS`/`CONTEXT_MAX_CHARS`
  values are unchanged. Behavior-only — no schema/migration; `CONTEXT_WINDOW_SEGMENTS=0`
  remains the kill-switch.
