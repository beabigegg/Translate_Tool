# Design: 資源釋放機制

## 概述
本設計描述如何在翻譯任務完成後自動釋放 GPU VRAM 和 Python 記憶體資源。

## 技術背景

### Ollama 模型卸載 API
Ollama 提供 `keep_alive` 參數來控制模型在記憶體中的保留時間：
- `keep_alive: 0` - 立即卸載模型
- `keep_alive: -1` - 永久保留
- 預設值為 5 分鐘

卸載 API 呼叫範例：
```bash
curl http://localhost:11434/api/generate -d '{"model": "translategemma:12b", "keep_alive": 0}'
```

### Python 記憶體管理
使用 `gc.collect()` 強制執行垃圾回收，釋放不再使用的物件。

## 架構設計

### 元件關係
```
TranslatorGUI
    │
    ├─► Worker Thread (process_path)
    │       │
    │       └─► OllamaClient.translate_*()
    │               │
    │               └─► 任務完成
    │                       │
    └───────────────────────▼
                    release_resources()
                        │
                        ├─► OllamaClient.unload_model()
                        │       │
                        │       └─► POST /api/generate {keep_alive: 0}
                        │
                        └─► gc.collect()
```

### 介面設計

#### OllamaClient.unload_model()
```python
def unload_model(self) -> Tuple[bool, str]:
    """卸載目前模型以釋放 VRAM。

    透過 Ollama API 發送 keep_alive=0 的請求來立即卸載模型。

    Returns:
        Tuple of (success, message)
    """
```

#### release_resources()
```python
def release_resources(
    client: Optional[OllamaClient] = None,
    log: Callable[[str], None] = lambda s: None
) -> None:
    """釋放系統資源。

    Args:
        client: Ollama 客戶端實例，用於卸載模型
        log: 日誌回調函數
    """
```

## 執行時機

資源釋放將在以下情況自動執行：
1. **翻譯任務成功完成** - 所有檔案處理完畢
2. **使用者中斷任務** - 點擊 Stop 按鈕後
3. **發生錯誤** - 任務因錯誤終止時

## 錯誤處理

- Ollama 服務不可用時，記錄警告但不中斷流程
- 卸載失敗時，記錄錯誤但不影響任務結果
- gc.collect() 失敗時靜默處理（極少發生）

## 效能考量

- `unload_model()` 呼叫通常在 100ms 內完成
- `gc.collect()` 可能需要數十毫秒，取決於物件數量
- 總釋放時間應小於 1 秒

## 日誌輸出

```
[CLEANUP] 正在釋放資源...
[CLEANUP] 正在卸載模型 translategemma:12b
[CLEANUP] VRAM 已釋放
[CLEANUP] Python 記憶體已清理
[CLEANUP] 資源釋放完成
```

## 測試策略

1. **單元測試**: 模擬 Ollama API 回應測試 `unload_model()`
2. **整合測試**: 驗證完整任務後資源釋放流程
3. **手動驗證**: 使用 `nvidia-smi` 確認 VRAM 釋放

## 參考資料

- [Ollama FAQ - Unloading Models](https://docs.ollama.com/faq)
- [GitHub Issue #1600](https://github.com/ollama/ollama/issues/1600)
