# Change: 修復停止按鈕功能

## Why
目前 GUI 的停止按鈕僅記錄訊息，但未實際停止翻譯處理。使用地端模型翻譯時處理時間較長，使用者必須能夠中斷進行中的翻譯工作。

## What Changes
- 在翻譯工作迴圈中檢查 `stop_flag` 狀態
- 正在處理的檔案完成後立即停止
- 顯示適當的停止訊息給使用者

## Impact
- Affected specs: translator-core
- Affected code: `document_translator_gui_with_backend.py:1504-1505`, `process_path` 函式
