# Regression Report — docx-header-footer-collection

The classifier required this report because the change alters observable output on
every DOCX translation job. Two risks needed durable evidence: that body/table
output is unchanged (AC-6), and that Windows is not double-translating (AC-3).

## 1. Body output unchanged (AC-6)

Header/footer collection is appended AFTER the body walk, so body segment indices
0..N-1 and the `docx:{stem}:{idx}` hook numbering are untouched. The txbxContent
strip is a NEW helper (`_p_text_no_txbx`) used only by the header/footer walk via a
threaded `text_extractor` parameter defaulting to `_p_text_with_breaks`; the body
call keeps the default, so `_p_text_with_breaks` and the body path are byte-for-byte
unchanged.

Green, no edits required: `tests/test_golden_regression.py`,
`tests/test_docx_nested_tables.py`, `tests/test_docx_parser.py`,
`tests/test_output_mode_processors.py`, `tests/test_ir_pipeline_decoupling.py`.
Full suite passed (`test-evidence.yml`, phase `full`), evidence timestamp verified
to postdate every source/test/contract file it covers.

Falsifiability (backend-engineer, snapshot→sabotage→restore, never `git checkout`):
moving header/footer collection BEFORE the body walk turns
`TestBodyIndicesUnaffectedByHeaderCollection` RED (`'HEADER_MARKER' == 'Body para 0'`).
The plain `ctx`-filtered order test alone stayed green under that sabotage — which is
why absolute-index and hook-block-id assertions were added as the real guard.

## 2. No double-translation on Windows (AC-3)

Verified against live source (main Claude + spec-architect, ADR-0019):
`postprocess_docx_shapes_with_word` iterates `sec.Headers/Footers(...).Shapes` →
`TextFrame` only — it never touches header paragraph or table text. So the native
path (paragraph text + tables) and the COM pass (header-anchored shapes) own
disjoint content domains, and each unit is translated exactly once by construction,
on both OSes, with no mutual-exclusion switch. The COM call site's `include_headers=True`
is unchanged (setting it False would regress Windows header-shape translation).

The one overlap hazard — `_p_text_with_breaks`'s `.//` xpath folds a hosted
textbox's text into its paragraph, which the COM shapes pass would also translate —
is removed by the txbxContent strip. Falsifiability: reverting the header extraction
to `_p_text_with_breaks` turns `TestTxbxContentStrippedFromHeader` RED
(`'HDR_PLAINTB_TEXT' == 'HDR_PLAIN'`). A call-site guard asserts the mocked COM
function still receives `include_headers=True`. This guarantee is unobservable on the
Linux CI (COM absent); it is pinned as a unit assertion, not a Windows integration
test.

## 3. Linked/shared-part collected once (AC-4)

`seen_parts` holds the `<w:hdr>`/`<w:ftr>` ELEMENTS (never `id()` — BR-81/BR-113).
Confirmed by live probe (`evidence/probe_r1_slots_and_linking.py`): a second
section's linked header returns `is_linked_to_previous == True` AND
`s2.header._element is section0.header._element` — the same element object — so the
set dedups by construction.

Two falsifiability nuances, both verified by sabotage (QA re-verified independently):

(1) **Table-cell fixture, not paragraph.** Removing the part-level dedup leaves the
two plain-paragraph AC-4 tests GREEN, because the pre-existing paragraph-level
`seen_par_keys` set already dedups repeated paragraph elements. The load-bearing
case is a header **table cell**: `_process_table`'s `seen_tc` is a fresh local set
per call with no cross-slot dedup, so a linked header table walked once per
referencing section would double-emit its cells. `TestLinkedPartCollectedOnce::test_linked_header_table_cell_collected_exactly_once`
is the genuine guard; a paragraph fixture would have been a tautology masked by
`seen_par_keys`.

(2) **Two independently-sufficient guards, not one.** The linked-part collection is
protected by BOTH `if slot.is_linked_to_previous: continue` (docx_processor.py L450)
AND the `seen_parts` element-identity set (L453). For a linked slot the first guard
short-circuits before the element is even read, so the second never fires — and vice
versa. Removing EITHER one alone leaves the table-cell test GREEN; only removing BOTH
reproduces `2 == 1`. `seen_parts` is the general guarantee (it catches element
sharing by any mechanism, not only `is_linked_to_previous`); the `is_linked`
short-circuit is an optimization that also happens to suffice for the common linked
case. This is redundant defense-in-depth, a strength, not a gap — but the test's RED
condition is "both guards removed", which this report states precisely rather than
attributing the RED to a single guard.

## 4. Real-document verification

`evidence/real-document-coverage.md`. Unique header/footer texts missing:
7→**0** and 9→**0** on the two real files. Examples collected-after, dropped-before:
`编制单位`, `第9页共12页`, `版本/版次`. Both headers are 15-cell tables now fully
collected. (Missing-before is <11 because a few header texts also appear in the body
and were already collected there.)

## 5. Residual risk (documented, owned, non-blocking)

- Header-anchored textboxes on Linux remain unhandled — pre-existing textbox-scope
  gap (COM owns them on Windows). Absent in the real files. Separate change.
- The body's pre-existing textbox double-count (`_p_text_with_breaks` fold +
  `_txbx_iter_texts`) is untouched. Pre-existing; out of scope; flagged so a future
  reader does not attribute it here.
- PPTX/XLSX headers are a different surface, not in scope. (PPTX group shapes are the
  next queued change.)

## Verdict

No regression found. Body output stable (AC-6), disjoint-domain exactly-once holds
(AC-3), linked parts deduped (AC-4), real documents fully collected (AC-1).
