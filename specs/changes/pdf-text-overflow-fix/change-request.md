# Change Request

## Original Request

User-provided screenshot (a translated CCR/8D-style report PDF, table-heavy
layout) shows translated text (Chinese/Vietnamese) overflowing its intended
placement and overlapping/obscuring adjacent table cells and text. User's
own framing: "對於PDF不管是覆蓋還是同步呈現,均會有文字沒有換行與遮蔽的問題"
— for PDF, regardless of whether the output is in **overlay** (覆蓋) or
**side-by-side/synchronized** (同步呈現) presentation mode, translated text
fails to line-wrap and ends up obscuring/overlapping other content.

An `Explore` investigation this session (full file:line map below) found
this is **two distinct bugs plus one shared upstream defect**, not one:

**Bug A — side-by-side (and ReportLab-fallback) rendering has NO word-wrap
at all.**
- `app/backend/renderers/text_region_renderer.py:491-604` (`render_text_region`)
  is what PDF's side-by-side mode actually draws with (confirmed call chain:
  `fitz_renderer.py:554-669` `_generate_side_by_side()` →
  `text_region_renderer.py:646-693` `create_text_regions_from_elements()`,
  built with `font_size=None` → `_create_page_overlay()` →
  `render_text_region()`).
- When `region.font_size is None`, it calls the legacy
  `app/backend/utils/font_utils.py:496-550` `fit_text_to_bbox()`, which only
  shrinks a single font size until `max_line_width <= bbox_width` — where
  `max_line_width = max(width(line) for line in text.split("\n"))`
  (font_utils.py:529-530). **No wrapping occurs; only pre-existing `\n`
  characters split "lines," and LLM translations essentially never contain
  literal `\n`.**
- Critically: `fit_text_to_bbox` returns `fits=False` when nothing works
  (font_utils.py:544-549), but the caller (`render_text_region`,
  text_region_renderer.py:581,600) **only logs a warning** and still draws
  the entire un-wrapped string as one line at the floor font size via
  `canvas.drawString`. This is the concrete mechanism for the reported
  overflow in 同步呈現.
- The same broken no-wrap path is also what the ReportLab **fallback**
  renderer uses when fitz crashes (BR-34) —
  `app/backend/renderers/coordinate_renderer.py:120-172` →
  `text_region_renderer.py:696-722` `create_text_regions_from_placements()`
  (again `font_size=None`) → same `render_text_region()`.
- `contracts/business/business-rules.md:55` BR-40 currently **actively
  restricts** the real fit-cascade (word-wrap + shrink + truncate, BR-36/85)
  to "exclusively... the fitz primary renderer path and the shared
  `bbox_reflow.py` component... No duplication... permitted in
  `coordinate_renderer.py`, `inline_renderer.py`, or `pdf_generator.py`." —
  i.e. side-by-side/fallback were deliberately scoped OUT of the cascade
  work, and nothing filled the gap with even basic wrapping.

**Bug B — table-cell bounding boxes never get corrected to the true cell
extent in the common case, causing both overlap (side-by-side) AND silent
truncation (overlay). Originally scoped too narrowly — corrected below
after a second screenshot showed OVERLAY mode also losing content.**

Original framing only covered "`find_tables()` fails on borderless tables."
A follow-up `Explore` investigation (triggered by the user pointing out that
**overlay mode also truncates text**, e.g. "Nguyên nhân phát…", "2. Sản…" —
cut off mid-sentence with a literal `…`) found the defect is broader and
more common than that:

- `app/backend/parsers/pdf_parser.py:260-268` (`_extract_page_elements`)
  builds each element's `para_bbox` as the tight union of the *original
  source-language* line boxes — sized to however many lines the SOURCE text
  needed, in both width AND height, with zero headroom for translation
  growth.
- `_split_elements_by_cells` (pdf_parser.py:487-605, esp. :560-574) DOES
  correctly extend a cell's bbox to the true cell rect in both axes — but
  this only runs when `_detect_and_mark_tables` (pdf_parser.py:420-442)
  finds that some element **spans multiple detected grid cells**
  (`_spans_multiple_cells`, a merged-row situation).
- **The far more common case — a cleanly laid-out table where fitz already
  segments text one-block-per-cell, no merge needed — takes the plain path
  at pdf_parser.py:444-452, which re-tags `element_type = TABLE_CELL` but
  NEVER touches `elem.bbox`.** This happens regardless of whether
  `find_tables()` succeeds or fails, and regardless of border style. So even
  a full fix to the original "borderless table detection" framing would
  leave most individual cells exactly as tight-and-wrong as before.
