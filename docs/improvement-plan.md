# 文件翻譯工具改善計畫 (Translate_Tool Improvement Plan)

> 版本：v1.0　|　撰寫日期：2026-06-17　|　目標：高品質翻譯 × 高保真版面還原
>
> 本文件綜合「現有程式碼調查」與「業界最佳實踐 / 商業平台 / 開源生態研究」，提出可落地、分階段的改善藍圖。所有模組路徑均以專案實際結構為準（`app/backend/...`）。

---

## 1. 專案現況分析 (Current State Analysis)

### 1.1 現有功能盤點 (Inventory of Existing Features)

| 領域 | 模組 | 已具備能力 |
|---|---|---|
| 翻譯編排 | `services/translation_service.py` | 兩階段翻譯（主模型 + 跨模型 refine）、去重、批次（SENTENCE_MODE）、stop-flag、簡轉繁（OpenCC） |
| 領域策略 | `services/translation_strategy.py` | 由檔名 + 取樣文字關鍵字偵測場景（技術/法律/金融/行銷/日常），調整 temperature/top_p/top_k/repeat_penalty 與 prompt 附加段 |
| 模型路由 | `services/model_router.py` | 以「第一個目標語言」做基準路由（越/德/日→HY-MT、韓→TranslateGemma、其餘→qwen3.5:9b），多目標分組 |
| LLM 用戶端 | `clients/ollama_client.py` | Ollama `/api/generate`（串流）、`/api/tags`、批次 payload、模型卸載 |
| 快取 | `services/translation_cache.py` | 以 (text, target_lang, src_lang, model) 為鍵，批讀批寫、每 10 段增量寫入 |
| 術語 | `services/term_db.py` / `term_extractor.py` | SQLite 術語庫（confidence/usage/status）、Phase 0 Qwen 抽取 + regex 過濾、JSON/CSV/XLSX 匯入匯出、Wikidata 查詢 |
| 品質驗證 | `utils/translation_verification.py` | 掃描失敗字串樣式（`[Translation failed|...` 等）並重試補洞、簡轉繁 |
| PDF 解析 | `parsers/pdf_parser.py` | PyMuPDF 行級 bbox + 字型 metadata、`find_tables()` 表格偵測、頁首頁尾偵測、閱讀順序排序、掃描檔啟發式偵測 |
| PDF 還原 | `renderers/pdf_generator.py` / `coordinate_renderer.py` / `text_region_renderer.py` | overlay（redaction + TextWriter）、side-by-side、字型自動縮放、語言別 Noto 字型、字型 subset |
| DOCX/PPTX | `processors/docx_processor.py` / `pptx_processor.py` / `parsers/*` | python-docx / python-pptx、表格 cell 追蹤、SmartArt（zip/XML 直解）、U+200B 冪等標記、COM/LibreOffice 後處理 |
| API | `api/routes.py` | 非同步 job（建立/輪詢/取消/下載）、術語 CRUD、route-info、cache stats |
| 前端 | `app/frontend/src/...` | 模組化 React（翻譯/術語/歷史/設定頁），i18n |

### 1.2 核心痛點 (Core Pain Points)

**A. 翻譯品質層面**

1. **單一供應商鎖定 (Provider lock-in)**：`clients/ollama_client.py` 與 `model_router.py` 僅支援本地 Ollama，無 OpenAI-compatible / DeepL / Google 雲端 fallback。本地 GPU 過載或不可用時整條流程癱瘓。
2. **路由僅看 `targets[0]`**：多目標語言批次時，`resolve_route_groups()` 以第一個目標語言決定模型，混合語言批次的模型分派不理想。
3. **品質驗證只認「錯誤字串」**：`translation_verification.py` 僅偵測 `[Translation failed|`、`[翻譯失敗]` 等已知失敗樣式，無法偵測語意誤譯、漏譯、幻覺。
4. **術語 confidence 未獨立驗證**：AI 抽取的 confidence 由 LLM 自評、從未獨立校驗，`confidence=1.0` 的未驗證術語與人工核可術語被同等注入。`status` 僅 unverified/approved，缺 `rejected` / `needs-review`。
5. **無術語套用一致性稽核**：無機制確認譯文最終確實一致套用了術語表（terminology hit rate）。
6. **SENTENCE_MODE 無重試與失敗 placeholder**：批次路徑失敗只是默默 `fail_cnt++`，不像逐句路徑會寫入 `[Translation failed|...]`，造成 done count 與輸出不一致。
7. **deferred context 偵測寫死繁中 prompt**（`以下是一份文件的開頭內容…`），非中文工作流不適用，且透過私有方法 `_build_no_system_payload` / `_call_ollama` 直接耦合 OllamaClient 內部。
8. **無長文件文件級上下文**：以段落為粒度、靠去重，導致同一句在不同語境得到單一翻譯（ambiguous source 誤譯）；無 Doc2Doc / 跨段 overlap 銜接。

**B. 版面還原層面**

