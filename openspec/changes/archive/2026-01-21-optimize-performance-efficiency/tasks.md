# Tasks: 效能與資源管理優化

## 1. 設定參數新增

- [x] 1.1 在 `config.py` 新增工作管理相關設定
  ```python
  MAX_JOBS_IN_MEMORY = int(os.environ.get("MAX_JOBS_IN_MEMORY", "100"))
  JOB_TTL_HOURS = int(os.environ.get("JOB_TTL_HOURS", "24"))
  CLEANUP_INTERVAL_MINUTES = int(os.environ.get("CLEANUP_INTERVAL_MINUTES", "30"))
  ```

- [x] 1.2 在 `config.py` 新增快取管理相關設定
  ```python
  CACHE_MAX_ENTRIES = int(os.environ.get("CACHE_MAX_ENTRIES", "50000"))
  CACHE_CLEANUP_BATCH = int(os.environ.get("CACHE_CLEANUP_BATCH", "5000"))
  ```

- [x] 1.3 在 `config.py` 新增 SSE 相關設定
  ```python
  SSE_IDLE_TIMEOUT_SECONDS = int(os.environ.get("SSE_IDLE_TIMEOUT_SECONDS", "60"))
  ```

- [x] 1.4 在 `config.py` 新增 HTTP 連線池相關設定
  ```python
  HTTP_POOL_CONNECTIONS = int(os.environ.get("HTTP_POOL_CONNECTIONS", "2"))
  HTTP_POOL_MAXSIZE = int(os.environ.get("HTTP_POOL_MAXSIZE", "5"))
  ```

## 2. 翻譯快取優化

- [x] 2.1 更新 `translation_cache.py` 的資料表 schema
  - 新增 `id` 欄位 (PRIMARY KEY AUTOINCREMENT)
  - 新增 `created_at` 欄位
  - 新增 `last_used_at` 欄位
  - 新增 `idx_last_used` 索引
  - 確保向後相容（檢查欄位是否存在再新增）

- [x] 2.2 實作 `get()` 方法更新 `last_used_at`

- [x] 2.3 實作 `_get_entry_count()` 方法

- [x] 2.4 實作 `_cleanup_if_needed()` 方法

- [x] 2.5 在 `put()` 方法中呼叫清理檢查

- [x] 2.6 新增 `get_stats()` 方法供除錯使用

## 3. HTTP 連線池實作

- [x] 3.1 在 `ollama_client.py` 新增 Session 管理
  - 類別變數 `_session` 和 `_session_lock`
  - 使用 `HTTPAdapter` 配置連線池
  - 使用 `Retry` 配置自動重試

- [x] 3.2 修改 `health_check()` 使用 session

- [x] 3.3 修改 `translate_once()` 使用 session

- [x] 3.4 修改 `translate_batch()` 使用 session

- [x] 3.5 修改 `unload_model()` 使用 session

- [x] 3.6 修改 `list_ollama_models()` 函式使用 session

- [x] 3.7 新增 `close_session()` 類別方法供清理使用

## 4. 工作管理器優化

- [x] 4.1 將 `self.jobs` 改為 `OrderedDict`

- [x] 4.2 實作 `_cleanup_by_capacity()` 方法

- [x] 4.3 實作 `_cleanup_expired_jobs()` 方法

- [x] 4.4 實作 `_cleanup_orphaned_dirs()` 方法

- [x] 4.5 實作 `_start_cleanup_thread()` 方法

- [x] 4.6 在 `__init__()` 中呼叫啟動清理

- [x] 4.7 在 `create_job()` 中呼叫容量檢查清理

- [x] 4.8 新增 `get_stats()` 方法供除錯使用

- [x] 4.9 新增 `_shutdown()` 方法和 atexit 註冊

## 5. 競態條件修復

- [x] 5.1 修改 `_archive_outputs()` 只回傳路徑

- [x] 5.2 修改 `_run_job()` 在鎖內設定 `output_zip`

- [x] 5.3 修改 `job_status()` 在鎖內讀取狀態

- [x] 5.4 修改 `download()` 在鎖內讀取 `output_zip`

## 6. SSE 串流優化

- [x] 6.1 將 `stream_logs()` 改為 `async def`

- [x] 6.2 新增 `Request` 參數以偵測斷線

- [x] 6.3 在迴圈中檢查 `request.is_disconnected()`

- [x] 6.4 新增閒置逾時機制

- [x] 6.5 將 `time.sleep()` 改為 `await asyncio.sleep()`

## 7. 資源清理整合

- [x] 7.1 在 `resource_utils.py` 新增 `full_shutdown_cleanup()` 函式

- [x] 7.2 在 `full_shutdown_cleanup()` 中呼叫 `OllamaClient.close_session()`

- [x] 7.3 註冊 `atexit` 清理

## 8. API 擴充

- [x] 8.1 新增 `/stats` 端點用於監控

## 9. 測試

- [x] 9.1 測試設定參數載入

- [x] 9.2 測試快取基本功能 (put/get/stats)

- [x] 9.3 測試 HTTP 連線池單例模式

- [x] 9.4 測試所有模組匯入

- [ ] 9.5 整合測試（需要 Ollama 服務）

## 驗收標準

- [x] 所有模組可正常匯入
- [x] 設定參數正確載入預設值
- [x] 快取 LRU 機制正常運作
- [x] HTTP 連線池正確複用連線
- [ ] 系統可連續運行 2 小時處理 50+ 個翻譯工作而記憶體使用量穩定（待驗證）
- [ ] 客戶端斷線後 SSE 生成器在 5 秒內停止（待驗證）
