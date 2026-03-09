# Translation Pipeline Configuration Reference

> 生成日期：2026-03-09（更新：2026-03-09 新增 Phase 0 術語萃取流程）
> 基於 `model_router.py`、`translation_strategy.py`、`ollama_client.py`、`config.py`、`orchestrator.py`、`translation_service.py`、`term_extractor.py`、`term_db.py`

---

## 1. 系統架構總覽

```
使用者上傳檔案
     │
     ▼
① 路由決策 (model_router.py)
   按目標語言選擇 Primary Model + Profile
     │
     ▼
② 文件採樣 (orchestrator.py)
   擷取前 ~500 字用於 Context Detection / Scenario Detection
     │
     ├─ Primary = General (Qwen) ──→ 立即執行 Context Detection
     └─ Primary = Dedicated (HY-MT/Gemma) ──→ deferred（Phase 2 後執行）
     │
     ▼
③ 動態 Scenario 偵測 (translation_strategy.py)
   filename + sample_text → 關鍵字評分 → Scenario
   → 修改 system_prompt / decode options / cache_variant
   → Scenario 映射為術語 domain（TECHNICAL_PROCESS→technical 等）
     │
     ▼
④ Phase 0：術語萃取 (term_extractor.py + term_db.py)  ← 新增
   ├─ Qwen 9B 載入
   ├─ 全文分段 → extraction prompt → 術語候選 JSON（含 context_snippet）
   ├─ 合併去重 → 查 Term DB → 過濾已知術語
   ├─ 未知術語 → translation prompt（Qwen 9B）→ {source, target, confidence}
   ├─ 寫入 Term DB（SQLite: translated_files/term_db.sqlite）
   ├─ Qwen 9B 卸載（keep_alive=0）
   │
   │  [若 mode=extraction_only：Phase 0 完成後直接回傳 term_summary，跳過 Phase 1/2]
   │
   └─ 取 Top-30 術語 → 注入 Phase 1 & Phase 2 Terminology constraints
     │
     ▼
⑤ Phase 1：Primary Model 翻譯 (translation_service.py)
   快取命中 → 直接使用（若有 refiner cache 則兩個 Phase 都跳過）
   未命中 → 送 Ollama（system prompt 含術語注入），結果寫入 Phase-1 cache
     │
     ▼
⑥ Phase 2：Cross-Model Refiner（僅限有 refine_model 的路由）
   HY-MT/Gemma 卸載 VRAM → Qwen 9b 載入
   ├─ 執行 deferred Context Detection（若有）
   ├─ 逐段精修 [SOURCE] + [DRAFT] → Corrected（system prompt 含術語注入）
   └─ 精修結果寫入 Phase-2（refiner）cache
     │
     ▼
⑦ 輸出文件
```

---

## 2. 路由表（按目標語言）

| 目標語言 | Primary Model | Profile | model_type | Phase 2 Refiner |
|---------|--------------|---------|-----------|----------------|
| **Vietnamese** | `demonbyron/HY-MT1.5-7B:Q4_K_M` | `technical_process` | `translation` | Qwen 3.5:9b |
| **German** | `demonbyron/HY-MT1.5-7B:Q4_K_M` | `technical_process` | `translation` | Qwen 3.5:9b |
| **Japanese** | `demonbyron/HY-MT1.5-7B:Q4_K_M` | `technical_process` | `translation` | Qwen 3.5:9b |
| **Korean** | `translategemma:4b` | `general` | `general` | Qwen 3.5:9b |
| **English、繁/簡中、Thai 等其他** | `qwen3.5:9b` | `general` | `general` | 無（直接輸出）|

> 依據：2026 年 3 月 Full-Factorial Benchmark。
> Qwen 在 zh→ja 的 BLEU 僅 11.97（catastrophic），HY-MT 顯著優勝；TranslateGemma 在 zh→ko 略勝。

---

## 3. 語言對詳細流程

### 3.1 簡體中文 → 越南文（代表性最完整流程）

#### Step 1：路由決策