- Net effect on overlay mode: `fit_text_cascade`
  (text_region_renderer.py:221-395) is verified sound — it wraps by width
  correctly, measures total height correctly, and only truncates when the
  bbox genuinely can't hold the text even after full font-shrink/line-spacing/
  letter-spacing degradation (this part needed NO change, correcting the
  original design's over-broad "overlay is fine" framing only insofar as it
  didn't say WHY overlay could still fail). It reaches truncation because it
  is fed a bbox sized for the ORIGINAL short source text, not because the
  cascade itself is broken — i.e. this is Bug B manifesting as truncation
  instead of overlap, not a third bug.
- **Original `find_tables()` strategy-fallback framing (BR-98, still valid)
  is necessary but not sufficient** — it only helps the "whole row merged
  into one block" case. The bbox-extension fix (BR-99) must be widened from
  "also fix the 1:1 case" to: **whenever a table's `cell_grid` is available
  at all, unconditionally extend every cell element's bbox to its detected
  `cell_rect` (both axes), independent of whether `_spans_multiple_cells`
  fired** — i.e. lift the extension logic in `_split_elements_by_cells:570-574`
  out of its current narrow gate and apply it on the common one-block-per-cell
  path too.
- Also newly found: `element.render_truncated` (BR-38's "no silent
  truncation" marker) IS set correctly (`fitz_renderer.py:515-517`,
  persisted per `models/translatable_document.py:240,255,272`), but has
  **zero production consumers** — repo-wide grep shows it's only read by
  test files and a test-only metrics helper
  (`tests/metrics/truncation_rate.py`). No UI badge, warnings-list entry, or
  report output surfaces it. The only in-code trace is a `logger.debug(...)`
  call (`fitz_renderer.py:518-521`) that never appears by default (app's
  `DEFAULT_LOG_LEVEL = logging.INFO`, `logging_utils.py:12`). In practice,
  BR-38's guarantee holds only at the data-model level — the end user's only
  way to discover truncation today is visually inspecting rendered PDF
  output, exactly how the user found this bug.
- (Historical framing, still accurate as one contributing case:)
  `app/backend/parsers/pdf_parser.py:387` calls PyMuPDF's `page.find_tables()`
  with **no `strategy=` argument**, i.e. PyMuPDF's default `lines_strict`
  strategy, which requires actual visible ruling lines to detect the grid.
  CCR-style reports with thin/no internal borders commonly fail this
  detection entirely.
- When detection fails, `_detect_and_mark_tables()`
  (pdf_parser.py:361-465) just `continue`s (line 388-389) — the row's text
  stays as whatever generic paragraph/text block fitz's own block
  segmentation produced, which — per the code's own comment — "frequently
  merge[s] a whole table ROW into one block." That merged block's bbox
  spans several columns' worth of text.
- Even when the table IS detected, `_split_elements_by_cells()`
  (pdf_parser.py:487-605) only rebuilds correct per-cell bboxes when a block
  is found to span multiple detected cells; if a block happens to align 1:1
  with a cell, the code just re-tags `element_type = TABLE_CELL`
  (pdf_parser.py:444-452) **without correcting the bbox** — keeping a bbox
  sized to the original (often short) source text, not the true cell
  extents.
- **This is the shared upstream root cause**: both overlay and side-by-side
  modes consume the identical `TranslatableDocument` IR
  (`bbox_reflow.reflow_document`), so a wrong/merged cell bbox produces the
  same visual overlap symptom in BOTH presentation modes — matching the
  user's report that neither mode is spared.
- Note: `TABLE_RECOGNITION_ENABLED` (the ML/TATR table-structure path,
  `config.py:187`) defaults `false` and has **zero renderer consumers**
  (confirmed via repo-wide grep) — turning it on today would not fix this;
  it would introduce a different bug (a whole flattened table string
  rendered into one bbox). `specs/archive/2026/p3-table-structure/design.md:41`
  already explicitly flagged "renderer-side follow-up if PDF table
  re-rendering is added later" as an open, deferred TODO.

## Business / User Goal

Translated PDF output must be legible and layout-faithful in BOTH PDF
presentation modes — text must wrap within its actual bounding box and must
never overlap or obscure adjacent cells/text, matching the "layout-faithful
output" promise this whole platform is built around (per CLAUDE.md's project
overview). Table-heavy documents with thin/borderless internal grids (a very
common real-world report format, as evidenced by the user's CCR-report
example) must not silently produce garbled, overlapping output.

