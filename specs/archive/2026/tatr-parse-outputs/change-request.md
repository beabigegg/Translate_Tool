# Change Request

## Original Request

Implement table_recognizer _parse_outputs: parse TATR grid detection output to real row/col TableStructure (item 1.3 of improvement plan / P3-3 in docs/improvement-plan.md).

Currently `_parse_outputs()` in `app/backend/parsers/table_recognizer.py` (lines 279–307) is a stub that always returns a single 1×1 empty cell, making the entire table structure recognition pipeline non-functional even when TABLE_RECOGNITION_ENABLED=true.

## Business / User Goal

Enable real cell-level table translation by providing correct row/col grid structure from TATR detection output. This unlocks Wave 2 (Track D) table context translation, which requires a real TableStructure IR with correct grid positions.

## Non-goals

- Do not redesign the rest of TableRecognizer or change the ONNX session loading logic
- Do not assign cell content (text extraction is done elsewhere)
- Do not enable TABLE_RECOGNITION_ENABLED by default

## Constraints

- TATR (Table Transformer) outputs: pred_logits (1,N,num_classes) and pred_boxes (1,N,4) in CXCYWH normalized format
- Categories detected: "table row", "table column", "table spanning cell" (and "table", "table projected row header")
- Row bboxes sorted by y-coordinate → row indices 0,1,2...
- Column bboxes sorted by x-coordinate → col indices 0,1,2...
- Cell assignment via IoU overlap between row-bbox and column-bbox intersections
- Content remains "" (filled by pdf_parser text extraction)
- Tests must be SELECTION tests, not just count assertions (CLAUDE.md anti-tautology rule)

## Known Context

- `app/backend/parsers/table_recognizer.py`: stub at lines 279–307
- `app/backend/models/translatable_document.py`: TableCell, TableStructure IR
- `tests/test_table_recognizer.py`: existing tests (IR shape, passthrough, batching)
- TABLE_RECOGNITION_ENABLED=false in config.py:163

## Open Questions

None — TATR output format is well-documented; implementation scope is clear.

## Requested Delivery Date / Priority

High — blocks Track D (table context translation)