9. **無版面偵測模型**：解析完全仰賴 PyMuPDF 幾何啟發式。閱讀順序用 `round(y0, 10pt)` 分桶，多欄 / 旋轉版面脆弱；無 DocLayout-YOLO 類結構偵測。
10. **掃描檔不走 OCR**：`has_text_layer=False` 只警告不路由 OCR，輸出近乎空白。
11. **文字膨脹只會縮字 + 截斷**：`_insert_text_in_rect` 縮到 min（約 4pt）後截斷並 log warning，不做 reflow / bbox 調整。英→德 +30%、英→西 +25% 時必爆框。
12. **兩套 overlay 實作並存**：`coordinate_renderer.py`（ReportLab）與 `pdf_generator.py`（fitz）職責重疊、無共用抽象。
13. **表格框線受損**：白色 redaction mask 會擦掉貼近文字的細表格線；`PDF_MASK_MARGIN_PT` 只能緩解。
14. **DOCX 翻譯為「附加」非「取代」**：輸出永遠源文 + 譯文並陳；無純譯文輸出模式。DOCX 頁碼一律 `page_num=1`；頁首頁尾 / shape 需 win32com（僅 Windows）。
15. **SmartArt 重序列化遺失 namespace**：ElementTree 回寫可能破壞 namespace 宣告；多目標語言以 ` / ` 串接而非分段。

**C. 合約 / 工程治理層面**

16. **合約幾乎為空殼**：`contracts/business/business-rules.md`、`contracts/data/data-shape-contract.md`、`contracts/api/api-contract.md` 的 rule inventory、decision table、error format、auth、`JobStatus.status` enum、multipart 請求 schema 全為空白，API 一致性檢查無從生效。
17. **無觀測性**：除 `/route-info` 外無模型延遲 / 失敗率 / 快取命中率 metrics 與告警。
18. **設定寫死**：`ALLOWED_ORIGINS` 只允許 `localhost:5173`；路由表是 `model_router.py` 內硬編 dict，新增/調權需改碼重部署；`OLLAMA_NUM_CTX` 會同時覆蓋 GENERAL/TRANSLATION 的 4096/3072 區分。
19. **API 無任何認證**：是否為刻意（本地工具）未在合約載明。

### 1.3 技術債 (Technical Debt)

- **平行實作未抽象**：CoordinateRenderer（ReportLab）與 PDFGenerator（fitz）兩條 overlay/side-by-side 路徑。
- **Legacy enum / profile 無遷移路徑**：`SEMICONDUCTOR_OI_CP_SOP`、`PROCESS_PRESENTATION` 等「為相容 dataset/benchmark 保留」，無 deprecation warning；`cache_variant` 以字串串接 scenario + `_ctx` / `_glossary`，scenario 值變動即破裂。
- **私有方法跨模組存取**：translation_service 直接呼叫 OllamaClient 私有方法。
- **每次插字重讀字型檔**：`_insert_text_in_rect` 每次呼叫從磁碟讀字型，無 buffer cache，重複 I/O。
- **去重語意不一致**：SENTENCE_MODE 的 done count 計法與逐句路徑不一致。
- **DOCX textbox 去重用 hash+長度**而非 XML element identity，內容相同的 textbox 可能被誤去重。

---

## 2. 業界參考案例 (Industry Reference Cases)

### 2.1 重點工具比較 (Key Tool Comparison)

| 工具 | 類型 | 版面策略 | 解析核心 | 翻譯後端 | 對本專案的啟示 |
|---|---|---|---|---|---|
| **PDFMathTranslate / pdf2zh** | OSS (AGPL) | DocLayout-YOLO → 分塊 → 還原；99.8% 數學版面還原 | PyMuPDF + DocLayout-YOLO(ONNX) | Google/DeepL/Ollama/OpenAI 可插拔 | 直接可借鏡的「版面感知 + 可插拔後端」範本 |
| **BabelDOC** | OSS (MIT) | **IR 中介層**：Frontend→IL→Midend(layout+譯)→Backend(重建) | DocLayout-YOLO | OpenAI-compatible LLM | **最關鍵架構**：解析/翻譯/渲染解耦，可換引擎不動版面邏輯 |
| **MinerU / PDF-Extract-Kit** | OSS (Apache-2.0) | 粗到細兩階段，輸出 Markdown/JSON | DocLayout-YOLO + ppocr-v5 + 公式模型 | （僅解析，不翻譯） | 高品質多格式解析骨幹；可作為 parser 升級選項 |
| **Marker / Surya** | OSS (GPL) | pipeline 分塊 + 選擇性推論 | Surya VLM（90+ 語言 OCR + 閱讀順序 + 表格） | （僅解析） | 多欄閱讀順序、掃描檔 OCR 的開源最佳解 |
| **Docling (IBM)** | OSS (MIT) | DoclingDocument 統一 IR | Surya / 自家 layout 模型 | （僅解析） | RAG 生態事實標準；IR 資料模型設計參考 |
| **DeepL Document** | 商業 SaaS | layout-aware 約束系統，文字膨脹自適應 | 原生結構 + OCR | 自家 NMT | 歐語品質標竿、formality 參數、文件級上下文 |
| **Translated.com / ModernMT** | 商業 | 樣式規則抽取 + 重套用，圖表文字隔離翻譯 | ModernMT 自適應 | 背景 + 前景雙模型 | TTE 品質度量、自適應從修正學習 |
| **Smartling** | 商業 TMS | XLIFF 工作流 + LQA | — | MT + 人工 | LQA 結構化錯誤分類、QE 分流 |
| **Trados / Google v3 / Amazon** | 商業 | XLIFF / TM / Glossary API | 各家 | 各家 NMT | XLIFF 為通用交換格式、TM 模糊比對、Glossary API |

### 2.2 最佳實踐 (Best Practices)

