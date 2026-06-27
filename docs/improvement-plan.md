# 文件翻譯工具 — 能力調查與改善計畫

> 版本：v2.0 ｜ 撰寫日期：2026-06-27 ｜ 範圍：版面偵測 × 翻譯品質 × 版面還原
>
> 本文件取代已刪除的 v1.0。內容綜合「現有程式碼實證調查」(5 個並行 subagent 直讀原始碼) 與「業界 SOTA / 商業平台 / 開源生態研究」,提出可落地、分階段、**每項皆附可驗證方式**的改善藍圖。所有路徑以專案實際結構為準 (`app/backend/...`)。

---

## 一、總體判斷

使用者回報的三個核心問題 — (1) PDF 版面還原不正確、(2) 表格 cell 翻譯缺上下文、(3) 譯文置於原文下方影響閱讀 — **全部屬實,且均可在程式碼定位根因**。

關鍵洞察:這三者是**同一架構缺陷的不同表象**。系統以「單行/單格凍結 bbox + 去重後的孤立字串」為翻譯與排版的最小單位,缺少業界標準的「**區塊聚合 → 帶上下文翻譯 → 重排版**」管線 (BabelDOC / pdf2zh 的雙向 IR 範式)。因此改善的主軸是:**把翻譯與排版的最小單位從「孤立片段」提升為「帶結構脈絡的區塊」**,並建立能客觀量測版面/品質的度量基建,讓每一步改善都能驗收。

---

## 二、三大痛點的實證結論

### 痛點 1：PDF 版面還原不正確

| 根因 | 證據 (file:line) | 後果 |
|---|---|---|
| 逐「行」凍結 bbox,無段落 reflow | `parsers/pdf_parser.py:193-255` | 譯文無法跨行重排;長度一變即縮字或截斷 |
| 靠 `search_for(原文)` 重新定位塗白,非用抽取 bbox | `renderers/fitz_renderer.py:292-328` | 連字/重複文字塗白失敗 → **原文透出疊在譯文下** |
| 文字膨脹只會縮到 4–6pt 後截斷 (overflow 那步形同停用) | `text_region_renderer.py:180-329`、`fitz_renderer.py:542` (`whitespace_below=0.0`) | 中→英/英→德必爆框,靜默截斷成「…」 |

附帶缺陷:
- **樣式抽取後渲染時完全不套用** — 一律黑色 Noto,顏色/粗體/逐 span 丟失 (`fitz_renderer.py:486-555`)。
- **旋轉/直書/RTL 主路徑不處理**;`PageInfo.rotation` 抽取了卻沒套用 (`pdf_parser.py:106`)。
- **掃描檔無 OCR** — `has_text_layer=False` 只 log warning,輸出近乎空白 (`pdf_parser.py:632`)。
- **ReportLab fallback 用空白 Canvas** (`coordinate_renderer.py:135`) — fitz 一失敗就整頁圖片/底色/表線全丟,且只有 WARNING 不告知使用者 (`pdf_processor.py:836-840`)。
- **路由陷阱**:預設 `output_format` 非 pdf 時,PDF 被轉成「雙語 DOCX + `--Page N--`」,**根本沒走版面還原** (`pdf_processor.py:376-414`)。版面還原僅在 `output_format="pdf"` 且 `layout_mode in (overlay, side_by_side)` 時發生 (`pdf_processor.py:110`)。
- **偵測解析度僅 72 DPI** (`pdf_parser.py:426`);多欄閱讀順序用單一 x-gap 閾值 `_COLUMN_GAP_THRESHOLD=0.1` (`layout_detector.py:509`),無法處理混合欄數/側欄。

### 痛點 2：表格 cell 翻譯缺上下文

**所有四種格式的表格 cell 都被當成「去重後的孤立字串」送進 LLM;行/列/表頭脈絡從未進入 prompt。** 唯一的 prompt builder `clients/ollama_client.py:625-647` 只把 cell 編號串成 flat list。

| 格式 | 證據 | 問題 |
|---|---|---|
| DOCX | `docx_processor.py:243` 算出 `Tbl(r,c)` 標籤但只用於去重;`:584-589` 扁平去重 | 結構不進翻譯 |
| XLSX | `xlsx_processor.py:134-139` 去重時丟掉 `r/c` | 列/欄位置遺失 |
| PPTX | `pptx_processor.py:268-281` 同樣扁平去重 | 同上 |
| PDF 結構化 | `translation_service.py:614` `batch_texts=[c.content ...]` | `TableCell` IR 帶 row/col/span (`translatable_document.py:48-56`) 卻不放進 prompt |

