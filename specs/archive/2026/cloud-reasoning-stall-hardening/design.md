# Design: cloud-reasoning-stall-hardening

## Summary
Four coordinated hardening fixes on the cloud (PANJIT `gpt-oss:120b`) translation
path, all empirically validated this session (see `change-request.md` §Original
Request). Item 1 suppresses runaway hidden reasoning on translation calls via a
harmony `Reasoning: low` directive delivered out-of-band in the SYSTEM channel
(ADR-0021, amending ADR-0016), keeping full reasoning only for the outline seam.
Item 2 lowers the wall-clock ceiling below Cloudflare's cutoff. Item 3 brings the
embedding path under the same bound. Item 4 adds a bounded, default-off cost lever
to the critique loop. No new provider, API, model, or UI surface; behavior-only,
no schema or migration.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| `_post_completion` reasoning prefix | `app/backend/clients/openai_compatible_client.py` | Already in working tree: `reasoning="low"` param prepends `Reasoning: <level>` to `system_context`. Backend to source default from new config constant (see Item 1). |
| `complete()` outline carve-out | same file | Already in tree: passes `reasoning=None`. Documented invariant, no further change. |
| `embed()` bound | same file | REQUIRES-WIRING: route the `_session.post` (currently unbounded, L273) through `self._run_bounded_post` (CONFIRMED same class, L125); degrade to `[]` (existing `except` path). |
| config constants | `app/backend/config.py` | Add `OPENAI_TRANSLATION_REASONING="low"` (hardcoded, not env); lower `OPENAI_TOTAL_TIMEOUT_SECONDS` default 480→120. |
| critique-loop cost gate | `app/backend/services/translation_service.py` | Add default-off skip of Phase-1 base-cache-HIT segments in the critique pre-filter (L466-469), reusing the already-tracked `cached_keys` set (L280/316). |

## Key Decisions

### Item 1 — Reasoning suppression (system-channel, outline exempt)
Decided: harmony `Reasoning: low` directive in the SYSTEM message is the only lever
PANJIT honors → recorded as **ADR-0021 (NEW, amends ADR-0016 composition ordering)**
rather than an edit to ADR-0016, so the no-leak invariant and the new leading-prefix
ordering are both explicit and independently reviewable. The directive composes
ahead of the BR-110 base prompt + BR-78 neighbor context in ONE `role:"system"`
message and never enters `user_content` (BR-109/ADR-0016 preserved). Level is a
hardcoded constant, matching the truncation-guard pattern.
Rejected: OpenAI `reasoning_effort`/`reasoning:{}`/`chat_template_kwargs` API params
— verified inert on PANJIT (identical reasoning-token counts). Rejected: lowering
`max_tokens` — Cloudflare kills long generations regardless and it truncates valid
output (explicit non-goal).

### Item 2 — Lower wall-clock ceiling 480→120s
Decided: BR-100 machinery is unchanged; only the default value drops so a
Cloudflare-cut CLOSE-WAIT stall aborts in ~2 min instead of ~8. Legit calls probe
3–16s, leaving ~7x headroom over the slowest observed valid call; item 1 further
shrinks per-call cost so 120s does not risk the (longer-prompt) critique calls.
Rejected: keeping 480 (leaves the 8–27 min hang); an env-driven change only
(default is the operative value in production).
Note the calibration tension (see Open Risks): 120s now sits at/below the 300s read
timeout and equals the 120s connect timeout.

### Item 3 — Bound `embed()`
Decided: route `embed()` through the SAME wall-clock bound (`_run_bounded_post`) so
the terminology/embedding path cannot hang indefinitely on the identical Cloudflare
half-close; on ceiling expiry the existing `except → return []` degradation holds
(embedding is already non-fatal). `_run_bounded_post` raises `requests.Timeout`,
caught by embed's broad `except`.
Rejected: a separate/shorter embed-specific timeout — reusing the one bound keeps a
single liveness contract (ADR-0011) and avoids a second tunable.

### Item 4 — Critique-loop cost (PRIMARY design decision)
Decided: **(a) skip the critique loop for segments whose base translation was a
Phase-1 cache HIT, gated behind a NEW default-OFF config flag** (contract-reviewer
to author the BR + name the flag). Default off ⇒ current behavior is byte-identical,
so quality is NOT silently degraded; when an operator opts in, base-cache-hit
segments (already translated on a prior run) skip fresh live `translate_once`
critique calls — the exact calls where the post-body stall was observed. Reuses the
existing `cached_keys` set; stacks on the existing `:c` critique cache and on item
1's reasoning-off (the default-path stall fix). BR intent: "when the flag is
enabled, Phase-1 base-cache-hit segments are excluded from the critique loop;
default disabled; loop otherwise unchanged and still degrades to last valid draft."
Rejected: (b) cap rounds/segment-count — `CRITIQUE_MAX_ITERATIONS` already caps
rounds and any further cap lowers quality for EVERY segment (silent degradation).
Rejected: (c) disabling `CRITIQUE_LOOP_ENABLED` wholesale — that gate already
exists and removing the loop is the "unconditional removal" the user forbade.
Why default-off not default-on: a base-cache HIT stores the RAW pre-critique draft
(L417); if a prior run was interrupted before critique persisted to `:c`, an
unconditional skip would serve an un-critiqued draft — a real quality drop for that
edge case. Default-off makes the trade explicit and operator-owned.

## Migration / Rollback
Behavior-only; no schema, data, or API migration. Rollback per item is a constant
revert: `OPENAI_TOTAL_TIMEOUT_SECONDS` back to 480 (or set very high to disable the
ceiling); leave the item-4 flag off (its default) to fully retain current critique
behavior; `reasoning` can be neutralized by setting `OPENAI_TRANSLATION_REASONING`
to a passthrough/None-equivalent, though this reopens the empty-content fallbacks.
`embed()` bounding degrades to `[]` (already the non-fatal contract). No coordinated
deploy ordering required.

## Open Risks
- REQUIRES-VERIFICATION (planner/backend, no-shell caveat): confirm the reference
  edit's literal `"low"` default in `_post_completion` is re-sourced from the new
  `OPENAI_TRANSLATION_REASONING` constant (constant does not yet exist in config.py).
- REQUIRES-VERIFICATION: confirm `contracts/env/env-contract.md` +
  `.env.example.template` document `OPENAI_TOTAL_TIMEOUT_SECONDS` and sync the new
  default only if so (it IS env-overridable, L99).
- Ceiling calibration: 120s equals the 120s connect timeout and sits below the 300s
  read timeout, so a legitimate cold-start connect could theoretically brush the
  ceiling. Probed legit calls complete 3–16s, so practically safe; record if any
  slow-but-valid critique/cold-start call is later observed near the bound.
- Item-4 flag naming + BR text are contract-reviewer scope; this design fixes only
  the mechanism (cache-hit skip, default-off), not the identifier.
