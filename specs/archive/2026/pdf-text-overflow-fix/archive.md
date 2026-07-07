# Archive: pdf-text-overflow-fix

## Change Summary
Translated PDF text overflowed its bbox on the side-by-side and ReportLab-fallback
render paths (only the fitz overlay path wrapped), and 1:1 table cells got a tight
bbox so per-cell text spanned columns. This change makes `fit_text_cascade`/
`_wrap_lines_simple` the ONE shared fit/wrap authority across all PDF render paths,
corrects table-cell geometry, and (amendment) adds a bounded local table-row-growth
stage before truncation plus a truncation-disclosure warning. Independent PDF
subsystem — no overlap with the judge-subsystem chain (#1-#3). Tier 2, feature lane.
Implemented by a backend-engineer agent (IP-1..IP-15), independently qa-reviewed.

## Final Behavior
- All PDF paths (fitz overlay, side-by-side, ReportLab fitz-crash fallback) wrap
  translated text within the bbox via the single shared cascade; truncation sets
  `render_truncated` (BR-38, BR-40 amended to a shared-authority rule).
- Borderless/thin tables recovered via a sanity-gated looser-strategy `find_tables()`
  fallback (BR-101); 1:1 block→cell bbox extended to true cell extent (BR-102).
- `available_whitespace_below` computed once in `bbox_reflow`, carried on `Placement`,
  consumed at the fitz cascade call (AC-9). Bounded table row-growth (BR-103), gated
  by `PDF_TABLE_ROW_GROWTH_ENABLED` (default true), shifts lower rows' bbox AND
  `metadata["lines"]` by an identical delta, capped at the table's local page budget.
  Residual truncation surfaces as one aggregated `job.warnings` entry per file (BR-104).
- fitz overlay `_insert_text_in_rect` cascade body unchanged (AC-6 must-not-regress).

## Final Contracts Updated
- `business-rules.md` — BR-40 amended, BR-36 clarifying note, BR-101/102/103/104 added
  (renumbered from the plan's 98/99/100/101 because siblings #2/#3 landed BR-98/99/100).
  Version 0.23.0 → 0.24.0.
- `data-shape-contract.md` — table_cell bbox-extent invariant + default-path metadata-keys
  section (`table_id`/`table_row`/`table_col`/`in_table`/`lines`). Version 0.15.0 → 0.16.0.
- `env-contract.md` / `.env.example.template` / `env.schema.json` — `PDF_TABLE_ROW_GROWTH_ENABLED`
  (CER-003 manifest expansion).

## Final Tests / Verification
- 8 PDF test files extended + new classes: wrap/no-silent-truncation, table-detection
  fallback + false-positive gate, 1:1 cell bbox, whitespace-below, bounded row-growth
  (bbox + `metadata["lines"]` delta parity, budget cap, no-metadata skip), truncation
  disclosure, dual-backend convergence. Behavioral, not tautological (qa-reviewer confirmed).
- Full suite 1150 passed, 4 skipped, 0 failed. `cdd-kit validate --contracts` green.
  4 evidence phases green. PR #17 CI all required gates green.

## Production Reality Findings
- **onnxruntime test-isolation artifact:** layout_detector tests (`TestLayoutDetectorIntegration`,
  `TestReadingOrderModel`, `TestDpiUpgrade`, `TestPyMuPDFParserIntegration`, `TestReadingOrderField`)
  fail with `onnxruntime: import numpy failed` when run as a scoped PDF subset, but PASS in the
  full suite and in CI (import-ordering dependent). Not this change's tests; a pre-existing env quirk.
- **Overlay-mode row-growth background collision (HIGH residual, documented):** in overlay mode the
  preserved source table rules are not shifted, so a grown row can cross them. Flag-gated
  (`PDF_TABLE_ROW_GROWTH_ENABLED` default true) + BR-104-disclosed; a human overlay visual
  spot-check is recommended before wide production rollout (surfaced in PR #17). Not a blocker.
- Agent deviations (all sound, qa-reviewer-approved): threaded style/element into `_render_side_by_side`;
  extended `test_coordinate_renderer.py` (in manifest, mapped in test-plan); additive
  `available_whitespace_below` param on `_insert_text_in_rect`; strengthened BR-101 sanity gate with a
  `MIN_READABLE_FONT_PT` height floor to avoid hallucinating a table over real prose.

## Lessons Promoted to Standards
1. **[promote-to-guidance]** `CLAUDE.md` cdd-kit:learnings — onnxruntime/numpy test-isolation gotcha:
   scope PDF/layout `cdd-kit test run` evidence phases to the change's NEW test classes by node-id, not
   whole `test_pdf_*` files, because layout_detector tests fail on `import numpy failed` in a scoped
   subset (pass in the full run / CI).
- Not promoted: the BR-number-collision-renumber discipline is already covered by the plan's
  "re-check live BR number at edit time"; the row-growth/disclosure behavior is product contract
  (BR-101..104 + ADR-0013).

## Follow-up Work
- Human overlay-mode visual spot-check of grown-table render before wide rollout (kill-switch available).
- `qa-mechanism-docs` (#6) is independent of this change; `#5`/`#7` unaffected (no file overlap).

## Cold Data Warning
This archive is historical evidence. Current requirements live in `contracts/` and active project guidance.
