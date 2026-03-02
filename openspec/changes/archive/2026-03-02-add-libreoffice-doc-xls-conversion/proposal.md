# Change: Add LibreOffice Headless Conversion for .doc and .xls Files

## Why
目前 .doc 和 .xls 檔案僅能透過 Windows COM (win32com) 進行轉換處理。在 WSL、Linux、macOS 等非 Windows 環境下：
- .doc 檔案直接被跳過（log: "Word COM not available; convert to .docx first"）
- .xls 檔案 fallthrough 到 openpyxl 但 openpyxl 不支援 .xls 二進位格式，導致失敗

專案主要部署環境為 WSL/Linux（如 translate_tool.sh 啟動腳本所示），因此需要跨平台的轉換方案。

LibreOffice headless 模式提供可靠的跨平台轉換能力，將舊格式轉為現有處理器已完整支援的 .docx/.xlsx。

## What Changes
- **新增 LibreOffice 轉換模組**：`app/backend/processors/libreoffice_helpers.py`
  - LibreOffice binary 偵測（環境變數 → PATH → 常見路徑）
  - subprocess 轉換（`soffice --headless --convert-to`）
  - 並行安全（獨立 UserInstallation profile 避免 lock 衝突）
  - 暫存檔管理與清理
- **修改 orchestrator.py**：.doc 處理流程改為 LibreOffice 優先 → COM 備用 → 錯誤提示
- **修改 xlsx_processor.py**：.xls 處理流程改為 LibreOffice 優先 → COM 備用 → 錯誤提示
- **修改 config.py**：新增 `LIBREOFFICE_PATH`、`LIBREOFFICE_TIMEOUT` 設定常數

## Impact
- Affected specs: `translator-core`（新增 LibreOffice 轉換需求）
- Affected code:
  - `app/backend/processors/libreoffice_helpers.py` — 新增
  - `app/backend/processors/orchestrator.py` — 修改 .doc 分支
  - `app/backend/processors/xlsx_processor.py` — 修改 .xls 分支
  - `app/backend/config.py` — 新增設定常數

## Dependencies
### 系統套件（非 Python 套件）
- `libreoffice-core`（Debian/Ubuntu: `sudo apt install libreoffice-core`）
- 或完整 LibreOffice（macOS: `brew install --cask libreoffice`）

## Out of Scope
- .ppt 格式支援（目前無需求）
- LibreOffice 用於 PDF 轉換（已有 PyMuPDF）
- 自動安裝 LibreOffice
