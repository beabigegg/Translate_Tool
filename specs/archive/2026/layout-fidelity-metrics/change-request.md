# Change Request

## Original Request

Build a layout fidelity metrics harness with three objective metrics for regression testing: BIoU (Bounding-box IoU — for each source bbox find best-matching rendered bbox, return mean IoU), residual-text check (after whiteover, verify no text leaks through each whiteover region), and truncation-rate (count elements where render_truncated=True, return ratio and overflow_area_sum). New modules live entirely in tests/metrics/ and tests/fixtures/golden/; no existing backend or frontend files are touched. Success criterion: Wave 2 PDF renderer refactor (Track G) can import these metrics as regression gates before and after changes.

## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