```
目標語言 = "Vietnamese"
→ Primary: HY-MT 1.5-7B:Q4_K_M  (model_type=translation)
→ Profile: technical_process
→ Refiner: qwen3.5:9b
```

#### Step 2：文件採樣與 Context Detection（Deferred）

由於 Primary 是 HY-MT（dedicated translation model），無法在 Phase 1 前用 HY-MT 做 context detection。
改為在 `refine_client` 上設定 deferred 屬性：

```python
refine_client._deferred_context_sample = "<前500字>"
refine_client._deferred_context_profile = "technical_process"
refine_client._deferred_context_target = "Vietnamese"
```

Context Detection 在 Phase 2 開始時（HY-MT 卸載後）執行，Prompt 為：

```
以下是一份文件的開頭內容，請用一句話描述這份文件的類型、所屬領域和主題。
只輸出描述，不要解釋。

{文件前500字}
```

回傳範例：`這是一份屬於工業設備維護領域的技術文檔，主題為 SMD C MAX 切彎腳機的操作與保養指南。`

#### Step 3：動態 Scenario 偵測

Profile `technical_process` 有固定 Scenario hint，**不做關鍵字評分**，直接鎖定：

```
Scenario = TECHNICAL_PROCESS（forced）
```

Scenario 決定的修改：

```python
# options_override（TRANSLATION model type）
{
    "temperature": 0.20,
    "top_p": 0.55,
    "top_k": 30,
    "repeat_penalty": 1.12,
}

# system_prompt appendix（附加在 profile 基礎 prompt 後）
"""
Scenario focus: Technical process documentation.
Style rules:
- Prioritize operational clarity and step-by-step executability.
- Preserve process limits, tolerances, units, and machine parameters exactly.
- Keep terminology consistent for SOP/OI/CP style instructions.
Terminology constraints:
- 切弯脚 / 切彎腳 => trim & form
- 作业指导书 / 作業指導書 => work instruction
- 作业指导卡 / 作業指導卡 => work instruction card
- 制程 => process
"""

# cache_variant
"technical_process_glossary"
```

#### Step 4：Phase 1 — HY-MT 翻譯

**System Prompt（完整）：**

```
Role declaration:
You are a professional translator for technical process and SOP documents.

Terminology guidance:
Use precise process engineering terminology and keep operation names, machine parameters,
tolerances, and quality control terms consistent across the file.

Register and tone:
Use exact and executable wording suitable for on-line operations and work instructions.
Avoid calque or word-for-word rendering; use phrasing natural to a native speaker of the target language.

Output rules:
1) Output only the translated text.
2) Never add explanations, commentary, or markdown wrappers.
3) Preserve line breaks and formatting structure.
4) If the input text is already entirely in the target language, return it unchanged without modification.
5) For short labels or column headers that already contain the target language alongside other languages, return the original text unchanged.
6) Prefer natural, idiomatic phrasing in the target language over literal or word-for-word translation.

Numerical and code preservation:
Preserve all numbers, units, formulas, model numbers, article/section numbering, URLs, and code tokens exactly.

Scenario focus: Technical process documentation.
[... appendix ...]
```

**Prompt Template（HY-MT dedicated，有 Chinese 來源）：**

```
将以下文本翻译为Vietnamese，注意只需要输出翻译后的结果，不要额外解释：

{原文}
```

**Decode 參數：**

| 參數 | 基礎值（config.py TRANSLATION） | Scenario Override | 最終值 |
|-----|-------------------------------|------------------|-------|
| `num_ctx` | 3072 | — | **3072** |
| `temperature` | 0.05 | 0.20 | **0.20** |
| `top_p` | 0.50 | 0.55 | **0.55** |
| `top_k` | 10 | 30 | **30** |
| `repeat_penalty` | 1.0 | 1.12 | **1.12** |
| `frequency_penalty` | 0.0 | — | **0.0** |
| `num_gpu` | 99（全部 GPU） | — | **99** |
| `kv_cache_type` | q4_0 | — | **q4_0** |
| `think` | false（強制關閉） | — | **false** |

