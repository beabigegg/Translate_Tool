# Change Request

## Original Request

User (verbatim, Chinese): 「合併\n然後繼續下一步的JSON格式改善」

This is step 3 — the final step — of the user's translation-prompt realignment.
Their original design, stated across earlier sessions:

1. the user picks a scenario, which selects a document style;
2. an LLM summarizes the document's type / domain / topic in ONE sentence;
3. that sentence becomes the 前情提要 (preamble) injected into every subsequent
   translation prompt;
4. translation happens **via JSON** — source paragraph JSON in, translated
   paragraph JSON out.

Steps 1–3 of that design shipped as `context-prefix-bleed-fix`,
`cloud-doc-context-summary`, `doc-context-sampling-fix`, and
`cloud-base-system-prompt-drop`. This change delivers point 4.

Two scope decisions the user made explicitly when asked:

- **Both paths**, not one: the table path *and* the body/paragraph path.
- **Fallback to the existing path** when the model's JSON is unparseable or
  fails schema validation — never fail the job, and log the reason.

Restated in the three required elements:

1. **Affected surface** — the table wire format (`app/backend/utils/table_serializer.py`
   and its callers in `xlsx_processor.py` / `pptx_processor.py` / the PDF cell-batch
   path), and the body wire format (`translate_merged_paragraphs` in
   `app/backend/utils/translation_helpers.py` → `client.translate_once`).
2. **Desired behavior** — source goes out as JSON and the translation comes back as
   JSON, validated against a schema. The table format carries explicit cell
   coordinates and sends only cells that actually hold content. On unparseable or
   schema-invalid JSON, both paths fall back to today's behavior.
3. **Observable success criterion** — the same XLS whose sheets currently log
   `parse() returned None (expected 9×257)` completes its table batch without
   falling back; a body paragraph round-trips through JSON with schema validation;
   and when either path's JSON is deliberately corrupted the job still completes,
   with an INFO line stating the reason.

## Business / User Goal

Two concrete defects, both measured on real jobs:

**The table path never succeeds.** `table_serializer.serialize()` builds a
Markdown pipe-grid sized `ws.max_row × ws.max_column`, and `parse()` accepts the
reply only if it has exactly that many rows and exactly that many columns per row.
On the user's real spreadsheet `ws.max_column` is **257** — phantom columns — while
only **47** cells hold content. The model is asked to echo back a 9×257 grid, cannot,
and `parse()` returns `None` every time. Job `53676512617243fcbbc60dbac0201102`
logged `parse() returned None (expected 9×257)` and `(expected 16×257)`. Each sheet
therefore burns one large LLM call for nothing before the BR-82 per-cell fallback
does the real work. Whole-table context is lost on every sheet.

