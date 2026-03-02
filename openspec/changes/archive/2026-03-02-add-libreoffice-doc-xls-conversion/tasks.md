# Tasks: Add LibreOffice Headless Conversion

## 1. 新增設定常數
- [x] 1.1 在 `app/backend/config.py` 新增 `LIBREOFFICE_PATH` (env var override, 預設空字串=自動偵測)
- [x] 1.2 在 `app/backend/config.py` 新增 `LIBREOFFICE_TIMEOUT` (預設 120 秒)

## 2. 建立 LibreOffice Helpers 模組
- [x] 2.1 建立 `app/backend/processors/libreoffice_helpers.py`
- [x] 2.2 實作 `_find_libreoffice_binary()` — 多策略偵測 (env → shutil.which → 常見路徑)
- [x] 2.3 實作 module-level `_LIBREOFFICE_BINARY` cache 和 `is_libreoffice_available()`
- [x] 2.4 實作 `_libreoffice_convert()` — subprocess 呼叫、timeout、獨立 profile dir
- [x] 2.5 實作 `doc_to_docx()` — temp dir 管理、shutil.move、cleanup
- [x] 2.6 實作 `xls_to_xlsx()` — temp dir 管理、shutil.move、cleanup

## 3. 修改 Orchestrator (.doc 處理)
- [x] 3.1 在 `orchestrator.py` 新增 LibreOffice imports
- [x] 3.2 重構 .doc 分支: LibreOffice 優先 → COM 備用 → 含安裝指引的錯誤訊息
- [x] 3.3 保留現有 temp file cleanup 邏輯

## 4. 修改 XLSX Processor (.xls 處理)
- [x] 4.1 在 `xlsx_processor.py` 新增 LibreOffice imports
- [x] 4.2 重構 .xls 分支: LibreOffice 優先 → COM 備用 → RuntimeError 含安裝指引
- [x] 4.3 保留現有 temp file cleanup 邏輯

## 5. 測試
- [x] 5.1 準備測試用 .doc 和 .xls 檔案
- [x] 5.2 驗證 LibreOffice 轉換成功（.doc → .docx、.xls → .xlsx）
- [x] 5.3 驗證翻譯流程正常（轉換後的檔案能正確翻譯）
- [x] 5.4 驗證 LibreOffice 不可用時的錯誤訊息
- [x] 5.5 驗證 log 輸出正確（"Converting via LibreOffice" / "Converting via COM"）
