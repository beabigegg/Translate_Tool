# Regression Report — docx-body-textbox-dedup

The classifier required this report because the change alters body-path extraction on
a code path every DOCX job runs. Two risks needed durable evidence: that textbox-free
output is unchanged (AC-5), and that the collection/restore extractor-family stays
consistent (AC-4).

## 1. Textbox-free output unchanged (AC-5)

The fix threads `_p_text_no_txbx` into the body walk `_process_container_content(doc._body,
"Body", 1)` at L429. That extractor differs from `_p_text_with_breaks` ONLY in excluding
`<w:txbxContent>` text — so for any paragraph or cell that hosts no textbox, the output
is byte-identical.

Real-document proof (`evidence/real-document-dedup.md`): the textbox-free document
`W-RM0901-G6` collects **7715 para/cell chars before and after — 0 delta**. Green suites:
`tests/test_golden_regression.py`, `tests/test_docx_parser.py`, `tests/test_docx_nested_tables.py`.
Full suite passed (`test-evidence.yml`, phase `full`), evidence timestamp postdates every
covered file.

## 2. Body/cell textbox fold eliminated (AC-1, AC-2, AC-3)

Bug-fix RED (`test-runs/20260711-113501`): `test_body_paragraph_excludes_textbox_text`
failed with `AssertionError: assert 'BODY_PLAINTB_TEXT' == 'BODY_PLAIN'` — a genuine
behavioral failure (the textbox text was folded into the paragraph segment). Green after
the fix.

Real-document proof: `EN-P-QC1102-D7` (10 body textboxes, 51 txbx chars) drops from
10177 to 10124 para/cell chars — the ~51 folded characters are removed, so the textbox
text is now collected exactly once via `_txbx_iter_texts` (`txbx_chars` = 51, unchanged).
Falsifiability: reverting the L429 `text_extractor=_p_text_no_txbx` turns AC-1/AC-2/AC-3
RED (bug-fix-engineer, snapshot-sabotage; re-confirmed by main Claude).

## 3. Extractor-family consistency (AC-4) — stated honestly

The `tmap` key `(tgt, seg.text, seg.col)` is fixed at COLLECTION (L429), so the body-walk
swap is the sole correctness-bearing edit. The three restore-time resume-idempotency reads
— the SDT branch (L552), the cell branch (L598), and `_scan_our_tail_texts`'s internal
call (L123) — were also switched to `_p_text_no_txbx`, but this is **inert to their
result**: those reads only ever see paragraphs the pipeline itself inserted (plain runs +
`INSERT_MARKER`, never a nested textbox). The swap is family-consistency hygiene, not a
tmap-miss fix. The AC-4 test asserts `_p_text_no_txbx` is actually invoked at those sites
via a spy across a resume-idempotency pass — it does not claim a collision the sites
cannot suffer. This framing is per the contract-reviewer's correction, which also fixed
two mis-cited seams in the original change-request (L123 is in `_scan_our_tail_texts`, not
`_txbx_iter_texts`; there is a THIRD restore site).

## 4. A pinning test was intentionally flipped

`tests/test_docx_header_footer.py::TestTxbxContentStrippedFromHeader::test_body_paragraph_textbox_fold_in_unchanged`
was written under the pre-amendment BR-115 scope to assert `body_seg.text ==
"BODY_PLAINTB_TEXT"` — i.e. it PINNED the fold-in bug as correct, guarding the header
change against globally altering the body. This change deliberately reverses that scope
(amended BR-115), so the assertion was flipped to `body_seg.text == "BODY_PLAIN"` plus
`"TB_TEXT" not in body_seg.text`, and its docstring updated. This is an intended contract
alignment, not a regression — without it the flipped body behavior and the amended BR-115
would contradict each other.

## 5. Residual risk (non-blocking)

- Header-anchored textboxes on Linux remain unhandled (pre-existing textbox-scope gap;
  COM owns them on Windows). Not widened here.
- `_p_text_with_breaks` is now referenced only as the closures' default parameter value
  (every live call site passes `_p_text_no_txbx`); it is retained, not dead, and left
  unchanged to avoid touching the byte-for-byte header/footer invariants.

## Verdict

No regression found. Textbox-free output byte-identical (AC-5), body/cell fold eliminated
(AC-1/2/3), extractor-family consistent (AC-4), the pinning test correctly realigned to
amended BR-115.
