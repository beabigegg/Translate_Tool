# Change Request

## Original Request

`config/providers.yml` 的 `fallback_chain` 目前為 `[panjit, ollama-local]`。
`ollama-local` 標記為 `role: layout_assist_only`，不應出現在翻譯 fallback chain。
改為 `[panjit, deepseek]`，且 deepseek 僅在使用者自行提供 API key 後才生效。

## Business / User Goal

系統已全面改用雲端 API（PANJIT 為主），本地 Ollama 不再承擔翻譯工作。
fallback chain 應反映現實，避免 PANJIT 失敗時嘗試打不存在的地端翻譯模型。

## Known Context

**已確認的決策（本 session 討論結果，勿更動）：**

1. `ollama-local` 從 fallback_chain 完全移除。
2. DeepSeek 作為第二 fallback，但**預設不啟用**；需使用者透過設定頁面自行輸入 API key 才啟動。
   - 目前 `.env` 有 DeepSeek key 是開發測試用；上線後預設無 key。
   - DeepSeek key UI 屬於 `settings-page-cloud-redesign`，本 change 不實作 UI。
3. `ollama-local` provider 條目本身保留在 providers.yml（版面偵測需要），只從 fallback_chain 移除。
4. `app/backend/processors/orchestrator.py` 約第 431–466 行有另一段走訪 fallback_chain 的邏輯，需同步移除 `ollama-local` 分支。
5. DeepSeek 的啟用判斷條件：`providers.yml` 中 `enabled: ${DEEPSEEK_ENABLED:-false}`；使用者未提供 key 時保持 false。

**相關程式碼位置：**
- `config/providers.yml` — fallback_chain: [panjit, ollama-local] → [panjit, deepseek]
- `app/backend/processors/orchestrator.py:431-466` — fallback 走訪邏輯
- `app/backend/config.py` — 相關常數（如有）

## Non-goals

- DeepSeek key 的 UI 輸入介面（屬於 settings-page-cloud-redesign）
- layout detection Ollama 路徑（parsers/layout_detector.py 不動）
- 其他 providers.yml 路由規則

## Constraints

- 不引入新 Python 套件
- layout_detector.py 不得受影響

## Requested Delivery Date / Priority

高優先。是 `settings-page-cloud-redesign` 的前置條件。
