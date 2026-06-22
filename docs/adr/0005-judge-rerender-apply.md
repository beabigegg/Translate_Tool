# ADR 0005: Judge re-render apply — deterministic per-block replay, async dispatch

## Status
proposed

## Context
p3-llm-judge adds an LLM-as-judge pass; on a 中/低 score the judge produces a re-translated
draft. The change-request now requires that, on explicit user confirm, the system re-renders the
document with that re-translated text and overwrites the job's output file (destructive, no backup).
Two questions have non-obvious, hard-to-reverse answers.

(1) How is the re-translated text materialized into the rendered document? The processors render
whole documents and translate via the LLM client; they have no block-patch seam, and re-running
translation with the judge feedback in the prompt is non-deterministic — it would NOT reproduce the
exact text the user saw and confirmed, and would double model cost.

(2) Should the apply endpoint be synchronous or asynchronous? Re-render runs the full processor
pipeline across N files and can exceed HTTP timeouts; the codebase already standardizes long work on
a background worker thread plus client polling (`useJobPolling`, `GET /jobs/{id}`).

## Decision
(1) Store the judge's accepted draft as a per-block map `{block_id: retranslated_text}` on the job
record, and re-render by replaying that map through a replacement seam the 5 processors consult before
each LLM call (block_id present → substitute, skip the call). No model is called during re-render, so
the output is deterministic and idempotent. The joined `judge.translated_text` remains display-only.

(2) `POST /jobs/{id}/judge/apply` is asynchronous: it flips the job to a transient `applying` state,
dispatches re-render on a daemon thread, returns 202, and the client polls `GET /jobs/{id}`. Re-render
rebuilds the output zip into a temp path and swaps `output_zip` only on success (fail-soft: the original
download survives any re-render error). The `download_url` is stable across apply.

## Consequences
- Re-render correctness depends on `block_id` stability between the judged pass and the apply pass; a
  processor that regenerates ids on re-parse silently mis-maps blocks. Id-set equality must be asserted
  before substitution, with fail-soft to the original on mismatch.
- Future engineers MUST NOT replace per-block replay with feedback-prompted re-translation: it breaks
  determinism, idempotency, and the "render exactly what the user confirmed" guarantee.
- The 50-job cap / 24h TTL can evict the original source before a late apply; apply must 409 when the
  source input is gone rather than re-rendering against missing input.
- Sync apply is intentionally rejected; reverting to sync reintroduces timeout risk on large jobs.
