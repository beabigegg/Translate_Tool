# Archive — docx-body-textbox-dedup

## Change Summary

A DOCX body paragraph or table cell hosting a textbox had the textbox's text folded
into the paragraph/cell segment (via `_p_text_with_breaks`'s descendant `.//` xpath)
AND collected again by `_txbx_iter_texts` — translated twice, and the paragraph restore
misplaced the textbox translation into the paragraph body. The body walk now threads the
existing `_p_text_no_txbx` extractor (added for headers by BR-115), so a hosted textbox's
text is collected once via `_txbx_iter_texts`. This closes the body double-count BR-115
had explicitly deferred.

## Final Behavior

Textbox-bearing document: para/cell char count drops by the folded-textbox amount (~51
on `EN-P-QC1102-D7`), textbox text now collected once. Textbox-free document byte-identical.

## Final Contracts Updated

- `contracts/business/business-rules.md` 0.33.0 → 0.33.1: BR-115 scope amended to cover
  the body + table-cell paragraph extraction (collection + the three restore-idempotency
  reads).
- `contracts/CHANGELOG.md`: paired entry.

## Final Tests Added / Updated

`tests/test_docx_body_textbox_dedup.py` (10 tests). Flipped
`tests/test_docx_header_footer.py::...::test_body_paragraph_textbox_fold_in_unchanged`
(it had pinned the fold-in bug as correct under the pre-amendment BR-115 scope). Full
suite 1411 passed, 0 failed.

## Final CI/CD Gates

No new gate, no CI/CD contract change, no workflow edit.

## Production Reality Findings

- **The contract-reviewer corrected three of main Claude's seam facts before
  implementation** — `L123` is inside `_scan_our_tail_texts`, not `_txbx_iter_texts`;
  there is a THIRD restore site (`_scan_our_tail_texts` at L664); and the `tmap` key is
  fixed at collection, so only the body-walk swap is correctness-bearing while the three
  restore-site swaps are inert extractor-family hygiene. The AC-4 test was framed honestly
  (invocation spy), not as a tmap-miss claim. This is the promoted seam-verification rule
  working as intended.
- **A naive substring probe over-counted "remaining folds" on the real document** (4 of
  10), which were coincidental matches of common textbox strings (`判定`, `OK`, `年度计划`)
  appearing as genuine independent content elsewhere. The clean measure is the para/cell
  character delta (−53 on the textbox doc, 0 on the textbox-free doc). Recorded so a future
  reader does not mistake the substring noise for a missed path.

## Lessons Promoted to Standards

- **Contract (applied during the change):** BR-115's scope amendment (0.33.1) records the
  body/cell txbxContent-strip.
- **CLAUDE.md: none.** No new cross-change rule. The two candidate lessons are already
  covered — the contract-reviewer's seam correction is the existing seam-verification
  learning working as intended, and the substring-probe-over-count is a specific instance
  of the standing verify-by-precise-measurement discipline. Net growth 0.

## Follow-up Work

- The complete-but-shortened cell truncation guard (4,827→370 with ok=True) — the LAST
  user-picked change in this loop, design-heavy; calibration data gathered (E = 3.51·cjk +
  0.75·latin; k=0.3 flags 0/233 real pairs while catching the 0.077 truncation).
- `<w:sdt>` content controls inside DOCX table cells still dropped (probed earlier; absent
  in the real files).
- Header-anchored textboxes on Linux remain unhandled (pre-existing, not widened).

## Cold Data Warning

This archive is historical evidence. Current requirements live in `contracts/` and active
project guidance.
