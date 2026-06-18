# P2 Change Requests — 預擬提案集 (Draft Proposals for Phase 2)

> 版本：v1.0　|　撰寫日期：2026-06-18　|　接力自：`docs/improvement-plan.md` §5 Phase 2
>
> 本文件把 `improvement-plan.md` 的 **P2-1 ~ P2-9** 拆成 9 個獨立可追蹤的 CDD change，
> 每個都預擬好 `change-request.md` 內容，待逐一以 `/cdd-new` 開立。
> 目的：**先把 request 寫清楚、把依賴排好，後續開發 P2 才不會亂。**
>
> 用法：對每個提案，把該節「`/cdd-new` 一句話描述」貼給 `/cdd-new`，
> 再以該節的完整 request 內容覆蓋 scaffolded 的 `change-request.md`。

---

## 0. 提案總覽與依賴排序 (Overview & Dependency Ordering)

| change-id | 對應 | 標題 | 軌道 | 估時 | 前置依賴 |
|---|---|---|---|---|---|
| `p2-ir-document-model` | P2-2 | IR 中介表示成熟化（解析↔翻譯↔渲染解耦）+ 黃金樣本回歸 | A·版面 | 14 PD | （P1 已完成；本change為track A基石） |
| `p2-layout-detection` | P2-1 | DocLayout-YOLO（ONNX）本地版面偵測接入 | A·版面 | 12 PD | `p2-ir-document-model` |
| `p2-renderer-convergence` | P2-3 | 渲染路徑收斂（fitz 主 / ReportLab fallback / 共用 bbox 重排） | A·版面 | 8 PD | `p2-ir-document-model`, `p2-layout-detection` |
| `p2-text-expansion` | P2-4 | 文字膨脹優先序策略 + metric 相容字型 fallback chain | A·版面 | 8 PD | `p2-renderer-convergence` |
| `p2-table-border-protection` | P2-9 | 表格框線保護 + side-by-side 右側 redaction 修正 | A·版面 | 5 PD | `p2-renderer-convergence` |
| `p2-prompt-fewshot-glossary` | P2-5 | Few-shot + glossary 注入 + translate-then-critique | B·翻譯品質 | 6 PD | （獨立，可立即開始） |
| `p2-long-doc-chunking` | P2-6 | 長文件語意分塊 + overlap + Doc2Doc 路徑 | B·翻譯品質 | 8 PD | （獨立；num_ctx 拆分已由 P1 完成） |
| `p2-comet-qe` | P2-7 | COMET/xCOMET 神經 QE 整合 + `/jobs/{id}/quality` | C·品質評估 | 8 PD | （獨立；新增 API endpoint，需更新 api-contract） |
| `p2-term-audit` | P2-8 | 術語套用稽核（terminology hit rate） | C·品質評估 | 5 PD | （獨立；依賴 P1 術語狀態機，已完成） |

### 建議執行波次 (Recommended Waves)

三軌可並行；軌道 A 內部須序列化（IR 重構為高回歸風險，先建黃金樣本再切換）。

```
Wave 1（立即並行啟動）
  ├─ A: p2-ir-document-model          ← track A 基石，先做
  ├─ B: p2-prompt-fewshot-glossary    ← 低風險高槓桿，獨立
  └─ C: p2-term-audit                 ← 低風險，獨立

Wave 2（Wave 1 對應前置完成後）
  ├─ A: p2-layout-detection           ← 需 IR 欄位就緒
  ├─ B: p2-long-doc-chunking          ← 獨立
  └─ C: p2-comet-qe                   ← 獨立

Wave 3
  └─ A: p2-renderer-convergence       ← 需 IR + layout

Wave 4
  ├─ A: p2-text-expansion             ← 需 renderer 收斂
  └─ A: p2-table-border-protection    ← 需 renderer 收斂
```

### 跨提案共通注意事項 (Cross-cutting Notes)

