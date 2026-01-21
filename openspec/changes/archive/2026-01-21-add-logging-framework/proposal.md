# Change: 新增正式日誌框架

## Why
目前使用 print 語句和自訂 log 回呼，而非 Python 的 logging 模組。這導致難以控制日誌層級、難以將日誌導向檔案、且不利於除錯。

## What Changes
- 採用 Python 標準 logging 模組
- 設定適當的日誌格式和層級
- 支援同時輸出到 GUI 和檔案

## Impact
- Affected specs: translator-core
- Affected code: `document_translator_gui_with_backend.py` 全檔的 print 語句和 log 呼叫