**CJK N/A Token 直接 Bypass（不送 LLM）：**

```python
# 若輸入文字 ∈ {"无", "無", "无。", "無。"}
→ 直接返回 "Không có"（Vietnamese）
```

**幻覺偵測（短輸入保護）：**

```python
# 若 len(input) < 10 且 len(output) > max(len(input) * 20, 100)
→ 返回原始輸入（passthrough）
```

**快取 Key（Phase 1）：**

```
demonbyron/HY-MT1.5-7B:Q4_K_M::technical_process::translation::scenario=technical_process_glossary
```

#### Step 5：Phase 2 — Qwen 9b 精修

HY-MT 卸載（`keep_alive=0`）→ Qwen 9b 載入

**執行 Deferred Context Detection：**

```python
prompt = "以下是一份文件的開頭內容，請用一句話描述..."
→ detected_context = "這是一份屬於工業設備維護領域的技術文檔..."
```

**Refiner System Prompt（完整）：**

```
You are a senior Vietnamese process/manufacturing engineer at a discrete component plant
reviewing a machine-translated SOP/maintenance manual draft.

Rules:
1. Cross-reference the [SOURCE] to verify professional terminology in the [DRAFT].
2. Correct unnatural literal renderings to standard industrial terms.
3. Department names: Chinese '部' (bù) in a factory context = 'Phòng' in Vietnamese
   (e.g., 工务部 → Phòng Kỹ thuật, 品质部 → Phòng Chất lượng, 生产部 → Phòng Sản xuất).
   Never use 'Bộ' for internal factory departments — 'Bộ' denotes a national ministry.
4. Ensure register matches standard SOP/work instruction formality.
5. Output ONLY the corrected Vietnamese. No explanations, no dialogue.

Document context: 這是一份屬於工業設備維護領域的技術文檔，主題為 SMD C MAX 切彎腳機的操作與保養指南。
```

**Refiner Prompt（逐段）：**

```
[SOURCE]: {原文}
[DRAFT]: {HY-MT 翻譯}

Corrected Vietnamese:
```

**Refiner Decode 參數（GENERAL 基礎，無 Scenario Override）：**

| 參數 | 值 |
|-----|----|
| `num_ctx` | 4096 |
| `temperature` | 0.05 |
| `top_p` | 0.50 |
| `top_k` | 10 |
| `repeat_penalty` | 1.0 |
| `frequency_penalty` | 0.0 |

**精修跳過條件：**
- 該 segment 已在 refiner cache 中命中 → 直接使用快取
- `len(source_text) < 3`（REFINEMENT_MIN_CHARS）→ 跳過

**快取 Key（Phase 2 / Refiner）：**

```
qwen3.5:9b
```

---

### 3.2 簡體中文 → 德文 / 日文

與 3.1（越南文）流程**完全相同**，差異僅在：

- Refiner System Prompt 不含越南文「部→Phòng」術語規則
- `_LANGUAGE_NA` bypass 映射不同（日文 `なし`，德文 `Keine`）

---

### 3.3 簡體中文 → 韓文

#### 路由

```
Primary: translategemma:4b  (model_type=general)
Profile: general
Refiner: qwen3.5:9b
```

#### Phase 1 — TranslateGemma

**Prompt Template（TranslateGemma 專用 no-system prompt）：**

```
You are a professional Chinese (zh) to Korean (ko) translator.
Your goal is to accurately convey the meaning and nuances of the original Chinese text
while adhering to Korean grammar, vocabulary, and cultural sensitivities.
Produce only the Korean translation, without any additional explanations or commentary.
Please translate the following Chinese text into Korean:

{原文}
```

**Context Detection：**
TranslateGemma 屬 `general` model type，但 `_is_translation_dedicated()` 回傳 `False`。
Context Detection **立即執行**（不 deferred）。

**Decode 參數（GENERAL type）：**

