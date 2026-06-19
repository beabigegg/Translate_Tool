# Change Request

## Original Request

p2-table-border-protection (P2-9): 表格框線保護 + side-by-side 右側 redaction 修正

Two related rendering defects in the fitz PDF renderer:

1. **Overlay mode — table border protection**: When the renderer draws a white mask over source text regions before inserting translated text, table grid lines (borders) are erased by the white rectangle. Grid lines must remain visible after text replacement. The fix must selectively mask only text content areas, not table rule lines.

2. **Side-by-side mode — right-panel redaction fix**: In side-by-side mode the right panel is supposed to show translated text over a masked (redacted) copy of the source page. Currently the source text on the right side is not properly masked before the translated copy is placed, resulting in source and translated text overlapping or source text showing through. The fix must ensure source text is fully masked on the right panel before translated text is rendered.

Success criteria:
- (AC-1) In overlay mode output PDFs, table grid lines (1-pt and multi-pt rules) are preserved and visible after translation; no white-mask rectangle covers a table border stroke.
- (AC-2) In side-by-side mode output PDFs, the right panel contains no visible source-language text; all source text regions are masked before translated text is placed.

## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
