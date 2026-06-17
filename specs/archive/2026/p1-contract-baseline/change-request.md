# Change Request

## Original Request

補齊合約空殼（P1-1）：contracts/business/business-rules.md、contracts/data/data-shape-contract.md、contracts/api/api-contract.md 的 rule inventory、decision table、error format、auth 政策、JobStatus.status enum、multipart 請求 schema 全為空白，API 一致性檢查（`cdd-kit validate --contracts`）無從生效。

參考來源：docs/improvement-plan.md §1.2 痛點 C.16、§5.1 Phase 1 P1-1（5 PD）、P1 Milestone 驗收標準第一條。

## Business / User Goal

讓 `cdd-kit validate --contracts` 與 `cdd-kit gate` 的 API 一致性檢查能正常執行——目前合約空殼導致任何下游 change 的 gate 均無基準可比對。此 change 是 p1-llm-client-abstraction、p1-sentence-mode-fix、p1-term-state-machine、p1-prompt-i18n-numctx 四個 change 的先決條件。

## Non-goals

- 不實作任何後端 API 路由或業務邏輯（那些在下游 change 做）
- 不修改 `contracts/env/env-contract.md`（env 合約由 p1-cloud-providers 處理）
- 不引入 OpenAPI 驗證自動化（由 p1-observability-metrics change 配套處理）
- 不修改前端程式碼

## Constraints

- 合約內容須反映**現有系統行為**，而非期望行為——只記錄程式碼已實作的 endpoint、payload、rule
- `JobStatus.status` enum 值需與 `app/backend/api/routes.py` 及 `app/backend/services/job_manager.py` 的實際程式碼對齊
- `contracts/api/api-contract.md` 的 auth 政策須記錄「API 無認證，此為刻意的本地工具設計決策」（目前未載明）
- error format 須反映 `app/backend/utils/exceptions.py` 及 `api/routes.py` 實際回傳的 HTTP 狀態碼與 error payload 形狀
- 合約檔案為 Markdown，不引入新的 JSON schema 或 OpenAPI 自動化工具

## Known Context

相關合約檔案（均為空殼）：
- contracts/api/api-contract.md — 無 endpoint inventory、無 auth rule
- contracts/api/api-inventory.md — 無實際端點清單
- contracts/api/error-format.md — 無 error payload schema
- contracts/business/business-rules.md — 無 rule inventory、無 decision table
- contracts/data/data-shape-contract.md — 無 JobStatus.status enum、無 multipart schema

現有 API 實作（參考讀取路徑）：
- app/backend/api/routes.py — 所有 API 端點
- app/backend/api/schemas.py — request/response Pydantic models
- app/backend/services/job_manager.py — job status 狀態流

## Open Questions

無。所有資訊可從現有程式碼讀取；合約只需反映已實作行為。

## Requested Delivery Date / Priority

優先（阻塞 4 個下游 P1 change）。預估 5 person-days。