| 參數 | Scenario GENERAL | 最終值 |
|-----|-----------------|-------|
| `num_ctx` | 4096 | **4096** |
| `temperature` | 0.05 | **0.05** |
| `top_p` | 0.50 | **0.50** |
| `top_k` | 10 | **10** |

#### Phase 2 — Qwen 9b Refiner

Refiner System Prompt（韓文 general）：

```
You are a senior Korean professional reviewing a machine-translated document draft
in a manufacturing context.

Rules:
1. Cross-reference the [SOURCE] to verify terminology and meaning in the [DRAFT].
2. Correct unnatural literal renderings to fluent, idiomatic phrasing.
3. Preserve the register and formality of the original document.
4. Output ONLY the corrected Korean. No explanations, no dialogue.
```

若有 Context Detection 結果：

```
...（同上）

Document context: {detected_context}
```

---

### 3.4 簡體中文 → 英文 / 繁體中文 / 其他

#### 路由

```
Primary: qwen3.5:9b  (model_type=general)
Profile: general
Refiner: 無（單 Phase）
```

#### Context Detection（立即，Phase 1 前）

Qwen 9b 本身做 context detection，結果注入 system_prompt：

```
Document context: {detected_context}
```

#### Scenario 偵測（自動，關鍵字評分）

filename + sample_text 內若有 ≥2 個關鍵字命中，升級 scenario：

| Scenario | 典型觸發詞 |
|---------|----------|
| `TECHNICAL_PROCESS` | `sop`, `oi`, `作业指导`, `设备`, `制程`, `良率` |
| `BUSINESS_FINANCE` | `财报`, `毛利`, `报价`, `invoice`, `ebitda` |
| `LEGAL_CONTRACT` | `合同`, `条款`, `shall`, `compliance`, `赔偿` |
| `MARKETING_PR` | `品牌`, `营销`, `campaign`, `slogan` |
| `DAILY_COMMUNICATION` | `谢谢`, `抱歉`, `please`, `let me know` |
| `GENERAL`（預設） | 未達 2 個關鍵字命中 |

**TECHNICAL_PROCESS Decode 參數（GENERAL model type）：**

| 參數 | 基礎值 | Override | 最終值 |
|-----|-------|---------|-------|
| `temperature` | 0.05 | 0.20 | **0.20** |
| `top_p` | 0.50 | 0.75 | **0.75** |
| `top_k` | 10 | 40 | **40** |
| `repeat_penalty` | 1.0 | 1.12 | **1.12** |
| `frequency_penalty` | 0.0 | 0.20 | **0.20** |

**GENERAL（無 Scenario）Decode 參數：**

| 參數 | 值 |
|-----|---|
| `temperature` | **0.05**（greedy） |
| `top_p` | 0.50 |
| `top_k` | 10 |
| `repeat_penalty` | 1.0 |
| `frequency_penalty` | 0.0 |

**Prompt Template（Qwen with system_prompt）：**

```
# System:
{system_prompt（含 profile + scenario appendix + doc_context）}

# User:
Translate from Simplified Chinese to English:

{原文}
```

---

## 4. Phase 0 術語萃取機制（新增）

### 概覽

Phase 0 在 Phase 1 之前執行，由本機 Qwen 9B 負責：
1. 全文分段術語萃取（extraction prompt）
2. 未知術語翻譯（translation prompt）
3. 結果寫入 Term DB（SQLite）
4. 卸載 Qwen 9B，釋放 VRAM 供 Phase 1 使用

### Scenario → Domain 映射

| Scenario | Domain |
|---------|--------|
| `TECHNICAL_PROCESS` | `technical` |
| `BUSINESS_FINANCE` | `finance` |
| `LEGAL_CONTRACT` | `legal` |
| `MARKETING_PR` | `marketing` |
| `DAILY_COMMUNICATION` | `general` |
| `GENERAL` | `general` |

### Term Extraction Prompt（Qwen 9B）

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

### Term Translation Prompt（Qwen 9B）

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

### Terminology 注入點