- **既有 scaffolding**：`app/backend/models/translatable_document.py`（已有 `ElementType`/`BoundingBox`/`TranslatableDocument`）與 `app/backend/renderers/base.py`（已有 `BaseRenderer`/`RenderMode`）**已存在**。軌道 A 提案皆為「成熟化 / 收斂 / 擴充」既有抽象，**非 greenfield**，request 與 design 須先讀現況再擴充。
- **隱私邊界**（已確認）：頁面影像 / 截圖一律本地推論（DocLayout-YOLO / OCR / 多模態 judge）；純文字段落才可送雲端。任何把頁面影像送外部端點的設計一律拒絕。
- **`cdd-kit gate` tier-floor 誤判**：P2 多個 change 含 `cache`、`integration`、`endpoint`、`embedding`、`alter table` 等觸發詞（見 CLAUDE.md Promoted Learnings），開 change 時預期需 `tier-floor-override` 並附書面理由。
- **新增 API endpoint（`p2-comet-qe`）**：改 `contracts/api/api-contract.md` 後務必 `cdd-kit openapi export --out contracts/api/openapi.yml` 並 commit，否則 CI `openapi export --check` gate 失敗。
- **黃金樣本回歸**：軌道 A 全程共用 `p2-ir-document-model` 建立的黃金樣本集（PDF/DOCX/PPTX 各 N 份）；後續 layout/renderer/text-expansion change 皆以同一套樣本做新舊雙跑比對。

---

## 1. `p2-ir-document-model` (P2-2)

**`/cdd-new` 一句話描述：**
> 將既有 translatable_document.py IR 成熟化為解析↔翻譯↔渲染的單一解耦中介層：擴充 ElementType 加入 table/figure/formula 區域型別、加入 reading_order 與序列化（含 bbox + 字型 metadata + element type），並建立 PDF/DOCX/PPTX 黃金樣本回歸測試集供整個 P2 版面軌道新舊雙跑比對。

### Original Request
P2-2（改善計畫 §4.1）：把現有 `app/backend/models/translatable_document.py`（已有 `ElementType` / `BoundingBox` / `TranslatableDocument` 雛形）成熟化為仿 BabelDOC 的 IR 中介層，作為「解析 → 翻譯 → 渲染」三段解耦的單一資料模型：
1. 擴充 `ElementType`，加入 layout 偵測所需的區域型別（至少 `TABLE` / `FIGURE` / `FORMULA` / `LIST`，現有僅到 `TABLE_CELL` 等文字級型別）。
2. 在 IR 上明確表示 `reading_order`，取代 parser 內 `round(y0,10pt)` 分桶啟發式（痛點 9 的資料面基礎）。
3. IR 可完整序列化 / 反序列化：bbox + 字型 metadata + element type + reading order，使「不重解析即可重渲染、不重渲染即可換 MT 引擎」成立。
4. 建立黃金樣本回歸測試集（PDF/DOCX/PPTX 各 N 份）與新舊路徑雙跑比對框架，供整個 P2 版面軌道（layout/renderer/text-expansion/table）共用。

### Business / User Goal
讓解析、翻譯、渲染三段以單一 IR 解耦，換 MT 引擎或換渲染器都不需動其他兩段，並讓後續 DocLayout-YOLO 接入有明確的資料落點。黃金樣本回歸框架是整個 P2 高風險版面重構的安全網。

### Non-goals
- 不在本 change 接入 DocLayout-YOLO（`p2-layout-detection`）。
- 不在本 change 收斂渲染器（`p2-renderer-convergence`）。
- 不改變翻譯主路徑行為與 API 介面。
- 不處理 OCR / 公式辨識（P3）。

### Constraints
- 須先讀現況 `models/translatable_document.py`（320 行）與 `renderers/base.py`（已有 `BaseRenderer` / `RenderMode`），以擴充而非重寫為原則，維持既有欄位與 `to_dict` 相容。
- 序列化格式需向下相容既有呼叫端（parsers / renderers / processors）。
- 黃金樣本回歸須可在 CI gate 內執行（離線、不需網路 / GPU）。

### Known Context
- IR 模型：`app/backend/models/translatable_document.py`
- 渲染抽象：`app/backend/renderers/base.py`（`BaseRenderer`, `RenderMode = {INLINE, SIDE_BY_SIDE, OVERLAY}`）
- PDF 解析現況：`app/backend/parsers/pdf_parser.py`（415 行，`round(y0,10pt)` 閱讀順序）
- 改善計畫 §4.1、§5.1 風險表「IR 重構大改 → 回歸風險」緩解策略

### Open Questions
- 黃金樣本集放置位置與大小上限（建議 `tests/fixtures/golden/`，每格式 3–5 份代表性文件）。

