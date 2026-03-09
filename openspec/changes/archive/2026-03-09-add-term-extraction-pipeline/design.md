# Design: Terminology Extraction Pipeline

## Context

翻譯 pipeline 目前包含 Phase 1（Primary Model）與 Phase 2（Refiner）。
本設計在其前插入 Phase 0，由本機 Qwen 9B 負責全文術語萃取與未知術語翻譯，完成後卸載模型再進入翻譯。

## Goals / Non-Goals

- Goals:
  - 自動累積術語庫，跨文件重複使用
  - 術語庫可匯出 / 匯入，支援人工審查與跨專案共用
  - 不依賴外部 LLM API，全程本機執行

- Non-Goals:
  - 不做後處理 Regex 替換（語法風險，尤其韓文黏著語）
  - 不提供術語庫 GUI 管理介面（本期）

## Decisions

### Decision 1：Phase 0 使用本機 Qwen 9B，不依賴外部 API

**理由**：外部 LLM（如 Dify + GPT）對業界專有慣例（例如 `切彎腳 = trim & form`）
不具備優勢，翻譯結果仍需人工修正。Qwen 9B 本機已有、品質相當、無外部依賴。

Phase 0 流程由同一 Qwen 9B 實例依序完成：
1. 萃取術語候選（extraction prompt）
2. 翻譯未知術語（translation prompt）

### Decision 2：Phase 0 為同步阻塞

Phase 0 必須完全結束後才卸載 Qwen 9B、才進入 Phase 1。
若 Qwen 9B 萃取或翻譯過程失敗，以現有 DB 術語繼續，不中斷翻譯。

### Decision 3：Domain 複用 Scenario

Scenario 偵測（`TECHNICAL_PROCESS` / `BUSINESS_FINANCE` / `LEGAL_CONTRACT` 等）在 Phase 0
之前已確定，直接做 `SCENARIO → domain` 映射。

```
SCENARIO_TO_DOMAIN = {
    "TECHNICAL_PROCESS":   "technical",
    "BUSINESS_FINANCE":    "finance",
    "LEGAL_CONTRACT":      "legal",
    "MARKETING_PR":        "marketing",
    "DAILY_COMMUNICATION": "general",
    "GENERAL":             "general",
}
```

### Decision 4：術語注入採 Prompt Injection，不做後處理 Regex

後處理 Regex 在黏著語（韓文助詞 은/는/이/가）會破壞文法。
統一做法：在 Phase 1 & Phase 2 system prompt 附加 `Terminology constraints` 段，
由 LLM 負責語法融合。

| 語言 | Phase 1 注入點 | Phase 2 注入點 |
|------|--------------|--------------|
| 越南 / 德 / 日（HY-MT） | HY-MT system prompt `Terminology constraints` | Refiner system prompt |
| 韓文（TranslateGemma） | N/A（no system prompt） | Refiner system prompt |
| 英 / 中（Qwen single-phase） | Phase 1 system prompt scenario appendix | N/A |

### Decision 5：Term DB 以 SQLite，UNIQUE on (source_text, target_lang, domain)

同一術語在不同 domain 可有不同譯文（如 Pin → chân / chốt），因此 UNIQUE 限制
必須包含 domain，不能只用 (source_text, target_lang)。

## Data Flow

```
文件上傳
  │
  ▼ Scenario 偵測（已有）
  │
  ▼ [Phase 0 - Term Extraction]
  │  1. Qwen 9B 載入
  │  2. 全文分段 → extraction prompt → 術語候選 JSON
  │  3. 合併去重 → all_extracted_terms[]
  │  4. 查詢 Term DB → unknown_terms[]
  │  5. unknown_terms → translation prompt（Qwen 9B）→ [{source, target, confidence}]
  │  6. 寫入 Term DB
  │  7. Qwen 9B 卸載（keep_alive=0）
  │
  ▼ Phase 1：Primary Model（現有，注入術語至 system prompt）
  │
  ▼ Phase 2：Refiner（現有，注入術語至 system prompt）
  │
  ▼ 輸出文件
```

## Term Extraction Prompt（Qwen 9B）

```
你是術語提取專家。請從以下【{domain}】領域文本中，提取所有專有名詞。
包含：品牌名稱、型號、設備名稱、縮寫、製程術語、動作術語、品質術語。
排除：
- 一般動詞、形容詞、介詞
- 數字、單位、數值範圍（如 100mm、±0.5）
- 文件編號、表單編號、版本號（如 SOP-001、Rev.1、Form-A）
- 料號、品號（如 P/N: xxxxx）
- 純代碼縮寫（如 OK、N/A、TBD）

輸出格式為 JSON array，不要任何額外說明：
[{"term": "...", "context": "...（術語出現的短語，10字以內）"}, ...]

文本：
{segment_text}
```

## Term Translation Prompt（Qwen 9B）

```
你是專業術語翻譯員。將以下【{domain}】領域的 {source_lang} 術語翻譯為 {target_lang}。
文件摘要：{document_context}

規則：
1. 根據 context 欄位判斷詞義，避免歧義
2. 品牌名稱、型號、縮寫保留原文不翻譯（confidence=1.0）
3. 優先使用目標語言業界標準術語，避免逐字直譯
4. 輸出嚴格符合 JSON，不加任何說明

術語列表：
{terms_json}

輸出格式：
{"translations": [{"source": "...", "target": "...", "confidence": 0.0~1.0}]}
```

## Export / Import Schema

**Export JSON（最完整，用於備份與遷移）：**

```json
{
  "version": 1,
  "exported_at": "2026-03-09T00:00:00Z",
  "terms": [
    {
      "source_text": "切彎腳",
      "target_text": "trim & form",
      "source_lang": "zh",
      "target_lang": "vi",
      "domain": "technical",
      "context_snippet": "切彎腳機的操作",
      "confidence": 0.95,
      "usage_count": 12
    }
  ]
}
```

**Import 衝突策略：**

| 策略 | 行為 |
|------|------|
| `skip`（預設） | 已存在的 (source, target_lang, domain) 保留舊值，不更新 |
| `overwrite` | 強制以新值蓋寫 |
| `merge` | confidence 較高者勝出 |

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| Qwen 9B 萃取誤報（一般詞彙誤判為術語） | context_snippet 保留供人工審查；import overwrite 可修正 |
| Qwen 9B 術語翻譯偏直譯 | 人工審查後以 import overwrite 修正，後續命中 DB 直接使用 |
| 術語量過大導致 system prompt 過長 | 注入時按 domain 過濾，最多注入 TOP_N 術語（按 usage_count 排序，預設 30） |
| 韓文助詞問題 | 不做後處理 Regex，統一 Prompt Injection，由 Qwen Refiner 處理文法融合 |

## Open Questions

- 術語庫最大注入術語數（TOP_N）預設值建議 30
- Export XLSX 是否需要多語言 sheet 分頁（待使用者確認）
