# Change Request

## Original Request

Make the one-sentence document-context summary run on cloud providers.

**Affected surface:** the document-context detection path in
`app/backend/processors/orchestrator.py` — specifically the
`_detect_document_context` call and its guard `... and _cloud_client is None`
(approx L556-589), which currently SKIPS the one-sentence summary whenever a
cloud client (PANJIT/DeepSeek) is the active translation client (the guard
assumes only local Ollama can run the summary).
`context_prompts._CONTEXT_DETECTION_PROMPTS` holds the summary prompt
("請用一句話描述這份文件的類型、所屬領域和主題").

**Desired behavior:** when translating via a cloud provider (PANJIT/DeepSeek),
generate the one-sentence document summary using the ACTIVE cloud translation
model/client (not requiring a local Ollama model), and inject that summary as
the document-context preamble into the translation system prompt (same
downstream wiring the local path already uses: `client.system_prompt` /
`build_strategy` → "Document context: <summary>"). Preserve the existing feature
flags (`CONTEXT_DETECTION_ENABLED` / `QWEN_CONTEXT_FLOW_ENABLED`) and the
translation-dedicated-client skip; only remove the hard `_cloud_client is None`
block so cloud runs also get the preamble. Do not change JSON I/O (that is a
separate later step / step 3 of the realignment).

**Observable success criterion:** on a cloud (PANJIT) run of a document, the log
shows the document-context summary being generated and injected (e.g. a
"Document context: ..." / doc-context log line), and the summary is present in
the system channel of subsequent translation calls — verifiable by re-running
the 8D PDF via PANJIT and seeing the one-sentence summary in the log/system
prompt where previously (task `7446112d79a64615a7c6444498c308b5`) it was absent.
Existing behavior on local Ollama and on translation-dedicated clients is
unchanged.

## Business / User Goal

This is Step 2 of the user's 3-step translation-prompt realignment (see memory
`translation-prompt-realignment`). The user's original dynamic-prompt design:
(1) scenario → document style; (2) an LLM summarizes the document type/domain in
ONE sentence; (3) that sentence = the 前情提要 (preamble) injected into every
subsequent translation prompt. Parts 1 and 3 already work on the LOCAL path, but
the summary (part 2) is skipped on cloud providers — and the user translates
exclusively via PANJIT/DeepSeek, so today the preamble never generates for them.
This change makes the preamble actually take effect on the user's real path.

## Non-goals

- JSON structured translation I/O (`{"text":…}`→`{"translation":…}`) — that is
  Step 3, a separate tracked change.
- Changing the summary prompt wording or the downstream injection wiring
  (system_prompt / build_strategy) — only the cloud generation path is new.
- Changing local-Ollama or translation-dedicated-client behavior.

## Constraints

- The active cloud translation client (PANJIT / DeepSeek, OpenAI-compatible) must
  be reused for the summary call; do NOT require a local Ollama model to be present.
- Preserve feature flags `CONTEXT_DETECTION_ENABLED` and `QWEN_CONTEXT_FLOW_ENABLED`.
- Preserve the translation-dedicated-client skip (`client._is_translation_dedicated()`).
- A failed / empty summary call must degrade gracefully (fall back to no preamble,
  i.e. current cloud behavior) — never abort the translation job.

## Known Context

- Prior step 1 (`context-prefix-bleed-fix`, merged) routed context via the system
  channel; step 2 builds on that wiring.
- `orchestrator._detect_document_context` currently takes an Ollama client.
- Providers in real use: PANJIT (default) + DeepSeek; Ollama is never used.

## Open Questions

None blocking — the active-cloud-client seam and injection point already exist;
this is a guard removal + client-parameterization.

## Requested Delivery Date / Priority

Next in sequence after step 1 (bleed) and the guard bug-fix, both merged.
