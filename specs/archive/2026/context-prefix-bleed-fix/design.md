# Design: context-prefix-bleed-fix

## Summary
The sliding-context window (BR-78) currently glues the preceding source segments
onto the segment being translated, inside the same user message that the cloud
client wraps with "Translate the following text… Output only the translation".
Two conflicting instructions in one user payload make PANJIT/DeepSeek translate the
context too, so segment N's output bleeds points N-1/N-2. The fix moves context
**out of the translatable user payload and into the LLM client's system channel**:
`translate_once` gains an optional `system_context` param, each client places it in
the system message (OpenAI) / `system` field (Ollama), and `translate_merged_paragraphs`
hands `build_context_prefix`'s output through that param instead of concatenating it
onto the text. This both fixes the bleed and preserves BR-78's local-coherence intent,
and it builds the exact system-channel seam that step-2 (doc-summary on cloud) will reuse.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| `build_context_prefix` (BR-78) | `app/backend/services/context_prompts.py` | repurpose: return a system-channel **reference block** (reworded label), no longer a user-text prefix; window/truncation logic unchanged |
| `translate_merged_paragraphs` | `app/backend/utils/translation_helpers.py` | stop gluing `prefix + text`; pass context via new `system_context=` kwarg; short-token bypass preserved |
| `LLMClient` Protocol | `app/backend/clients/base_llm_client.py` | add optional `system_context: Optional[str] = None` to `translate_once` signature + docstring |
| OpenAI-compatible client (live) | `app/backend/clients/openai_compatible_client.py` | thread `system_context` into `_post_completion`; emit a leading `role:"system"` message when present (else unchanged single user message) |
| Ollama client (protocol parity, runtime-unused) | `app/backend/clients/ollama_client.py` | thread `system_context` into `translate_once`; merge into payload `system` field |
| BR-78 rule + Table V | `contracts/business/business-rules.md` | reword: context travels via system channel, never in the translatable payload |
| Config | `app/backend/config.py` | **no change** — `CONTEXT_WINDOW_SEGMENTS=2`, `CONTEXT_MAX_CHARS=300` retained (listed to confirm) |

## Key Decisions
- **Decision — (b) route context via the system channel.** The change-request's
  desired behavior, Constraints, and AC-4 all prefer retaining context out-of-band;
  the intended end-design unifies context into the system message; and step-2
  (doc-summary on cloud) needs this same seam anyway, so building it once now is not
  gold-plating — it is the foundation of the 3-step realignment. (b) is the option
  that fixes the bleed **without losing** the coherence value BR-78 provides: a
  system message is the standard chat-completions channel for non-translatable
  reference, which cloud models respect far more reliably than two conflicting
  instructions in one user message.
  → **Rejected: (a) delete the prefix entirely.** Smallest, zero-protocol-risk fix
  and it does stop the bleed, but it silently drops BR-78's context until step-2
  re-plumbs a *different* context (the doc-summary), leaving a coherence gap and
  requiring the system-channel seam to be built later regardless. Kept on the shelf
  as the trivial fallback (see Open Risks): if a provider still bleeds from the
  system channel, `translate_merged_paragraphs` passes `system_context=None`.

## The `translate_once` seam (Decision (b))
Signature delta (all three implementations + the Protocol), additive and back-compatible:
```
def translate_once(self, text, tgt, src_lang,
                   cancel_event=None,
                   system_context: Optional[str] = None) -> Tuple[bool, str]
```
`system_context=None` (default) reproduces today's behavior exactly, so the ~15
existing call sites (pdf/pptx/docx/xlsx processors, translation_service critique,
translation_verification, BatchTranslator) are untouched. Only
`translate_merged_paragraphs` passes it.

Per-client placement (≤10-line pseudocode):
- **OpenAI (live)** — `_post_completion`/`_build_messages` prepend a system message
  when context is present; user message keeps the unchanged "Translate the following…"
  wrapper:
  ```
  msgs = []
  if system_context: msgs.append({"role": "system", "content": system_context})
  msgs.append({"role": "user", "content": prompt})
  ```
  (The existing ignored `system_prompt: str = ""` compat-stub is unrelated and stays ignored.)
