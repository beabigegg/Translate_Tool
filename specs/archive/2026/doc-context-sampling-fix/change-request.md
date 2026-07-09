# Change Request

## Original Request

User (verbatim, Chinese): 「先修123點」「第四點等等獨立進行, 跟著json提案一起」

This followed a live-run investigation of job `d19484ce43f94fa4b076ef0a0d07abae`
(2 files, PANJIT cloud provider `gpt-oss:120b`, target Vietnamese) in which the
user asked to confirm the end-to-end flow and translation quality before the
planned JSON structured-I/O change. The investigation surfaced four defects.
The user asked to fix the first three now, and to defer the fourth.

Restated in the three required elements:

1. **Affected surface** — `_sample_file_text` and `_detect_document_context` in
   `app/backend/processors/orchestrator.py`.
2. **Desired behavior** — `.xls` sampling must read the document's real text;
   `.docx` / `.pptx` sampling must include table text; a skipped or failed
   document-context summary must be visible at INFO level.
3. **Observable success criterion** — re-running the legacy `.xls` and the
   table-only `.docx` from job `d19484ce43f94fa4b076ef0a0d07abae` both emit a
   `[CONTEXT] Detected:` INFO line; when a sample genuinely cannot be obtained,
   the log states why instead of skipping silently.

## Business / User Goal

BR-109 (`cloud-doc-context-summary`, merged in PR #25) made the one-sentence
document-context summary reach cloud models via the system channel. Live
verification shows the summary **never fires on real documents**, because the
sampler that feeds it returns an empty string for two very common document
shapes. BR-109's benefit is therefore invisible in production.

Observed consequence in job `d19484ce43f94fa4b076ef0a0d07abae`: header cells
were translated with generic rather than document-aware meaning — e.g.
`制作日期` (document preparation date) rendered as `Ngày sản xuất`
(manufacturing date), and `审核(工务)` (facilities/plant engineering review)
rendered as `Kiểm duyệt (công vụ)` (public-affairs review). These are exactly
the class of error the summary preamble exists to prevent.

## Non-goals

- **Out of scope (deferred to the JSON structured-I/O change):** the xlsx
  table-batch phantom-column defect. `xlsx_processor` builds a proxy grid from
  `ws.max_row × ws.max_column` (observed `9×257` and `16×257` against only 47
  real cells), so `table_serializer.parse()` can never match the demanded shape
  and always returns `None`, wasting one large LLM call per sheet before the
  BR-82 per-cell fallback. Tracked as a follow-up, not fixed here.
- No change to how the summary is delivered to the model (that is BR-109,
  already shipped and verified).
- No change to translation quality logic, chunking, caching, or output modes.
- No new environment variables or feature flags.

## Constraints

- `CONTEXT_DETECTION_ENABLED` is a hardcoded constant in `config.py`, not an
  env var. `QWEN_CONTEXT_FLOW_ENABLED` is a real env var (default on). Both
  were verified on and are not the cause.
- The `.xls` → `.xlsx` LibreOffice conversion already exists at
  `app/backend/processors/xlsx_processor.py:64`, but runs **after** the
  orchestrator samples, so the sampler still sees the legacy file. Any reuse of
  that conversion must leave the processor's own conversion and its per-file
  timing semantics untouched, and must itself convert at most once per file.
  (Original wording said "must not double-convert or change per-file timing".
  implementation-planner showed those two clauses contradict each other: leaving
  the processor untouched necessarily means a `.xls` is converted twice per run.
  The sampler's extra conversion is accepted as a bounded cost — it is paid only
  when the context-detection gates are already open — and a shared/cached
  conversion is recorded as follow-up. See AC-7 in `change-classification.md`.)
- Sampling must stay cheap and must never raise into the job pipeline: a
  sampling failure degrades to "no preamble", never to a failed job.

## Known Context

Evidence gathered from the live run and live source:

- `_sample_file_text` `.xls`/`.xlsx` branch calls `openpyxl.load_workbook`.
  Confirmed by direct execution: on the job's `.xls`, openpyxl raises
  `InvalidFileException: openpyxl does not support the old .xls file format`.
  `_sample_file_text` returns `''`.
- The job's `.docx` (`W-QA1101-D1 量测系统分析作业规范.docx`) has 1 paragraph
  (empty) and 1 table with 36 non-empty cells. The `.docx` branch reads only
  `doc.paragraphs`, so `_sample_file_text` returns `''`.
- The `.pptx` branch reads only `shape.has_text_frame`, so table and
  graphic-frame text is likewise invisible to sampling.
- No `[CONTEXT] Detected:` line appears anywhere in `translator.log` for this
  job; the most recent one is dated 2026-06-19. `Processing:` and `[STRATEGY]`
  are stamped in the same second for both files, which a real `complete()`
  round-trip to PANJIT could not achieve.
- The empty-sample branch in `orchestrator.py` logs nothing, and
  `_detect_document_context` swallows exceptions at `logger.debug`, so INFO
  logs cannot distinguish "summary ran" from "summary skipped".

Translation quality itself was verified sound in that run: 47/47 cells
translated, zero silent drops, bilingual output as configured.

## Open Questions

- For `.xls`, should sampling reuse the existing LibreOffice conversion, or
  read the legacy format directly (e.g. via `xlrd`)? Reusing the conversion
  avoids a new dependency but changes ordering; reading directly keeps the
  sampler self-contained. Decision belongs to the implementation plan.

## Requested Delivery Date / Priority

Priority: ahead of the JSON structured-I/O change (step 3 of the
translation-prompt realignment), because it establishes the quality baseline
that change will be measured against.
