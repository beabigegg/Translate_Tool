# Change Request

## Original Request

DOCX header and footer text is never translated on Linux. The orchestrator only translates headers/footers through a Windows-only COM postprocess path (postprocess_docx_shapes_with_word, gated by is_win32com_available which is False on this host), so on Linux _collect_docx_segments walks only doc._body and every section header/footer is silently dropped. Verified live on both of the user's real .docx files: EN-P-QC1102-D7 has a 293-char header (a table with 15 text cells) plus footer, W-RM0901-G6 has a 282-char header (also a 15-cell table) plus footer — none translated.

Affected surface: app/backend/processors/docx_processor.py header/footer collection + restore.
Desired behavior: header and footer content (paragraphs AND tables, including nested tables, reusing the BR-113/BR-114 _process_container_content walker) is collected, translated, and written back natively via python-docx regardless of COM availability, without double-translating on Windows where the COM path also handles headers.
Success criterion: on Linux, both real documents' header/footer text is fully translated in the output (0 header/footer paragraphs or table cells left in the source language), and existing body/table translation is unchanged.

Verified facts (main Claude, live probes):
- is_win32com_available() returns False on this host; the COM postprocess (postprocess_docx_shapes_with_word, include_headers=True) at docx_processor.py L1102-1103 is the ONLY header/footer path and never runs on Linux.
- Both real docs: section header is a <w:tbl> with 15 text cells (~293/282 chars); footer is a single paragraph (page number). is_linked_to_previous=False, 1 section each.
- _Header/_Footer expose ._element (the <w:hdr>/<w:ftr> root) whose children iterate as p/tbl exactly like doc._body, so _process_container_content is directly reusable.
- Write-back to a run's .text inside a header persists across doc.save() (proven).
- section exposes header, first_page_header, even_page_header and the three footer variants; each has is_linked_to_previous. Shared/linked parts must be collected once, not per-referencing-section.
## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
