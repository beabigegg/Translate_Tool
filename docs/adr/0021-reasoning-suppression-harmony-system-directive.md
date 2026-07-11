# ADR 0021: gpt-oss reasoning suppression via a harmony system-channel directive (amends ADR-0016 composition ordering)

## Status
proposed

## Context
The PANJIT `gpt-oss:120b` endpoint runs a harmony/reasoning model. On translation
calls its hidden reasoning routinely exhausts `OPENAI_COMPLETION_MAX_TOKENS`
before emitting the final `content`, returning empty content
(`finish_reason='stop'`/`'length'`) that our client already treats as a failure —
producing dozens of "Empty content" / "unparseable JSON" fallbacks per real DOCX
run, and feeding the 27-minute Cloudflare-cut stalls (see ADR-0011). Verified this
session against the live endpoint: the OpenAI `reasoning_effort` / `reasoning:{}` /
`chat_template_kwargs` API params are IGNORED by PANJIT; the ONLY honored lever is a
harmony `Reasoning: <level>` directive placed in the SYSTEM message content
(probed: reasoning 453→94 tokens, latency 2.8→1.5s, valid output; real-run empty
fallbacks dozens→0). The one-shot document-outline summary (`complete()` →
`orchestrator._detect_document_context`) benefits from full reasoning and must keep
it. ADR-0016 established the invariant that the system channel carries all
out-of-band instruction and NOTHING leaks into the translatable user payload; this
directive must compose onto that channel without violating that invariant.

## Decision
Suppress hidden reasoning on every cloud TRANSLATION call by prepending a harmony
`Reasoning: <level>` directive to the SYSTEM message content, delivered strictly
out-of-band via the existing `system_context` composition — never concatenated into
`user_content`. `_post_completion` gains `reasoning: Optional[str]="low"`;
`translate_once`/`translate_json` (main translation, critique loop, JSON-fallback,
judge) inherit the `"low"` default, while `complete()` (the sole outline seam)
passes `reasoning=None` to preserve full reasoning. The level is a hardcoded config
constant `OPENAI_TRANSLATION_REASONING = "low"` (matching the truncation-guard
constant pattern), NOT an env var.

This AMENDS ADR-0016's system-message composition ordering: the leading system
message is now, in order, `Reasoning: <level>` → BR-110 base/scenario prompt +
"Document context: <summary>" preamble (`self.system_prompt`) → BR-78 neighbor
`system_context` — a single `role:"system"` message. ADR-0016's no-leak invariant
is unchanged and extended to the new prefix: the directive lives only in the system
channel and appears in no user-role message.

Chosen over the API params (verified inert on PANJIT) and over lowering
`max_tokens` (rejected — the user confirmed Cloudflare kills long generations
regardless, and a smaller cap truncates legitimate long output).

## Consequences
- Invariant future changes must not reverse: the `Reasoning:` directive travels in
  the SYSTEM channel ONLY; re-gluing it (or any system content) onto the user
  payload reintroduces the ADR-0016 bleed. Tests assert exact-equality on the
  outgoing system message AND directive-absence from every user-role message.
- The outline carve-out is load-bearing: a future change routing `complete()`
  through the `"low"` default would silently degrade summaries. `reasoning=None`
  on `complete()` is intentional, not an oversight.
- ADR-0016's no-leak / system-message-content tests need updating for the new
  leading prefix (this is expected, not a regression).
- Cross-references ADR-0011 (this removes the dominant trigger of the wall-clock
  stall) and ADR-0016 (composition ordering amended here). ADR-0016 stays
  `proposed`; on acceptance of this ADR its composition note should point here.