1. **以座標感知解析取代純文字抽取**（PyMuPDF / pdfplumber），保留 bbox 供重建。
2. **翻譯前先跑版面偵測模型**（DocLayout-YOLO / Surya），把頁面切成 typed regions（text/table/figure/formula/header）。
3. **以段落 / 區塊為翻譯粒度**，非逐句，保留語境、減少過度切分。
4. **數學公式以 LaTeX pass-through**，絕不送入 MT。
5. **IR（中介表示）層解耦**解析↔翻譯↔渲染——換 MT 引擎安全、不重解析即可重渲染。
6. **預分類 native vs 掃描 PDF**，僅在必要時 OCR（OCR 5-15% 字元錯誤會與 MT 錯誤疊加）。
7. **處理文字膨脹**：優先序為「縮字級 → 縮行距 → 縮字距 → 受控溢出至鄰近空白 → 最後才截斷並標記」。
8. **Glossary 注入是領域翻譯單一最高槓桿**；system prompt glossary + RAG 檢索 precedents。
9. **Few-shot 範例**是鎖定格式/語域/風格一致性最有效的單一技巧。
10. **大 context window 走 Doc2Doc**（Claude 200K–1M / GPT-4o 128K）；需分塊時以段落邊界 + 1–2 段 overlap。
11. **以 LLM-as-judge / COMET 取代 BLEU** 做品質量測；對譯後 PDF 跑 multimodal LLM-as-judge 抓版面回歸。
12. **文件翻譯天生非同步、檔案式**：upload → job_id → poll/webhook → download（本專案已符合）。
13. **CJK 字型嵌入須處理書寫方向與字型變體**；目標語言字型以 metric 相容（x-height/cap-height/字寬）優先，Noto 為標準 fallback。

### 2.3 開源生態系亮點 (Open-Source Ecosystem Highlights)

- **DocLayout-YOLO**（Apache-2.0，0.91 mAP，ONNX）：翻譯 pipeline 的事實版面偵測骨幹，已被 BabelDOC / MinerU / PDF-Extract-Kit 採用。
- **Surya v2**（GPL-3.0）：單一 VLM 統一 layout + OCR + 閱讀順序 + 表格，90+ 語言。
- **BabelDOC**（MIT）：IR 範式參考實作；可直接作為 PDF 翻譯後端評估。
- **OPUS-MT / Helsinki-NLP**（CC-BY-4.0）：1500+ 離線小模型，可作為無 GPU 環境的高吞吐 fallback。
- **TableFormer / TATR**：表格結構辨識（row/col/cell 拓樸）。
- **COMET / xCOMET**（unbabel-comet, PyPI）：神經品質評估，xCOMET 可標出錯誤 span。

---

## 3. 翻譯品質改善計畫 (Translation Quality Improvement Plan)

### 3.1 LLM 端點設計與配置 (LLM Endpoint Design)

**架構定向**（已與使用者確認）：
- **翻譯主力**：全面使用雲端 LLM 端點（DeepSeek / Panjit 遠端），**不再依賴本地 Ollama 進行翻譯**。
- **版面偵測**：DocLayout-YOLO、PaddleOCR、Surya 等仍走**本地 HuggingFace / Ollama**，不上傳頁面影像至外部服務。
- **隱私邊界**：純文字段落可送雲端；頁面截圖 / 影像一律本地推論。

---

#### 3.1.0 實測端點能力彙整 (Endpoint Capability Report)

> 測試日期：2026-06-17　|　測試語對：EN → 繁體中文　|　樣本：技術段落（136 tokens input）

**已驗證端點（`.env` 設定）**

| 變數 | 值 |
|---|---|
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` |
| `DEEPSEEK_API` | `sk-xxx...` |
| `PANJIT_LLM_BASE_URL` | `https://ollama_pjapi.theaken.com` |
| `PANJIT_API` | `Lh1NTt...` |

兩端點均相容 **OpenAI `/v1/chat/completions` 介面**，可共用 `OpenAICompatibleClient`。

**DeepSeek 端點**

| 模型 | 延遲 | Completion tokens | Reasoning tokens | 翻譯品質觀察 | 建議用途 |
|---|---|---|---|---|---|
| `deepseek-v4-flash` | **3.4s** | 217 | 123（內部） | 優秀，術語準確，書面語自然 | **翻譯主力**（速度/品質平衡最佳） |
| `deepseek-v4-pro` | 7.5–10s | 580（2048 budget） | **492**（CoT 耗盡大量額度） | 非常高，但 CoT 顯著消耗 token | **LLM-as-judge / translate-then-critique**（非批量翻譯主路徑） |

> ⚠️ **v4-pro 重要注意**：v4-pro 為 reasoning model，每次翻譯消耗 ~450–500 reasoning tokens，批量文件翻譯成本是 v4-flash 的 3–4×，且速度更慢。翻譯主路徑使用 v4-flash；v4-pro 僅用於品質審查與 LLM-as-judge。

**Panjit 端點（OpenAI-compatible，遠端 Ollama/MLX gateway）**

可用翻譯模型：

| 模型 ID | 延遲 | Context | 提供者 | 翻譯品質觀察 | 建議用途 |
|---|---|---|---|---|---|
| `gpt-oss:120b` | **6.8s** | 131K | MLX (Apple Silicon) | 極佳，術語精準，書面語流暢，有 prompt cache | **翻譯備援 / 大文件 Doc2Doc** |
| `gemma3:27b` | 12.6s | 128K | Ollama | 良好，有雙語括號傾向 | 一般用途，非主力 |
| `gemma4:latest`（8B） | 未測 | 128K | Ollama | 輕量快速，品質待驗 | 術語抽取 / 分類輔助 |
| `mlx-community/Qwen3.6-35B-A3B-4bit` | 未測 | **256K** | MLX MoE | 超長上下文 MoE，中文強 | 超長文件翻譯（> 100K tokens） |
| `nemotron3:33b` | 未測 | 128K | Ollama | 多模態 33B，影像可用 | 多模態 OCR 整理（版面理解輔助） |