### Requested Delivery Date / Priority
P2 軌道 A 基石，最高優先。`p2-layout-detection` / `p2-renderer-convergence` 依賴本 change。

---

## 2. `p2-layout-detection` (P2-1)

**`/cdd-new` 一句話描述：**
> 新增 parsers/layout_detector.py，以本地 DocLayout-YOLO（ONNX）將 PDF 頁面切成 typed regions（text/title/table/figure/formula/header/footer/list）並寫入 IR 的 reading_order，取代脆弱的 round(y0,10pt) 啟發式；模型一律本地推論、不上傳頁面影像。

### Original Request
P2-1（改善計畫 §4.1.1）：在 `parsers/pdf_parser.py` 之後插入 `app/backend/parsers/layout_detector.py`，呼叫本地 **DocLayout-YOLO（ONNX）** 把頁面切成 typed regions（text/title/table/figure/formula/header/footer/list），填入 `p2-ir-document-model` 定義的 `ElementType` 與 `reading_order`，取代 `round(y0,10pt)` 分桶啟發式（痛點 9）。模型權重以本地 HuggingFace / 離線權重載入，**不上傳頁面影像至外部服務**。

### Business / User Goal
以版面感知偵測取代脆弱幾何啟發式，讓多欄 / 旋轉版面的閱讀順序正確、區域型別明確，為公式 pass-through、圖片排除翻譯、表格區處理鋪路。目標：多欄學術 PDF 閱讀順序正確率 > 95%。

### Non-goals
- 不做 OCR（掃描檔，P3-1）；本 change 僅針對有文字層的 native PDF 區域偵測。
- 不做公式 LaTeX 還原（P3-2）、不做表格 cell 拓樸辨識（P3-3）；僅標記 region 型別。
- 不改渲染器。

### Constraints
- **本地推論強制**：頁面影像不得送雲端；模型走本地 HuggingFace / ONNX runtime。
- 模型權重須可離線 bundle（Docker image 預載 + 離線權重路徑設定），緩解下載受網路限制風險（§5.1）。
- 授權：優先 Apache-2.0 的 DocLayout-YOLO，避免 GPL 靜態連結污染。
- 偵測結果寫入 `p2-ir-document-model` 的 IR，不得另立平行資料結構。
- 須以 `p2-ir-document-model` 黃金樣本做新舊閱讀順序雙跑比對。

### Known Context
- 前置：`p2-ir-document-model`（IR 須先具備 region 型別與 reading_order）
- PDF 解析：`app/backend/parsers/pdf_parser.py`、`app/backend/parsers/base.py`
- 改善計畫 §2.3（DocLayout-YOLO 0.91 mAP）、§6.2、§6.3、§5.1 風險表

### Open Questions
- ONNX runtime 與 GPU/CPU 推論的部署需求（是否需要 onnxruntime-gpu）。

### Requested Delivery Date / Priority
P2 軌道 A，Wave 2。前置 `p2-ir-document-model`。

---

## 3. `p2-renderer-convergence` (P2-3)

**`/cdd-new` 一句話描述：**
> 將 coordinate_renderer.py（ReportLab）與 pdf_generator.py（fitz）兩條重疊的 overlay/side-by-side 路徑收斂到單一 fitz 主路徑 + 共用 bbox 重排邏輯，ReportLab 降為 fallback，全部實作 renderers/base.py 的 BaseRenderer 介面。

### Original Request
P2-3（改善計畫 §4.1.3 / 技術債）：把目前並存的兩套 overlay/side-by-side 實作——`renderers/coordinate_renderer.py`（ReportLab）與 `renderers/pdf_generator.py`（fitz，711 行）——收斂為**單一 fitz 主路徑 + 共用 bbox 重排邏輯**，ReportLab 路徑降為 fallback。兩者皆實作 `renderers/base.py` 既有的 `BaseRenderer` 介面，消除職責重疊與重複維護成本。

### Business / User Goal
消除兩套渲染路徑的維護分裂與行為不一致，建立單一 bbox 重排邏輯，讓 `p2-text-expansion` 與 `p2-table-border-protection` 有單一落點可改，不必兩處同步。

### Non-goals
- 不實作文字膨脹策略（`p2-text-expansion`）。
- 不實作表格框線保護（`p2-table-border-protection`）。
- 不移除 ReportLab（保留為 fallback）。
- 不改 DOCX/PPTX 渲染。

