# Change: 重構例外處理

## Why
多處使用裸露的 `except Exception:` 語句，隱藏真實錯誤，難以除錯。應捕獲特定例外類型並記錄相關資訊。

## What Changes
- 將 `except Exception:` 改為捕獲特定例外類型
- 加入適當的錯誤日誌記錄
- 保留必要的降級處理邏輯

## Impact
- Affected specs: translator-core
- Affected code: `document_translator_gui_with_backend.py:36, 42, 113, 147` 等多處
