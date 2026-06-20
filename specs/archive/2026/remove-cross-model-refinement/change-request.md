# Change Request

## Original Request

移除 cross-model refinement（HY-MT → Qwen 二階段潤色）功能。
此功能是針對地端 7B 小模型的補丁，雲端路徑已設 `refine_model=None` 完全不執行。
改用 PANJIT 120B 模型後此功能廢棄，是死碼（dead code）。

## Business / User Goal

清除已無用的地端 refinement 路徑，降低程式複雜度，避免未來維護者誤解此功能仍在作用中。

## Known Context

**已確認的決策（本 session 討論結果，勿更動）：**

**Cross-model refinement 的原始設計：**
- Step 1：HY-MT 7B（翻譯專用小模型）翻譯越/德/日文
- Step 2：Qwen 9B（通用 LLM）看 [SOURCE] + [DRAFT] → 潤色自然度
- 兩個小模型互補短處

**現況分析：**
- `app/backend/services/model_router.py:200`：Cloud 路徑 `refine_model=None`（不執行 refinement）
- `app/backend/processors/orchestrator.py:494-506`：建立 `refine_client = OllamaClient(...)` 但 cloud 路徑根本不走到這裡
- PANJIT `gpt-oss:120b` 本身已足夠強，不需要二階段潤色
- `CROSS_MODEL_REFINEMENT_ENABLED` 預設 `"1"`（true），但 cloud 路徑的 `refine_model=None` 讓它完全無效

**需要刪除的程式碼：**
- `app/backend/config.py` — `CROSS_MODEL_REFINEMENT_ENABLED`、`REFINEMENT_ENABLED`、`REFINEMENT_MIN_CHARS` 常數（若相關）
- `app/backend/processors/orchestrator.py` — `refine_client` build block（約 494–506 行）、所有 `refine_client` 使用處（約 545、551–553、668–674、697、728、747、761 行）
- `app/backend/clients/ollama_client.py` — `refine_translation()` 方法（約 510–531 行）、`_build_refine_prompt()`、`_build_refine_system_prompt()`（約 533–600+ 行）
- `app/backend/services/model_router.py` — `refine_model` 欄位（RouteGroup 約 71 行）、`refine_model` 賦值邏輯（約 212–223 行）
- `tests/test_hy_mt_quality_refinement.py` — 整個測試檔案退役（或移至 archive）

**注意：**
- HY-MT 和 TranslateGemma 的本地模型路由條目（model_router.py 第 43–44 行）也可一併移除，因為這些模型現在完全不使用。
- 移除後 `model_router.py` 的 RouteGroup 不應有 `refine_model` 欄位。

## Non-goals

- 不建立雲端版的 refinement（translate-then-critique 屬於未來功能）
- 不修改 layout detection 路徑

## Constraints

- 移除後所有現有翻譯測試仍需通過
- Cloud 路徑（PANJIT）的翻譯行為不得改變

## Requested Delivery Date / Priority

高優先。是 `term-extraction-db-first` 的前置條件（兩者都改 orchestrator.py / model_router.py）。