- **Ollama (parity, unused at runtime)** — merge into the `system` field:
  ```
  sys = "\n\n".join(p for p in (self.system_prompt, system_context) if p)
  payload = _build_payload(prompt); if sys: payload["system"] = sys
  ```

`translate_merged_paragraphs` change: replace `prompted_text = prefix + text` with
`ctx = build_context_prefix(...); ok, translated = client.translate_once(text, tgt, src_lang, system_context=(ctx or None))`.
The `on_segment_done(text, …)` snapshot already records the raw segment, so the
progress panel's source/draft length mismatch also resolves.

## Test doubles to update (same change — additive-kwarg breakage)
The new kwarg is passed **only** through `translate_merged_paragraphs`, so the break
surface is exactly the doubles reached via the paragraph path whose `translate_once`
uses a **fixed positional** signature (hand-written fakes or `side_effect` fns) —
**not** `MagicMock(spec=OllamaClient)` (tolerates extra kwargs):
- `tests/test_context_prefix_bleed.py` (NEW) — fake client must accept `system_context`.
- `tests/test_context_window_segments.py` — patches `_call_ollama`, so signature-safe,
  but its **payload assertions** move from `prompt` to the `system` field (content update).
- `tests/test_sentence_mode_consistency.py::translate_once_side_effect(text,t,s)` —
  update **only if** it flows through the paragraph path; otherwise leave.
- `tests/test_pdf_layout_table_fixes.py` fake `translate_once(self, prompt, tgt, src)` —
  **not** required now (PDF path calls `translate_once` directly, not via merged paragraphs; threading context there is CER-001 / step-2, out of scope).
- `MagicMock(spec=...)` doubles (`test_fewshot_glossary.py`, `test_orchestrator_judge.py`,
  `test_critique_loop_batching.py`) — no signature change needed.

## BR-78 wording consequence
BR-78 and Table V must be reworded: preceding segments are delivered as a **read-only
system-channel reference block** (not prepended to the translatable user text); the
to-translate user payload for segment N contains **only** segment N. Keep: window size
(`CONTEXT_WINDOW_SEGMENTS`), char cap (`CONTEXT_MAX_CHARS`), the "0 disables → identical
to pre-change" clause (now: no system context emitted), and "neighbor text never
appears in output". Drop the literal `"Context (do not translate):"` **prefix** wording.

## What `build_context_prefix` returns after the fix
Still exists (retains BR-78 ownership + window/truncation). Returns the reference-block
**content string** intended for the system channel (e.g. a reworded
"Previous segments — reference only, do NOT translate or repeat:\n<segs>"), **without**
the trailing user-glue framing; returns `""` when window ≤ 0 or on the first segment.

## Migration / Rollback
Behavior-only; no persisted state, schema, or migration. Rollback = revert the diff.
Operational kill-switch already exists: `CONTEXT_WINDOW_SEGMENTS=0` disables context
with no code change. Provider-specific residual-bleed fallback: pass `system_context=None`
from `translate_merged_paragraphs` (reduces to Decision (a) with zero protocol churn).

## Open Risks
- Raw **source-language** preceding segments are a weaker coherence signal than step-2's
  doc-summary and depend on each provider honoring system-vs-user separation. Mitigation:
  reference-only system phrasing + the `system_context=None` fallback above; the bleed
  repro test must assert the user payload excludes neighbors on the live (OpenAI) path.
- CER-001 (thread context up through `pdf_processor`) stays **pending / out of scope**;
  this change fixes only the `translate_merged_paragraphs` seam where the bleed occurs.
- No API / env / data-shape / CI contract change; only `contracts/business/business-rules.md`
  (BR-78) changes. ADR `docs/adr/0016-context-out-of-band-system-channel.md` records the
  protocol-boundary decision.