## Scope Amendment (post-design, informed by industry-practice research)

User asked whether this change should go further than "shrink then truncate"
— e.g. switching to a flowing layout when fixed-layout restoration fails —
and asked for industry-practice research before deciding scope. Findings
(web research, this session):

- DTP/localization industry's standard fix ORDER is: copy edit → **frame/box
  adjustment** (grow the box, reposition neighbors) → tracking/leading
  compression → **font-size reduction last**. Our current cascade order is
  the opposite: font-shrink → line/letter-spacing → controlled-overflow →
  truncation, with **no box-growth step at all**.
- Commercial layout-preserving PDF translators explicitly market that table
  cells "automatically adjust" to translated text length (grow), rather than
  staying fixed-size.
- Text expansion of 20-35% for many target languages (vs. English source) is
  normal/expected, not an edge case — validating that a fixed-box-only
  approach is a structural, not incidental, gap.

**Decision (user-confirmed)**: full flowing-layout fallback (recomputing
page layout, pushing subsequent rows/content/pages) is explicitly OUT of
scope for this change — see new Non-goal below; it's a separately-scoped,
larger capability for a future change. **In scope for THIS change**: add a
bounded, LOCAL box-growth capability before falling back to
truncation — specifically:
1. Fix the confirmed bug where the cascade's own existing "controlled
   overflow" step (`fit_text_cascade` step (d), text_region_renderer.py:369-384)
   is neutered today by `fitz_renderer.py:511`'s hardcoded
   `available_whitespace_below=0.0` — this step already exists and already
   grows into available local whitespace up to 15% of bbox height, but is
   currently always disabled on the actual overlay call site.
2. Extend cell/box growth for TABLE_CELL elements specifically: when a
   cell's cascade would otherwise reach truncation, grow the row's height
   (not just the single cell) and push only the OTHER rows within the SAME
   table down by the same delta (bounded to that table's local region on the
   current page) — mirroring "cells automatically adjust" from industry
   practice, without requiring full cross-table/cross-page reflow.
3. Whatever text still cannot be accommodated after steps 1-2 and the
   existing shrink/compress cascade falls back to truncation as today, but
   now paired with the `job.warnings` surfacing decided below (this change
   no longer just minimizes truncation — it also makes any residual
   truncation visible).

## Non-goals

- **Full flowing-layout / page-reflow fallback** (recomputing entire page
  layout, pushing content across table boundaries, cascading pagination
  changes when growth exceeds a page) — explicitly out of scope per the
  Scope Amendment above; row-growth here is bounded to within a single
  table on its own page. A future change can pursue full reflow if the
  bounded growth proves insufficient in practice.
- Not adopting the ML/TATR table-structure path (`TABLE_RECOGNITION_ENABLED`,
  `table_recognizer.py`) as part of this fix — turning it on requires
  building actual renderer consumers for `TableStructure`/`TableCell`, which
  is a much larger, separately-scoped effort (already flagged as deferred in
  `specs/archive/2026/p3-table-structure/design.md`). This change fixes the
  DEFAULT (non-TATR) path's bbox correctness and the side-by-side wrap gap.
- Not changing DOCX/XLSX/PPTX rendering — this is PDF-specific
  (`RenderMode`/`pdf_layout_mode`, distinct from the office-only `OutputMode`
  enum).
- Not redesigning the BR-36/BR-85 fit-cascade algorithm itself (font-shrink →
  line-spacing compression → letter-spacing → controlled overflow →
  truncation) — that cascade already works correctly on the overlay/fitz
  path; this change is about (a) reaching it (or an equivalent) from
  side-by-side/fallback, and (b) feeding it a correct bbox for table cells.
