# Change Request

## Original Request

Expand `Term.status` from `{unverified, approved}` to `{unverified, needs_review, approved, rejected}`, tighten the prompt-injection gate so `rejected` and `needs_review` terms are never injected, cap LLM self-assessed confidence at 0.85 to prevent unverified AI-extracted terms from bypassing the gate via `confidence=1.0`, and expose `reject` / `flag-needs-review` transitions via the API.

## Business / User Goal

術語注入的信賴度問題：目前 `get_top_terms` / `get_document_terms` 的注入閘條件為 `status='approved' OR confidence=1.0`。`term_extractor.py` 的 prompt 明確指示 LLM 對品牌名、縮寫設 `confidence=1.0`，這使 AI 自評術語在完全未經人工審查的情況下就進入翻譯 prompt，與人工核可術語地位相同。

新的四狀態機強制術語必須走過明確的 `approved` 步驟才能注入；`rejected` 永不注入；`needs_review` 提供人工標注疑慮術語但不立即刪除的暫存槽位。移除 `confidence=1.0` bypass 之後，注入決策完全由 `status` 主控，LLM confidence 數值降回僅作優先排序用途。

## Non-goals

- 術語套用稽核（hit-rate tracking） — 後續獨立 `term_audit.py` change
- RAG / embedding 術語向量檢索 — P2/P3
- 前端 UI 狀態轉換操作 — P1 僅 backend + REST API，前端可透過現有 API 驅動
- XLIFF / TBX 格式支援 — P3
- confidence 跨模型校準或語意品質量測 — 本 change 只做 LLM 上限截斷（cap at 0.85）

## Constraints

- SQLite `status` 欄位已為 `TEXT NOT NULL DEFAULT 'unverified'`，無需 `ALTER TABLE`；資料遷移僅 `UPDATE` 現有行，不改 schema
- `Term.status: str` 維持字串型別（不改為 Python Enum），保持 JSON 序列化相容性；valid values 以常數集合 `_VALID_STATUSES` 在 term_db.py 驗證
- 現有四種 conflict strategy（skip / overwrite / merge / force）繼續運作；`overwrite` 和 `merge` 須同等保護 `rejected`（現在只保護 `approved`），`force` 可覆蓋任何狀態
- 注入閘移除 `confidence=1.0` bypass 後，所有既有 `unverified` 術語不再被注入；透過 `TERM_INJECT_HIGH_CONFIDENCE_UNVERIFIED=false`（預設 false）和 `TERM_INJECT_CONF_THRESHOLD=0.9` 可選開啟寬鬆閘，以平滑遷移（不改變預設行為即安全）
- 現有 389 測試基線必須維持通過
- 現有 API 路徑（`/terms/approve`、`/terms/approved`、`/terms/unverified`）維持不動；新增端點不破壞既有客戶端

## Known Context

- 注入閘漏洞位置：`term_db.py:105-115`（`get_top_terms`）和 `:130-142`（`get_document_terms`）— `AND (status='approved' OR confidence=1.0)`
- LLM confidence 賦值：`term_extractor.py:344,361,456,470`；品牌名/縮寫被 prompt 指示設 `confidence=1.0`（`term_extractor.py:74`）
- `Term` model：`app/backend/models/term.py:20` — comment 僅列 `"unverified" | "approved"`，需更新
- `insert()` 的 `overwrite`/`merge` 策略保護 `approved`（`term_db.py:189-195`），`rejected` 目前無保護
- 現有方法：`approve()`（`:294`）、`get_unverified()`（`:304`）、`get_approved()`（`:363`）、`get_stats()`（`:339`，只計 total + unverified）
- API 術語端點：`routes.py:420`（`/terms/approve` POST）、`:429`（`/terms/approved` GET）、`:403`（`/terms/unverified` GET）、`:325`（`/terms/export` GET，`status` 參數只認 `approved | unverified`）
- `get_stats()` 回傳 `total` + `unverified`；需增加 `needs_review`、`approved`、`rejected` 欄位
- `contracts/business/business-rules.md` 須新增術語狀態機轉換規則與注入閘規則

## Open Questions

（無 — 所有設計決策已在上述 Constraints 與 Non-goals 中確認）

## Requested Delivery Date / Priority

P1 最後一項，接續 `p1-prompt-i18n-numctx` 完成後開始。
