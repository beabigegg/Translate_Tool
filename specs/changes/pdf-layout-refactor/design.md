# Design: pdf-layout-refactor

## Summary
Seven PDF-fidelity defects (3.1–3.7) are fixed inside one sequential worktree spanning the
PDF parse→detect→translate→render pipeline. The unifying seam is the unified IR
(`TranslatableDocument`): the parser is upgraded to emit paragraph-aggregated elements with
per-span style, the layout detector gains a column-aware reading-order model and a higher render
DPI, and both renderers (fitz primary, ReportLab fallback) consume the same IR through the shared
`bbox_reflow` placement seam plus the `fit_text_cascade` fit seam. Data flow direction is unchanged
(parser → IR → translation → renderer); the changes are additive to the IR shape and to two
config flags, preserving the fitz-primary / ReportLab-fallback convergence (BR-34/35) and the
TATR path (TABLE_RECOGNITION_ENABLED=false).

## Affected Components
| component | file path(s) | nature of change |
|---|---|---|
| IR model | `app/backend/models/translatable_document.py` | add `StyleInfo.is_underline`; per-span style list in `metadata["spans"]`; paragraph element semantics |
| PDF parser | `app/backend/parsers/pdf_parser.py` | paragraph aggregation (3.2); per-span style capture (3.4); DPI-scaled rasterise matrix (3.6); scanned→OCR routing (3.7) |
| Layout detector | `app/backend/parsers/layout_detector.py` | `LayoutReader`-style reading-order model replacing x-gap threshold (3.5); RTL handling |
| OCR backend (new) | `app/backend/parsers/ocr_backend.py` | lazy-imported `ocr_backend` seam (Surya/PaddleOCR) gated by `OCR_ENABLED` (3.7) |
| fitz renderer | `app/backend/renderers/fitz_renderer.py` | bbox-exact whitening replacing `search_for` (3.1); per-span `insert_text` from StyleInfo (3.4) |
| reflow/fit seam | `app/backend/renderers/bbox_reflow.py`, `renderers/text_region_renderer.py` | iterative binary-search scale-fit replacing shrink-to-floor-then-truncate (3.3) |
| ReportLab fallback | `app/backend/renderers/coordinate_renderer.py` | inherits shared fit/placement changes; convergence preserved |
| PDF processor | `app/backend/processors/pdf_processor.py` | paragraph element-count + block_id stability; FORMULA pass-through; scanned-page warning seam |
| Config | `app/backend/config.py` | new `PDF_RENDER_DPI` (default 150), `OCR_ENABLED` (default False), `MIN_READABLE_FONT_PT` (8) |

## Key Decisions

### D-1: Bbox-exact whitening (3.1)
Current: `_generate_overlay` calls `page.search_for(original_text, quads=True)` to locate the
redaction rect, falling back to the placement bbox. New: white-out the element's IR `bbox` rect
directly via redaction, dropping the text-search dependency. Chosen over keeping search-as-primary
because `search_for` is fragile on non-Latin and multi-line runs (residual bleed-through). Constraint:
parser stores `bbox` in page-space points (from `get_text("dict")` line bbox), so no coordinate
transform is needed; the configurable mask margin (`PDF_MASK_MARGIN_PT`) is retained to spare table borders.

### D-2: Paragraph aggregation + reflow (3.2)
Current: `_extract_page_elements` emits one element per line (block→line). New: consecutive lines in
the same block/region are grouped into one paragraph element (BabelDOC paradigm — paragraph is the
translation unit), with in-block reflow at render. Chosen over ML region grouping (no training data).
Constraint: this reduces element count, so the `pdf:{stem}:{idx}` block_id contract used by the judge
`block_overrides` seam must remain index-stable post-aggregation; the original line bboxes are kept in
`metadata` for whitening so D-1 still masks every source line.

### D-3: Iterative scale-fitting (3.3)
Current: `fit_text_cascade` shrinks the font by `FONT_SIZE_SHRINK_FACTOR` to the `MIN_FONT_SIZE_PT`
floor, then truncates with `render_truncated=True`. New: binary-search the font size between
`MIN_READABLE_FONT_PT` (8pt) and the original size until the text fits, only falling to truncation
when even 8pt overflows. Chosen over linear shrink for a tighter, readable fit. Constraint: the seam is
shared by both fitz and ReportLab via `text_region_renderer`; the `CascadeDecision`/`render_truncated`
contract (BR-38) is unchanged so the fallback path and QA safety net keep working.

