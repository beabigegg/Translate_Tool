# Change Request

## Original Request

P1-6（改善計畫）：兩個相互獨立但同在 `config.py` / `translation_strategy.py` / `orchestrator.py` 範圍內的改動一起交付：

1. **Deferred context prompt 國際化（i18n）**：
   - 受影響函式：`orchestrator._detect_document_context`（`orchestrator.py:291`）與 `translation_service.py:245-248`（deferred path）。
   - 現況：context-detection prompt 硬寫繁中字串「以下是一份文件的開頭內容，請用一句話描述這份文件的類型、所屬領域和主題。只輸出描述，不要解釋。」，對任何 target_lang 都送相同中文 prompt。
   - 目標：改為依 `target_lang` 從 i18n 模板選 prompt，最少支援 `en`（English）、`zh-TW`（Traditional Chinese）、`ja`（Japanese）三種，其餘語言 fallback 到 `en`。

2. **`OLLAMA_NUM_CTX` 拆分成 `GENERAL_NUM_CTX` / `TRANSLATION_NUM_CTX` 獨立 env**：
   - 受影響模組：`app/backend/config.py`（lines 31-37）。
   - 現況：`GENERAL_NUM_CTX` 和 `TRANSLATION_NUM_CTX` 兩個 Python 常數都衍生自單一 `OLLAMA_NUM_CTX` env var；無法個別覆蓋。
   - 目標：新增 `GENERAL_NUM_CTX` / `TRANSLATION_NUM_CTX` env vars（分別 fallback 到 `OLLAMA_NUM_CTX`，再 fallback 到預設值 4096/3072），並更新 env-contract.md。

## Business / User Goal

- context-detection prompt 以 target language 提問，讓非繁中目標語言（英文、日文等）的 LLM 回應更準確，改善 context flow 的 document summary 品質。
- 允許在不同硬體場景下分別設定 GENERAL 模型（推理用）與 TRANSLATION 模型（翻譯用）的 context window，避免現況「設大影響翻譯速度、設小影響推理品質」的兩難。

## Non-goals

- 不改變 context-detection 觸發條件（`CONTEXT_DETECTION_ENABLED`, `QWEN_CONTEXT_FLOW_ENABLED`）
- 不改變 `build_strategy` / `StrategyDecision` 的資料結構
- 不改 `OLLAMA_NUM_CTX` 的向下相容性（舊有 env 設定仍有效）
- 不改 UI 或 API routes

## Constraints

- `OLLAMA_NUM_CTX` 必須作為 backward-compat fallback 繼續讀取（BR-17 unresolved ref disables provider — 不適用，此為 `os.environ.get` 場景）
- `translate_texts` / `translate_blocks_batch` 函式簽名不變
- 所有現有測試必須通過（396 passed baseline）

## Known Context

- `_detect_document_context`: `app/backend/processors/orchestrator.py:291`
- deferred context path: `app/backend/services/translation_service.py:239-269`
- num_ctx config: `app/backend/config.py:31-37`
- env contract: `contracts/env/env-contract.md`
- target_lang 在 immediate path 由 `targets[0]`（`orchestrator.py:549` 已存進 `refine_client._deferred_context_target`）取得
- target_lang 在 deferred path 由 `_ctx_target`（`translation_service.py:244`）取得

## Open Questions

（無）

## Requested Delivery Date / Priority

P1，緊接 p1-sentence-mode-fix 完成後。
