# Change Request

## Original Request

翻譯完成後前端的「下載譯文」按鈕永遠不出現。
根本原因：`JobStatus` API response 沒有 `download_url` 欄位，前端等待此欄位卻永遠等不到。

## Business / User Goal

使用者翻譯完成後應能直接點擊下載按鈕取得譯文 zip 檔。

## Known Context

**已確認的 root cause（程式碼位置精確）：**

**後端：**
- `app/backend/api/schemas.py` — `JobStatus` dataclass/model 無 `download_url` 欄位
  - 現有欄位：job_id, status, processed_files, total_files, error, output_ready, current_file, segments, elapsed, progress, eta, term_summary, provider, quality_score_avg, audit_hit_rate
  - 缺少：`download_url: Optional[str]`
- `app/backend/services/job_manager.py` — `JobRecord` 有 `output_zip: Optional[Path]`（第 80 行），但從未轉換為 URL
  - 第 423 行：`job.output_zip = archive_path` — 只存 Path，未設 URL
- `app/backend/api/routes.py:339-350` — `GET /jobs/{job_id}/download` endpoint **已存在且可用**，只是 URL 從未通知前端

**前端：**
- `app/frontend/src/pages/TranslatePage.jsx:173` — 已寫好下載按鈕邏輯：
  ```jsx
  {jobStatus.download_url && <a className="btn btn-primary" href={jobStatus.download_url} download>下載譯文</a>}
  ```
  但因 `download_url` 永遠為 `undefined`，按鈕永遠不渲染。

**修法：**
1. `schemas.py`：`JobStatus` 加 `download_url: Optional[str] = None`
2. `job_manager.py`：在 `output_zip` 設值時同步設 `download_url = f"/api/jobs/{job_id}/download"`
3. 前端不需修改（邏輯已正確）

## Non-goals

- 不改變下載 endpoint 本身（routes.py:339-350 保持不動）
- 不修改前端按鈕樣式或邏輯

## Constraints

- `download_url` 只在 `status == "completed"` 且 `output_zip` 存在時才設值
- 不得影響其他 JobStatus 欄位

## Requested Delivery Date / Priority

獨立 change，任何時候都可執行。優先度：高（影響核心使用者流程）。
