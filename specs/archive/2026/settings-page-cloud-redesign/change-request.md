# Change Request

## Original Request

設定頁面（`app/frontend/src/pages/SettingsPage.jsx`）目前完全針對地端 Ollama（GPU VRAM 選擇、num_ctx slider、Ollama 狀態）。
系統改用雲端 API 後這些設定無意義。

重新設計為：
1. Provider 健康狀態（PANJIT / DeepSeek）
2. 各 provider 的模型清單與基本參數
3. 單句翻譯測試功能（各模型對比 + COMET 評分）
4. DeepSeek API key 輸入（使用者自行提供，存於 localStorage）

## Business / User Goal

讓使用者能夠：
- 確認各 provider 是否在線
- 了解可用模型與其特性
- 用自己的文句在不同模型/設定下測試翻譯品質
- 自行決定哪種業務情境要用哪個模型
- 自行輸入 DeepSeek API key 啟用付費功能

## Known Context

**已確認的決策（本 session 討論結果）：**

**DeepSeek API Key 政策（重要）：**
- 目前 `.env` 有 DeepSeek key 是開發者測試用，**不應自動載入到使用者界面**
- 使用者必須自行在設定頁面輸入 key
- Key 存在 `localStorage`（前端），不傳到後端 env
- 後端在接收 DeepSeek 請求時，key 由前端在 request header 或 body 中傳入
- 使用者未輸入 key 時，DeepSeek 選項顯示為 disabled

**設定頁面功能規格（已決定）：**

A. **系統狀態區塊**（取代舊的 Ollama 狀態）
   - PANJIT 健康狀態：綠/紅指示燈 + 延遲（ping `/v1/models` 或類似端點）
   - DeepSeek 健康狀態：若有 key 則 ping，否則顯示「未設定」
   - 後端需要新的 API endpoint：`GET /api/providers/health`

B. **模型清單區塊**
   - PANJIT 可用模型（從 providers.yml 讀取，或呼叫 `/v1/models`）
   - 每個模型顯示：model ID、context size、建議用途、估計延遲
   - DeepSeek 模型（有 key 時顯示）

C. **模型測試區塊**（核心功能）
   - 使用者輸入單句來源文字
   - 選擇翻譯設定（來源語言、目標語言、翻譯情境 profile）— 與 TranslatePage Step 2 相同的控制項
   - 選擇要測試的模型（可多選）
   - 點擊「測試」→ 後端並行呼叫各模型翻譯同一句話
   - 顯示各模型的：翻譯結果、耗時、COMET 品質分數
   - 後端需要新的 API endpoint：`POST /api/providers/test-translation`
   - COMET 評分：若 `QE_ENABLED=false` 則跳過，只顯示翻譯結果和耗時

D. **DeepSeek API Key 設定**
   - 輸入框（type="password"）
   - 「儲存」按鈕 → 存到 localStorage key `deepseek_api_key`
   - 「清除」按鈕 → 清除 localStorage
   - 顯示目前狀態：已設定 / 未設定
   - **不從後端 env 自動填入**

E. **翻譯預設值**（保留現有功能）
   - 預設來源語言（現有）

**現有程式碼需移除/修改：**
- `app/frontend/src/pages/SettingsPage.jsx` — 全面重寫
- `app/frontend/src/components/domain/VramCalculator.jsx` — 移除（或降為隱藏）
- `app/frontend/src/hooks/useHealthCheck.js` — 改為 provider-aware health check
- `app/frontend/src/api/system.js` — 加入 `fetchProviderHealth()`、`testTranslation()` 等

**需要新增的後端 API：**
- `GET /api/providers/health` — 回傳各 provider 的健康狀態與延遲
- `GET /api/providers/models` — 回傳各 provider 的模型清單（從 providers.yml 讀取）
- `POST /api/providers/test-translation` — 接受 {text, src_lang, targets, profile, models[]} 並行翻譯，回傳 results[]

**COMET 整合：**
- `services/quality_evaluator.py` 的 `run_quality_evaluation()` 已存在
- test-translation endpoint 在翻譯完成後呼叫此函數（若 QE_ENABLED）
- 結果格式：`{model_id, translation, duration_ms, comet_score}`

## Non-goals

- 不保留 GPU VRAM / num_ctx slider（完全移除）
- 不在設定頁面實作完整翻譯工作流（只是單句測試）
- 不實作模型的即時編輯/新增（providers.yml 仍由 admin 管理）

## Constraints

- depends-on: `fallback-chain-cloud-providers`（設定頁面需反映更新後的 provider 設定）
- depends-on: `term-extraction-db-first`（設定頁面的 provider 狀態應反映最終的 provider 架構）
- DeepSeek key 只存 localStorage，後端不持久化 key
- 測試翻譯 endpoint 必須是 async/非阻塞（後端現有翻譯用 BackgroundTasks）
- PANJIT 連線使用 `verify_ssl=False`（自簽憑證）

## Open Questions

- 測試翻譯是否需要 job_id？建議：不需要，使用同步 response（單句很快）
- 測試翻譯要並行還是循序？建議：並行（asyncio.gather），結果一起回傳

## Requested Delivery Date / Priority

最後執行，需等 `fallback-chain-cloud-providers` 和 `term-extraction-db-first` 完成。