- **`TABLE_RECOGNITION_ENABLED` 預設 false 且僅限 PDF** (`config.py:163`)。
- 即使開啟,`parsers/table_recognizer.py:279-307` `_parse_outputs()` **是 placeholder,只回傳一個 1×1 空 cell** — 結構化表格端到端不可用。

實際失敗模式:短表頭 (如 `Lead`/`型`) 無欄位脈絡而誤譯;去重導致 A 欄表頭「No.」與否定詞「No.」共用一譯;數值與單位/表頭永不同框。

### 痛點 3：譯文置於原文下方,閱讀不變

後端**已有 `output_mode`** = `append`(預設,堆疊在下)/`replace`(原地取代) (`api/schemas.py:11-13`),但:

1. **前端從不送此參數** (`grep output_mode app/frontend/src` = 0 筆;`TranslatePage.jsx:117-126`) → Office 檔實務上永遠 append。
2. **XLSX 完全無此開關**,硬編成同格 `src\n譯文` + 強制 `wrap_text` (`xlsx_processor.py:192-208`) → 列高爆炸。
3. DOCX 表格 cell / SDT / 文字方塊、PPTX SmartArt **硬編 append**,無 replace 分支。
4. **無真正的「雙語並排 / 左右雙欄 / 獨立譯文檔」模式** — 只有「堆在下面」或「原文消失」兩個極端 (PDF 另有 `side_by_side` 但不適用 Office)。

---

## 三、調查中發現的其他關鍵問題

**翻譯品質核心層 (跨所有格式):**

1. **每段完全孤立翻譯,看不到相鄰段落。** `CONTEXT_WINDOW_SEGMENTS=2`、`CONTEXT_MAX_CHARS=300`、`MAX_MERGE_SEGMENTS=4` 是**死設定,全程式碼無人使用** (`config.py:104-105`;僅 `translation_helpers.py:400` 註解假裝有)。
2. **長文件路徑品質反而更低。** `translate_document()` (>40000 字才走、僅 DOCX 單目標) **收了 `terms` 卻不用**,且**不跑 critique、不做術語替換** (`translation_service.py:384-533`);50-token overlap 只用於去重、無語境銜接。
3. **Critique loop 預設開但無評分守門** (`config.py:125`) — 每段多一次 LLM 呼叫使延遲近乎翻倍,卻**不判斷修訂是否更好**,最後一次永遠勝出。
4. **COMET QE 與 LLM-judge 預設都關** (`QE_ENABLED`/`JUDGE_ENABLED` false);judge 開了也是**整份文件一個 高/中/低** (`quality_judge.py:238-241`),無法定位問題。
5. **術語強制替換粗暴**:缺詞時直接把目標詞接到譯文尾 (`context_prompts.py:190-192`),破壞通順度;只在 `translate_texts` 路徑生效。
6. **無中途跨 provider failover**:client 在 job 開始時定一次 (`orchestrator.py:436-466`),單段失敗只寫 `[Translation failed|...]`。

---

## 四、業界對標

| 能力 | 本工具現況 | 業界 SOTA / 可借鏡 |
|---|---|---|
| PDF 版面 | 逐行凍結框 + search_for 塗白 | **BabelDOC/pdf2zh**:雙向 IR + DocLayout-YOLO + LayoutReader 閱讀順序 + **迭代縮放因子**自適應裝箱 |
| 文字膨脹 | 縮到 4pt 後截斷 | BabelDOC:scale 從 1.0 每步 0.05 縮到剛好裝下,不截斷 |
| 公式 | 當圖跳過或亂譯 | placeholder 保護,LaTeX 不進 MT |
| 表格上下文 | 孤立 cell | **「整表當 context、單格當 target」** (Table-Meets-LLM);序列化成 HTML/OTSL **整表一次翻**;指令置於表前、≥1-shot |
| 表格結構 | placeholder 1×1 | TableFormer/TATR/SLANet,輸出 HTML |
| 輸出模式 | append/replace (前端不可選) | DeepL/Smartcat/Crowdin/Phrase/Trados 標配**雙語雙欄 DOCX 匯出**;pdf2zh 有 `-mono/-dual/交錯頁` |
| 品質度量 | COMET (關)、judge 整檔一分 | **CometKiwi 逐段 QE** (runtime 無參考)、**xCOMET 錯誤 span**、MQM 人工金標;BLEU 已被 WMT22 棄用 |
| 版面保真度量 | 僅座標 ±2pt 一致性測試 | **BIoU**(原文↔還原框 IoU)、**SSIM** 頁面影像、**TEDS/GriTS** 表格、**MLLM-as-judge** 對頁面影像評版面 1-5 分 (BabelDOC benchmark) |