> Panjit 端點另有 embedding 模型（`bge-m3`、`Qwen3-Embedding-8B`）與 reranker（`bge-reranker-v2-m3`），可用於術語庫 RAG 檢索（P2/P3 功能）。

**翻譯主路徑推薦**

```
預設主路徑：gpt-oss:120b（Panjit，免費）
超長文件（>50K tokens）：Qwen3.6-35B-A3B-4bit（Panjit，256K context，免費）
可選升級：deepseek-v4-flash（DeepSeek，需 API key，付費）
品質審查（LLM-as-judge）：deepseek-v4-pro（DeepSeek，需 API key，僅抽樣用）
```

> Panjit 端點為免費服務，作為系統預設；DeepSeek 為可選付費升級，在 `providers.yml` 中設定但預設 disabled。

---

**3.1.1 抽象介面**

新增 `clients/base_llm_client.py`，定義 `LLMClient` 抽象基底：

```
class LLMClient(Protocol):
    def translate_once(self, text, src, tgt, *, options) -> str: ...
    def translate_batch(self, texts, src, tgt, *, options) -> list[str]: ...
    def refine_translation(self, src, draft, tgt, *, options) -> str: ...
    def health(self) -> bool: ...
    def list_models(self) -> list[str]: ...
    def unload(self) -> None: ...   # 雲端 client 為 no-op
```

現有 `clients/ollama_client.py` 改為 `OllamaClient(LLMClient)`；translation_service 改為依賴 `LLMClient` 介面，**移除對 `_build_no_system_payload` / `_call_ollama` 私有方法的直接呼叫**（痛點 7）。

**3.1.2 新增 Provider**

| Provider | 端點模式 | 用途 |
|---|---|---|
| `OpenAICompatibleClient` | `POST {base_url}/v1/chat/completions`（OpenAI / vLLM / LM Studio / OpenRouter / DeepSeek 通用） | 雲端高品質 / 大 context |
| `DeepLClient` | `POST /v2/translate`、文件走 `/v2/document` async + glossary API | 歐語高品質、formality 參數 |
| `OllamaClient`（既有） | `/api/generate`、`/api/tags` | 本地隱私 |

**3.1.3 設定外部化（取代硬編路由表，痛點 18）**

新增 `config/providers.yml`（由 `config.py` 載入），結構（反映 `.env` 實際端點）：

```yaml
providers:
  # ── 預設翻譯主力：Panjit（免費，OpenAI-compatible gateway）────────────────
  - id: panjit
    type: openai
    enabled: true                           # 預設啟用
    base_url: ${PANJIT_LLM_BASE_URL}        # https://ollama_pjapi.theaken.com
    api_key: ${PANJIT_API}
    models:
      translate: gpt-oss:120b               # 主翻譯：131K context，6.8s，prompt cache
      long_doc: mlx-community/Qwen3.6-35B-A3B-4bit   # 超長文件：256K context
      embed: Qwen3-Embedding-8B             # 術語庫向量化（P2/P3）
      rerank: bge-reranker-v2-m3            # 術語 RAG 二階段排序

  # ── 可選升級：DeepSeek（付費，預設關閉）────────────────────────────────────
  - id: deepseek
    type: openai
    enabled: ${DEEPSEEK_ENABLED:-false}     # 設 DEEPSEEK_ENABLED=true 啟用
    base_url: ${DEEPSEEK_BASE_URL}          # https://api.deepseek.com
    api_key: ${DEEPSEEK_API}
    models:
      translate: deepseek-v4-flash          # 付費翻譯升級（3.4s，高品質）
      judge: deepseek-v4-pro                # LLM-as-judge（reasoning model，勿做批量翻譯）

  # ── 本地 Ollama（僅版面偵測輔助，不參與翻譯路由）────────────────────────
  - id: ollama-local
    type: ollama
    base_url: ${OLLAMA_BASE_URL:-http://localhost:11434}
    role: layout_assist_only                # 不進入翻譯路由

routing:
  rules:
    # 超長文件（> 50K src tokens）走 Panjit 256K context 模型
    - match: { src_tokens_gt: 50000 }
      model: mlx-community/Qwen3.6-35B-A3B-4bit
      provider: panjit
  default:
    model: gpt-oss:120b
    provider: panjit                        # 預設走免費 Panjit
    profile: general

# DeepSeek 啟用時由 model_router 自動插入到鏈首：[deepseek, panjit]
fallback_chain: [panjit]
```

`model_router.py` 改為讀此設定並支援 **多目標語言精準路由**（痛點 2）：對每個 target_lang 各自解析路由，而非僅 `targets[0]`。

**驗收**：`/route-info` 回傳含 provider 欄位與當前模型；以環境變數切換端點無需改碼；主後端離線時自動 fallback 並在 `JobStatus` 記錄使用的 provider。

### 3.2 Prompt 工程策略 (Prompt Engineering)

於 `services/translation_strategy.py` 與 system prompt 組裝處導入：