| 語言 | Phase 1 注入 | Phase 2 注入 |
|-----|------------|------------|
| Vietnamese / German / Japanese（HY-MT） | ✅ HY-MT system prompt `Terminology constraints` | ✅ Refiner system prompt |
| Korean（TranslateGemma） | ❌（無 system prompt） | ✅ Refiner system prompt |
| English / 中文（Qwen single-phase） | ✅ Phase 1 system prompt scenario appendix | N/A |

- 注入上限：每次最多 Top 30 術語（按 `usage_count` 排序）
- 術語塊格式：`- {source_text} => {target_text}`

### mode=extraction_only

`POST /api/jobs` 傳入 `mode=extraction_only` 時：
- Phase 0 執行完整（extract → translate unknown → write DB → unload Qwen）
- Phase 1 & Phase 2 跳過，不產生翻譯輸出
- 回傳 `term_summary`：`{extracted, skipped, added}`

### Term DB

| 項目 | 說明 |
|-----|-----|
| 位置 | `translated_files/term_db.sqlite` |
| UNIQUE 約束 | `(source_text, target_lang, domain)` |
| 衝突策略 | `skip`（預設）/ `overwrite` / `merge`（取 confidence 較高者） |
| 匯出格式 | JSON（完整備份）/ CSV（人工審查）/ XLSX（每個 target_lang 一個 sheet） |
| API | `GET /api/terms/stats`、`GET /api/terms/export?format=<json\|csv\|xlsx>`、`POST /api/terms/import?strategy=<skip\|overwrite\|merge>` |

---

## 5. Context Detection 機制詳解

### 觸發條件

```python
CONTEXT_DETECTION_ENABLED = True
QWEN_CONTEXT_FLOW_ENABLED = True
```

兩個 flag 同時啟用才觸發。

### 執行時機

| Primary Model | Context Detection 時機 |
|--------------|----------------------|
| Qwen（general） | Phase 1 前，立即執行 |
| HY-MT / TranslateGemma（dedicated） | Phase 1 後（deferred），HY-MT 卸載後執行 |

> 設計原因：若 Primary 是 HY-MT，Phase 1 前 VRAM 已滿，Qwen 無法載入。故 deferred 到 Phase 2 前執行。

### 採樣來源

| 格式 | 採樣方式 |
|-----|---------|
| `.docx` / `.pptx` / `.xlsx` | 讀取前 500 字元的真實文本 |
| `.pdf` / `.doc` | 使用檔案名稱（去 `_`、`-`） |

### Context Flow（注入 system_prompt）

偵測到 context 後，注入 system_prompt（僅限 `model_type=general`，且 `scenario ≠ MARKETING_PR`）：

```
{原有 system_prompt}

Document context: {detected_context（截斷至 240 字）}
```

**注意**：HY-MT（`model_type=translation`）主 prompt **不**注入 context，
但 Qwen Refiner 的 system_prompt 會包含（Phase 2 deferred context detection 結果）。

---

## 6. 動態 Scenario 機制詳解

### 決策優先順序

```
1. Profile 有固定 Scenario hint（如 technical_process → TECHNICAL_PROCESS）
   → 不做關鍵字評分，直接鎖定
2. 無固定 hint → 對 filename + sample_text + detected_context 做關鍵字評分
   → 最高分 ≥ 2 → 使用該 Scenario
   → 最高分 < 2 → GENERAL
```

### Scenario 對各模型的影響範圍

| 影響項目 | Qwen（general） | HY-MT（translation） | Refiner |
|--------|----------------|---------------------|---------|
| `system_prompt appendix` | ✅ 附加 | ✅ 附加 | ❌ 不影響（refiner 有獨立 prompt） |
| `decode options override` | ✅ 覆蓋 | ✅ 覆蓋（translation 版本） | ❌ 始終 greedy |
| `context flow（doc_context）` | ✅ 注入 | ❌ 跳過 | ✅ 注入（deferred） |
| `cache_variant suffix` | ✅ 隔離 | ✅ 隔離（`_glossary`） | ❌ key = `qwen3.5:9b`（固定） |

