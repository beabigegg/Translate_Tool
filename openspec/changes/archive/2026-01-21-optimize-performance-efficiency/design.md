# Design: 效能與資源管理優化

## Context

Translate Tool 是一個本機運行的文件翻譯服務。在長時間連續使用的情境下（例如翻譯大量文件），系統資源會逐漸累積而不被釋放，導致：

- 記憶體使用量持續上升
- 硬碟空間被快取和暫存檔案佔用
- HTTP 連線建立開銷影響翻譯速度
- 背景資源（如 SSE 生成器）未正確釋放

作為本機服務，我們優先考慮**穩定性**和**效率**，而非安全性防護。

## Goals

1. 系統可以穩定運行 24 小時以上而不需重啟
2. 記憶體使用量維持在合理範圍（< 500MB 基礎開銷）
3. 硬碟快取有明確上限，不會無限增長
4. HTTP 連線複用，減少翻譯延遲
5. 資源正確釋放，無記憶體或檔案洩漏

## Non-Goals

- 分散式部署支援
- 多用戶隔離
- 安全性增強（認證、速率限制等）
- 效能基準測試框架

---

## Decision 1: 工作記錄管理策略

### 選擇：混合式 LRU + TTL 清理

**方案：**
```python
# config.py 新增設定
MAX_JOBS_IN_MEMORY = 100      # 記憶體中最多保留 100 個工作
JOB_TTL_HOURS = 24            # 工作記錄 24 小時後可被清理
CLEANUP_INTERVAL_MINUTES = 30  # 每 30 分鐘執行一次清理
```

**實作方式：**
- 使用 `collections.OrderedDict` 維護工作記錄，自動保持插入順序
- 清理觸發條件：
  1. 新增工作時，若數量超過 `MAX_JOBS_IN_MEMORY`，清理最舊的已完成工作
  2. 背景執行緒定期掃描，清理超過 TTL 的工作
- 清理時一併刪除對應的工作目錄（input/output 檔案）

**替代方案考量：**
| 方案 | 優點 | 缺點 |
|------|------|------|
| 純 LRU | 簡單實作 | 長時間閒置後仍佔用記憶體 |
| 純 TTL | 可預測的生命週期 | 短時間大量工作仍會撐爆記憶體 |
| **混合式** | 兼顧兩種情境 | 實作稍複雜 |
| Redis 外部儲存 | 可持久化 | 增加依賴，本機服務不需要 |

---

## Decision 2: 翻譯快取管理策略

### 選擇：SQLite + 記錄數上限 + LRU 淘汰

**方案：**
```python
# config.py 新增設定
CACHE_MAX_ENTRIES = 50000     # 最多快取 5 萬條翻譯
CACHE_CLEANUP_BATCH = 5000    # 每次清理 5000 條最舊記錄
```

**Schema 調整：**
```sql
CREATE TABLE IF NOT EXISTS translations(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    src TEXT NOT NULL,
    tgt TEXT NOT NULL,
    text TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (src, tgt, text)
);

CREATE INDEX IF NOT EXISTS idx_last_used ON translations(last_used_at);
```

**清理邏輯：**
```python
def _cleanup_if_needed(self) -> None:
    count = self._get_entry_count()
    if count > CACHE_MAX_ENTRIES:
        # 刪除最久未使用的記錄
        self._delete_oldest(CACHE_CLEANUP_BATCH)
```

**替代方案考量：**
| 方案 | 優點 | 缺點 |
|------|------|------|
| 檔案大小限制 | 直觀 | SQLite 檔案大小計算不精確 |
| **記錄數限制** | 簡單可靠 | 單條記錄大小不一 |
| 時間過期 | 自動清理舊資料 | 常用翻譯也會被清除 |
| LRU by last_used | 保留常用翻譯 | 需要更新 last_used_at |

**選擇記錄數 + LRU**：簡單可靠，且透過 `last_used_at` 追蹤使用頻率，確保常用翻譯不被清除。

---

## Decision 3: HTTP 連線池

### 選擇：requests.Session 單例

**方案：**
```python
class OllamaClient:
    _session: Optional[requests.Session] = None

    @classmethod
    def _get_session(cls) -> requests.Session:
        if cls._session is None:
            cls._session = requests.Session()
            adapter = HTTPAdapter(
                pool_connections=2,
                pool_maxsize=5,
                max_retries=Retry(total=3, backoff_factor=0.5)
            )
            cls._session.mount("http://", adapter)
            cls._session.mount("https://", adapter)
        return cls._session
```

