# Change Request

## Original Request

DOCX body paragraph text that hosts a textbox is translated twice and the textbox translation is misplaced into the paragraph body. In `app/backend/processors/docx_processor.py`, the body/cell paragraph extraction uses `_p_text_with_breaks` (L38) whose descendant-or-self `.//` xpath reaches INTO a hosted `<w:txbxContent>` and folds the textbox's text into the paragraph string; the dedicated textbox path `_txbx_iter_texts` (L131) ALSO collects that same textbox text separately.

Affected surface: docx_processor.py body + table-cell paragraph extraction (collection AND restore-matching).
Desired behavior: the body and table-cell paragraph extraction excludes `<w:txbxContent>` text (reuse the existing `_p_text_no_txbx` helper added for headers/footers, BR-115), so a hosted textbox's text is collected and translated exactly once via the dedicated `_txbx_iter_texts` path and restored only to the textbox, not duplicated/misplaced into the enclosing paragraph.
Success criterion: a synthetic body paragraph (and a table cell) hosting a textbox yields the textbox text in exactly one collected unit (the txbx segment), zero occurrences folded into the para/cell segment, translated once; existing body output WITHOUT textboxes is unchanged.

Verified facts (main Claude, live probes):
- Live repro: a body paragraph "BODY_PLAIN " + a textbox "TEXTBOX_TEXT" yields a `para` segment 'BODY_PLAIN TEXTBOX_TEXT' AND a `txbx` segment 'TEXTBOX_TEXT'. `_p_text_no_txbx` already yields 'BODY_PLAIN' correctly.
- The body walk is driven by `_process_container_content(doc._body, "Body", 1)` at L427 with the DEFAULT `text_extractor=_p_text_with_breaks`. The header/footer walk already passes `_p_text_no_txbx` (L458). The threading param already exists on `_add_paragraph`/`_cell_direct_text`/`_process_table`/`_process_container_content`.
- `_txbx_iter_texts` walks `doc._element` (`.//txbxContent`), so it catches textboxes in body paragraphs AND in table cells — both are double-counted today.
- CRITICAL consistency requirement: the restore/matching pass uses `_p_text_with_breaks` at L550 (paragraph) and L596 (cell). If collection excludes txbxContent but restore matching does not, the tmap key lookup will MISS and restore will fail. Collection AND both restore-matching sites must use the SAME extractor (`_p_text_no_txbx`).
- No golden regression fixture contains a body textbox (grep of tests/ found none), so no golden re-baseline is required; the change is behavior-neutral for all textbox-free documents.
- One real user document (EN-P-QC1102-D7) has 10 body textboxes.
- Out of scope: `_txbx_iter_texts`'s OWN internal use of `_p_text_with_breaks` at L123 (it correctly extracts the textbox's own paragraphs — leave it); the header/footer path (already fixed, BR-115).
## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