### Constraints
- 收斂後行為須以 `p2-ir-document-model` 黃金樣本做新舊雙跑比對，視覺回歸可接受才切換。
- 須維持 `BaseRenderer.render(document, output_path, translations, mode)` 既有簽名與 `RenderMode` 三模式。
- fitz 為主路徑；ReportLab fallback 行為需明確觸發條件並記錄於 design。

### Known Context
- 前置：`p2-ir-document-model`、`p2-layout-detection`
- 渲染器：`app/backend/renderers/{base,coordinate_renderer,pdf_generator,text_region_renderer,inline_renderer}.py`
- 改善計畫 §4.1.3、§1.3 技術債「平行實作未抽象」

### Open Questions
- ReportLab fallback 的明確觸發條件（哪些 fitz 失敗場景才降級）。

### Requested Delivery Date / Priority
P2 軌道 A，Wave 3。前置 `p2-ir-document-model` + `p2-layout-detection`。

---

## 4. `p2-text-expansion` (P2-4)

**`/cdd-new` 一句話描述：**
> 在 text_region_renderer.py 實作文字膨脹優先序策略（縮字級→縮行距→縮字距→受控溢出鄰近空白→最後才截斷並標記），取代「縮到4pt直接截斷」；並在 utils/font_utils.py 建立 metric 相容（x-height/cap-height/字寬）字型 fallback chain 避免 tofu 方框。

### Original Request
P2-4（改善計畫 §4.3.1-2，痛點 11）：在 `renderers/text_region_renderer.py`（312 行）以優先序策略取代現況「縮到約 4pt 直接截斷」：`縮字級 → 縮行距 → 縮字距 → 受控溢出至鄰近空白 → 最後才截斷並標記`，並內建英→德/西/法膨脹係數查表。同時在 `app/backend/utils/font_utils.py` 建立 **metric 相容字型 fallback chain**：目標語言缺字時依 x-height/cap-height/字寬選 metric 相容字型（Noto 為標準 fallback），降低版面位移與 tofu 方框。

### Business / User Goal
解決英→德（+30%）/西（+25%）必爆框與缺字 tofu 兩大版面瑕疵。目標：英→德/西 benchmark 0 爆框、缺字 0 tofu。

### Non-goals
- 不做 CJK 垂直書寫（P3-5）、不做 RTL 鏡像（P3-4）。
- 不做表格框線保護（`p2-table-border-protection`）。
- 不改翻譯內容，只調整渲染呈現。

### Constraints
- 須在 `p2-renderer-convergence` 收斂後的單一 fitz 主路徑 + 共用 bbox 重排上實作，不得在舊雙路徑各做一份。
- 截斷為最後手段，且截斷必須標記（供 QA 安全網 / 人工審查）。
- 字型 fallback 須與既有語言別 Noto 字型載入相容；可結合 P1 的字型 buffer LRU cache。
- 以黃金樣本 + 英→德/西膨脹 benchmark 驗收。

### Known Context
- 前置：`p2-renderer-convergence`
- 渲染器：`app/backend/renderers/text_region_renderer.py`、字型工具：`app/backend/utils/font_utils.py`
- P1 已完成字型 buffer LRU cache（`p1-font-lru-cache`）
- 改善計畫 §4.3、§5.1 風險「文字膨脹 reflow 與原版面衝突」

### Open Questions
- 膨脹係數查表的語對覆蓋範圍（先英→德/西/法，其餘預設係數？）。

### Requested Delivery Date / Priority
P2 軌道 A，Wave 4。前置 `p2-renderer-convergence`。

---

## 5. `p2-table-border-protection` (P2-9)

**`/cdd-new` 一句話描述：**
> 修正 redaction 改為僅遮文字 quad（非整 cell）或先擷取框線向量回寫後重繪，避免白色 mask 擦除貼近文字的細表格線；並修正 side-by-side 模式對右側複本套用 redaction，避免原文透出。

### Original Request
P2-9（改善計畫 §4.4.2 / §4.4.4，痛點 13）：兩個表格 / side-by-side 渲染瑕疵一起修：
1. **表格框線保護**：白色 redaction mask 會擦掉貼近文字的細表格線（`PDF_MASK_MARGIN_PT` 只能緩解）。改為 redaction **僅遮文字 quad**（非整 cell），或先擷取框線向量、於回寫後重繪。
2. **side-by-side 右側 redaction 修正**：side-by-side 模式對右側複本套用 redaction，避免原文透出。