---

## 7. 快取系統

### Phase 1 Cache Key 格式

| 模型 | 格式 |
|-----|-----|
| HY-MT + technical_process + glossary variant | `demonbyron/HY-MT1.5-7B:Q4_K_M::technical_process::translation::scenario=technical_process_glossary` |
| Qwen + general（無 scenario） | `qwen3.5:9b` |
| Qwen + TECHNICAL_PROCESS（scenario 有 context） | `qwen3.5:9b::general::scenario=technical_process_ctx` |

### Phase 2（Refiner）Cache Key

```
qwen3.5:9b
```

固定使用 refiner 模型名稱（不含 profile/scenario）。

### 快取查詢優先順序（每個 segment）

```
1. 查 Refiner Cache（Phase 2 key）
   命中 → 直接使用，Phase 1 和 Phase 2 均跳過
      ↓ 未命中
2. 查 Phase-1 Cache（Primary Model key）
   命中 → 放入 tmap，Phase 1 跳過，但 Phase 2 仍執行
      ↓ 未命中
3. 執行 Phase 1（Primary Model 翻譯），結果寫入 Phase-1 Cache
      ↓
4. 執行 Phase 2（Refiner 精修），結果寫入 Refiner Cache
```

---

## 8. 各 Scenario 完整 Decode 參數對照

### General Model（Qwen）

| Scenario | temp | top_p | top_k | repeat_penalty | freq_penalty |
|---------|------|-------|-------|---------------|-------------|
| GENERAL | 0.05 | 0.50 | 10 | 1.0 | 0.0 |
| TECHNICAL_PROCESS | 0.20 | 0.75 | 40 | 1.12 | 0.20 |
| BUSINESS_FINANCE | 0.25 | 0.80 | 50 | 1.10 | 0.20 |
| LEGAL_CONTRACT | 0.18 | 0.70 | 40 | 1.10 | 0.25 |
| MARKETING_PR | 0.55 | 0.92 | 70 | 1.04 | 0.15 |
| DAILY_COMMUNICATION | 0.38 | 0.90 | 60 | 1.06 | 0.18 |

### Translation Model（HY-MT）

| Scenario | temp | top_p | top_k | repeat_penalty |
|---------|------|-------|-------|---------------|
| GENERAL | 0.05 | 0.50 | 10 | 1.0 |
| TECHNICAL_PROCESS | 0.20 | 0.55 | 30 | 1.12 |
| BUSINESS_FINANCE | 0.25 | 0.62 | 30 | 1.08 |
| LEGAL_CONTRACT | 0.18 | 0.55 | 25 | 1.10 |
| MARKETING_PR | 0.42 | 0.72 | 45 | 1.04 |
| DAILY_COMMUNICATION | 0.32 | 0.72 | 40 | 1.05 |

---

## 9. 環境變數覆蓋

| 變數 | 預設值 | 說明 |
|-----|-------|-----|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | WSL 環境自動偵測 |
| `DEFAULT_MODEL` | `qwen3.5:9b` | 預設 General / Refiner 模型 |
| `HYMT_DEFAULT_MODEL` | `demonbyron/HY-MT1.5-7B:Q4_K_M` | HY-MT 模型 |
| `TGEMMA_DEFAULT_MODEL` | `translategemma:4b` | Korean 模型 |
| `OLLAMA_NUM_CTX` | General=4096, Translation=3072 | Context 長度 |
| `OLLAMA_KV_CACHE_TYPE` | `q4_0` | KV Cache 量化（server-side） |
| `CROSS_MODEL_REFINEMENT_ENABLED` | `1` | Phase 2 精修開關 |
| `DYNAMIC_SCENARIO_STRATEGY_ENABLED` | `1` | 動態 Scenario 偵測開關 |
| `QWEN_CONTEXT_FLOW_ENABLED` | `1` | Context Detection + Flow 開關 |
| `SCENARIO_CACHE_VARIANT_ENABLED` | `1` | Scenario 快取隔離開關 |
