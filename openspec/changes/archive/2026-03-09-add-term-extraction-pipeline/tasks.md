## 1. Data Model

- [x] 1.1 建立 `app/backend/models/term.py`：定義 `Term` dataclass（source_text, target_text, source_lang, target_lang, domain, context_snippet, confidence, usage_count, created_at）

## 2. Term Database（term_db.py）

- [x] 2.1 建立 `app/backend/services/term_db.py`
- [x] 2.2 實作 `TermDB.__init__`：在 `translated_files/term_db.sqlite` 建立 `terms` table（UNIQUE on source_text, target_lang, domain）
- [x] 2.3 實作 `TermDB.exists(source_text, target_lang, domain) -> bool`
- [x] 2.4 實作 `TermDB.get_unknown(candidates, target_lang, domain) -> list[dict]`：批次過濾已知術語
- [x] 2.5 實作 `TermDB.insert(term: Term, strategy="skip")`：支援 skip / overwrite / merge 衝突策略
- [x] 2.6 實作 `TermDB.get_top_terms(target_lang, domain, top_n=30) -> list[Term]`：按 usage_count 排序
- [x] 2.7 實作 `TermDB.increment_usage(source_text, target_lang, domain)`
- [x] 2.8 實作 `TermDB.export_json(path)` / `export_csv(path)` / `export_xlsx(path)`
- [x] 2.9 實作 `TermDB.import_file(path, strategy="skip") -> dict`：回傳 inserted/skipped/overwritten 計數
- [x] 2.10 實作 `TermDB.get_stats() -> dict`：回傳 total / by_target_lang / by_domain 統計

## 3. Term Extractor（term_extractor.py）

- [x] 3.1 建立 `app/backend/services/term_extractor.py`
- [x] 3.2 實作 `TermExtractor.extract_from_segments(segments, domain) -> list[dict]`：逐段呼叫 Qwen 9B extraction prompt，輸出術語候選列表
- [x] 3.3 實作術語候選 JSON 解析與去重（by term + domain）
- [x] 3.4 實作 `TermExtractor.translate_unknown(terms, source_lang, target_lang, domain, document_context) -> list[dict]`：對未知術語呼叫 Qwen 9B translation prompt，回傳 `[{source, target, confidence}]`
- [x] 3.5 實作 `SCENARIO_TO_DOMAIN` 映射表

## 4. Orchestrator 整合（Phase 0）

- [x] 4.1 在 `orchestrator.py` 的 pipeline 入口插入 Phase 0 流程
- [x] 4.2 Phase 0 順序：extract → filter known → translate unknown → write DB → unload Qwen（keep_alive=0）
- [x] 4.3 支援 `mode=extraction_only`：Phase 0 完成後直接回傳 term_summary，不進 Phase 1
- [x] 4.4 確保 Phase 0 失敗時 pipeline 不中斷（catch exception，log warning，繼續）

## 5. Prompt Injection 整合

- [x] 5.1 在 `translation_strategy.py` 新增 `build_terminology_block(terms: list[Term]) -> str`：產生 `Terminology constraints` 段落
- [x] 5.2 Phase 1 system prompt 組裝時注入術語塊（Qwen single-phase + HY-MT）
- [x] 5.3 Phase 2 Refiner system prompt 組裝時注入術語塊
- [x] 5.4 TranslateGemma（韓文）：僅注入 Phase 2 Refiner，不注入 Phase 1

## 6. 後端 API 擴充

- [x] 6.1 `POST /api/jobs` 接受可選 `mode` 參數（`translation` / `extraction_only`，預設 `translation`）
- [x] 6.2 `GET /api/terms/stats`：回傳 total / by_target_lang / by_domain
- [x] 6.3 `GET /api/terms/export?format=<json|csv|xlsx>`：回傳對應格式檔案下載
- [x] 6.4 `POST /api/terms/import?strategy=<skip|overwrite|merge>`：接受 JSON/CSV 檔案，回傳 inserted/skipped/overwritten

## 7. 前端：萃取模式切換

- [x] 7.1 在設定頁（step 1）新增模式切換：「翻譯」/ 「僅萃取術語」
- [x] 7.2 切換為「僅萃取術語」時，action button 改為「開始萃取」，form data 加入 `mode=extraction_only`
- [x] 7.3 `api.js` 新增 `submitExtractionJob(formData)` 或讓現有 `submitJob` 支援 mode 參數

## 8. 前端：萃取進度與結果顯示

- [x] 8.1 extraction_only job 執行中顯示萃取進度（段落進度 N/M）
- [x] 8.2 job 完成後顯示 term_summary（萃取 N 筆 / 略過 N 筆 / 新增 N 筆）
- [x] 8.3 顯示「匯出結果」按鈕，觸發 `GET /api/terms/export?format=json`

## 9. 前端：術語庫管理面板

- [x] 9.1 新增「術語庫」入口按鈕或 tab（主 UI 任意步驟可見）
- [x] 9.2 面板顯示統計：total / by_target_lang / by_domain（呼叫 `GET /api/terms/stats`）
- [x] 9.3 匯出功能：格式選擇器（JSON / CSV / XLSX）+ 下載觸發
- [x] 9.4 匯入功能：檔案選擇器（.json / .csv）+ 衝突策略選擇器 + 確認上傳
- [x] 9.5 匯入完成後顯示結果摘要並重新整理統計

## 10. 測試

- [x] 10.1 `TermDB` 單元測試：insert / skip / overwrite / merge 衝突策略
- [x] 10.2 `TermDB` export / import 往返測試（JSON round-trip）
- [x] 10.3 `TermExtractor.extract_from_segments` prompt 輸出解析測試（mock Qwen 回傳）
- [x] 10.4 `TermExtractor.translate_unknown` prompt 輸出解析測試（mock Qwen 回傳）
- [x] 10.5 Orchestrator Phase 0 順序測試（正常 / Qwen 失敗兩種情境）
- [x] 10.6 Orchestrator extraction_only 模式測試（Phase 1 不執行）
- [x] 10.7 `/api/terms/stats` / `/api/terms/export` / `/api/terms/import` API 測試