1. **角色 + 領域 + 受眾**：`You are a professional {domain} translator. Translate from {src} to {tgt} for a {audience} audience.`
2. **Few-shot 範例區塊**（最高槓桿一致性技巧）：每個 scenario 維護 2–3 組 `<examples>` 來源/譯文對，依偵測場景注入。
3. **Glossary 區塊**：將 `term_db` 命中的術語以 Markdown 表格注入 system prompt（`build_terminology_block()` 已有雛形，擴充為標準表格格式，上限 100–200 詞）。
4. **Translate-then-critique**：把現有 Phase 2 refine 升級為「檢查 (1) 術語準確 (2) 流暢 (3) 漏譯」後輸出修訂版。
5. **Chunk handoff with overlap**：分塊時注入「前一段譯文最後 1–2 段」作為銜接（痛點 8）。
6. **約束輸出格式**：`Return only the translated text...`（既有，保留）。
7. **deferred context prompt 國際化**（痛點 7）：依 target_lang 從 i18n 模板取 context-detection prompt，移除寫死繁中字串。

**驗收**：scenario few-shot 注入後，固定 benchmark 集的術語命中率 +10pp；context prompt 支援至少 en/zh-TW/ja 三種模板。

### 3.3 術語一致性強化 (Terminology Consistency)

1. **狀態機擴充**（痛點 4）：`term_db` `status` 由 `{unverified, approved}` 擴為 `{unverified, needs_review, approved, rejected}`；僅 `approved`（與可選 high-confidence unverified，受 flag 控制）會被注入，`rejected` 永不注入。
2. **獨立信心校驗**：AI 抽取 confidence 不再直接信任；新增「來源加權」——Wikidata / 人工匯入 > LLM 自評。
3. **術語套用稽核（新模組 `services/term_audit.py`）**：翻譯完成後，掃描譯文檢查每個 approved 術語是否一致套用，產出 `terminology_hit_rate` 與未套用清單，寫入 `qa-report`。
4. **XLIFF / TBX 相容**：匯入匯出新增 TBX（termbase）與 TMX（翻譯記憶）格式，與 Trados/memoQ 互通。

**驗收**：對含 20 個 approved 術語的測試文件，hit rate 報告可產出且 ≥ 95%；`rejected` 術語 0 注入。

### 3.4 品質評估機制 (Quality Evaluation)

現況只認錯誤字串（痛點 3）。導入三層：

1. **規則層（既有強化）**：`translation_verification.py` 補上 SENTENCE_MODE 的 placeholder 與重試退避（痛點 6），每次重試 log 個別結果。
2. **神經度量層**：整合 **COMET / xCOMET**（`unbabel-comet` PyPI）作為離線 QE，對抽樣段落產生 0–1 分；低分段落進入 review 佇列（QE 分流，效法 Smartling）。
3. **LLM-as-judge 層**：新增 `services/quality_judge.py`，以較強模型對抽樣段落評 adequacy / fluency / terminology（MQM 結構化錯誤分類）；對譯後 PDF 可選跑 **multimodal LLM-as-judge** 抓版面回歸。

**指標**：以 **TTE（Time to Edit）** 與 **terminology hit rate** 取代 BLEU。

**驗收**：新增 `/jobs/{id}/quality` 回傳每段 QE 分數分佈與 MQM 摘要；QE < 0.6 的段落自動標記 needs-review。

### 3.5 長文件分塊策略 (Long Document Chunking)

1. **語意分塊**：以段落 / section 邊界切分，配 1–2 段 overlap（取代固定 token 切分）。
2. **Doc2Doc 優先**：當文件 token 數 < 模型 context（雲端大窗）時，整份單次翻譯保語篇連貫。
3. **多層記憶**：維持 sentence / paragraph / document 三級記憶，document-level summary 於每 chunk 前注入做 priming。
4. **context window 還原差異化**（痛點 18）：拆分 `OLLAMA_NUM_CTX` 對 GENERAL(4096)/TRANSLATION(3072) 的覆蓋，改為 `GENERAL_NUM_CTX` / `TRANSLATION_NUM_CTX` 各自獨立 env。

**驗收**：20 頁文件啟用 overlap 後，跨段代名詞 / 術語一致性人工抽查通過率 +15pp。

---

## 4. 版面還原改善計畫 (Layout Restoration Improvement Plan)

### 4.1 PDF 版面還原深化 (PDF Layout Restoration Deepening)

**核心架構轉向：導入 IR 中介層（仿 BabelDOC）**

1. **新增版面偵測**：在 `parsers/pdf_parser.py` 後插入 `parsers/layout_detector.py`，呼叫 **DocLayout-YOLO（ONNX）** 將頁面切成 typed regions（text/title/table/figure/formula/header/footer/list），取代脆弱的 `round(y0,10pt)` 閱讀順序啟發式（痛點 9）。
2. **IR 模型**：擴充 `models/translatable_document.py` 為中介表示，序列化 bbox + 字型 metadata + element type + reading order，**解析↔翻譯↔渲染解耦**。
3. **統一渲染抽象**（技術債）：在 `renderers/base.py` 定義 `Renderer` 介面，`coordinate_renderer.py`（ReportLab）與 `pdf_generator.py`（fitz）收斂為單一 fitz 主路徑 + 共用 bbox 重排邏輯，ReportLab 路徑降為 fallback。
4. **公式 pass-through**：formula region 偵測後以 LaTeX / 點陣原樣保留，不送 MT（最佳實踐 4）。
5. **掃描檔 OCR 路由**（痛點 10）：`has_text_layer=False` 時自動路由至 OCR（Surya / PaddleOCR-VL），而非輸出空白。
6. **字型 buffer cache**（技術債）：`_insert_text_in_rect` 改為 module-level LRU 快取字型 buffer，消除每次插字的磁碟 I/O。

**驗收**：多欄學術 PDF 閱讀順序正確率 > 95%；掃描檔不再輸出空白；公式區塊 0 誤譯。

### 4.2 DOCX/PPTX 格式保真 (DOCX/PPTX Format Fidelity)

