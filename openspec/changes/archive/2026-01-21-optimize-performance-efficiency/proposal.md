# Change: 優化服務效能與資源管理

## Why

目前系統在長時間運行下存在以下效能問題：

1. **記憶體無限增長** - JobManager 將所有工作記錄保存在記憶體中，永不清理
2. **快取無限增長** - SQLite 翻譯快取沒有大小限制，長期使用會佔滿硬碟
3. **HTTP 連線效率低** - 每次 API 請求都建立新連線，未使用連線池
4. **SSE 資源洩漏** - 客戶端斷線後，伺服器端的串流生成器仍持續運行
5. **暫存檔案殘留** - 異常情況下工作目錄未被清理

這些問題會導致系統在持續使用後變慢、佔用過多資源，最終可能導致服務不穩定。

## What Changes

### 記憶體管理
- 新增工作記錄自動清理機制（保留最近 N 個工作或 TTL 過期清理）
- 實作 LRU 策略管理記憶體中的工作記錄

### 快取管理
- 新增快取大小上限設定
- 實作 LRU 淘汰策略清理舊快取
- 新增快取統計 API

### 連線效率
- 使用 `requests.Session` 實現連線池
- 複用 HTTP 連線減少建立開銷

### 資源洩漏修復
- SSE 串流新增客戶端斷線偵測
- 新增閒置連線逾時機制
- 修復競態條件（output_zip 同步問題）

### 清理機制
- 新增啟動時清理孤立工作目錄
- 新增定期清理過期工作檔案

## Impact

- **Affected specs**: translation-backend
- **Affected code**:
  - `app/backend/services/job_manager.py` - 工作生命週期管理
  - `app/backend/cache/translation_cache.py` - 快取管理
  - `app/backend/clients/ollama_client.py` - HTTP 客戶端
  - `app/backend/api/routes.py` - SSE 串流處理
  - `app/backend/config.py` - 新增設定參數
