## 1. 移除 DifyClient 類別

- [x] 1.1 刪除 `translate_tool/clients/dify_client.py` 檔案
- [x] 1.2 從 `translate_tool/clients/__init__.py` 移除 DifyClient 匯出
- [x] 1.3 從 `document_translator_gui_with_backend.py` 移除 DifyClient 類別定義
- [x] 1.4 移除 `DIFY_API_BASE_URL` 和 `DIFY_API_KEY` 全域變數

## 2. 簡化型別註解

- [x] 2.1 將所有 `Union[DifyClient, OllamaClient]` 改為 `OllamaClient`
- [x] 2.2 移除 DifyClient 的 import 語句
- [x] 2.3 更新 `translate_tool/compat.py` 移除 DifyClient 相容層

## 3. 更新 GUI

- [x] 3.1 移除後端選擇下拉選單（固定為 Ollama）
- [x] 3.2 移除 Dify Base URL 輸入欄位
- [x] 3.3 移除 Dify API Key 輸入欄位
- [x] 3.4 更新 `translate_tool/gui/translator_gui.py` 對應元件

## 4. 移除 API 設定檔

- [x] 4.1 刪除 `api.txt` 檔案
- [x] 4.2 移除 `load_api_config_from_file()` 函式
- [x] 4.3 更新 `translate_tool/config.py` 移除 Dify 相關常數和設定載入

## 5. 更新處理流程

- [x] 5.1 簡化 `process_path()` 參數（移除 base_url, api_key）
- [x] 5.2 簡化 client 建立邏輯（移除後端判斷）
- [x] 5.3 更新 `translate_tool/processors/orchestrator.py`

## 6. 更新測試

- [x] 6.1 從 `tests/conftest.py` 移除 MockDifyClient
- [x] 6.2 從 `tests/test_api_client_network.py` 移除 DifyClient 測試類別
- [x] 6.3 從各整合測試移除 `TestXxxWithDifyClient` 測試類別
- [x] 6.4 確保所有單元測試通過

## 7. 更新文件

- [x] 7.1 更新 `openspec/project.md` 技術棧說明
- [x] 7.2 更新 `SETUP.md` 移除 Dify 相關說明
- [x] 7.3 更新程式碼註解移除 Dify 相關說明

## 8. 實機測試（使用地端模型）

- [x] 8.1 確認 Ollama 服務運行中且 translategemma:12b 模型已載入
- [x] 8.2 啟動 GUI 應用程式，確認介面正常顯示
- [x] 8.3 測試翻譯 DOCX 檔案（英文→繁體中文）
- [x] 8.4 測試翻譯 PPTX 檔案
- [x] 8.5 測試翻譯 XLSX 檔案
- [x] 8.6 測試停止按鈕功能
- [x] 8.7 驗證翻譯快取正常運作
