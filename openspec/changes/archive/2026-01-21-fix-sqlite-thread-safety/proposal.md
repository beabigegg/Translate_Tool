# Change: 修復 SQLite 執行緒安全問題

## Why
目前使用 `check_same_thread=False` 並共用單一連線，加上鎖定實作可能導致死鎖。多執行緒環境下可能造成資料損壞或程式當機。

## What Changes
- 改用每次操作建立新連線的模式
- 啟用 WAL 日誌模式提升並行效能
- 確保連線正確關閉

## Impact
- Affected specs: translator-core
- Affected code: `document_translator_gui_with_backend.py:118-148`, `TranslationCache` 類別
