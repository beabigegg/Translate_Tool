## 1. 新增 OllamaClient.unload_model() 方法

- [x] 1.1 在 `translate_tool/clients/ollama_client.py` 新增 `unload_model()` 方法
- [x] 1.2 使用 `keep_alive: 0` 參數呼叫 Ollama API 卸載模型
- [x] 1.3 處理網路錯誤和服務不可用情況
- [x] 1.4 新增單元測試驗證 unload_model 功能

## 2. 新增 release_resources() 函數

- [x] 2.1 在 `translate_tool/utils/resource_utils.py` 新增 `release_resources()` 函數
- [x] 2.2 整合 OllamaClient.unload_model() 呼叫
- [x] 2.3 整合 gc.collect() 呼叫
- [x] 2.4 新增適當的日誌輸出

## 3. 整合資源釋放到翻譯流程

- [x] 3.1 修改 `document_translator_gui_with_backend.py` 中的 worker 函數
- [x] 3.2 在任務成功完成後呼叫 release_resources()
- [x] 3.3 在使用者中斷任務後呼叫 release_resources()
- [x] 3.4 在發生錯誤時呼叫 release_resources()

## 4. 更新 GUI 狀態顯示

- [x] 4.1 在資源釋放期間顯示「正在釋放資源...」狀態
- [x] 4.2 資源釋放完成後更新狀態為「已完成」

## 5. 測試與驗證

- [x] 5.1 新增 unload_model 的單元測試
- [x] 5.2 新增 release_resources 的單元測試
- [x] 5.3 整合測試：驗證完整翻譯流程後資源釋放
- [x] 5.4 手動測試：使用 nvidia-smi 驗證 VRAM 釋放 (待使用者手動驗證)
