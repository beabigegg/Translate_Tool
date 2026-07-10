# ADR 0017: JSON-structured translation I/O via a dedicated system-channel seam

## Status
proposed (supersedes ADR-0006 "Markdown pipe-grid as the table-translation wire
format"). ADR-0006 is itself still `proposed`, never advanced to `accepted`;
on acceptance of this ADR its status should be set to `superseded` with a pointer
here. Until then it is a superseded-while-proposed decision — recorded, not
silently dropped.

## Context
Table and body translation used line-shaped wire formats: a positional Markdown
pipe-grid (ADR-0006) validated by exact `num_rows × num_cols` shape echo, and
free-text body replies guarded after the fact by the BR-108 `is_meta_refusal`
string classifier. On real spreadsheets `ws.max_column` reaches 257 phantom
columns against ~47 real cells, so the grid never round-trips and every sheet
burns one whole-table LLM call before per-cell fallback — losing row context that
demonstrably changes translations (`制作日期` → correct `Ngày tạo` only with row
neighbors). A live probe against the real PANJIT and DeepSeek endpoints
established four load-bearing facts: (1) a coordinate table envelope actually
fixes the context defect on both providers; (2) `gpt-oss:120b` is a reasoning
model — with the JSON instruction phrased `Reply ONLY with JSON` / `Output a JSON
object with a single key`, it spends its budget in `reasoning_content` and returns
empty `content`, while `Return: {"translation": <your translation>}` returns valid
JSON reliably; (3) `response_format` (`json_object`/`json_schema`) is accepted but
inert on PANJIT; (4) schema-valid is not translated — a well-formed
`{"translation": "制作日期"}` echo of the source passes parse+schema.

## Decision
Both paths translate via JSON envelopes. Tables carry a coordinate cell list of
content-bearing, non-numeric cells only (remapped by `(row, col)`, not by
position count); body sends `{"text": …}` and parses `{"translation": …}`.
The JSON payload travels through a NEW client seam implemented on BOTH concrete clients and deliberately kept OFF the five-method `LLMClient` Protocol (consistent with the `complete()` precedent; see design.md §Protocol surface), NOT
through `translate_once` (whose "Output only the translation" framing plus a JSON
payload is the proven empty-content shape) and NOT through `complete()` (which
carries no system prompt). The new seam reuses `translate_once`'s system-channel
merge so scenario style, few-shot, the BR-109 doc-context preamble and the BR-110
profile prompt still reach the model. The exact instruction phrasing lives in one
shared builder and is pinned by a test that also asserts the known-bad phrasings
are absent. Native JSON mode is not relied upon. Validation is parse + schema +
an echoed-source check (body: equals source; table: whole grid unchanged). Every
failure falls back to the legacy path, never fails the job, and logs one INFO
line via the `TranslateTool` `log(...)` channel. A single kill-switch flag
(default ON) reverts the whole system to the legacy pipeline without redeploy.

## Consequences
- **Invariants future changes must not reverse:** the JSON translation payload
  must never be wrapped by the `translate_once` translate-framing (reintroduces
  empty content on reasoning models); `response_format` must never be treated as
  the JSON guarantee (inert on PANJIT); the echoed-source trigger must never be
  dropped (untranslated but schema-valid replies would be accepted); the prompt
  phrasing must stay in the shared builder pinned by test.
- The additive seam breaks test doubles that mirror the client signature; they
  are updated in the same change (per the shared-seam lesson).
- ADR-0006's pipe-grid format is retired; the data-shape contract's wire-format
  section is rewritten and gains a consumers table naming all seven files.
- BR-108 is retained (defends the fallback reply), avoiding the absence-test
  retirement hazard. BR-107 and BR-68 passthrough are unchanged.
