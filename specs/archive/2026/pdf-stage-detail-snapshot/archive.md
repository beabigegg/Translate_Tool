# Archive — pdf-stage-detail-snapshot

## Change Summary
Follow-up bug-fix to `translation-progress-detail-ui` (#7, BR-105). The live
progress-detail snapshot fields (`current_stage` / `current_segment_source` /
`current_segment_draft`) never populated for **PDF** jobs, so the frontend
StageDetailPanel showed no current-segment source/draft for the most common
format here. Root cause: the PDF pipeline `pdf_processor.translate_pdf` →
`translate_blocks_batch` bypasses `translation_service.translate_texts` (the only
call site #7 wired for `CurrentSegmentSnapshot`), and `translate_pdf` had no
`status_callback` parameter, so PDF jobs never reached `job_manager._status_cb`.
Fix is additive/observational: thread an optional `status_callback` into
`translate_pdf` and its 3 flatten-batch sub-functions, and emit a snapshot from
each `translate_blocks_batch` call's existing `on_segment_done` hook.

## Final Behavior
For a running PDF job, `GET /api/jobs/{id}` now returns `current_stage="translate"`
with non-null `current_segment_source` + `current_segment_draft` while translating,
matching Office (DOCX/PPTX/XLSX). Only the `translate` stage applies for PDF (batch
translation — no critique/QE/adopt loop). Office and judge snapshot paths unchanged.

## Final Contracts Updated
- `contracts/data/data-shape-contract.md` — additive PDF-path parity note under the
  JobStatus/JobRecord current-segment snapshot section; `schema-version` 0.17.2 → 0.17.3.
- `contracts/CHANGELOG.md` — `[data 0.17.3] — 2026-07-08` entry.
- `contracts/api/api-contract.md` — no change (JobStatus snapshot fields already
  declared by #7, format-agnostic; this is a values-populate fix, not a schema change).

## Final Tests Added / Updated
- `tests/test_pdf_stage_snapshot.py` (new) — 3 anti-tautology tests that fire
  `on_segment_done` and assert exact `stage`/`source`/`draft` + single-overwrite;
  includes AC-8 repro `test_pymupdf_path_on_segment_done_emits_translate_stage_snapshot`.
- `tests/test_job_manager_current_segment.py` (extended) — real end-to-end
  `create_job → process_files → translate_pdf` .pdf case, only `translate_blocks_batch` mocked.
- Full backend sweep: 1191 passed, 4 skipped, 0 failed (translate-tool conda env).

## Final CI/CD Gates
- `contract-and-fast-tests` (required) — blanket `pytest tests/` + `cdd-kit validate
  --contracts`; picks up the new/edited tests with no workflow edit. **Green on PR #21.**
- `full-regression` (informational) — **green on PR #21.**
- Format/renderer gates (golden-sample, renderer-equivalence, libreoffice, text-expansion,
  expose-output-mode-ui, layout-detector-dependency) — **all green on PR #21.**
- Local `cdd-kit gate --strict` (pre-commit) — green.
- No new workflow, job, secret, or retention change.

## Production Reality Findings
- The PDF path uses `translate_blocks_batch`, NOT `translate_texts`, so it has no
  critique/QE/adopt loop — only the `translate` stage snapshot is emitted (by design).
- Two out-of-scope PDF sub-paths do not emit the snapshot and were intentionally not
  wired: the Windows-only COM `word_convert` route inside `translate_pdf`, and the
  `_translate_pdf_tables_with_context` table-cell path (per implementation-plan Known
  Risks; AC-3 scopes only the 3 flatten-batch sub-functions).
- The #7 unit tests + qa-review missed this gap because they exercised `translate_texts`
  directly and never a real PDF orchestration run — the defect surfaced only on the
  user's live PDF run. (Root learning already promoted by #7 lineage; see Follow-up.)

## Lessons Promoted to Standards
- **promote-to-contract** (contract-reviewer approved): `contracts/data/data-shape-contract.md`
  → `### JobStatus / JobRecord — current-segment snapshot fields` — added an **Architecture
  note** documenting the three independent per-segment translation entry points
  (`translate_texts` = Office, `translate_blocks_batch` = PDF, `translate_document` =
  chunked Doc2Doc); a cross-cutting per-segment concern wired at only one entry point
  leaves the others silently unpopulated (as happened for PDF here), so future per-segment
  concerns must be wired AND tested through each format's real entry point. `schema-version`
  0.17.3 → 0.17.4 + `contracts/CHANGELOG.md` `[data 0.17.4]` entry.
  Evidence: `agent-log/bug-fix-engineer.yml` `root_cause` (L42-44); this archive's
  "Production Reality Findings".
- **No CLAUDE.md growth**: the test-side manifestation (a test exercising only one seam
  passes while the other format is unwired) is already generalized by the existing
  `cdd-kit:learnings` tautological-tests entry, form "(1b) wrong entry point". Not folded
  into the "shared module / verify consumer imports" entry — the two seams never
  import/reference each other, so a grep-the-importers check would not have caught it.

## Follow-up Work
- **N1 (non-blocking, deferred):** the PDF path does not emit a terminal
  `status_callback(None)`, so a completed PDF job leaves `current_segment` frozen at
  the last translate segment (Office clears it). Harmless terminal-state parity gap;
  not fixed to keep scope tight. Candidate for a future small parity change.

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and
active project guidance.
