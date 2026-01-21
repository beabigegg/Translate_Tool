# Change: 移除 Dify 後端，轉換為全地端應用

## Why
目前應用程式同時支援 Dify（雲端）和 Ollama（地端）兩種翻譯後端。由於已完成 TranslateGemma 地端模型的整合，Dify 後端不再需要。移除 Dify 相關程式碼可以簡化架構、減少維護負擔、消除對外部雲端服務的依賴，並使應用程式成為完全離線可用的地端翻譯工具。

## What Changes
- **BREAKING**: 移除 `DifyClient` 類別及其所有相關程式碼
- **BREAKING**: 移除 GUI 中的後端選擇器和 Dify 設定欄位
- 刪除 `api.txt` 設定檔（不再需要雲端 API 設定）
- 簡化型別註解：`Union[DifyClient, OllamaClient]` → `OllamaClient`
- 移除測試檔案中的 Dify 相關測試案例
- 更新文件和說明

## Impact
- Affected specs: translation-backend, translator-core
- Affected code:
  - `document_translator_gui_with_backend.py`: DifyClient 類別、GUI 元件、process_path 參數
  - `translate_tool/clients/dify_client.py`: 整個檔案刪除
  - `translate_tool/clients/__init__.py`: 移除 DifyClient 匯出
  - `translate_tool/gui/translator_gui.py`: 移除 Dify 設定 UI
  - `tests/conftest.py`: 移除 MockDifyClient
  - `tests/test_api_client_network.py`: 移除 DifyClient 測試
  - `tests/test_*_integration.py`: 移除 DifyClient 相關測試
  - `api.txt`: 刪除整個檔案
  - `openspec/project.md`: 更新技術棧說明