1. **純譯文輸出模式**（痛點 14）：`docx_processor.py` / `pptx_processor.py` 新增 `output_mode = {append, replace}`，replace 模式取代原文而非並陳（保留 append 為預設以維持冪等）。
2. **SmartArt namespace 修正**（痛點 15）：重序列化改用 `lxml`（保留 namespace 註冊）取代 ElementTree；多目標語言以獨立段落附加而非 ` / ` 串接。
3. **XLIFF 往返**：導入 XLIFF 2.1 抽取/回填路徑（效法 Apryse / Trados），分離可譯文字與結構標記，提升保真並與 CAT 工具互通。
4. **跨平台頁首頁尾**（痛點 14）：以 python-docx + 直接 XML（`w:hdr`/`w:ftr`）解析頁首頁尾，降低對 win32com 的依賴。
5. **textbox / 合併 cell 去重修正**（技術債）：DOCX textbox 改用 XML element identity；PPTX 合併 cell 去重納入 merge 判定避免重複處理。

**驗收**：replace 模式輸出無重複源文；SmartArt 多語輸出 namespace 完整且可在 PowerPoint 正常開啟。

### 4.3 字體處理與文字膨脹 (Font Handling & Text Expansion)

1. **文字膨脹自適應**（痛點 11）：在 `renderers/text_region_renderer.py` 實作優先序策略——`縮字級 → 縮行距 → 縮字距 → 受控溢出鄰近空白 → 截斷並標記`，取代「縮到 4pt 直接截斷」。英→德/西/法膨脹係數內建查表。
2. **字型 metric 相容替換**：目標語言字型缺字時，依 x-height/cap-height/字寬選 metric 相容字型（Noto 為標準 fallback），降低版面位移；建立 fallback chain 避免 tofu 方框。
3. **CJK 書寫方向**：偵測 writing-mode metadata，垂直文字（tate-gumi）選具 vert/vrt2 OpenType feature 的字型，避免旋轉 fallback。
4. **RTL 支援**：Arabic/Hebrew 於 IR 階段做頁面鏡像（對齊翻轉、欄序反轉）+ Unicode BIDI + HarfBuzz contextual shaping，而非僅翻 text-direction。

**驗收**：英→德文件 0 爆框（以 reflow/縮放吸收 +30%）；目標語言缺字 0 tofu 方框。

### 4.4 表格與圖表處理 (Table & Figure Handling)

1. **表格結構辨識**：以 **TableFormer / TATR** 做 row/col/cell 拓樸辨識，cell 級獨立翻譯後回填，取代純 `find_tables()` bbox（最佳實踐 / 痛點 13）。
2. **表格框線保護**（痛點 13）：redaction 改為僅遮文字 quad（非整 cell），或先擷取框線向量於回寫後重繪。
3. **圖片區域遮罩**：figure region 排除翻譯、原樣 pass-through；相鄰 caption 獨立翻譯並重新定位。
4. **side-by-side 右側 redaction 修正**（PDF 痛點）：side-by-side 模式對右側複本套用 redaction，避免原文透出。

**驗收**：含合併儲存格表格 cell 對位正確；表格細線不被 mask 擦除；圖片區塊原樣保留。

---

## 5. 分階段實施計畫 (Phased Implementation Plan)

> 估時以 person-days（PD）標示，假設 1–2 名工程師。

### Phase 1 (P1) — 基礎強化（1–2 個月）

| # | 工作項 | 模組 | 估時 |
|---|---|---|---|
| P1-1 | 補齊合約空殼（api/data-shape/business-rules、`JobStatus.status` enum、multipart schema、error format、auth 政策） | `contracts/**` | 5 PD |
| P1-2 | LLMClient 抽象層 + 重構 OllamaClient，移除私有方法耦合 | `clients/base_llm_client.py`, `ollama_client.py`, `translation_service.py` | 8 PD |
| P1-3 | OpenAICompatibleClient（vLLM/LM Studio/OpenRouter 通用） | `clients/openai_compatible_client.py` | 5 PD |
| P1-4 | 路由表外部化 + 多目標精準路由 + fallback chain | `services/model_router.py`, `config/providers.yml` | 6 PD |
| P1-5 | SENTENCE_MODE 重試 + placeholder + done-count 一致化 | `translation_service.py`, `translation_verification.py` | 4 PD |
| P1-6 | deferred context prompt 國際化 + context_ctx 拆分 GENERAL/TRANSLATION num_ctx | `translation_strategy.py`, `config.py` | 3 PD |
| P1-7 | 術語狀態機擴充（needs_review/rejected）+ 注入閘 | `services/term_db.py` | 4 PD |
| P1-8 | 字型 buffer LRU cache | `renderers/pdf_generator.py` | 2 PD |
| P1-9 | 基礎觀測性：模型延遲/失敗率/快取命中 metrics 端點 | `api/routes.py` | 4 PD |

**P1 Milestone 驗收標準**
- `cdd-kit validate --contracts` 與 `cdd-kit gate` 在 API 一致性檢查下通過（合約不再空殼）。
- 以環境變數切換至 OpenAI-compatible 雲端端點完成一次端到端翻譯，無需改碼。
- 主後端（Ollama）離線時，job 自動 fallback 並在 `JobStatus` 記錄 provider。
- SENTENCE_MODE 失敗段落寫入 placeholder 且 done/fail count 與逐句路徑一致（單元測試覆蓋）。
- `rejected` 術語 0 注入（單元測試）。

### Phase 2 (P2) — 品質提升（2–3 個月）