### D-4: Per-span style re-application (3.4)
Current: parser captures style from the **first span only**; fitz renderer ignores `StyleInfo` and
renders one font/colour per block. New: parser stores a per-span style list (font, size, colour, bold,
italic, underline) and the fitz renderer emits one `insert_text` per span run. Chosen because the
fidelity loss is at the span granularity. Constraint: `StyleInfo` lacks an underline field today —
add `is_underline`; `to_dict`/`from_dict` stay backward-compatible (defaulted), and elements without a
span list fall back to the single-style path.

### D-5: Reading-order model (3.5)
Current: `_assign_reading_order` splits columns with a single `_COLUMN_GAP_THRESHOLD` x-gap and the
heuristic uses `round(y0/10)`. New: an internal `LayoutReader` class assigns each element a column then
sorts by (column, y) — replacing the bare x-gap heuristic. Chosen over the external LayoutReader ONNX
model (avoids a second ONNX dependency/version conflict). Constraint: must honour RTL by ordering
columns right-to-left when page/text direction is RTL; fail-soft to the existing heuristic on any error.

### D-6: DPI upgrade (3.6)
Current: `_run_layout_detector` rasterises at `fitz.Matrix(1, 1)` (72 DPI). New: a `PDF_RENDER_DPI`
config flag (default 150) drives `fitz.Matrix(dpi/72, dpi/72)` for detector input, improving
classification quality. Chosen over a fixed 200 DPI to bound memory/time. Constraint: higher DPI raises
per-page memory and latency; the flag is documented and can be set back to 72 for opt-out; detection
boxes are already normalised 0..1 so downstream math is unaffected.

### D-7: Formula placeholder + OCR (3.7)
Current: the detector already sets `should_translate=False` for FORMULA/FIGURE, but the heuristic path
does not, and scanned PDFs (no text layer) yield near-blank output. New: (a) FORMULA content is
preserved as-is on every path (explicit placeholder, no LLM call); (b) when `page.get_text()` is empty
on a page with visible objects, a lazy-imported OCR backend runs, gated by `OCR_ENABLED` (default
False). Chosen so scanned files are recoverable without making OCR a hard dependency. Constraint: the
OCR library must be lazy-imported behind an `ocr_backend` seam; when absent or disabled, scanned pages
emit a warning (reusing `has_text_layer`) and never crash — CI must pass without the library installed.

## Rejected Alternatives
- External LayoutReader ONNX model — too heavy; adds a second ONNX runtime alongside the heron-101
  detector with version-conflict risk. Geometric column+y ordering covers the multi-column metric.
- ML region-detection for paragraph aggregation — overkill with no training data; geometric block
  grouping is sufficient and deterministic.
- PaddleOCR as the sole OCR engine — Surya is pure-Python and easier to gate in CI; the design abstracts
  both behind an `ocr_backend` seam so either can be swapped without touching the parser.

## Migration / Rollback
No schema or on-disk migration: the IR is in-memory and additive (`StyleInfo.is_underline` and a
`metadata["spans"]` list both default-safe via `from_dict`). 3.6 (`PDF_RENDER_DPI`) and 3.7
(`OCR_ENABLED`) ship behind config flags — setting DPI=72 and OCR_ENABLED=False reproduces today's
behaviour. 3.1–3.5 are behavioural refactors of the shared seams kept convergent across fitz and
ReportLab, so the existing `_dispatch_render` fallback still converges and `render_truncated` keeps its
BR-38 meaning (now rarely set because D-3 fits more text). Rollback is per-item: each of 3.1–3.7 is an
isolated seam change revertable without disturbing the others, and the TATR path
(TABLE_RECOGNITION_ENABLED=false) is untouched.

## Open Risks
- ADR not required: no boundary move, persistence, or consistency change; the OCR addition is an
  optional lazy seam, and the reading-order model deliberately avoids a new ONNX engine.
- Paragraph aggregation (D-2) interacts with the judge `block_id` index contract — index stability must
  be verified by the implementation-planner before wiring `block_overrides`.
- `MIN_FONT_SIZE_PT` (6) vs the cascade docstring (4pt floor) vs the new `MIN_READABLE_FONT_PT` (8) must
  be reconciled to one source of truth during implementation.
