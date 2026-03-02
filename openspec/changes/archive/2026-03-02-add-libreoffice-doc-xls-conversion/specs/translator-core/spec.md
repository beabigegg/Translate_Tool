## ADDED Requirements

### Requirement: LibreOffice Headless Conversion for Legacy Office Formats
The system SHALL support converting .doc and .xls files to .docx and .xlsx via LibreOffice headless mode, enabling processing on non-Windows platforms. The system MUST prefer LibreOffice over COM when both are available.

#### Scenario: 使用 LibreOffice 轉換 .doc
- **WHEN** 使用者上傳 .doc 檔案進行翻譯
- **AND** 系統偵測到 LibreOffice 可用
- **THEN** 系統透過 `soffice --headless --convert-to docx` 轉換為 .docx
- **AND** 使用現有 docx_processor 處理翻譯
- **AND** 清理暫存的 .docx 檔案

#### Scenario: 使用 LibreOffice 轉換 .xls
- **WHEN** 使用者上傳 .xls 檔案進行翻譯
- **AND** 系統偵測到 LibreOffice 可用
- **THEN** 系統透過 `soffice --headless --convert-to xlsx` 轉換為 .xlsx
- **AND** 使用現有 xlsx_processor 處理翻譯
- **AND** 清理暫存的 .xlsx 檔案

#### Scenario: LibreOffice 不可用時使用 COM 備用
- **WHEN** 使用者上傳 .doc 或 .xls 檔案
- **AND** LibreOffice 不可用
- **AND** Windows COM (win32com) 可用
- **THEN** 系統使用 COM 進行轉換（現有行為）
- **AND** log 記錄使用 COM 備用方案

#### Scenario: LibreOffice 和 COM 都不可用
- **WHEN** 使用者上傳 .doc 或 .xls 檔案
- **AND** LibreOffice 和 COM 都不可用
- **THEN** 系統記錄包含 LibreOffice 安裝指引的錯誤訊息
- **AND** 跳過該檔案，不中斷整個工作

#### Scenario: 並行轉換隔離
- **WHEN** 多個檔案同時需要 LibreOffice 轉換
- **THEN** 每次轉換使用獨立的 LibreOffice UserInstallation profile
- **AND** 轉換之間不會因 lock file 互相干擾

#### Scenario: LibreOffice binary 偵測
- **WHEN** 系統啟動
- **THEN** 依序檢查: LIBREOFFICE_PATH 環境變數 → PATH 中的 soffice/libreoffice → 常見安裝路徑
- **AND** 快取偵測結果供後續使用