**主要參考來源**:BabelDOC (arXiv 2605.10845, MIT)、PDFMathTranslate/pdf2zh (EMNLP 2025 demo)、Docling+TableFormer (IBM, arXiv 2408.09869)、DocLayout-YOLO (Apache-2.0)、Surya/Marker (datalab)、COMET/xCOMET (Unbabel)、WMT22「Stop Using BLEU」(aclanthology 2022.wmt-1.2)、Table-Meets-LLM (arXiv 2305.13062)。

**差異化機會**:「帶上下文的整表 LLM 翻譯」連商業 CAT 工具都還沒做好 (多半仍逐格切句),這是真正的差異化,不只是補課。

---

## 五、分階段改善計畫 (每項附可驗證方式)

> 原則:**先建立度量基建**,否則所有改善無法驗收。建議執行序:階段 0 → 1 → 2 → 3 → 4。

### 階段 0 — 量測基建 + 低風險速贏

| # | 改善 | 變更點 | 驗證方式 |
|---|---|---|---|
| 0.1 | 建立版面保真度量 harness | render→rasterize | 對 golden PDF 做 identity-translate,計算逐區塊 **BIoU** 與非文字區 **SSIM**;設回歸預算 |
| 0.2 | 殘留原文檢查 | 塗白後 `get_text()` 該區應為空 | 直接抓「原文透出」失敗模式,做成必過測試 |
| 0.3 | 截斷率指標 | 統計 `render_truncated` 數與溢出面積 | 設預算,回歸即 fail |
| 0.4 | 前端開放 `output_mode` | `TranslatePage.jsx` 加下拉並送參數 | E2E:replace → 輸出無原文;append → 兩者皆在 |
| 0.5 | Fallback 降級告知 | ReportLab fallback 在 job 結果標記 degraded | 測試:fitz 失敗時 job 帶 warning flag |
| 0.6 | 修死設定 | 接上 `CONTEXT_WINDOW_SEGMENTS` 或刪除假註解 | 單元測試斷言相鄰段落確實進 prompt |

### 階段 1 — 表格上下文翻譯 (差異化重點)

| # | 改善 | 變更點 | 驗證方式 |
|---|---|---|---|
| 1.1 | 整表序列化翻譯 | 表格不再逐格送;序列化成 HTML/Markdown 表,指令置於表前,整表一次翻 | **選擇型測試**:捕捉送進 LLM 的字串,斷言「資料格與其欄位表頭同框出現」(今天必失敗) |
| 1.2 | 去重改 key=(text, 欄位) | `xlsx/docx` 去重加入欄位脈絡 | 測試:不同欄相同字串不被強制同譯;相同表頭跨列一致 |
| 1.3 | 修 `_parse_outputs()` placeholder | 真正解析 TATR/SLANet 格線 → row/col | TEDS/GriTS 對 golden 表格;移除 1×1 退化 |
| 1.4 | 數值+單位+表頭同框 | cell 上下文帶鄰格 | disambiguation fixture (同字依欄不同譯) |

### 階段 2 — Office 輸出排版

| # | 改善 | 驗證方式 |
|---|---|---|
| 2.1 | 新增「雙語雙欄 DOCX」輸出模式 (業界標配) | 結構斷言:原文與譯文在不同欄/段,非同 run 堆疊 |
| 2.2 | XLSX 加 `output_mode`:相鄰欄/儲存格註解/取代 三選一 | 測試:replace 時來源格未被污染;adjacent 時譯文在鄰欄 |
| 2.3 | DOCX 表格 cell/SDT、PPTX SmartArt 支援 replace | 補上目前缺的 replace 分支測試 |

### 階段 3 — PDF 版面還原重構 (核心,風險最高)

