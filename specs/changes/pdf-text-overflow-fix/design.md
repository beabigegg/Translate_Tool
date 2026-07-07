# Design: pdf-text-overflow-fix

## Summary
Two coupled PDF defects produce translated-text overflow in BOTH overlay and
side-by-side modes. Bug A: the ReportLab draw path (`render_text_region`, used
by side-by-side AND the fitz-crash fallback) has no word-wrap — it calls the
legacy shrink-only `fit_text_to_bbox`, splits only on literal `\n`, and on
`fits=False` still draws the whole unwrapped string at floor size. Bug B: the
PDF parser detects tables only with PyMuPDF's strict `lines_strict` strategy,
so thin/borderless grids (CCR-style reports) fail detection and leave a whole
row as one multi-column bbox; even on a successful 1:1 block-to-cell match the
bbox is left sized to the short source text. Both feed the same `bbox_reflow`
IR, so the symptom appears in both modes. This design makes `fit_text_cascade`
the single shared source of truth for ALL PDF renderer paths (amending BR-40),
adds an additive looser-strategy table-detection fallback behind a sanity gate,
and corrects the 1:1 cell bbox to true cell extents. A post-design scope
amendment adds bounded LOCAL box-growth before truncation (per industry DTP
fix-order): (AC-9) real neighbor whitespace is computed and fed to the cascade's
existing controlled-overflow step (dead today); (AC-10) a shared upstream
row-growth pre-pass grows a table cell's row and pushes only same-table rows down;
(AC-11) residual truncation is surfaced to `job.warnings` via the BR-96 plumbing.

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| ReportLab draw path | `renderers/text_region_renderer.py:491-604` | replace shrink-only `fit_text_to_bbox`+`\n`-split with `fit_text_cascade`→`_wrap_lines_simple`→per-line `canvas.drawString`; set `render_truncated` on truncation |
| Region model | `renderers/text_region_renderer.py:398-409,646-722` | carry source `StyleInfo`/element ref through `TextRegion`/placement so the cascade has a starting font size + a truncation-marker target |
| Fallback renderer | `renderers/coordinate_renderer.py:120-172` | inherits wrap via the shared draw path (no per-path cascade duplication) |
| Reference path (guard) | `renderers/fitz_renderer.py:407-552` | unchanged; must-not-regress reference for cascade behavior |
| Legacy fitter | `utils/font_utils.py:496-550` | no longer the wrap authority on PDF paths; retained for any non-PDF callers |
| Table detection | `parsers/pdf_parser.py:361-465` | additive looser-strategy fallback + sanity gate; correct 1:1 cell bbox to cell extents |
| Whitespace source (AC-9) | `renderers/bbox_reflow.py:34-131` | add `available_whitespace_below` to `Placement`; page-group elements + compute per-element gap-below; fitz `fitz_renderer.py:507-512` reads it instead of hardcoded `0.0` |
| Row-growth pre-pass (AC-10) | `renderers/text_region_renderer.py` (new fn) invoked by `processors/pdf_processor.py:1035-1075` `_dispatch_render` | shared upstream pre-pass: measure per-row required height via `fit_text_cascade`/`_wrap_lines_simple`, grow row + shift lower rows' bbox & `metadata["lines"]` in IR before either backend renders |
| Truncation warning (AC-11) | `processors/pdf_processor.py:1035-1075` `_dispatch_render` | post-render sweep of `doc` for `render_truncated`; emit per-file `job.warnings` via existing `warnings_callback` |
| Business rules | `contracts/business/business-rules.md:55` | amend BR-40; add BR for bounded-local-row-growth (AC-10) + residual-truncation-disclosure (AC-11); guard BR-36/38/84/85 (contract-reviewer owns) |
| Data shape | `contracts/data/data-shape-contract.md:122` | affirm TABLE_CELL bbox = true cell extent; note post-translation row-shift of cell/sibling bboxes upstream of `reflow_document` (contract-reviewer confirms) |

## Key Decisions

