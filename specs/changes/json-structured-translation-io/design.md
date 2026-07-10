# Design: json-structured-translation-io

## Summary
Both LLM translation paths (whole-table and body/paragraph) move from
line-shaped wire formats to JSON envelopes. Tables leave the pipe-grid
(position-counted, `num_rows × num_cols`) for a coordinate-carrying JSON cell
list that sends only content-bearing, non-numeric cells — killing the phantom
`9×257` shape-echo that fails on every real spreadsheet. The body path sends
`{"text": …}` and parses `{"translation": …}`. Neither payload may be wrapped
by the existing `translate_once` "Translate the following text… Output only the
translation" framing: the live probe proved that framing plus a JSON payload is
the exact "v1" shape that makes a reasoning model (`gpt-oss:120b`) spend its
budget in `reasoning_content` and return empty `content`. A new shared,
JSON-aware client seam carries the pinned prompt phrasing while still delivering
the scenario style, few-shot, doc-context preamble (BR-109) and profile prompt
(BR-110) through the system channel. Every failure mode falls back to today's
path (per-cell BR-82 for tables, plain-text `translate_once` for body), never
fails the job, and logs one INFO line through the `TranslateTool` `log(...)`
channel.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| Table wire format | `app/backend/utils/table_serializer.py` | replace pipe-grid `serialize()`/`parse()` with coordinate JSON build/parse; content-cells only |
| Shared JSON prompt phrasing | new small module (e.g. `app/backend/utils/json_translation.py`) | single source of the probe-validated `Return: {…}` phrasing + envelope builders/validators for both paths |
| Client seam | `ollama_client.py`, `openai_compatible_client.py` | add JSON-translation seam to BOTH concrete clients; retire per-client `_build_table_translate_prompt` mirroring in favor of the shared builder. `base_llm_client.py` (the 5-method Protocol) is deliberately NOT modified — see the Protocol-surface decision |
| Table cell-batch caller | `app/backend/services/translation_service.py` (L900–908) | call new seam; parse by `(r,c)`; fallback trigger + INFO log |
| Office/PDF table callers | `xlsx_processor.py`, `pptx_processor.py`, `docx_processor.py`, `pdf_processor.py` | send content-cells only (no phantom columns); consume coordinate parse; BR-82 fallback preserved |
| Body path | `app/backend/utils/translation_helpers.py` (`translate_merged_paragraphs`) | envelope post-BR-107 segments; parse `{"translation":…}`; fallback to plain `translate_once`; keep BR-108 guard on fallback |
| Contracts | `contracts/data/data-shape-contract.md` §Table Serialization Wire Format (+consumers table), `contracts/business/business-rules.md`, `contracts/env/env-contract.md` + `contracts/env/env.schema.json` + `.env.example.template` | wire-format rewrite, envelope/fallback rules, kill-switch flag (all three env files per Deployment Sync Policy) |

## Key Decisions
- **A new JSON-aware client seam, not `translate_once` and not `complete()`.**
  Rationale: `translate_once` prepends "Output only the translation" — with a
  JSON payload that is the proven empty-content shape (Finding 2); `complete()`
  sends no system prompt and would drop BR-109/BR-110/BR-78 context (wrong for
  translation). The new seam reuses `translate_once`'s system-channel merge
  (system_prompt ahead of system_context) but frames the user payload with the
  pinned JSON phrasing. → Rejected *reuse `translate_once` verbatim*: reintroduces
  the empty-content regression. → Rejected *restructure `translate_once`*: it is a
  shared boundary with many callers (ADR-0016); additive seam is lower-blast.
