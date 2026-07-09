# Change Request

## Original Request

User (verbatim, Chinese): 「合併, 然後修小bug」— approving the merge of
`doc-context-sampling-fix` and directing that the "small bug" found during its
live verification be fixed next.

The defect was discovered while investigating why the newly-working BR-109
document-context summary did not improve certain header-cell translations in job
`53676512617243fcbbc60dbac0201102`. Intercepting the real pipeline's outgoing
`/v1/chat/completions` POST bodies showed the summary was present in the system
message — but the translation profile's own base system prompt was not.

Restated in the three required elements:

1. **Affected surface** — `OpenAICompatibleClient.__init__` in
   `app/backend/clients/openai_compatible_client.py`, and the cloud-client
   construction plus the `base_system_prompt = client.system_prompt` read in
   `app/backend/processors/orchestrator.py`.
2. **Desired behavior** — the cloud client receives the caller's `system_prompt`,
   exactly as `OllamaClient` already does, so the profile's base prompt feeds
   `build_strategy` and reaches the model.
3. **Observable success criterion** — with `profile_id=semiconductor` and provider
   `panjit`, the system message in the outgoing `/v1/chat/completions` request
   contains the semiconductor profile's role-declaration text, asserted on the
   captured request payload (never on `client.system_prompt`); local Ollama
   behavior is unchanged; and BR-109's `Document context:` preamble still composes
   *after* the base prompt rather than replacing it.

## Business / User Goal

On every cloud translation the model is missing the profile's role declaration
and its terminology/register guidance. For the `semiconductor` profile that means
instructions like "You are a professional semiconductor translator for IC design,
packaging…" have never once reached PANJIT or DeepSeek. Domain-specific
terminology discipline — the entire point of choosing a profile — is silently
inert on the cloud path, which is the default path.

## Non-goals

- **Out of scope:** the xlsx table-batch phantom-column defect. `ws.max_column`
  is 257 against 47 real cells, so `table_serializer.parse()` can never match the
  demanded shape and always returns `None`, wasting one large LLM call per sheet
  before the BR-82 per-cell fallback. Deferred to the JSON structured-I/O change.
- **Out of scope:** the critique-loop call volume (each segment issues 1 translate
  + 3 critique calls). Observed, not investigated; separate follow-up.
- No change to BR-109's delivery mechanism (ADR-0016 system-channel routing), to
  `build_strategy`'s composition order, or to the scenario/few-shot blocks.
- No new environment variables or feature flags.
- No change to how `job_manager` resolves the profile.

## Constraints

- `OllamaClient.__init__` already accepts `system_prompt`; the fix must not change
  local-Ollama behavior in any way.
- BR-109 requires that the cloud client deliver `self.system_prompt` merged ahead
  of the per-segment BR-78 `system_context` on every `translate_once`. That
  delivery already works. This change only ensures the value being delivered is
  no longer empty at the base.
- `build_strategy(base_system_prompt=…)` composes base → scenario appendix →
  few-shot block → `Document context:` preamble. The preamble must remain last and
  must compose after the base prompt rather than replacing it.
- Acceptance must be asserted at the real boundary (the captured outgoing request
  payload), never on `client.system_prompt`. Asserting on that attribute is
  exactly the tautology that let the sibling BR-109 defect ship.

## Known Context

Evidence gathered from live source and a live pipeline interception:

- `OllamaClient.__init__` accepts `system_prompt`; `OpenAICompatibleClient.__init__`
  accepts only `base_url`, `api_key`, `model`, `provider_id`, `connect_timeout`,
  `read_timeout`, `verify_ssl`, `max_tokens`. Confirmed by `inspect.signature`.
- `OpenAICompatibleClient.system_prompt` is a class attribute defaulting to `""`.
- `orchestrator.py` constructs the cloud client without `system_prompt`, passes
  `system_prompt=system_prompt` only to the Ollama client, then reads
  `base_system_prompt = client.system_prompt` after `client` has been reassigned
  to the cloud client — yielding `""`.
- `job_manager.py:405` sources the value from
  `_get_translation_profile(group.profile_id).system_prompt`, so a real, non-empty
  prompt exists and is passed into `process_files`.
- Interception of the real pipeline's POST bodies confirmed the outgoing system
  message contains the scenario appendix, the few-shot block, and the
  `Document context:` line, but not the profile's role declaration.

This is the same family as the BR-109 defect closed in `doc-context-sampling-fix`:
there a write to `client.system_prompt` was silently discarded by a compatibility
stub; here the write never happens at all.

## Open Questions

- Should `OpenAICompatibleClient.__init__` gain a `system_prompt` keyword
  (mirroring `OllamaClient`), or should the orchestrator assign
  `client.system_prompt` after construction? The former matches the sibling class
  and is harder to forget; the latter touches one file. Decision belongs to the
  implementation plan, which must also check every other construction site of
  `OpenAICompatibleClient` (the provider fallback chain, the judge client, the
  provider health / test-translation endpoints) for impact.

## Requested Delivery Date / Priority

Priority: ahead of the JSON structured-I/O change (step 3 of the
translation-prompt realignment). It affects the quality of every cloud
translation, which is the default path.
