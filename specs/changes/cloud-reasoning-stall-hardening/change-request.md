# Change Request

## Original Request

Harden cloud (PANJIT `gpt-oss:120b`) translation reliability and quality via four
coordinated fixes, all empirically validated this session against the real PANJIT
endpoint:

1. **Reasoning suppression for translation (keep for outline).** Surface:
   `app/backend/clients/openai_compatible_client.py`. Suppress gpt-oss hidden
   reasoning on ALL translation calls; KEEP it on the one-shot document-outline
   summary. Success: on a real Chinese→Vietnamese DOCX, the
   `Empty content (finish_reason='stop')` / `unparseable JSON` fallback log lines
   drop from dozens to ~0, while `_detect_document_context` still returns a valid
   summary. VERIFIED: the PANJIT endpoint IGNORES the OpenAI `reasoning_effort` /
   `reasoning:{}` / `chat_template_kwargs` API params; the ONLY honored lever is a
   harmony `Reasoning: low` directive prepended to the SYSTEM message (probed:
   reasoning 453→94 tokens, latency 2.8→1.5s, valid output). Drafted + verified in
   the working tree: `_post_completion` gained `reasoning: Optional[str]="low"`
   that prepends `f"Reasoning: {reasoning}"` to `system_context`; `complete()`
   (sole outline seam) passes `reasoning=None`. `translate_once`/`translate_json`
   inherit "low" so main translation, the critique loop, the JSON-fallback, and
   the judge all get reasoning off. Captured-payload check confirmed. MUST preserve
   the BR-109 / ADR-0016 invariant (directive in the SYSTEM channel, never
   concatenated into the user payload). Level = hardcoded config constant
   (`OPENAI_TRANSLATION_REASONING="low"`), NOT an env var. ADR-0016
   no-leak / system-message-content tests WILL need updating for the new prefix.

2. **Lower the cloud wall-clock ceiling below the Cloudflare timeout.** Surface:
   `app/backend/config.py` `OPENAI_TOTAL_TIMEOUT_SECONDS` (default 480). A stalled
   PANJIT call should abort in ~120s instead of 480s. ROOT CAUSE
   (faulthandler-confirmed on a real 27-minute hang): Cloudflare closes
   long-running requests → socket goes CLOSE-WAIT → our client blocks in an SSL
   read (`_run_bounded_post` worker at `_post_completion`) until the ceiling. The
   BR-100 machinery already works; only the default value changes. Legit calls
   complete in 3–16s (probed), so ~120s keeps ample headroom.

3. **Bound `embed()`.** Surface: `openai_compatible_client.py` `embed()` calls
   `self._session.post` directly with NO `_run_bounded_post` wrapper, so the
   terminology/embedding path can hang indefinitely on the same Cloudflare
   dribble/half-close. Route it through the wall-clock bound so it degrades to `[]`
   within the ceiling. Structurally identical latent hang to (2), not yet observed
   live.

4. **Reduce critique-loop cost.** Surface: `translation_service.py` critique loop
   (`CRITIQUE_LOOP_ENABLED`, `translate_texts` ~L441, `_batched_critique_adopt`).
   Even with body translations fully cache-hit, the loop still issues live
   `translate_once` calls per segment (the observed post-body stall was IN this
   loop). Reasoning-off from (1) already cuts per-call cost; this item further
   reduces the loop's cost/exposure. Options (define in design): gate it, cap
   rounds, or skip segments whose base translation was a cache hit. MUST NOT
   silently degrade translation quality below current behavior; prefer a
   bounded/opt-out lever over unconditional removal.

Cross-cutting: cloud-provider (PANJIT / OpenAI-compatible) behavior only; the
local Ollama path is `role=layout_assist_only` and NOT used for translation. Live
PANJIT probing is authorized. The drafted reasoning edit is already in the working
tree on branch `cloud-reasoning-stall-hardening` and is the validated reference
for item (1).

## Business / User Goal

Standing goal: correct, never-dropped translation output (品質 100% 正確且不會漏翻).
Today the cloud path frequently emits empty/garbage content that falls back to
plain-text, and can stall for 8–27 minutes on a single Cloudflare-cut request,
effectively hanging a whole document (all output lost until the ceiling fires).

## Non-goals

- No change to the local Ollama translation path (it is not used for translation).
- No enlarging of `OPENAI_COMPLETION_MAX_TOKENS` (user confirmed Cloudflare's
  timeout protection kills long generations even when gpt-oss could accept more).
- No new provider, no model swap, no UI change.

## Constraints

- Preserve BR-109 / ADR-0016 (system-channel delivery; nothing leaks into the
  translatable user payload).
- Reasoning level is a hardcoded config constant, not an env var.
- Critique change must not silently lower translation quality.

## Known Context

Empirical evidence gathered this session (probes + faulthandler stacks + real
Chinese→Vietnamese DOCX runs against live PANJIT). The reasoning-off reference
edit is in the working tree.

## Open Questions

- Exact ceiling value (~120s proposed; confirm vs Cloudflare's actual cutoff).
- Item (4) mechanism: gate vs cap vs cache-hit skip.

## Requested Delivery Date / Priority

High — directly serves the standing no-drop / correctness goal.
