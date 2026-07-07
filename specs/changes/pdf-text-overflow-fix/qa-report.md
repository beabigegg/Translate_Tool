# QA Report: pdf-text-overflow-fix

## Verdict
**release-ready-with-notes** — no blocking correctness bugs (independent qa-reviewer pass on the working-tree diff).

## Evidence
- Full suite `pytest tests/` = **1150 passed, 4 skipped, 0 failed** (torch env). The 13 `onnxruntime: import numpy failed` failures seen when running only the PDF subset are a pre-existing env/import-ordering artifact in layout_detector tests (`TestLayoutDetectorIntegration`, `TestReadingOrderModel`, `TestDpiUpgrade`, `TestPyMuPDFParserIntegration`, `TestReadingOrderField`) — NOT this change's tests, absent from the full run and from CI. Confirmed via full-run + git-stash-on-main baseline.
- `cdd-kit validate --contracts` = pass (43 env vars). BR numbering collision-free & sequential (siblings landed BR-98/99/100; this change → BR-101/102/103/104). Versions bumped: business 0.24.0, data-shape 0.16.0.
- test-evidence.yml phases collect/targeted/changed-area/contract = passed (scoped to the change's new test classes to avoid the onnxruntime landmine; `full` runs at CI).
- `fitz_renderer._insert_text_in_rect` cascade body byte-for-byte unchanged (only additive `available_whitespace_below` param) → AC-6 must-not-regress preserved.

## qa-reviewer findings (all focus areas pass)
1. Scope contained (only Allowed-Path files; `_split_elements_by_cells` untouched; `fit_text_to_bbox` retired from PDF paths per BR-40).
2. BR-101/102/103/104 used consistently across contracts, code, and test docstrings; verified-by columns match.
3. BR-103 row-growth: `_shift_cell_down` shifts bbox.y0/y1 AND every `metadata["lines"]` rect by the same delta (design Open Risk resolved), capped at local page budget, gated by `PDF_TABLE_ROW_GROWTH_ENABLED`, skips cleanly with no table metadata.
4. New tests are behavioral (line-y counts, numeric bbox deltas, exact coords, one-warning-per-file), not tautological; each fails if its fix is reverted.
5. BR-101 sanity gate (≥2 rows/cols, >2.0pt, ≥MIN_READABLE_FONT_PT height) prevents `strategy="text"` hallucinating a grid over prose (AC-7 holds).
6. AC-11: exactly one aggregated `job.warnings` entry per file, disclosure-only, fires on both render branches.

## Non-blocking notes (carried to PR + follow-up)
1. **Overlay-mode row-growth background collision (HIGH residual, documented).** In overlay mode the preserved source table rules are not shifted, so a grown row's text can cross them. Mitigated by `PDF_TABLE_ROW_GROWTH_ENABLED` (default `true`) + BR-104 disclosure; side-by-side unaffected. **Recommended human visual spot-check of an overlay-mode grown-table render (or defaulting the flag off) before wide production rollout** — flagged to the user in the PR. Not automatable in this pipeline; not a correctness blocker (output always safe + warned).
2. `full` phase not recorded as a cdd-kit run (full suite independently green + CI-scheduled).
3. ReportLab draw path passes hardcoded `available_whitespace_below=0.0` (within IP-9 scope; overflow handled upstream by `grow_table_rows` for both backends). Follow-up only if step-(d) cross-backend parity is later desired.

## Owner / follow-up
- Visual spot-check of overlay-mode row-growth → human/ops before wide rollout (kill-switch available).