| # | 工作項 | 模組 | 估時 |
|---|---|---|---|
| P2-1 | DocLayout-YOLO（ONNX）版面偵測接入 | `parsers/layout_detector.py` | 12 PD |
| P2-2 | IR 中介表示重構（解析↔翻譯↔渲染解耦） | `models/translatable_document.py`, `renderers/base.py` | 14 PD |
| P2-3 | 渲染路徑收斂（fitz 主、ReportLab fallback、共用 bbox 重排） | `renderers/*` | 8 PD |
| P2-4 | 文字膨脹優先序策略 + metric 相容字型 fallback chain | `renderers/text_region_renderer.py`, `utils/font_utils.py` | 8 PD |
| P2-5 | Few-shot + glossary 注入 + translate-then-critique | `translation_strategy.py` | 6 PD |
| P2-6 | 長文件語意分塊 + overlap + Doc2Doc 路徑 | `translation_service.py` | 8 PD |
| P2-7 | COMET/xCOMET QE 整合 + `/jobs/{id}/quality` | `services/quality_judge.py`, `api/routes.py` | 8 PD |
| P2-8 | 術語套用稽核（hit rate） | `services/term_audit.py` | 5 PD |
| P2-9 | 表格框線保護 + side-by-side 右側 redaction 修正 | `renderers/pdf_generator.py` | 5 PD |

**P2 Milestone 驗收標準**
- 多欄學術 PDF 閱讀順序正確率 > 95%（以 10 份樣本人工評）。
- 英→德/西 benchmark 0 爆框，缺字 0 tofu。
- benchmark 集 terminology hit rate ≥ 95%，COMET 分數較 P1 基線 +0.03 以上。
- `/jobs/{id}/quality` 回傳每段 QE 與 MQM 摘要；QE < 0.6 自動標 needs-review。

### Phase 3 (P3) — 進階功能（3–4 個月）

| # | 工作項 | 模組 | 估時 |
|---|---|---|---|
| P3-1 | 掃描檔 OCR 路由（Surya / PaddleOCR-VL） | `parsers/ocr_router.py` | 12 PD |
| P3-2 | 公式 LaTeX pass-through（pix2text / Mathpix 選配） | `parsers/formula_handler.py` | 8 PD |
| P3-3 | 表格結構辨識（TableFormer/TATR）cell 級翻譯 | `parsers/table_recognizer.py` | 12 PD |
| P3-4 | RTL 頁面鏡像 + BIDI + HarfBuzz shaping | `renderers/text_region_renderer.py` | 10 PD |
| P3-5 | CJK 垂直書寫支援 | `renderers/*`, `utils/font_utils.py` | 6 PD |
| P3-6 | XLIFF 2.1 / TMX / TBX 往返（CAT 互通） | `processors/xliff_processor.py`, `services/term_db.py` | 12 PD |
| P3-7 | LLM-as-judge + multimodal 版面回歸偵測 | `services/quality_judge.py` | 8 PD |
| P3-8 | DeepLClient（文件 async + glossary） | `clients/deepl_client.py` | 5 PD |
| P3-9 | DOCX replace 模式 + SmartArt namespace 修正（lxml） | `processors/docx_processor.py`, `pptx_processor.py` | 6 PD |

**P3 Milestone 驗收標準**
- 掃描 PDF 端到端可譯，OCR 字元錯誤率 < 10%（樣本評）。
- 數學公式區塊還原率 > 95%、0 誤譯。
- 合併儲存格表格 cell 對位正確；XLIFF 往返可與 Trados/memoQ 交換。
- RTL（Arabic）輸出頁面鏡像正確、無字序反轉。

### 5.1 風險評估 (Risk Assessment)

| 風險 | 影響 | 機率 | 緩解 |
|---|---|---|---|
| DocLayout-YOLO 模型下載受網路限制 | P2 阻塞 | 中 | 預先 bundle 模型於 Docker image；提供離線權重路徑設定 |
| IR 重構大改 → 回歸風險 | 高 | 中 | 先建黃金樣本回歸測試集（PDF/DOCX/PPTX 各 N 份），IR 與舊路徑並行雙跑比對後切換 |
| 雲端 LLM 引入資料外洩疑慮 | 高 | 中 | 預設本地優先；雲端為 opt-in；合約載明 data residency；敏感文件強制本地 |
| OSS 授權衝突（Surya/Marker 為 GPL） | 法務 | 中 | GPL 元件以子程序 / 服務隔離呼叫，避免靜態連結污染；優先選 Apache/MIT（DocLayout-YOLO、Docling、BabelDOC） |
| 上游 API 破壞性變更（pdf2zh/docling 版本churn） | 維護成本 | 高 | pin 版本、封裝 adapter 層、升級走測試 gate |
| COMET/LLM-judge 推論成本 | 成本 | 中 | 僅對抽樣段落跑 QE；高信心段落輕量審查 |
| 文字膨脹 reflow 與原版面衝突 | 品質 | 中 | bilingual 輸出作為 QA 安全網；溢出超閾值時標記人工審查 |

---

## 6. 技術選型建議 (Technology Selection Recommendations)

### 6.1 推薦的 LLM API 整合方案

> 以下基於 2026-06-17 實測端點能力（見 §3.1.0）。

**翻譯端點角色分工**

