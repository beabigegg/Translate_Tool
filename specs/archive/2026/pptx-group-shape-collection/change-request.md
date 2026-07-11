# Change Request

## Original Request

PPTX text inside grouped shapes is never translated. `app/backend/processors/pptx_processor.py` collects with a flat `for shape in slide.shapes` loop (L214-239); a GroupShape has `shape_type == MSO_SHAPE_TYPE.GROUP` (6) and reports `has_text_frame == False` and `has_table == False`, so it is silently skipped — every text frame and table nested inside a group is never collected and never translated.

Affected surface: app/backend/processors/pptx_processor.py collection loop + restore.
Desired behavior: recurse into `GroupShape.shapes` (bounded depth, never drop) so grouped text frames and grouped tables are collected, translated, and written back through their existing tf/cell refs, mirroring the DOCX BR-113 nested-table recursion.
Success criterion: text in single and nested groups (text frames AND tables) is fully collected and translated in synthetic python-pptx fixtures (no user .pptx test files exist); grouped-table cells map to correct coordinates with no cross-table id() collision; existing flat-shape PPTX translation is unchanged.

Verified facts (main Claude, live probes — scratchpad/pptx_*.py):
- Flat walk skips groups: a slide with a plain textbox + a 2-textbox group yields only the plain textbox.
- GroupShape: shape_type == MSO_SHAPE_TYPE.GROUP (==6), has_text_frame False, has_table False, exposes `.shapes` for recursion; nested groups are possible.
- Grouped text-frame write-back persists across save (proven); grouped cell/tf refs are real python-pptx objects.
- SECOND in-scope fix, same loop: L220 `shape_id = id(shape)` keys table-cell grouping on id() of an lxml-backed shape proxy. Probe: 30 table shapes under GC collapse to 2 distinct ids (28 collisions). Masked today only because each cell segment retains its shape via cell._parent — the exact unstated-retention invariant CLAUDE.md now forbids. Group recursion adds more shapes whose ids can collide, so replace id(shape) with a per-presentation document-order counter (mirror DOCX next_table_id, BR-113).
- SmartArt is handled separately (`_extract_smartart_texts`) — out of scope. No user .pptx test files in docs/TEST_DOC/ — synthetic fixtures only.
## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
