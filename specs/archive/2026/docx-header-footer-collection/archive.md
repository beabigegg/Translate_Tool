# Archive — docx-header-footer-collection

## Change Summary

DOCX header/footer paragraph text and tables were dropped on every OS: the native
collector walked only `doc._body`, and the only header-touching code — the
Windows-only COM postprocess — translates header-anchored SHAPES only, never header
paragraph or table text. The native path now collects, translates, and restores
header/footer paragraphs and tables (including nested) across all six per-section
`<w:hdr>`/`<w:ftr>` slots on both OSes, reusing the BR-113/BR-114
`_process_container_content` / `_process_table` walkers — zero new table/restore code.

## Final Behavior

On the two real documents, header/footer-only unique texts missing dropped 7→0 and
9→0 (`编制单位`, `版本/版次`, page numbers, etc.). Both headers are 15-cell tables now
fully collected.

## Final Contracts Updated

- `contracts/business/business-rules.md` 0.31.0 → 0.32.0: BR-115
  (`header-footer-native-collection`).
- `contracts/CHANGELOG.md`: paired entry.
- `docs/adr/0019-native-header-footer-com-shape-boundary.md`.

## Final Tests Added / Updated

`tests/test_docx_header_footer.py` (14 tests, all fixtures in-test, none reads
`docs/TEST_DOC/`). Full suite 1393 passed, 0 failed.

## Final CI/CD Gates

No new gate, no CI/CD contract change, no workflow edit. Blanket sweep covers the
new file; golden-sample-regression covers AC-6.

## Production Reality Findings

- **A classifier-framed "mutual-exclusion invariant" was a phantom.** The change was
  framed as needing COM-vs-native mutual exclusion over headers. Live source
  (com_helpers.py L126-133) showed the COM pass touches header SHAPES only, never
  header text/tables — so the two paths were ALREADY disjoint and exactly-once holds
  by construction. Building a mutual-exclusion switch would have encoded a conflict
  that does not exist; the classifier's "obvious candidate" (`include_headers=False`)
  would have silently regressed Windows header-shape translation. Caught by
  spec-architect reading source, confirmed by main Claude. ADR-0019.
- **One real overlap did exist and was fixed cleanly (Option C).**
  `_p_text_with_breaks`'s `.//` xpath folds a hosted textbox's text into its
  paragraph string, which the COM shapes pass would also translate on Windows → double
  translation. Resolved by a NEW `_p_text_no_txbx` used only by the header/footer
  walk; the body path is byte-for-byte unchanged (AC-6).
- **The pre-existing body textbox double-count was discovered and left alone.**
  `_collect_docx_segments` on a body paragraph+textbox emits the textbox text BOTH
  folded into the para segment AND via `_txbx_iter_texts`. Pre-existing, out of scope,
  documented so it is not attributed to this change.
- **An AC-4 test was nearly a tautology.** A linked-part dedup test built on a
  paragraph fixture stays green even with the part-level guard removed, because the
  pre-existing `seen_par_keys` masks it. The genuine guard is a header TABLE-CELL
  fixture (`seen_tc` is per-table, no cross-slot dedup). Corrected to a table-cell
  fixture before merge.
- **The dedup has two independently-sufficient guards** (the `is_linked_to_previous`
  short-circuit and the `seen_parts` element set); the test's RED condition is "both
  removed". QA flagged the regression-report wording; corrected before merge.

## Lessons Promoted to Standards

- **Contract (applied during the change):** BR-115 encodes the native header/footer
  behavior, the txbxContent-strip precondition, the element-identity linked-part
  dedup, and the disjoint-domain COM boundary. ADR-0019 records the phantom
  mutual-exclusion finding.
- **CLAUDE.md (promoted at close):** folded ONE clause into the existing no-shell-agent
  seam-verification learning — the duty to verify a classifier-framed CONFLICT (a
  "mutual-exclusion invariant" / "double-translation") against live source before
  building machinery for it, since the two paths may already own disjoint domains and
  the "obvious" reconciliation can silently regress the innocent path. Net growth ≈ 0
  (folded, not appended); points to ADR-0019.
- **Not re-promoted:** the `id()`-on-lxml-proxy rule (already a CLAUDE.md line from
  `docx-nested-table-collection`, reinforced here by `seen_parts`); the
  tautological-test taxonomy (the AC-4 paragraph-fixture masking is a known instance of
  form (2) selection-not-count).

## Follow-up Work

- Header-anchored textboxes on Linux remain unhandled (pre-existing textbox-scope
  gap; COM owns them on Windows). Absent in the real files. Separate change.
- The body's pre-existing textbox double-count (`_p_text_with_breaks` fold +
  `_txbx_iter_texts`) is untouched. Separate change if it matters.
- PPTX group shapes (`for shape in slide.shapes` skips `GroupShape.shapes`) — the next
  queued change in this loop; facts already probed.

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and
active project guidance.