- **Decision 1 (BR-40): reuse the exact `fit_text_cascade`/`_wrap_lines_simple`
  functions on the ReportLab path; amend BR-40 to name the cascade the single
  shared source of truth for ALL PDF renderer paths, not fitz-only.** Both draw
  sites are already per-wrapped-line loops over the SAME output shape: fitz does
  `tw.append((x,y), line, ...)` (fitz_renderer.py:540-547), ReportLab does
  `canvas.drawString(line_x, line_y, line)` (text_region_renderer.py:589-600).
  Wrapping and sizing are canvas-API-agnostic — only the terminal draw primitive
  differs. So `render_text_region` can call `fit_text_cascade` then
  `_wrap_lines_simple(decision.fitted_text, font, decision.font_size, width)` and
  draw each line, honoring `decision.line_spacing` and `decision.truncated`.
  → Rejected: a separate-but-equivalent wrap pass for the ReportLab canvas —
  rejected because it duplicates the exact logic BR-40 was written to prevent,
  creates two cascades that will drift (the recurring "duplicate renderer logic"
  failure mode in this repo), and buys nothing since the primitive difference is
  one line. The cascade already lives in `text_region_renderer.py` (a shared
  module both paths import), so reuse does not move any boundary. See ADR 0012.

- **Decision 2 (table-detection fallback): retry looser strategies
  (`lines_strict` → `lines` → `text`) ONLY when the strict pass finds nothing
  (`tables.tables` empty), never overriding a successful strict detection, and
  gate any fallback result behind a sanity check before accepting it.** This is
  additive (AC-7): already-working documents take the strict result unchanged.
  The false-positive risk is real — `strategy="text"` clusters whitespace and can
  hallucinate a grid over ordinary prose, which would corrupt non-table paragraph
  layout. Sanity gate to accept a fallback detection: ≥2 rows AND ≥2 columns, and
  each detected cell rect wider/taller than a minimum (reuse the existing
  `>2pt`-overlap floor already in `_spans_multiple_cells`). If the fallback
  result fails the gate, discard it and keep the original paragraph blocks
  (current behavior) — the fallback can only improve or no-op, never worsen.
  → Rejected: always run `strategy="text"` and merge with strict — rejected;
  overriding good strict grids risks regressing working cases (violates AC-7) and
  the merge semantics are ambiguous. → Rejected: gate on a numeric confidence
  score from `find_tables()` — PyMuPDF exposes none; the structural row/col/size
  check is the available, deterministic proxy.

- **Decision 3 (1:1 block-to-cell bbox): yes — correct the bbox to true cell
  extents even when no multi-cell merge occurred, reusing the extend-into-cell
  logic `_split_elements_by_cells` already applies.** At pdf_parser.py:444-452 the
  element is re-tagged TABLE_CELL but keeps a bbox sized to the (often short)
  source text; once the translation is longer it overflows exactly as reported —
  shrink-only is NOT enough, wrap needs the real cell width. When `_locate_cell`
  returns `(ri,ci)`, extend the element's `x1`/`y1` to the cell rect minus the
  same `_pad=2.0` border padding used at text_region_renderer... (pdf_parser.py:
  569-574), leaving `x0`/`y0` at the tight text origin. Keep the tight per-line
  bbox for whitening via `metadata["lines"]` (BR-84) so cell borders are spared.
  → Rejected: leave 1:1 bbox as source-text-tight and rely on the cascade to
  shrink — rejected; guarantees overflow/over-shrink for any expanding language
  and contradicts AC-5. → Rejected: extend in all four directions to the full
  cell rect — rejected; would push text origin off its baseline and over
  neighboring cells' borders. Right/bottom extension only preserves origin.