| 角色 | 端點 | 模型 | 延遲 | Context | 備註 |
|---|---|---|---|---|---|
| 翻譯主力（預設） | Panjit | `gpt-oss:120b` | 6.8s | 131K | **免費**，MLX Apple Silicon，有 prompt cache |
| 超長文件（預設） | Panjit | `Qwen3.6-35B-A3B-4bit` | 未測 | **256K** | **免費**，MoE，中文強 |
| 術語向量化 | Panjit | `Qwen3-Embedding-8B` | — | 32K | **免費**，P2/P3 術語 RAG |
| Reranker | Panjit | `bge-reranker-v2-m3` | — | 8K | **免費**，術語候選二階段排序 |
| 翻譯升級（可選） | DeepSeek | `deepseek-v4-flash` | 3.4s | 64K | 付費，`DEEPSEEK_ENABLED=true` 啟用 |
| 品質審查（可選） | DeepSeek | `deepseek-v4-pro` | 7.5–10s | 64K | 付費，Reasoning model，**僅用於 LLM-as-judge** |

**抽象層設計**：自建 `LLMClient` Protocol，兩實作：
- `OpenAICompatibleClient`（覆蓋 Panjit + DeepSeek，兩端點均驗證為 `/v1/chat/completions`）
- `OllamaClient`（既有，僅保留用於本地版面輔助，不進翻譯路由）

**不再建議的路徑**：
- ~~本地 Ollama 翻譯~~：本地資源保留給 DocLayout-YOLO / PaddleOCR。
- ~~OPUS-MT fallback~~：Panjit 免費端點品質遠優於 OPUS-MT，無需此 fallback。

**設定**：`config/providers.yml` 外部化（見 §3.1.3 樣本），env 覆蓋 base_url/api_key；DeepSeek 以 `DEEPSEEK_ENABLED=true` opt-in 啟用。

### 6.2 推薦的 PDF 解析升級路徑

1. **短期**：續用 **PyMuPDF（fitz）≥ 1.24**（純文字抽取較 pdfplumber 快 10×），補字型 buffer cache。
2. **中期**：PyMuPDF（座標）+ **DocLayout-YOLO（ONNX, Apache-2.0）** 版面偵測雙軌，建立 IR。
3. **掃描檔**：**Surya v2**（OCR + 閱讀順序）或 **PaddleOCR-VL**（109 語言、Apache-2.0，授權較友善）。
4. **高保真選配**：評估直接以 **BabelDOC（MIT）** 作為 PDF 翻譯後端（IR 範式成熟），或 **MinerU / Docling** 作為解析骨幹。
5. **公式**：**pix2text**（OSS，本地）為主，**Mathpix**（商業 API）為高精度選配。

### 6.3 推薦的版面分析工具

| 用途 | 首選 | 授權 | 備註 |
|---|---|---|---|
| 版面區域偵測 | **DocLayout-YOLO** | Apache-2.0 | 0.91 mAP、ONNX、事實標準骨幹 |
| OCR + 閱讀順序 | **Surya v2** / **PaddleOCR-VL** | GPL-3.0 / Apache-2.0 | 掃描檔；PaddleOCR-VL 授權較友善 |
| 表格結構 | **TableFormer / TATR** | 開源 | row/col/cell 拓樸 |
| 統一解析骨幹 | **Docling（DoclingDocument）** | MIT | RAG 生態事實標準、IR 資料模型參考 |
| PDF 翻譯後端參考 | **BabelDOC** | MIT | IR 範式、可換引擎 |
| 品質評估 | **unbabel-comet（COMET/xCOMET）** | 開源 | 神經 QE、錯誤 span |

---

## 附錄：優先級總覽 (Priority Summary)

- **必做（P1，解鎖一切）**：合約補齊、`OpenAICompatibleClient` 接通 DeepSeek + Panjit、`config/providers.yml` 路由外部化 + `fallback_chain`、SENTENCE_MODE 修正、術語狀態機。
- **高槓桿（P2，品質躍升）**：DocLayout-YOLO + IR 重構（本地推論）、文字膨脹自適應、few-shot/glossary 注入、COMET QE、術語稽核、`deepseek-v4-pro` LLM-as-judge。
- **進階（P3，全面對標商業平台）**：OCR 掃描檔（本地 Surya / PaddleOCR）、公式 pass-through、表格結構辨識、RTL/CJK、XLIFF/TMX/TBX 互通、Panjit embedding RAG 術語建議。

**端點使用邊界（已確認）**

| 功能 | 執行位置 | 模型 / 端點 | 成本 |
|---|---|---|---|
| 文字翻譯 | Panjit（預設） | `gpt-oss:120b` | **免費** |
| 超長文件翻譯（>50K tokens） | Panjit（預設） | `Qwen3.6-35B-A3B-4bit` | **免費** |
| 術語抽取（NER） | Panjit（預設） | `gpt-oss:120b` 或 `gemma4:latest` | **免費** |
| 翻譯升級（opt-in） | DeepSeek | `deepseek-v4-flash` | 付費 |
| 品質審查（LLM-judge，opt-in） | DeepSeek | `deepseek-v4-pro` | 付費（抽樣） |
| 版面偵測（DocLayout-YOLO） | **本地** HuggingFace | ONNX 推論 | 免費 |
| OCR（Surya / PaddleOCR） | **本地** HuggingFace | — | 免費 |
| 公式識別（pix2text） | **本地** | — | 免費 |
| 術語向量化 / RAG | Panjit | `Qwen3-Embedding-8B` + `bge-reranker` | **免費** |

> 核心戰略：**先把「可換引擎 + 可觀測 + 合約化」的地基打好（P1），再以 IR 中介層 + 版面偵測模型把版面還原拉到 BabelDOC/PDFMathTranslate 等級（P2），最後補齊 OCR/公式/表格/RTL/CAT 互通對標商業平台（P3）。**