- **Prompt phrasing lives in ONE shared builder, pinned by test.** It is now a
  contract-relevant artifact. The pinning test (cannot hit the live endpoint in
  CI) must assert the built user payload (a) contains the validated `Return:
  {"translation": …}` framing, (b) does NOT contain the known-bad `Reply ONLY
  with JSON` / `Output a JSON object with a single key` phrasings, and (c) is NOT
  re-wrapped by the `translate_once` "Output only the translation" framing.
  → Rejected *mirror the phrasing in each client* (today's BR-80 pattern): drift
  risk; a single source is strictly safer.
- **Protocol surface: keep the new seam OFF the 5-method `LLMClient` Protocol
  (option b), consistent with the `complete()` precedent.** `base_llm_client.py`
  defines exactly five methods and `tests/test_llm_client_protocol.py` pins that
  (`test_protocol_defines_five_methods` asserts `len(methods) == 5`;
  `test_protocol_method_signatures` matches "design.md table"). BR-109's
  `complete()` seam was deliberately kept off the Protocol for exactly this
  reason; adding a sixth method would force both pinned tests to change and expand
  the design.md signature table. Enforcement that both concrete clients implement
  the seam (which the structural Protocol no longer provides) comes from a
  targeted unit test asserting `OllamaClient` and `OpenAICompatibleClient` each
  expose the seam with the correct signature, plus the four integration paths that
  exercise it end-to-end. `complete()` being off-Protocol is a pre-existing,
  runtime-safe inconsistency; leaving it is in scope-preserving and consistent —
  do NOT "fix" it here. → Rejected *(a) add the seam to the Protocol*: churns the
  two pinned tests, requires a new 6-method design.md signature table, and turns
  `complete()`'s off-Protocol status into a live inconsistency rather than a
  documented one, for no runtime benefit (both clients are concrete and directly
  constructed).
- **Do NOT rely on native JSON mode.** `response_format` (`json_object` /
  `json_schema`) is accepted but inert on PANJIT (Finding 3). The pinned prompt
  phrasing is the sole mechanism; `response_format` may be sent best-effort but
  MUST NOT be depended on. → Rejected *provider JSON mode as the guarantee*:
  silently no-ops on the primary provider.
- **Coordinate JSON, content-cells only.** Each sent cell carries explicit
  `(row, col)` and its source text; numeric (BR-68) and empty cells are NOT sent
  (already partitioned out before serialization). Parsing remaps by `(r,c)`, so
  grid-shape/position counting disappears and the phantom-column defect cannot
  recur. → Rejected *keep positional grid, just drop phantom columns*: still
  couples correctness to exact shape echo.
- **Fallback trigger set (shared vs per-path).** Shared, format-level validator:
  empty `content` (already surfaces as `ok=False` at the client seam),
  unparseable JSON, schema-invalid JSON (missing key/wrong type; table: missing
  or out-of-bounds `(r,c)`, or a sent coordinate absent from the reply). Per-path
  logic: the **echoed-source** trigger (Finding 4 — schema-valid ≠ translated) at
  the correct granularity — body: `translation == source`; table: the WHOLE grid
  unchanged (a single unchanged cell is legitimate for proper nouns/numbers and
  MUST NOT trigger) — plus the fallback action and the INFO `log(...)` line.
- **Keep BR-108 `is_meta_refusal`; do not retire it.** Finding 4 argues for a
  content-level guard regardless of the envelope; it moves to defend the
  plain-text fallback reply. Also avoids the `business-rules.md` absence-test
  retirement hazard. → Rejected *retire BR-108*: removes the only guard on the
  fallback reply and risks the zero-reference regression tests.
- **One kill-switch flag `JSON_STRUCTURED_TRANSLATION_ENABLED`, default `true`.**
  The built-in fallback covers *malformed* JSON but NOT a systemic quality
  regression on *well-formed* JSON on this system-wide default path; a flag is the
  only instant, redeploy-free revert to the legacy pipe-grid/plain-text pipeline.
  Because it is read from `os.environ` in `config.py`, the Deployment Sync Policy
  requires a matching row in ALL THREE of `contracts/env/env-contract.md`,
  `.env.example.template`, and `contracts/env/env.schema.json` in this change.
  The gate's tier-floor may trip on "flag"/"rollback"; use `tier-floor-override`
  with this rationale — a gate concern, not a reason to drop the flag.

## No split (conditional-split exit NOT exercised)
Finding 5 (behavior differs across routed models) is per-model, not per-path:
both paths use the same two clients and the same new seam, and per-model
divergence is absorbed uniformly by the pinned phrasing + universal fallback, not
by splitting. Consumer verification is bounded to the seven enumerated files.
Coupling (one shared fallback invariant, one seam, one validator) is real, so the
change stays atomic.

## Migration / Rollback
No data migration, no DDL — this is a wire-format and prompt change only.
Old and new formats never coexist on the wire: a single request is either JSON
(flag ON) or legacy (flag OFF / fallback). All seven consumers plus both prompt
builders change together (AC-7); the shared serializer is the sole implementation
so no consumer can be left on the old grid — verify by grepping the five
`serialize()`/`parse()` call sites before marking done. Rollback is the flag set
OFF (byte-for-byte legacy behavior) or, per-request, the automatic
never-fail fallback. Test doubles that mirror the client signature
(`_StubTableClient` in `tests/test_pdf_layout_table_fixes.py`, fixed-arg fakes)
must gain the new seam in this change or integration tests break. See ADR-0017
(supersedes ADR-0006's pipe-grid decision).

## Open Risks
- **Echoed-source granularity is subtle.** Too aggressive on tables (any single
  unchanged cell) would fall back on legitimate proper-noun/number cells and
  throw away good whole-table context. The whole-grid-unchanged rule must be
  asserted at the captured boundary, not on internal attributes.
- **Per-model non-uniformity (Finding 5) is only empirically bounded.** The
  pinned phrasing was validated on `gpt-oss:120b`, `deepseek-chat`, and the
  `long_doc` MLX model; a future routed model could need different framing. The
  universal fallback caps the blast radius but a silent quality dip on
  well-formed JSON is only caught by the kill-switch, not by tests.
- **`data-shape-contract.md` §Table Serialization Wire Format has no consumers
  table today (AC-8 adds one).** Until it lands, grep is the only orphan defense;
  `docx_processor.py` was already invisible to both contract and classifier.
- **`.cdd/code-map.yml` currency not independently reverified here**; line
  numbers cited (e.g. `translation_service.py` L900–908) were read from live
  source, but the planner must re-verify every seam before wiring.