### Business / User Goal
讓含表格的 PDF 翻譯不再擦除細框線、side-by-side 右側不再透出原文，提升版面保真度。目標：表格細線不被 mask 擦除；side-by-side 右側無原文殘留。

### Non-goals
- 不做表格 cell 拓樸辨識（TableFormer/TATR，P3-3）。
- 不做圖片 caption 重定位（屬 §4.4.3，可另開或併入 P3）。
- 不改翻譯邏輯。

### Constraints
- 在 `p2-renderer-convergence` 收斂後的 fitz 主路徑上修，不在舊雙路徑各修一份。
- 以含合併儲存格 / 細框線表格的黃金樣本驗收。

### Known Context
- 前置：`p2-renderer-convergence`
- 渲染器：`app/backend/renderers/pdf_generator.py`、`coordinate_renderer.py`
- 既有緩解：`PDF_MASK_MARGIN_PT`
- 改善計畫 §4.4、痛點 13

### Open Questions
- 框線「向量擷取後重繪」vs「僅遮文字 quad」二擇一或併用，待 design 決。

### Requested Delivery Date / Priority
P2 軌道 A，Wave 4。前置 `p2-renderer-convergence`。可與 `p2-text-expansion` 並行。

---

## 6. `p2-prompt-fewshot-glossary` (P2-5)

**`/cdd-new` 一句話描述：**
> 在 translation_strategy.py 與 system prompt 組裝處導入：依偵測場景注入 2-3 組 few-shot 範例、把 term_db 命中術語以 Markdown 表格注入 system prompt（上限 100-200 詞）、並把 Phase 2 refine 升級為 translate-then-critique（檢查術語準確/流暢/漏譯後輸出修訂版）。

### Original Request
P2-5（改善計畫 §3.2）：在 `services/translation_strategy.py`（305 行）與 system prompt 組裝處導入三項 prompt 工程：
1. **Few-shot 範例**：每個 scenario 維護 2–3 組 `<examples>` 來源/譯文對，依偵測場景注入（最高槓桿一致性技巧）。
2. **Glossary 區塊**：把 `term_db` 命中的 approved 術語以 Markdown 表格注入 system prompt（擴充既有 `build_terminology_block()` 雛形，上限 100–200 詞）。
3. **Translate-then-critique**：把現有 Phase 2 refine 升級為「檢查 (1) 術語準確 (2) 流暢 (3) 漏譯」後輸出修訂版。

### Business / User Goal
以 few-shot 鎖定格式/語域/風格一致性、以 glossary 注入提升領域術語準確、以 critique 抓漏譯。目標：scenario few-shot 注入後固定 benchmark 集術語命中率 +10pp。

### Non-goals
- 不做 COMET QE（`p2-comet-qe`）、不做術語套用稽核（`p2-term-audit`）。
- 不做長文件分塊（`p2-long-doc-chunking`）。
- 不改路由 / provider 設定。

### Constraints
- glossary 只注入 P1 術語狀態機的 `approved`（與受 flag 控制的 high-confidence unverified）；`rejected` 永不注入（沿用 P1 注入閘）。
- few-shot 範例庫須與既有 scenario 偵測（技術/法律/金融/行銷/日常）對齊。
- translate-then-critique 須沿用既有 LLMClient 介面，不耦合特定 provider 內部。

### Known Context
- 翻譯策略：`app/backend/services/translation_strategy.py`、`translation_service.py`
- 既有雛形：`build_terminology_block()`、`build_strategy` / `StrategyDecision`
- 術語：`app/backend/services/term_db.py`（P1 狀態機 `{unverified, needs_review, approved, rejected}` 已完成）
- 改善計畫 §3.2

### Open Questions
- few-shot 範例的來源（人工策展 vs 從歷史高品質翻譯抽取）。

### Requested Delivery Date / Priority
P2 軌道 B，Wave 1（獨立，可立即開始）。低風險高槓桿。

---

## 7. `p2-long-doc-chunking` (P2-6)