**效益：**
- TCP 連線複用，減少三向交握開銷
- 內建連線池管理
- 自動處理 Keep-Alive

**替代方案考量：**
| 方案 | 優點 | 缺點 |
|------|------|------|
| **requests.Session** | 簡單，相容現有程式碼 | 同步阻塞 |
| httpx.AsyncClient | 非同步支援 | 需重構大量程式碼 |
| aiohttp | 高效能非同步 | 學習曲線，大幅重構 |

本機服務翻譯速度瓶頸在 LLM 推論（每次 1-5 秒），HTTP 連線開銷（~50ms）相對影響小。選擇最小改動的 `requests.Session`。

---

## Decision 4: SSE 資源管理

### 選擇：客戶端斷線偵測 + 閒置逾時

**方案：**
```python
@router.get("/jobs/{job_id}/logs")
async def stream_logs(job_id: str, request: Request, from_index: int = 0):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        idx = max(from_index, 0)
        idle_count = 0
        max_idle = 120  # 60 秒無新日誌則結束（0.5s * 120）

        while True:
            # 檢查客戶端是否斷線
            if await request.is_disconnected():
                break

            with job.lock:
                logs = list(job.logs)
                status = job.status

            if idx < len(logs):
                idle_count = 0
                while idx < len(logs):
                    yield f"data: {logs[idx]}\n\n"
                    idx += 1
            else:
                idle_count += 1
                if idle_count > max_idle:
                    break

            if status in {"completed", "failed", "stopped"}:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

**關鍵改進：**
1. 使用 `request.is_disconnected()` 偵測客戶端斷線
2. 新增閒置逾時（60 秒無新日誌）
3. 改為 `async def` 以支援非同步檢查

---

## Decision 5: 競態條件修復

### 選擇：在鎖內完成狀態更新

**問題：**
```python
# 原本的問題程式碼
self._archive_outputs(job)  # 在鎖外設定 job.output_zip
with job.lock:
    job.status = "completed"
```

**修復：**
```python
# 修復後
archive_path = self._archive_outputs(job)  # 只回傳路徑
with job.lock:
    job.output_zip = archive_path  # 在鎖內設定
    job.status = "completed"
```

---

## Decision 6: 啟動清理機制

### 選擇：啟動時掃描 + 定期清理

**方案：**
```python
class JobManager:
    def __init__(self) -> None:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self.jobs: OrderedDict[str, JobRecord] = OrderedDict()
        self._cleanup_orphaned_dirs()  # 啟動時清理
        self._start_cleanup_thread()   # 背景定期清理

    def _cleanup_orphaned_dirs(self) -> None:
        """清理沒有對應工作記錄的目錄"""
        for job_dir in JOBS_DIR.iterdir():
            if job_dir.is_dir() and job_dir.name not in self.jobs:
                shutil.rmtree(job_dir, ignore_errors=True)
                logger.info("Cleaned orphaned job dir: %s", job_dir.name)
```

---

## Risks / Trade-offs

| 風險 | 影響 | 緩解措施 |
|------|------|----------|
| 清理進行中的工作 | 資料遺失 | 只清理 completed/failed/stopped 狀態的工作 |
| 快取清理影響效能 | 翻譯重複呼叫 API | 使用 LRU 保留常用翻譯，批次清理減少 I/O |
| Session 單例執行緒安全 | 並發問題 | requests.Session 本身是執行緒安全的 |
| 啟動清理誤刪 | 刪除有用資料 | 只清理 JOBS_DIR 下的目錄，不影響其他位置 |

---

## Migration Plan

1. **階段一：基礎設施**
   - 新增設定參數（可透過環境變數覆蓋）
   - 更新 TranslationCache schema（向後相容）

2. **階段二：核心實作**
   - 實作 JobManager 清理機制
   - 實作 TranslationCache LRU 淘汰
   - 改用 requests.Session

3. **階段三：資源管理**
   - 修復 SSE 串流
   - 修復競態條件
   - 新增啟動清理

4. **回滾計畫**
   - 所有新設定都有預設值，可透過環境變數停用
   - 快取 schema 變更向後相容，舊資料仍可讀取

---

## Open Questions

1. **快取上限數值** - 5 萬條是否合適？需要根據實際使用情況調整
2. **工作保留時間** - 24 小時 TTL 是否足夠？使用者可能需要更長時間下載
3. **清理頻率** - 30 分鐘是否過於頻繁或太少？

這些數值都設為可配置，可在實際使用中調整。
