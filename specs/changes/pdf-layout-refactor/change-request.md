# Change Request

## Original Request

Wave 2 Track G — pdf-layout-refactor: fix 7 PDF renderer defects sequentially within one worktree (items 3.1→3.7 from docs/improvement-plan.md):

- 3.1: Replace text-whitening via `search_for` with bbox-exact extraction; decouple whitening from text search so residual source text after render = 0.
- 3.2: Aggregate lines into paragraphs + in-block reflow (BabelDOC IR paradigm); metric: BIoU improves, truncation rate falls.
- 3.3: Iterative scale-fitting replaces "shrink to 4pt then truncate" fallback; metric: truncation rate → 0, minimum font ≥ readable threshold.
- 3.4: Per-span style fidelity: color, bold, italic, underline re-applied per span run after translation; metric: render assertion confirms output preserves source StyleInfo.
- 3.5: Reading-order model (LayoutReader-style) replaces single x-gap column threshold; metric: multi-column fixture reading-order normalized edit distance ↓.
- 3.6: DPI detection upgrade 72 → ~150–200; metric: layout-detector classification mAP improves on high-DPI documents.
- 3.7: Formula element placeholder protection (pass-through, no translation); scanned-file path pipes to OCR (PaddleOCR or Surya); metric: formula pass-through tests pass, scanned-blank test no longer fails.

## Business / User Goal

PDF output currently has 7 layout-fidelity defects that make translated PDFs unreadable or visually broken: residual source text bleeds through after rendering, paragraph context is lost in line-by-line mode, text is silently truncated rather than scaled, span styles (color/bold) are stripped, multi-column reading order is wrong, high-DPI documents are parsed at 72 DPI losing detail, and formula elements are corrupted. Fixing these brings the PDF renderer to production quality.

## Non-goals

- Table structure recognition (p3-table-structure, already shipped)
- Table context translation (table-context-translation, Track D, already in PR#7)
- Office output-mode changes (Track F, Wave 3)
- Quality evaluator or critique loop changes

## Constraints

- All 7 items touch the same renderer/parser/processor files; Track G must be a single sequential worktree (per improvement-plan §8.3 and §8.5).
- Prerequisites: B (layout fidelity metrics harness, PR#3 merged ✓) and 0.2 residual-text check baseline (PR#2 merged ✓).
- `TABLE_RECOGNITION_ENABLED` defaults to false; TATR path must remain unaffected.
- PDF processor (`pdf_processor.py`) is owned by this track; no other wave-2 track touches it.
- Item 3.7 OCR dependency (PaddleOCR or Surya) may be optional/lazy-loaded; gate must not require it at CI unless the library is present.

## Known Context

- Current renderer entry points: `renderers/fitz_renderer.py` (primary), `renderers/bbox_reflow.py` (shared reflow), `renderers/coordinate_renderer.py` (ReportLab fallback).
- Whitening currently uses PyMuPDF `search_for` text search — fragile on non-Latin scripts and multi-line runs.
- Paragraph aggregation is absent; renderer iterates raw line objects, losing paragraph context.
- Scale fallback: `bbox_reflow.py` shrinks to 4pt and sets `render_truncated=True` instead of iteratively fitting.
- Style data: `StyleInfo` (color, bold, italic, underline) exists in the IR but is not re-applied post-translation.
- Reading order: single x-gap heuristic in `layout_detector.py`; fails on multi-column or RTL layouts.
- DPI: parser defaults to 72 DPI for layout-detector matrix; high-DPI documents lose detail.
- Formulas: no placeholder; `FORMULA` ElementType exists in IR but passes through translation unchanged (wrong).

## Open Questions

None — improvement-plan.md items 3.1–3.7 define full scope.

## Requested Delivery Date / Priority

Wave 2 — high priority (highest-risk change; must complete before Wave 3 PDF quality work).
