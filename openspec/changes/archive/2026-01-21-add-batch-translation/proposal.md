# Change: 實作批次翻譯以改善效能

## Why
目前每個獨特文字段落觸發個別 API 呼叫（N+1 查詢模式）。使用地端模型時，逐一呼叫會導致極度緩慢的處理速度。批次處理可顯著提升效能。

## What Changes
- 收集多個待翻譯段落後一次性送出
- 實作批次大小控制（可設定）
- 保持向後相容，單一段落仍可正常處理

## Impact
- Affected specs: translator-core
- Affected code: `document_translator_gui_with_backend.py:935-949`, `translate_block_sentencewise` 函式
