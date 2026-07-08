# Change Request

## Original Request
Fix a gap in the just-merged `translation-progress-detail-ui` (#7) change: the
live progress-detail fields (`current_stage` / `current_segment_source` /
`current_segment_draft`) never populate for **PDF** jobs, so the frontend
StageDetailPanel shows no "current segment" source/translated text for PDFs
(the most common format here). Verified on a real running PDF job:
`GET /api/jobs/{id}` returns all `current_segment_*` = `null` throughout.

Root cause (code-traced): the PDF pipeline `pdf_processor.translate_pdf` →
`translate_blocks_batch` bypasses `translation_service.translate_texts`, which is
where #7 wired the `status_callback` current-segment snapshot; and `translate_pdf`
has no `status_callback` parameter at all. DOCX/PPTX/XLSX go through
`translate_texts` and already populate it; judge fields populate via `job_manager`
(format-agnostic) and are unaffected.

## Business / User Goal
A translator watching a long **PDF** job sees which segment's original + draft
text is currently being translated in the StageDetailPanel, same as Office formats.

## Non-goals
- Adding a critique/QE/adopt loop to the PDF path (PDF uses batch translation; only
  the "translate" stage applies for PDF — matching existing behavior).
- Any change to Office (docx/pptx/xlsx) or judge snapshot wiring (already work).
- New endpoint / env var / UI component (the fields + panel already exist).

## Constraints
- Additive/observational only; no change to PDF translation output or performance.
- Reuse `translate_blocks_batch`'s existing per-segment `on_segment_done(src,
  translated)` callback; lazy-import `CurrentSegmentSnapshot` from `job_manager`
  (matching `translation_service`'s convention) to avoid a circular import.

## Known Context
- Fix seam: `pdf_processor.translate_pdf` + internal `_translate_pdf_with_pymupdf` /
  `_translate_pdf_to_pdf` / `_translate_pdf_with_pypdf2`; `orchestrator.py` .pdf branch;
  `job_manager._status_cb` already writes `job.current_segment`.

## Open Questions
None — root cause and fix seam are confirmed.

## Success Criterion
`GET /api/jobs/{id}` for a running PDF job returns `current_stage="translate"` with
non-null `current_segment_source` + `current_segment_draft` while translating.

## Requested Delivery Date / Priority
Follow-up fix to #7; normal priority.