- **Decision 4 (AC-9): compute real `available_whitespace_below` in the shared
  `bbox_reflow` placement authority, not in each renderer.** The cascade's step (d)
  overflow (≤15% bbox height into local free space) is dead today because
  `fitz_renderer.py:511` hardcodes `0.0`. Since both backends consume the same
  `reflow_document` output (BR-35), compute the gap ONCE there and carry it as a new
  `Placement.available_whitespace_below` field. Rule: for a TABLE_CELL, gap = distance
  from this cell's `y1` to the nearest element's `y0` in the next row of the SAME
  `table_id`/`table_col` (else the table's bottom, else page bottom margin); for a
  non-table element, gap = distance to the next element below on the page whose x-range
  overlaps this one (no horizontal collision ⇒ no constraint). fitz then reads the
  field instead of `0.0`. → Rejected: compute it inside `fitz_renderer` per element —
  rejected; duplicates cross-element geometry the ReportLab path also needs, reviving
  the two-implementations drift BR-40/ADR-0012 exist to prevent. Overflow moves no
  neighbor (draws into an existing free gap), so it stays distinct from Decision 5.

- **Decision 5 (AC-10): a single shared row-growth PRE-PASS on the translated IR,
  invoked once in `_dispatch_render` upstream of both backends — measured
  post-translation, never estimated at parse time.** (1) WHERE: not the parser
  (translated text is unknown at parse time, so only a fixed-factor guess is possible,
  which grows rows that don't need it); not inside a renderer (would duplicate per
  backend). It runs on `doc` in `_dispatch_render` before dispatch, reusing the SAME
  `fit_text_cascade`/`_wrap_lines_simple` measurement (ADR-0012) — a true two-pass on
  actual wrapped-line counts. (2) DATA: group by `(page_num, metadata["table_id"])`
  then `metadata["table_row"]`/`table_col` — all confirmed populated by
  `_split_elements_by_cells` (pdf_parser.py:595-599) and the 1:1 path via `_locate_cell`
  (:449-452); when no `cell_grid` exists (find_tables fully failed) there is no row
  metadata and growth is skipped → truncation + AC-11 warning. (3) PUSH: per row take
  the max required height; if it exceeds the row's current height, grow that row's cells'
  `y1` by delta and shift every lower-row element's bbox AND its `metadata["lines"]`
  whitening bboxes down by the cumulative delta, in the IR, so overlay and side-by-side
  both inherit it (like Bug B's upstream cell correction). (4) ABORT: cap cumulative
  growth at the table's remaining local budget (page bottom margin, or top of the first
  non-table element below the table); a row needing more than the budget grows by the
  budget and its residual falls to cascade truncation + AC-11 warning. Best-effort, not
  a new hard guarantee. → Rejected: parser-time heuristic growth — rejected (imprecise,
  pre-translation). → Rejected: cross-table/cross-page reflow — explicit Non-goal. See
  ADR 0013.

- **Decision 6 (AC-11): surface residual truncation via a post-render sweep in
  `_dispatch_render`, reusing the BR-96 `warnings_callback` → `_record_job_warning`
  plumbing — not by threading the callback into the renderer.** The renderer already
  sets `render_truncated=True` in-place on IR elements (fitz `_insert_text_in_rect`;
  the ReportLab path once Decision-1's element-ref threading lands). `_dispatch_render`
  holds both `doc` (post-render, markers set) and `warnings_callback` (already a param,
  line 1044). After the render call returns, sweep `doc` for `render_truncated` and emit
  ONE aggregated per-file `warnings_callback` entry naming `doc_id` + affected page(s)/
  segment(s), mirroring BR-96's "converted from a legacy format… layout fidelity may be
  lower" wording (contract-reviewer sets exact string). One aggregated entry per file,
  not per element, to avoid warning-spam on table-heavy docs. → Rejected: thread the
  callback down into `_insert_text_in_rect` — rejected; invasive across two backends and
  couples the renderer to job plumbing when the marker-on-IR + processor-sweep seam
  already cleanly separates "who detects" from "who reports." Dependency: fallback-path
  coverage requires Decision-1/AC-8 element-ref threading (else fitz-only).

## Migration / Rollback
No data migration, schema, or env changes — reuses `MIN_READABLE_FONT_PT`,
`FONT_SIZE_SHRINK_FACTOR`, `FONT_SIZE_CONFIG` (config.py). Behavior-only change to
runtime render paths. The amendment enlarges scope but adds no persisted state: the
row-growth pre-pass mutates the in-memory IR per render and the `Placement`
whitespace field is transient, so rollback stays a pure code revert plus reverting
the BR-40/BR-row-growth/BR-truncation-disclosure amendments — nothing on disk carries
the new behavior. The four sub-fixes are independently shippable/revertible and
SHOULD be feature-staged: wrap (Dec 1) → cell-bbox (Dec 3) → detection fallback
(Dec 2) → whitespace (Dec 4) → row-growth (Dec 5) → warning (Dec 6). Row-growth (the
largest, highest-risk piece) can be gated behind a config flag so it can be disabled
in production without reverting the rest, given its overlay-mode border-crossing risk.
Implementation deferred to a later approved session (STOP after implementation-plan.md
this pass).

## Open Risks
- **Cascade starting font on the ReportLab path**: `render_text_region` today
  derives font size from the bbox when `font_size is None`. The cascade wants the
  ORIGINAL source font size (as fitz_renderer.py:481-488 does via `element.style`).
  The `TextRegion`/placement plumbing must carry `StyleInfo`; if unavailable the
  cascade falls back to the language `FONT_SIZE_CONFIG` max — acceptable but
  slightly less faithful. Flagged for implementation-planner.
- **`render_truncated` marker on the ReportLab path**: BR-38 requires the marker
  on the IR element. `create_text_regions_from_placements` currently drops the
  element ref (placement carries text/bbox only). Setting the marker requires
  threading the element (or element_id) through to the draw call, matching the
  fitz path's `element` param. If not threaded, truncation degrades to log-only
  (as the fitz legacy call-sites with `element=None` already do) — a BR-38 gap on
  fallback; implementation-planner must decide whether to thread it now.
- **`strategy="text"` cost**: the looser fallback runs a second `find_tables()`
  only on pages where strict found nothing, so cost is bounded, but on
  large/dense pages `strategy="text"` can be slower. Acceptable given it is
  page-scoped and skipped whenever strict succeeds.
- **`.cdd/code-map.yml` freshness**: not re-validated this pass; ranges above were
  read directly from source, not the map. No staleness observed in the files read.
- **RESOLVED (Decision 6): `render_truncated` zero-consumer gap.** The flag was set
  and persisted but only read by tests — no user-facing surface. Decision 6 adds a
  `_dispatch_render` post-render sweep → `job.warnings` (BR-96 plumbing). Residual
  dependency: fallback-path coverage needs Decision-1/AC-8 element-ref threading.
- **RESOLVED (Decision 4): hardcoded `available_whitespace_below=0.0`.** Decision 4
  computes real neighbor whitespace in `bbox_reflow` and carries it on `Placement`.
- **Overlay-mode row-growth border-crossing (new, AC-10).** In overlay mode the source
  PDF background — original table rules/graphics preserved by `apply_redactions(graphics=0)`
  — is NOT moved by the pre-pass; only our whitening + drawn text shift down. Pushed-down
  rows can therefore land over original horizontal rules. Side-by-side (fresh canvas) is
  unaffected. The within-table page-capped bound limits but does not eliminate this;
  hence the recommended config flag to disable row-growth in production (Migration).
  implementation-planner must decide whether overlay-mode growth is more conservative
  (or disabled) than side-by-side.
- **Cascade order deviation (AC-10).** This change inserts row-growth just before
  truncation, keeping the existing font-shrink-first cascade order rather than the pure
  DTP grow-first order the research recommends. Deliberate lower-risk scoping; full
  reorder is deferred to the future reflow change (Non-goal).
- **`metadata["lines"]` shift coupling (AC-10).** When a lower row is pushed down, its
  per-line whitening bboxes (`metadata["lines"]`, BR-84) must shift by the same delta or
  whitening will mask the old location. Concrete implementation hazard flagged for
  implementation-planner.