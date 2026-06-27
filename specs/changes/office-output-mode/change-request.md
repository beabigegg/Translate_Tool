# Change Request

## Original Request

Wave 3 Track F — implement Office output modes (improvement-plan §階段 2):
- 2.1 新增「雙語雙欄 DOCX」輸出模式: original text and translation in separate columns/paragraphs, not stacked in the same run. Industry standard (DeepL, Smartcat, Crowdin, Phrase, Trados all provide bilingual dual-column DOCX export).
- 2.2 XLSX add output_mode: three choices — adjacent column (translation in next column), annotation (cell comment), replace (overwrite source). Currently XLSX is hard-coded to "src\n譯文" + wrap_text, causing row height explosion.
- 2.3 DOCX table cell / SDT / text box + PPTX SmartArt: add replace branch. Currently these are hard-coded append; `output_mode=replace` has no effect on them.

## Business / User Goal

Users currently have no control over bilingual output layout in Office formats. The only options are "translation stacked below original" or "original disappears". Standard CAT/MT platforms export dual-column DOCX as a basic feature. XLSX append causes severe row height inflation making spreadsheets unusable. DOCX table cells ignore output_mode entirely.

## Non-goals

- PDF output mode changes (handled by separate Track G, already done)
- New frontend UI for output_mode selection (already shipped in Wave 1 Track A, expose-output-mode-ui)
- New translation quality features (Track H)
- Implementing a true "page-interleave" mode like pdf2zh (out of scope for this wave)

## Constraints

- Track D (table-context-translation) must already be merged to main before this track starts (shared ownership of processors/{docx,xlsx,pptx}_processor.py)
- No API surface changes: `output_mode` field already exists in `api/schemas.py`; no new endpoints
- Must not regress existing append/replace behavior in the paths that already work

## Known Context

- `output_mode` = append (default) / replace already exists in `api/schemas.py:11-13` but:
  - Frontend now sends it (Wave 1 Track A merged)
  - XLSX ignores it entirely (`xlsx_processor.py:192-208` hard-coded append)
  - DOCX table cell/SDT/text box and PPTX SmartArt have no replace branch
  - 2.1 "bilingual dual-column" is a NEW third mode not in the current schema
- Affected files: `processors/docx_processor.py`, `processors/xlsx_processor.py`, `processors/pptx_processor.py`, `api/schemas.py` (new mode value), `contracts/api/api-contract.md`, `contracts/data/data-shape-contract.md`

## Open Questions

None — improvement-plan §階段 2 acceptance criteria are clear.

## Requested Delivery Date / Priority

Wave 3, parallel with Track H. High priority.
