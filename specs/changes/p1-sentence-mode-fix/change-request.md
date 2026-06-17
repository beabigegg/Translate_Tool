# Change Request

## Original Request

Fix SENTENCE_MODE批次路徑的三個缺陷，使其行為與逐句（非SENTENCE_MODE）路徑一致：

1. **placeholder不一致**：非SENTENCE_MODE失敗時寫入 `[Translation failed|{tgt}] {original_text}`（含原文）；SENTENCE_MODE批次失敗時 tmap 存入的是句子級別的 inline marker 拼接，未提供一致的 block 級別 placeholder。
2. **done/fail count不一致**：SENTENCE_MODE 在批次完成後一次性遞增 `done += len(texts_to_translate) + dedup_saved`，即使批次中斷（stop_flag）也會多計；非SENTENCE_MODE 在迴圈內逐段遞增，中斷即停。
3. **缺乏 stop_flag 支援**：SENTENCE_MODE 呼叫 `translate_blocks_batch` 無法在批次執行中途響應 stop_flag；批次完成後也無 `if stopped: break` 跳出 outer targets 迴圈。

受影響的模組：`app/backend/services/translation_service.py`、`app/backend/utils/translation_helpers.py`、`app/backend/utils/translation_verification.py`。

## Business / User Goal

保證在 SENTENCE_MODE 下失敗段落可被識別、可被重試（`verify_and_fill_tmap` 已在 docx/xlsx/pptx 呼叫側存在），且 done/fail 計數與非 SENTENCE_MODE 路徑一致，使 metrics 端點（`p1-observability-metrics`）回報的 `provider_failure_count`、`translation_count` 數值可信。

## Non-goals

- 不改變批次翻譯策略或 batch size 邏輯
- 不改動 PDF processor 的 `verify_and_fill_dict` 呼叫（已獨立實作）
- 不加入 E2E / 壓測覆蓋（Tier 2）

## Constraints

- API 行為（HTTP routes、回應 schema）不變
- `translate_texts` 函式簽名維持不變（現有呼叫者不需改動）
- 修改必須通過現有完整測試套件（389 passed 基線）

## Known Context

- `SENTENCE_MODE` 在 `app/backend/config.py` 中為環境變數旗標，預設為 True
- `translate_blocks_batch` 位於 `translation_helpers.py:385`，由 `BatchTranslator` 驅動
- `verify_and_fill_tmap` 位於 `translation_verification.py:49`，由 docx/xlsx/pptx 處理器在 `translate_texts` 之後呼叫
- PDF processor 使用 `verify_and_fill_dict`，不在本 change 範圍內

## Open Questions

（無）

## Requested Delivery Date / Priority

P1 優先，接續 p1-observability-metrics 完成後立即開始。