| # | 改善 | 驗證方式 |
|---|---|---|
| 3.1 | 塗白改用抽取 bbox,脫鉤 `search_for` | 0.2 殘留原文檢查歸零 |
| 3.2 | 行→段落聚合 + 區塊內 reflow (BabelDOC IR 範式) | BIoU 提升;截斷率下降 |
| 3.3 | 迭代縮放裝箱取代「縮到 4pt 截斷」 | 截斷率→0;字級不低於可讀閾值 |
| 3.4 | 樣式保真:逐 span run + 顏色/粗體回套 | 渲染斷言:輸出保留來源 StyleInfo |
| 3.5 | 閱讀順序模型 (LayoutReader 類) 取代單一 x-gap 閾值 | 多欄 fixture 的 reading-order 正規化編輯距離 |
| 3.6 | 偵測 DPI 72 → ~150–200 | 分類 mAP 提升 |
| 3.7 | 公式 placeholder 保護;掃描檔接 OCR (PaddleOCR/Surya) | 公式 pass-through 測試;掃描檔不再近空白 |

### 階段 4 — 翻譯品質與度量 (持續)

| # | 改善 | 驗證方式 |
|---|---|---|
| 4.1 | CometKiwi 逐段 QE 預設開,低分段路由重譯 | 建立 source→reference 語料 + CI COMET 回歸門檻 |
| 4.2 | judge 改逐段/逐區塊;對 PDF 頁面影像跑 MLLM-as-judge 版面 1-5 分 (複用既有 Gemma judge) | A/B 不同策略的 MQM/COMET 分數 |
| 4.3 | critique loop 加評分守門 (改善才採用) | 斷言修訂分數 ≥ 原譯才替換 |
| 4.4 | 長文件路徑補回 terms + critique + overlap 語境 | 斷言 `translate_document` 與短文件路徑同等品質 |

---

## 六、可驗證度量基建 (總表)

| 維度 | 指標 | 工具 / 依據 |
|---|---|---|
| 版面保真 | BIoU、SSIM (頁面影像) | 自建 harness;BabelDOC 範式 |
| 原文殘留 | 塗白後區塊 `get_text()` 為空 | PyMuPDF |
| 文字裝箱 | 截斷率、溢出面積、最小字級 | IR `render_truncated` |
| 表格結構 | TEDS / GriTS | PubTabNet / TATR 官方度量 |
| 表格上下文 | prompt 內容斷言 (表頭與資料格同框) | 選擇型單元測試 |
| 翻譯品質 | CometKiwi (runtime)、xCOMET (錯誤 span)、MQM (人工 A/B) | Unbabel COMET |
| 閱讀順序 | 正規化編輯距離 / Kendall's τ | golden IR 標註 |

---

## 七、優先順序與下一步

**執行序**:階段 0 (度量基建 + 前端開 output_mode) → 階段 1 (表格,差異化最高、ROI 最佳) → 階段 2 (Office 雙欄) → 階段 3 (PDF 重構,風險最高放後) → 階段 4 (品質與度量,持續)。

**為何此序**:先有度量,後續每步才能客觀驗收;表格上下文是差異化最高且風險可控的速贏;PDF 重構牽動最廣、風險最高,放在度量與經驗成熟後。

每個階段以 `/cdd-new` 開立獨立 CDD change,依本計畫的「驗證方式」欄定義 acceptance criteria 與 gate。

---

## 八、執行編排計畫 (Execution & Orchestration Plan)

本節將工作項目切成可由 AI agent 編排、**以 git worktree + 獨立 PR 並行推進、完成後合併回 `main`** 的軌道 (track)。並行的前提是 **PR 之間不碰同一批檔案**;有相依或共用檔案者必須序列化。

### 8.1 相依關係與檔案擁有權

| 項目 | 軌道 | 相依於 (前置) | 主要檔案 (擁有權) |
|---|---|---|---|
| 0.4 前端 output_mode | A 前端 | — (後端 schema/route 已存在) | `frontend/.../TranslatePage.jsx`、`frontend/src/api/*` |
| 0.1/0.2/0.3 度量 harness | B 度量基建 | — | 新增 `tests/metrics/*`、`tests/fixtures/golden/*` (純新增) |
| 0.6 修死設定 (context window) | C 品質設定 | — | `services/translation_helpers.py`、`config.py` |
| 0.5 fallback 降級告知 | (併入 G 前) | — | `processors/pdf_processor.py` |
| 1.3 TATR `_parse_outputs` | E 表格結構 | — | `parsers/table_recognizer.py` (孤立) |
| 1.1/1.2/1.4 表格上下文 | D 表格翻譯 | 1.3 (僅 PDF 表格路徑) | `clients/ollama_client.py` (prompt)、`processors/{docx,xlsx,pptx}_processor.py` |
| 3.1–3.7 PDF 重構 | G PDF 還原 | B (驗證需 BIoU/SSIM)、0.2 (驗 3.1) | `renderers/*`、`parsers/pdf_parser.py`、`parsers/layout_detector.py`、`processors/pdf_processor.py` |
| 2.1/2.2/2.3 Office 輸出模式 | F 輸出排版 | **D (共用三個 processor)** | `processors/{docx,xlsx,pptx}_processor.py` |
| 4.1/4.2 QE + judge | H 品質度量 | B (4.2 需 rasterize)、語料 | `services/quality_*.py`、`services/translation_service.py` |
| 4.3/4.4 critique 守門 + 長文件 parity | H 品質度量 | C (共用 translation_service) | `services/translation_service.py` |

