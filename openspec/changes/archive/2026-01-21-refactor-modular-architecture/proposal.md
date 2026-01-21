# Change: 重構單體架構為模組化結構

## Why
整個應用程式包含在單一 1,540 行的檔案中，包括 GUI、API 客戶端、文件處理器、快取層和工具函式。這導致難以維護、測試和擴展，程式碼耦合度高。

## What Changes
- 將程式碼拆分為多個模組
- 建立清晰的目錄結構
- 維持向後相容的入口點

## Impact
- Affected specs: translator-core
- Affected code: `document_translator_gui_with_backend.py` 整個檔案
