# Change: 建立資源釋放機制

## Why
目前應用程式在翻譯任務完成後，Ollama 模型會持續佔用 VRAM（預設 5 分鐘後才自動卸載）。對於 TranslateGemma:12b（約 8GB VRAM），這會阻止使用者在翻譯完成後立即使用 GPU 進行其他工作。此外，大量文件處理後的 Python 物件也可能佔用記憶體。

新增資源釋放機制可以：
- 任務完成後立即釋放 VRAM 供其他應用使用
- 清理 Python 記憶體中的暫存物件
- 提升系統資源利用效率

## What Changes
- 新增 `release_resources()` 函數，透過 Ollama API 卸載模型並呼叫 `gc.collect()`
- 修改 `OllamaClient` 新增 `unload_model()` 方法
- 在翻譯任務完成（成功或中斷）後自動呼叫資源釋放
- 新增 GUI 狀態顯示資源釋放進度

## Impact
- Affected specs: translator-core
- Affected code:
  - `translate_tool/clients/ollama_client.py`: 新增 `unload_model()` 方法
  - `translate_tool/utils/__init__.py`: 新增 `release_resources()` 函數
  - `document_translator_gui_with_backend.py`: 在 worker 完成時呼叫資源釋放
  - `translate_tool/gui/translator_gui.py`: 更新狀態顯示