**衝突區 (同檔案,不可並行,須序列化):**
- `processors/{docx,xlsx,pptx}_processor.py` → 軌道 **D 先、F 後**。
- `processors/pdf_processor.py` → 0.5 先 (Wave 1)、軌道 G 後 (Wave 2)。
- `services/translation_service.py` → 軌道 C 先、軌道 H 後。
- `contracts/` 為全域共用且 `cdd-kit gate` 全域驗證 → **合約變更先在 `main` 上小步落地,再開實作軌道**,避免多 PR 同改合約互相阻擋 gate。

### 8.2 並行波次 (Waves)

```
Wave 1  ── 全獨立,可同時開 5 個 worktree/PR ──────────────
  A  前端 output_mode (0.4)
  B  度量 harness (0.1, 0.2, 0.3)
  C  品質設定修死碼 (0.6)
  E  TATR 表格結構 (1.3)
  +  0.5 fallback 降級旗標 (小型獨立)
                │ 全部合併回 main
                ▼
Wave 2  ── 2 條並行 (不同檔案集) ─────────────────────────
  D  表格上下文翻譯 (1.1→1.2→1.4)   [需 E 已併入供 PDF 表格]
  G  PDF 版面重構 (3.1→3.2→…→3.7)   [需 B 度量、0.2 殘留檢查]
                │ 全部合併回 main
                ▼
Wave 3  ── 2 條並行 (不同檔案集) ─────────────────────────
  F  Office 輸出模式 (2.1, 2.2, 2.3)  [需 D 已併入,共用 processor]
  H  品質度量與守門 (4.1, 4.2, 4.3, 4.4)  [需 B、C 已併入]
```

並行度:Wave 1 ≈ 5 PR、Wave 2 ≈ 2 PR、Wave 3 ≈ 2 PR。軌道 G (PDF) 內部 3.1→3.7 為單一 worktree 內的序列,因為都改同一批 renderer 檔案。

### 8.3 Worktree + PR 協定

每條軌道一個 worktree、一個 CDD change、一個 PR:

1. **開軌道**:`/cdd-new <軌道描述>` 取得 change-id,scaffolds 合約/測試/gate;實作 agent 以 `isolation: "worktree"` 在獨立 worktree 工作 (`git worktree add ../tt-<track> -b feat/<track>`)。
2. **驗收**:以本計畫對應項目的「驗證方式」為 acceptance criteria;PR 前跑 `cdd-kit gate <id> --strict`。
3. **PR**:每軌道一個 PR → `main`;CI 必過 (`cdd-kit gate`、測試、`openapi export --check`)。
4. **合併序**:依 8.2 波次;同波次內互不相依者合併順序自由,跨波次須等前一波全部併入。
5. **下一波 rebase**:Wave N+1 的 worktree 開分支前先 `git fetch && git rebase origin/main`,確保拿到前一波的檔案變更 (尤其衝突區檔案)。
6. **CDD 收尾**:每軌道完成後 `/cdd-close <id>` 提升 learnings 並 archive。

### 8.4 AI agent 編排建議

- **Wave 1 可一次派 5 個並行實作 agent** (各自 `isolation: "worktree"`),因檔案集互斥、零衝突風險,適合用 workflow / 多 subagent 同時推進。
- **Wave 2/3 每波 2 個並行 agent**;波次之間設 barrier (前一波全 PR 合併後才啟動下一波)。
- 軌道 G (PDF) 因內部序列且風險最高,建議單一 agent 逐步 (3.1→3.7) 並在每步以 BIoU/截斷率回歸把關,而非並行拆碎。
- 編排者 (orchestrator) 負責:派工 → 收 PR → 跑 gate → 依序合併 → rebase 下一波 → 重派。
