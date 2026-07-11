# Archive — docx-nested-table-collection

## Change Summary

The DOCX `<w:tbl>` walk read only each cell's direct paragraphs and never
descended into `cell.tables`, silently dropping every nested table — 65 of 275 and
218 of 523 body paragraphs (7.3% and 25.2% of text) on the user's two real
documents. It also emitted a horizontally-merged `<w:tc>` once per spanned column,
translating a 4,827-char layout-frame cell four times. This change makes the walk
recurse into nested tables (each its own group, own private coordinate space,
bounded depth with flatten-and-warn), reroutes a structurally-identified
layout-frame cell's prose to the body path, and deduplicates a merged cell by
element identity.

## Final Behavior

Both documents now collect 100% of body text. Table groups collected: 1→3 and 1→7.
Redundant emitted characters: 26,203→101. Largest single cell handed to the LLM:
8,729→207 chars. `docx_processor.py` contains no `id()`-keyed collection.

## Final Contracts Updated

- `contracts/business/business-rules.md` 0.30.0 → 0.31.0: BR-113
  (`nested-table-collection`), BR-114 (`layout-frame-cell-reroute`), BR-81 amended
  (element-identity dedup, key shape unchanged), two Table T rows.
- `contracts/data/data-shape-contract.md` 0.18.0 → 0.18.1: nested-table identity /
  payload-boundary note, legacy pipe-grid degrade note, consumers-row update.
- `contracts/CHANGELOG.md`: paired entries for both bumps.
- `docs/adr/0018-nested-table-frame-routing.md`.

## Final Tests Added / Updated

`tests/test_docx_nested_tables.py` (13 tests, all fixtures built in-test with
python-docx, none reads `docs/TEST_DOC/`). Full suite 1375 passed, 0 failed.

## Final CI/CD Gates

No new gate, no CI/CD contract change, no workflow edit. A drafted targeted-test
step was withdrawn: the blanket sweep already collects the new file, and the
workflow already carries six stale steps for archived changes — see Follow-up.

## Production Reality Findings

- **`id(cell._tc)` cannot key a dedup set.** CPython recycles a freed lxml proxy's
  address; a walk recording `id()` without retaining the element saw 8 distinct
  keys for a 60×5 table's 300 cells. The pre-existing `id()` keys
  (`id(child_element)`, `id(p._p)`) were correct only by an unstated invariant —
  every recorded key's element was transitively held by an already-emitted
  `Segment`. This change moved all of them to element/counter identity.
- **An overclaim was authored, then caught and corrected before merge.** The first
  contract draft said an `id()`-keyed set "would turn the 17% drop into 95%".
  Sabotage showed the main cell loop masks the hazard (13/13 green under `id()`
  keys); only the no-retention flatten path breaks. The rule stands on the
  invariant-fragility argument, not on a false blast radius. Evidence:
  `evidence/id-key-hazard.md`.
- **The 17.1%/35.8% figures in change-request.md were not reproducible** — they used
  the emitted-character denominator, which double-counts the merged cell. Contracts
  cite the reproducible 7.3%/25.2%. Evidence: `evidence/real-document-coverage.md`.

## Lessons Promoted to Standards

- **Contract (already applied during the change):** the `id()`-on-lxml-proxy
  prohibition is encoded in BR-81 and BR-113, with evidence in
  `evidence/id-key-hazard.md`. Not re-promoted; it lives in the contracts.
- **CLAUDE.md (promoted at close):** two one-line rules folded into the learnings
  region — (1) never key a collection on `id()` of a python-docx/lxml proxy; verify
  by sabotage, don't over-state blast radius; (2) silent-drop-by-non-recursion is a
  class — sweep sibling containers and sibling-format processors when fixing one
  walk gap. Both point to this change's contracts/evidence for detail.

## Follow-up Work

- **Silent-drop audit surfaced three more "un-walked container" defects of the same
  class**, confirmed by probe during this change: DOCX headers/footers (Linux has no
  COM path — live on both of the user's documents, 293/282 chars each), PPTX group
  shapes (`for shape in slide.shapes` does not recurse `GroupShape.shapes`), and
  `<w:sdt>` content controls inside table cells (top-level handled, cell-level not).
  Headers/footers and PPTX groups are the next two changes in this loop.
- A general per-cell length-ratio truncation guard remains unbuilt. Cache-derived
  data (180 real pairs) shows the expansion ratio runs 0.8×–4.9× with source
  CJK-density, so a fixed threshold would false-positive; the guard must model
  source script composition. Separate change.
- The BR-109 doc-context sampler still walks only top-level `doc.tables`.
- The `tmap` key omits `table_id` (pre-existing, benign, now documented).
- Six stale targeted-test steps for already-archived changes remain in
  `.github/workflows/contract-driven-gates.yml` (`term-extraction-db-first`,
  `fallback-chain-cloud-providers`, `p3-table-structure`, `p3-llm-judge`,
  `pdf-renderer-fallback-warn`, and the whole `expose-output-mode-ui-gate` job).
  Removed at this close-out per the CLAUDE.md whole-workflow-sweep rule.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and
active project guidance.
