# Change: 新增文件大小限制

## Why
`_collect_docx_segments()` 將所有段落載入記憶體，無大小限制。處理超大文件時可能耗盡記憶體導致應用程式崩潰。地端模型處理速度較慢，記憶體佔用時間更長，問題更為嚴重。

## What Changes
- 新增最大段落數限制（預設 10,000）
- 新增最大字元數限制（預設 100,000）
- 超過限制時顯示友善錯誤訊息

## Impact
- Affected specs: translator-core
- Affected code: `document_translator_gui_with_backend.py:567-668`, `_collect_docx_segments` 及類似函式