- Not fixing the ReportLab fallback path's weaker text-masking (`canvas.rect`
  fill vs. true PyMuPDF redaction, BR-84) — a related but separate,
  lower-priority cosmetic gap noted during investigation, not in scope here
  unless it's cheap to bundle once the fallback path is being touched anyway
  (design/implementation-planner's call).

## Constraints

- Must not weaken BR-36/BR-38/BR-85's existing guarantees on the
  overlay/fitz path (word-wrap, iterative scale-fit, no-silent-truncation
  marker `render_truncated`) — this change extends coverage, not replaces
  working behavior.
- BR-40's restriction (cascade logic confined to fitz + `bbox_reflow.py`)
  must be explicitly revisited — either amended to permit reuse from
  side-by-side/fallback, or a deliberately equivalent (not necessarily
  identical-code) wrap+shrink pass must be designed for those paths. This is
  a design decision for spec-architect, not a decision to make silently
  during implementation.
- Table-detection fix must not regress documents where `find_tables()`
  already succeeds today (i.e., any added fallback detection strategy must
  be additive/attempted-after, not a replacement that could produce worse
  results for already-working cases).
- STOP after `implementation-plan.md` — do not commission
  `backend-engineer`/`bug-fix-engineer` to write product code in this pass.
  Implementation is deferred to a later, separately-approved session,
  consistent with every other change planned this session.

## Known Context

- Full investigation performed by an `Explore` agent this session; see the
  file:line map in "Original Request" above for the concrete code paths.
- Relevant existing BRs: BR-36 (text-expansion-fit-cascade), BR-38
  (no-silent-truncation), BR-40 (cascade-path-restriction — the rule that
  currently blocks side-by-side from having wrap logic), BR-68 through
  BR-71 (table-cell *translation* strategy — NOT rendering/placement; do not
  conflate), BR-84 (bbox-exact-whitening, fitz-path-only), BR-85
  (iterative-scale-fitting).
- `pdf_layout_mode` (`contracts/data/data-shape-contract.md:53`,
  `overlay`/`side_by_side`) and `RenderMode`
  (`app/backend/renderers/base.py:13-18`, `INLINE`/`SIDE_BY_SIDE`/`OVERLAY`)
  are the actual PDF-specific mode flags — confirmed real, distinct code
  branches (`PDFGenerator.generate()`, fitz_renderer.py:186-223), not a UI
  artifact.
- Constants already available for reuse: `MIN_READABLE_FONT_PT=8`,
  `FONT_SIZE_SHRINK_FACTOR=0.9` (config.py:214-219), per-language
  `FONT_SIZE_CONFIG` (config.py:224-226).
- The user's screenshot appears to be a real company CCR/8D report document
  (PANJIT-branded corrective-action tracking template) — likely sourced from
  or similar to files in `docs/TEST_DOC/` (untracked, never committed —
  treat any such document as reference-only, do not copy its content into
  any committed artifact).

## Open Questions

- BR-40's fix direction (amend to permit cascade reuse in side-by-side, vs.
  design a separate-but-equivalent wrap pass for that path) — deferred to
  spec-architect.
- Table-detection fallback strategy: PyMuPDF's `find_tables()` supports a
  `strategy` param (`"lines_strict"` default, `"lines"`, `"text"` as
  alternatives per its own docs) — should the parser retry with progressively
  looser strategies when the strict one finds nothing, and if so what's the
  acceptable false-positive risk (detecting a "table" where there isn't
  one)? Deferred to spec-architect/contract-reviewer.
- Should the 1:1 block-to-cell case (`pdf_parser.py:444-452`, currently
  re-tagged as TABLE_CELL without bbox correction) also get its bbox
  corrected to the true cell extent, even when no multi-cell merge was
  detected? (Likely yes, for consistency, but confirm during design — this
  affects whether "shrink-only" is enough or wrap is also needed even in the
  best-detected case.)
- Whether to bundle the ReportLab fallback's weaker masking gap (BR-84,
  noted as a Non-goal above) given the fallback path is already being
  touched for the wrap fix — implementation-planner's call once scope is firm.
- ~~Should this change also surface `render_truncated`...~~ **RESOLVED: yes.**
  User confirmed: add a `job.warnings` entry (matching the established BR-96
  legacy-conversion-disclosure precedent) whenever a segment is truncated
  after exhausting the full cascade (including the new bounded box-growth
  steps above), so residual truncation is visible without requiring visual
  PDF inspection.
- ~~Should full flowing-layout reflow be added...~~ **RESOLVED: no, not in
  this change.** See Scope Amendment above — bounded local row-growth within
  a table is in scope; cross-table/cross-page reflow is an explicit Non-goal,
  deferred to a possible future change.

## Requested Delivery Date / Priority

No fixed deadline. Priority: correctness/legibility of translated PDF output
for table-heavy real-world documents (directly demonstrated by user's own
example) — plan now, implement in a later session once reviewed.