**`/cdd-new` 一句話描述：**
> 在 translation_service.py 導入長文件語意分塊（以段落/section 邊界切分配 1-2 段 overlap，取代固定 token 切分）、文件 token 數小於模型 context 時走 Doc2Doc 整份單次翻譯、並維持 sentence/paragraph/document 三級記憶於每 chunk 前注入 document summary 做 priming。

### Original Request
P2-6（改善計畫 §3.5，痛點 8）：在 `services/translation_service.py`（304 行）導入長文件策略：
1. **語意分塊**：以段落 / section 邊界切分，配 1–2 段 overlap，取代固定 token 切分。
2. **Doc2Doc 優先**：文件 token 數 < 模型 context（雲端大窗，如 Panjit `gpt-oss:120b` 131K / `Qwen3.6-35B-A3B-4bit` 256K）時，整份單次翻譯保語篇連貫。
3. **多層記憶**：維持 sentence / paragraph / document 三級記憶，document-level summary 於每 chunk 前注入做 priming。

### Business / User Goal
解決「以段落為粒度 + 去重導致同句不同語境得到單一翻譯（ambiguous source 誤譯）」與跨段代名詞/術語不連貫。目標：20 頁文件啟用 overlap 後跨段一致性人工抽查 +15pp。

### Non-goals
- **不含** `OLLAMA_NUM_CTX` 拆分（GENERAL/TRANSLATION num_ctx 已由 P1 `p1-prompt-i18n-numctx` 完成）。
- 不做 COMET QE、不做 few-shot/glossary（各為獨立 change）。
- 不改 provider 路由（超長文件路由規則已於 P1 providers.yml 定義 `src_tokens_gt: 50000`）。

### Constraints
- 須與 P1 providers.yml 的超長文件路由（`Qwen3.6-35B-A3B-4bit`, 256K）協同：Doc2Doc 門檻須對齊實際路由模型 context。
- overlap 銜接須與既有去重 / cache 鍵（text, target_lang, src_lang, model）相容，避免 overlap 段污染 cache。
- 不破壞 SENTENCE_MODE 既有路徑與 P1 修正的 done/fail count 一致性。

### Known Context
- 翻譯編排：`app/backend/services/translation_service.py`、`translation_cache.py`
- 路由設定：`config/providers.yml`（P1 已外部化，含超長文件規則）
- P1 已完成：num_ctx 拆分、SENTENCE_MODE 重試/placeholder/done-count 一致化
- 改善計畫 §3.5

### Open Questions
- document-level summary 由哪個模型產生（主翻譯模型 vs 較小的 `gemma4:latest`）。

### Requested Delivery Date / Priority
P2 軌道 B，Wave 2（獨立）。

---

## 8. `p2-comet-qe` (P2-7)

**`/cdd-new` 一句話描述：**
> 新增 services/quality_judge.py 整合 COMET/xCOMET 神經 QE，對抽樣段落產生 0-1 分，低分（<0.6）段落自動標記 needs-review 進 review 佇列；新增 /jobs/{id}/quality API 回傳每段 QE 分數分佈與 MQM 摘要，並同步更新 api-contract 與 openapi.yml。

### Original Request
P2-7（改善計畫 §3.4，痛點 3）：把品質評估從「只認錯誤字串」升級為神經度量層：
1. 新增 `app/backend/services/quality_judge.py`，整合 **COMET / xCOMET**（`unbabel-comet` PyPI）作為離線 QE，對抽樣段落產生 0–1 分。
2. QE < 0.6 的段落自動標記 needs-review 進 review 佇列（QE 分流，效法 Smartling）。
3. 新增 API endpoint `GET /jobs/{id}/quality`，回傳每段 QE 分數分佈與 MQM 摘要。

### Business / User Goal
以神經 QE 取代 BLEU / 純錯誤字串偵測，自動把低品質段落分流人工審查，並對外暴露品質指標。目標：`/jobs/{id}/quality` 可回傳每段 QE 與摘要；QE < 0.6 自動標 needs-review。

### Non-goals
- 不含 LLM-as-judge / multimodal 版面回歸（P3-7，留待 P3，可選用 `deepseek-v4-pro`）。
- 不含 SENTENCE_MODE placeholder/重試強化（已於 P1 完成）。
- 不改翻譯主路徑行為。

