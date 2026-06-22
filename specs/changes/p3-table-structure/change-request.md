# Change Request

## Original Request

P3-3: 表格結構辨識（TableFormer/TATR）cell 級翻譯 + 數值 cell passthrough + 同表格 cell 批次合送
模組: parsers/table_recognizer.py（新建）
估時: 14 PD
來源: docs/improvement-plan.md § Phase 3 P3-3

Three required elements confirmed:
- Affected surface: PDF/document table parsing path (parsers/table_recognizer.py, new) + translation pipeline cell batching
- Desired behavior: Recognize table structure via TableFormer or TATR → translate at cell granularity; pass through numeric-only cells without translation; batch all cells from the same table into a single LLM request
- Success criterion: A document with a table produces cell-level translation output where numeric cells are unchanged, text cells are translated, and all cells from the same table are sent in one LLM batch

## Business / User Goal

## Non-goals

## Constraints

## Known Context

## Open Questions

## Requested Delivery Date / Priority
