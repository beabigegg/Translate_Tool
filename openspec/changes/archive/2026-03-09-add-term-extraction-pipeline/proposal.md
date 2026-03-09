# Change: Add Terminology Extraction Pipeline (Phase 0)

## Why

術語注入目前是靜態硬編碼於 `translation_strategy.py`，無法跨文件累積專業術語知識。
新增 Phase 0 術語萃取流程，讓系統隨使用時間自動建立術語庫，提升翻譯一致性與準確性。

## What Changes

- **新增 Phase 0**：Qwen 9B 全文掃描，萃取寬定義「專有名詞」，同一 Qwen 9B 實例接著翻譯未知術語，完成後卸載模型再進入翻譯
- **新增 Term DB**（SQLite）：儲存術語對應，含 domain、context_snippet、confidence、usage_count 欄位，以 `(source_text, target_lang, domain)` 做 UNIQUE 索引
- **術語注入**：以 Prompt Injection 方式注入 Phase 1 & Phase 2 system prompt 的 `Terminology constraints` 段，不做後處理 Regex 替換
- **Export / Import**：支援匯出（JSON / CSV / XLSX）與匯入（衝突策略：skip / overwrite / merge by confidence）

## Impact

- Affected specs: `term-extraction`（新建）、`translation-backend`（修改 pipeline + 新增 API）、`frontend-ui`（新增模式切換與術語庫管理）
- Affected code: `orchestrator.py`、`translation_strategy.py`、`ollama_client.py`、`routes/`
- New modules: `services/term_extractor.py`、`services/term_db.py`、`models/term.py`
- Frontend: 新增 extraction-only 模式切換、萃取進度與結果顯示、術語庫管理面板（統計/匯出/匯入）