That lost context has a measured translation cost. A deterministic 5×-repeated live
trial against PANJIT showed `制作日期` renders as `Ngày sản xuất` ("manufacturing
date") under every prompt condition — with the scenario style, with the BR-109
document summary, and with the profile's base prompt. It is a document-header field
meaning "date prepared". A four-character cell translated in isolation lacks the row
context (`文件编号`, `版别`, `页数`, `制作日期` sitting together) that disambiguates it.
Restoring whole-table translation is the fix; no prompt preamble substitutes for it.

**The body path validates by string heuristics.** `translate_merged_paragraphs`
sends `"Translate the following text…"` and receives free text, then guards it after
the fact with the BR-108 `is_meta_refusal()` detector — a precise-but-fragile string
classifier for replies like "Could you please provide the text you'd like
translated?". A structured `{"translation": …}` envelope makes a malformed or meta
reply a *parse* failure rather than a *classification* problem.

## Non-goals

- **Out of scope:** the critique-loop call volume. Each segment currently issues
  1 translate + 3 critique calls; observed while intercepting payloads, not
  investigated here.
- **Out of scope:** the residual double LibreOffice conversion of `.xls` (the
  sampler converts, then `xlsx_processor` converts again). Carried over from
  `doc-context-sampling-fix`.
- BR-107 (body-segment passthrough) and BR-68 (numeric-cell passthrough) are
  unchanged: trivial and non-translatable segments still bypass the LLM entirely,
  before any JSON envelope is built.
- No change to BR-109's document-context delivery, BR-110's constructor parity,
  BR-78's system-channel neighbor context, or ADR-0016's routing.
- No new environment variables or feature flags unless the implementation plan
  proves one is needed for rollback; if so it must be recorded in the env contract.

## Constraints

- **Fallback is mandatory and must be to the existing path**, per the user's
  explicit choice: unparseable or schema-invalid JSON → per-cell BR-82 for tables,
  plain-text `translate_once` for body. The job never fails for this reason.
- **The fallback must be observable.** BR-109 (business-rules 0.29.0) requires that
  a skip or failure be visible at INFO through the job's `log(...)` callback — the
  channel that reaches `translator.log` via the `TranslateTool` logger. A
  `logging.getLogger(__name__)` call reaches no production handler and does not
  satisfy this.
- **Acceptance must be asserted at the real boundary**: the captured outgoing
  request payload and the real returned translations, never on internal attributes.
  Asserting on an attribute is the assignment-without-delivery tautology that let
  two defects ship in this subsystem already.
- The table wire format is a contract surface (`contracts/data/data-shape-contract.md`
  §Table Serialization Wire Format) with a named consumers table. Changing it
  requires updating that contract and every listed consumer in the same change.
- `table_serializer.py` is shared by the Ollama client, the OpenAI-compatible
  client, and the PDF `translation_service` cell-batch path. All three must be
  verified against live source before the format changes.

## Known Context

Evidence gathered from live source and real runs:

- `table_serializer.serialize()` fills a grid from `max(c.row)+1 × max(c.col)+1` and
  joins with `" | "`; `parse()` requires `len(pipe_lines) == num_rows` and
  `len(cells) == num_cols` per row, returning `None` on any mismatch.
- `xlsx_processor.py` builds `proxy_cells` from
  `range(ws.max_row) × range(ws.max_column)` — hence the phantom columns — then
  calls `client._build_table_translate_prompt(serialized, …)` and
  `client.translate_once(prompt, …)`, and on `grid is None` falls back to
  `translate_texts` per cell (BR-82).
- `[Excel] cells: 47` against `expected 9×257` and `expected 16×257` in
  `translator.log` for job `53676512617243fcbbc60dbac0201102`, run 2026-07-09.
  Both warnings are emitted without a job-id prefix.
- `translate_merged_paragraphs` (`translation_helpers.py`) calls
  `client.translate_once(text, tgt, src_lang, system_context=system_ctx)` once per
  segment, then applies `is_meta_refusal(translated, text)` (BR-108) and the BR-107
  `should_translate()` guard before it.
- `OpenAICompatibleClient.translate_once` wraps the payload in
  `"Translate the following text from {src} to {tgt}. Output only the translation,
  no explanations.\n\n{text}"` and merges `self.system_prompt` ahead of
  `system_context` into one leading system message.

## Live Provider Probe (run by main Claude before design; these are facts, not assumptions)

Probed directly against the real PANJIT and DeepSeek `/v1/chat/completions`
endpoints. All results below are reproduced verbatim from those runs.

**Finding 1 — the table JSON envelope actually fixes the motivating defect.**
Sending four header cells together with their `(r, c)` coordinates —
`文件编号`, `版别`, `制作日期`, `页数` — makes both providers translate `制作日期`
correctly:

| provider | isolated cell | table JSON with row neighbors |
|---|---|---|
| PANJIT `gpt-oss:120b` | `Ngày sản xuất` (manufacturing date) | **`Ngày tạo`** (date created) |
| DeepSeek `deepseek-chat` | `Ngày sản xuất` | **`Ngày tạo`** |

PANJIT returned byte-identical output on two consecutive runs. This confirms the
hypothesis in §Business Goal: the missing ingredient is row context, and no prompt
preamble substitutes for it.

**Finding 2 — `gpt-oss:120b` is a reasoning model, and the wrong JSON phrasing
makes it return an EMPTY translation.** Its reply carries `reasoning_content`
alongside `content`. With the instruction phrased as `Reply ONLY with JSON: …`
or `Output a JSON object with a single key …`, it spends its budget in
`reasoning_content` and returns `content == ""` with `finish_reason == "stop"`.
Rephrasing to `Return: {"translation": <your translation>}` yields valid JSON on
3 of 3 runs. A naive implementation would therefore fall back on **every single
call**, making this change a net loss.

**Finding 3 — `response_format` is accepted but inert on PANJIT.** Both
`{"type": "json_object"}` and `{"type": "json_schema", …}` return HTTP 200 and
change nothing; `content` is still empty under the bad phrasing. Native JSON mode
cannot be relied on for this provider.

**Finding 4 — schema-valid JSON is not the same as a translation.** Under the bad
phrasing DeepSeek returns `{"translation": "制作日期"}` — well-formed, schema-valid,
and completely untranslated. A validator that only checks parse-and-schema would
accept it. The fallback trigger must therefore also catch a reply whose
`translation` equals the source.

**Finding 5 — the `long_doc` model (`mlx-community/Qwen3.6-35B-A3B-4bit`) has no
`reasoning_content`** and returns JSON directly. Behavior is not uniform across the
models this product routes to.

## Open Questions

- Should the table JSON envelope be sent through `translate_once` (which prepends
  the "Translate the following text…" framing) or through a new dedicated seam that
  sends the JSON instruction unwrapped? The `complete()` seam added by BR-109 is
  system-prompt-free by design and therefore wrong for translation. `design.md` must
  decide and verify against live source.
- Does the body path need a JSON envelope for *every* segment, or only for segments
  above a length threshold? Very short segments already bypass the LLM under BR-107.
  A JSON envelope around a two-word cell may cost more than it protects.

## Recorded scope decision: the body envelope stays one segment per call

Presented to the user with the evidence below; they chose **one segment per call**
(the shape BR-112 already specifies) and chose to **keep the critique loop out of
scope**. Recording the reasoning so a future reader does not mistake this for an
oversight.

**What the body envelope buys, and what it does not.** It replaces BR-108's
`is_meta_refusal()` string heuristic with structural validation on the happy path —
a robustness gain. It buys **no translation-quality gain**, because a single segment
wrapped in JSON is still a single segment: no neighbour context is added. The table
path's quality win comes from sending row-neighbours *together*, and the body path
as specified does not do the analogous thing.

**The rejected alternative — batching.** Sending N paragraphs per envelope with an
index (`{"segments":[{"i":0,"text":…}, …]}` → `{"segments":[{"i":0,"translation":…}, …]}`)
would be the true analogue of the table path: cross-paragraph context, and a call
count divided by N. It would reuse the same validator, the same coordinate-style
remap, and the same whole-batch fallback. It was rejected for this change because it
widens a Tier 1 blast radius on the default translation path, and because a larger
batch loses more on a single bad reply.

**The cost being accepted.** The body path continues to issue one translate call per
segment, and the out-of-scope critique loop adds three more. The user's 134-segment
`.docx` therefore stays at ~536 LLM calls and ~47 minutes. The critique loop was
measured to be conservative — given the correct draft `Ngày tạo` it returned it
unchanged 3/3, and given the wrong draft `Ngày sản xuất` it also returned it
unchanged 3/3 — so it neither undoes this change's table-path fix nor repairs a bad
translation. It is a cost problem, not a correctness problem, and belongs in its own
change.

Follow-up, not tracked here: batch the body envelope; and separately, evaluate the
critique loop's cost/benefit now that it is known to be near-inert on short segments.

## Discovered during review, OUT OF SCOPE here: nested-table text is silently dropped (DOCX)

The user asked how a table-inside-a-table is handled — an outer table used as a
layout frame wrapping body text, with the real table nested inside a cell.

`docx_processor.py` (~L261-285) walks `<w:tbl>` children and reads only
`cell.paragraphs`, the cell's **direct** paragraphs. A nested table hangs off
`cell.tables`, which the file never reads — `grep -c "cell.tables"` returns 0. So
the inner table's cells are never collected as segments, never translated, and the
source text remains in the output. This is silent partial translation, not a crash.

Reproduced on a constructed minimal `.docx` (outer 1×1 frame + inner 2×2 table): the
processor walk saw exactly one segment, `'OUTER-FRAME-TEXT'`; all four inner cells
were invisible.

Measured on the user's two real documents in `docs/TEST_DOC/` (untracked):

| document | visible chars | total chars | silently dropped |
|---|---:|---:|---:|
| `EN-P-QC1102-D7 量测系统分析(MSA)程序.docx` | 35,775 | 43,134 | 7,359 (17.1%) |
| `W-RM0901-G6 机器设备保养及维护管理准则.docx` | 19,997 | 31,169 | 11,172 (35.8%) |

Behaviour is exactly inverted from what it should be: the outer layout frame's body
text is treated as a table cell and routed through whole-table translation, while
the real inner table is dropped. No contract mentions nested tables at all. `.xlsx`
and `.pptx` have no nesting surface; this is DOCX-specific. The BR-109 sampler also
only walks `doc.tables` (top level), which affects the summary but not the output.

**Orthogonal to this change.** JSON changes how collected cells are *sent*, not
which cells are *collected*. It neither fixes nor worsens the defect. But it makes
the fix tractable: the old pipe-grid demanded a single `num_rows × num_cols` matrix,
which a nested table cannot occupy; the coordinate cell list has no shape constraint,
so an inner table can be sent as its own payload while the outer frame's prose
returns to the body path.

Tracked as the next change, after this one, per the user's stated ordering.
- **Answered by the probe above**: PANJIT and DeepSeek have no usable native
  JSON/response-format mode, the prompt phrasing is load-bearing and must be pinned
  by experiment, and parse-plus-schema validation is insufficient — an
  echoed-source reply must also trigger fallback. `design.md` must carry these
  forward as constraints.
- Should BR-108's `is_meta_refusal()` be retired once structured validation lands, or
  kept as defense-in-depth on the fallback path? Finding 4 argues for keeping a
  content-level guard regardless of the envelope. Note that `business-rules.md` has
  absence-regression tests on other retired tokens; retiring a rule has bitten this
  repo before.

## Requested Delivery Date / Priority

Priority: this is the last step of the realignment. It also subsumes the deferred
phantom-column defect, which has been wasting one large LLM call per sheet on every
spreadsheet job since the table path shipped.
