# Change Request

## Original Request

新增 services/term_audit.py：翻譯完成後掃描譯文檢查每個 approved 術語是否一致套用，產出 terminology_hit_rate 與未套用清單寫入 qa-report，並驗證 rejected 術語 0 注入。

P2-8（改善計畫 §3.3.3，痛點 5）：新增 `app/backend/services/term_audit.py`：翻譯完成後掃描譯文，檢查每個 `approved` 術語是否一致套用，產出 `terminology_hit_rate` 與未套用清單，寫入 `qa-report`。確認譯文最終確實一致套用術語表（terminology hit rate），補上目前完全缺失的術語套用一致性稽核。

## Business / User Goal

提供「譯文是否真的套用了術語表」的可量測證據，閉環 P1 術語狀態機與 P2 glossary 注入。目標：對含 20 個 approved 術語的測試文件，hit rate 報告可產出且 ≥ 95%；`rejected` 術語 0 注入。

## Non-goals

- 不含 glossary 注入本身（`p2-prompt-fewshot-glossary`）；本 change 只稽核結果。
- 不含 COMET QE（`p2-comet-qe`）。
- 不含 XLIFF/TBX/TMX 互通（P3-6）。

## Constraints

- 依賴 P1 術語狀態機 `{unverified, needs_review, approved, rejected}`（已完成）；稽核對象為 `approved`。
- hit rate 計算需處理大小寫 / 詞形變化 / 多目標語言；演算法須於 design 載明並可測。
- 報告寫入既有 `qa-report` 結構，不另立平行報告格式。

## Known Context

- 新模組：`app/backend/services/term_audit.py`
- 術語庫：`app/backend/services/term_db.py`（P1 狀態機）、`models/term.py`
- 改善計畫 §3.3、驗收標準
- 與 `p2-prompt-fewshot-glossary` 互補：一個注入、一個稽核

## Open Questions

- 詞形變化 / 形態學比對的嚴格度（精確比對 vs lemmatized 比對）。

## Requested Delivery Date / Priority

P2 軌道 C，Wave 1（獨立，低風險，可立即開始）。
