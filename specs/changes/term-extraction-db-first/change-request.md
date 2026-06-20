# Change Request

## Original Request

Phase 0 術語萃取目前硬編碼走地端 Ollama（localhost:11434），每次翻譯都對同一段文字呼叫 LLM 兩次（一次萃取、一次翻譯），浪費時間且依賴地端 GPU。

改為：先查 term DB（embedding 相似度），命中術語直接以 LLM-side glossary 注入；DB sparse 才呼叫 PANJIT LLM 萃取（不再打地端 Ollama）。

## Business / User Goal

- 消除術語萃取的地端 Ollama 依賴
- 減少重複 LLM call（DB 有術語時完全不需要萃取 call）
- 術語注入使用 LLM-side 方式（放入 system prompt），不做後處理字串替換

## Known Context

**已確認的決策（本 session 討論結果）：**

**注入方式決策：LLM-side injection（確認）**
- 把命中術語以 Markdown 表格格式注入 system prompt
- 讓 LLM 在翻譯時自行套用術語，不做 post-process 機械替換
- 術語命中率由後續 term_audit 驗證（已有 `services/term_audit.py`）
- 這個決策已在 session 中確認，不需要重新討論

**新流程設計（已決定）：**
```
翻譯請求到來
  └─ Step 1: Embedding lookup
       使用 PANJIT Qwen3-Embedding-8B 對 source segments 做向量化
       在 term_db 查找語意相似術語（similarity threshold 需設定）
       └─ 有命中 → build_terminology_block() 注入 system prompt → 翻譯
       └─ 無命中（DB sparse）→ 呼叫 PANJIT gemma4:latest 萃取術語 → 存入 DB → 注入 → 翻譯
```

**現有程式碼分析：**

**需修改的檔案：**
- `app/backend/services/term_extractor.py`
  - `run_phase0_multi()` — 目前硬編碼 `base_url=OLLAMA_BASE_URL`（localhost:11434）
  - `_call()` 方法 — 直接打 `/api/generate`（Ollama 格式）
  - 需改為：先 embedding lookup，hit → skip LLM call；miss → 打 PANJIT OpenAI-compatible endpoint
  - PANJIT embedding endpoint：`POST {PANJIT_LLM_BASE_URL}/v1/embeddings`，model `Qwen3-Embedding-8B`
  - PANJIT 萃取 LLM endpoint：`POST {PANJIT_LLM_BASE_URL}/v1/chat/completions`，model `gemma4:latest`（輕量）

- `app/backend/services/term_db.py`
  - 可能需要加 `get_similar_terms_by_embedding()` 方法
  - 現有 `get_document_terms()` 是精確查詢，需要語意相似查詢

- `app/backend/processors/orchestrator.py`
  - `_phase0_hook`（約 617–637 行）：`run_phase0_multi(base_url=OLLAMA_BASE_URL)` → 改用 provider config
  - term injection 邏輯（約 658–674 行）：已有 `build_terminology_block()` 注入，保留此機制

**PANJIT Embedding 能力（improvement-plan.md §6.1 已確認）：**
- Endpoint：`Qwen3-Embedding-8B`（32K context）
- Reranker：`bge-reranker-v2-m3`（可選，二階段過濾）
- 兩者都是免費的 PANJIT 服務

**Similarity threshold：**
- 初始建議 0.75（需可由 config 設定）
- 低於閾值視為 DB sparse，走 LLM 萃取

**萃取用 LLM 模型選擇（已決定）：**
- `gemma4:latest`（PANJIT，8B，輕量快速，適合 NER 任務）
- 不用 `gpt-oss:120b`（太重，術語萃取不需要）

## Non-goals

- 不改動 extraction_only 模式（使用者主動要求術語萃取，仍走完整 LLM 流程）
- 不改動 term_db 的 CRUD API
- Wikidata lookup 不動
- 不實作 embedding 向量的持久化儲存（第一版用即時計算，之後可加 pgvector/sqlite-vss）

## Constraints

- depends-on: `remove-cross-model-refinement`（兩者都改 orchestrator.py，避免衝突）
- 不引入 vector DB 套件（pgvector/chromadb/faiss）— 第一版用 cosine similarity 即時計算
- PANJIT 的 embedding endpoint 需使用 `verify_ssl=False`（自簽憑證）
- 地端 Ollama 呼叫完全從 term_extractor.py 的翻譯路徑移除

## Open Questions

- Embedding similarity 計算：對整個 source text 還是 per-segment？建議 per-segment（與現有 `run_phase0_multi` 的 segments 參數一致）
- 若 embedding call 失敗（PANJIT 暫時無法連線），fallback 行為：跳過術語注入（保守）或走 LLM 萃取（激進）？建議：跳過，翻譯照常進行（非致命路徑）

## Requested Delivery Date / Priority

中優先。需等 `remove-cross-model-refinement` 完成後再進行（避免 orchestrator.py 衝突）。
