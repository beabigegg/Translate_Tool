# Change Request

## Original Request

新增 OpenAICompatibleClient，支援 Panjit（gpt-oss:120b / Qwen3.6-35B-A3B-4bit）與 DeepSeek（deepseek-v4-flash）雲端端點，以 OpenAI /v1/chat/completions 相容介面實作 LLMClient Protocol；新增 config/providers.yml 設定外部化，移除 model_router.py 硬編碼路由表，改為讀設定驅動；主後端離線時自動 fallback 並在 JobStatus 記錄使用的 provider。

## Business / User Goal

將翻譯主力從僅支援本地 Ollama 擴展為支援雲端 LLM 端點（Panjit 免費 gateway / DeepSeek 付費升級），消除本地 GPU 過載或不可用時的整條流程癱瘓問題。使用者可透過環境變數切換端點無需改碼；主端點離線時自動 fallback 並在 JobStatus 記錄使用的 provider。

## Non-goals

- 不包含 DeepLClient（P3-8）
- 不包含路由觀測性指標端點（p1-observability-metrics）
- 不包含 COMET/LLM-as-judge 品質評估
- 不包含多目標語言精準路由（p1-provider-routing 範疇）
- 版面偵測 / OCR / 字型 LRU cache 不在本提案範疇

## Constraints

- `OpenAICompatibleClient` 必須實作 `LLMClient` Protocol（定義於 `app/backend/clients/base_llm_client.py`），不得依賴 OllamaClient 內部
- 已驗證端點：Panjit（`PANJIT_LLM_BASE_URL` / `PANJIT_API`）與 DeepSeek（`DEEPSEEK_BASE_URL` / `DEEPSEEK_API`）均相容 OpenAI `/v1/chat/completions`
- 雲端端點為主翻譯路徑；Ollama 本地端保留但降為 fallback / 版面輔助
- `config/providers.yml` 以環境變數插值（`${VAR:-default}` 語法），由 `config.py` 載入
- `.env` 中已有端點設定，不得將 API key 寫入程式碼或版本控制

## Known Context

- `app/backend/clients/base_llm_client.py`：`LLMClient(Protocol)` 已定義（p1-llm-client-abstraction 完成）
- `app/backend/clients/ollama_client.py`：`OllamaClient` 已有 Protocol alias methods
- `app/backend/services/model_router.py`：目前硬編碼語言→模型映射，需改為讀 providers.yml
- `app/backend/services/translation_service.py`：已依賴 `LLMClient` 介面
- `docs/improvement-plan.md` §3.1：詳細端點能力彙整、providers.yml 設計、路由規則

## Open Questions

（無）

## Requested Delivery Date / Priority

P1 里程碑，高優先。依賴本提案：p1-provider-routing、p1-observability-metrics。