### Constraints
- COMET / xCOMET 為**本地離線**推論（不送外部）；僅對**抽樣**段落跑以控成本（§5.1 風險）。
- 新增 endpoint 必須先更新 `contracts/api/api-contract.md`，再 `cdd-kit openapi export --out contracts/api/openapi.yml` 並 commit（否則 CI gate 失敗）。
- 開 change 時 `integration` / `endpoint` 觸發 tier-floor，預期需 `tier-floor-override` + 書面理由。
- review 佇列 / needs-review 標記須與 P1 `JobStatus` 與術語 `needs_review` 狀態語意一致，不引入衝突 enum。

### Known Context
- 新模組：`app/backend/services/quality_judge.py`
- API：`app/backend/api/routes.py`、`contracts/api/api-contract.md`、`contracts/api/openapi.yml`
- 既有規則層：`app/backend/utils/translation_verification.py`
- 改善計畫 §3.4、§6.3（unbabel-comet）

### Open Questions
- 抽樣比例與觸發策略（固定比例 vs 依文件長度動態）。
- COMET 模型權重大小與是否需 bundle 進 image。

### Requested Delivery Date / Priority
P2 軌道 C，Wave 2（獨立）。

---

## 9. `p2-term-audit` (P2-8)

**`/cdd-new` 一句話描述：**
> 新增 services/term_audit.py：翻譯完成後掃描譯文檢查每個 approved 術語是否一致套用，產出 terminology_hit_rate 與未套用清單寫入 qa-report，並驗證 rejected 術語 0 注入。

### Original Request
P2-8（改善計畫 §3.3.3，痛點 5）：新增 `app/backend/services/term_audit.py`：翻譯完成後掃描譯文，檢查每個 `approved` 術語是否一致套用，產出 `terminology_hit_rate` 與未套用清單，寫入 `qa-report`。確認譯文最終確實一致套用術語表（terminology hit rate），補上目前完全缺失的術語套用一致性稽核。

### Business / User Goal
提供「譯文是否真的套用了術語表」的可量測證據，閉環 P1 術語狀態機與 P2 glossary 注入。目標：對含 20 個 approved 術語的測試文件，hit rate 報告可產出且 ≥ 95%；`rejected` 術語 0 注入。

### Non-goals
- 不含 glossary 注入本身（`p2-prompt-fewshot-glossary`）；本 change 只稽核結果。
- 不含 COMET QE（`p2-comet-qe`）。
- 不含 XLIFF/TBX/TMX 互通（P3-6）。

### Constraints
- 依賴 P1 術語狀態機 `{unverified, needs_review, approved, rejected}`（已完成）；稽核對象為 `approved`。
- hit rate 計算需處理大小寫 / 詞形變化 / 多目標語言；演算法須於 design 載明並可測。
- 報告寫入既有 `qa-report` 結構，不另立平行報告格式。

### Known Context
- 新模組：`app/backend/services/term_audit.py`
- 術語庫：`app/backend/services/term_db.py`（P1 狀態機）、`models/term.py`
- 改善計畫 §3.3、驗收標準
- 與 `p2-prompt-fewshot-glossary` 互補：一個注入、一個稽核

### Open Questions
- 詞形變化 / 形態學比對的嚴格度（精確比對 vs lemmatized 比對）。

### Requested Delivery Date / Priority
P2 軌道 C，Wave 1（獨立，低風險，可立即開始）。

---

## 附：開立順序快速指引 (Quick Start)

```
# Wave 1（並行）
/cdd-new <p2-ir-document-model 一句話描述>
/cdd-new <p2-prompt-fewshot-glossary 一句話描述>
/cdd-new <p2-term-audit 一句話描述>

# Wave 2（待對應前置完成）
/cdd-new <p2-layout-detection 一句話描述>      # 需 p2-ir-document-model
/cdd-new <p2-long-doc-chunking 一句話描述>
/cdd-new <p2-comet-qe 一句話描述>

# Wave 3
/cdd-new <p2-renderer-convergence 一句話描述>   # 需 IR + layout

# Wave 4
/cdd-new <p2-text-expansion 一句話描述>          # 需 renderer 收斂
/cdd-new <p2-table-border-protection 一句話描述> # 需 renderer 收斂
```

> 每次 `/cdd-new` 後，把本文件對應節的完整 request 內容覆蓋 scaffolded 的 `change-request.md`，再續跑 CDD agent flow。
