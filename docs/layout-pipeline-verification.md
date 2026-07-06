# 版面管線驗證報告：版面偵測、版面還原、譯文插入後版面確認

驗證日期：2026-07-06（基準 commit：`23a258f`）
驗證方法：全測試套件基準執行（1086 passed / 4 skipped）＋ 端到端接線追蹤（orchestrator → parser → detector → renderer → API → frontend）。

## 1. 版面偵測（Layout Detection）— ✅ 已確認接線完整

呼叫鏈（PDF-to-PDF 與 PDF-to-DOCX 共用同一 parser）：

```
orchestrator.process_files (orchestrator.py .pdf 分支)
  → pdf_processor.translate_pdf
     → _translate_pdf_to_pdf / _translate_pdf_with_pymupdf
        → PyMuPDFParser.parse
           → _run_layout_detector (pdf_parser.py:152，LAYOUT_DETECTOR_ENABLED runtime 讀取)
              → LayoutDetector.detect (layout_detector.py:252)
                 → _run_inference → _assign_element_types → _map_class_index
                 → _assign_reading_order（欄位感知閱讀順序）
```

- **heron-101 class-index 映射**（commit `757fac5` 修正）：`_HERON_CLASS_NAMES`
  使用 DocLayNet 字母序（layout_detector.py:76-88），由
  `tests/test_layout_detector.py::test_class_names_list_matches_canonical_order`
  等測試釘住，防止 Text/Table 誤判為 Figure/Formula 的回歸。
- **Fail-soft**（BR-33/D-2）：模型缺失、ONNX 載入失敗、推論失敗時逐頁退回
  `round(y0,10pt)` 啟發式排序，不中斷任務。
- **layout_viz 持久化**：`_save_layout_viz`（pdf_processor.py）在 DOCX 路徑與
  PDF-to-PDF 路徑（`757fac5` 補上）都會寫出 `layout_viz.json`＋頁面縮圖，
  經 `GET /api/jobs/{id}/layout` 提供給前端 `LayoutViewer.jsx`。
  測試：`tests/test_pdf_layout_viz_persistence.py`。

## 2. 版面還原（Layout Restoration）— ✅ 已確認接線完整

| 輸出模式 | layout_mode | 使用的渲染器 |
|---|---|---|
| PDF | `inline` | 拒絕（`ValueError`，pdf_processor.py） |
| PDF | `overlay` / `side_by_side` | fitz 主渲染（`fitz_renderer.PDFGenerator`） |
| PDF | 上述模式且 fitz 例外 | ReportLab 備援（`coordinate_renderer`，BR-34 單一備援路徑＋`FITZ_FALLBACK_WARNING`） |
| DOCX | `inline`（預設） | 直接以 `python-docx` 建構（非 renderer 類別） |

- **BR-36 裝箱串接**（縮字 → 行距 → 字距 → 受控下溢 ≤15% → 截斷）唯一實作於
  `text_region_renderer.py`，僅 fitz 與 coordinate 兩個 PDF 渲染器引用；
  單一路徑由 `tests/test_text_region_renderer.py::test_cascade_not_imported_in_other_renderers`
  強制（BR-40）。
- 兩個 PDF 渲染器都經共用 `bbox_reflow.reflow_document` 產生 Placement，
  收斂性由 `tests/test_renderer_convergence.py` 驗證（含 AC-6 接線防呆）。

## 3. 譯文插入後版面確認 — ⚠️ 發現缺口，本次修正

### 驗證發現的缺口

1. **渲染溢出防護默默丟行（BR-38 違反）**：`fitz_renderer.py`
   `_insert_text_in_rect` 的最後防線在行數超出 bbox 底線時直接丟棄剩餘行，
   只寫 `logger.debug`，未設 `render_truncated` —— 屬於契約禁止的
   silent truncation。
2. **`render_truncated` 是死信號**：渲染器有設旗標（cascade step e），
   IR 序列化也有帶，但 runtime 沒有任何消費者 —— 不會進 job warnings、
   不會進 API、前端看不到。唯一讀取者是測試指標 `tests/metrics/truncation_rate.py`。
3. **版面品質指標僅存在於測試**：`tests/metrics/`（BIoU、殘留文字、截斷率）
   只被 `tests/test_layout_metrics.py` 與 CI gate 引用，真實任務的輸出
   從未被這些指標檢查。
4. **`layout_viz` 是「偵測結果預覽」而非「輸出確認」**：bbox 與縮圖都來自
   **來源** PDF（parse 時建立、`_save_layout_viz` 對 `in_path` 轉圖），
   前端 LayoutViewer 疊加的是偵測框，不能證明譯文放得下。

### 本次修正（把確認機制接到使用者看得見的地方）

- `fitz_renderer.py`：溢出防護丟行時設 `element.render_truncated = True`
  並升級為 WARNING log（BR-38 合規）。
- `pdf_processor.py`：PDF-to-PDF 路徑渲染後統計 `render_truncated` 元素數，
  透過既有 `warnings_callback` 管道發出
  `render_truncation_warning(count, lang)` —— 進入 `job.warnings`，
  由 `GET /api/jobs/{id}` 的 `warnings` 欄位呈現給前端。
  旗標於每種語言渲染前重置，避免多語言互相污染與反序列化殘留旗標誤報。
- 契約同步更新：`contracts/business/business-rules.md`（BR-38）、
  `contracts/data/data-shape-contract.md`（`render_truncated` 欄位規則、
  渲染器消費規則）。
- 新測試：`tests/test_layout_confirmation_warnings.py`（8 項，含
  無 mock 渲染路徑的全鏈整合測試，證明渲染器標記的元素實例與
  處理器統計的是同一批）。

### 輸出側版面 QA（第二階段，本分支後續 commit）

把「渲染後重新解析輸出、量化驗證版面」接入 runtime：

- **指標升格**：`tests/metrics/{biou, residual_text, truncation_rate}.py` 的實作
  移至 `app/backend/services/layout_qa.py`（測試路徑保留 re-export shim，
  `contracts/ci/ci-gate-contract.md` 引用的 pytest 指令不受影響）。
- **渲染後 QA**：PDF-to-PDF 路徑每個輸出檔渲染完成後，`run_layout_qa` 重新
  打開輸出 PDF 量測：BIoU（來源元素 bbox vs 輸出文字區塊，逐頁對齊，
  預算 0.8）、殘留原文（遮罩 bbox 內是否仍可讀到原文——以正規化前綴
  比對區分譯文與原文）、截斷率。`side_by_side` 模式頁面重組，bbox 同一性
  指標回報 `null`，僅量測截斷。Fail-soft：QA 失敗只記 log，不影響任務。
- **浮出鏈**：`layout_qa_callback` 比照 `warnings_callback` 從
  `job_manager → orchestrator.process_files → translate_pdf →
  _translate_pdf_to_pdf` 穿線；結果存入 `JobRecord.layout_qa`（以
  (file, target_lang) 去重），經 `GET /api/jobs/{id}` 的 `layout_qa` 欄位
  （`LayoutQAEntry[]`）到前端 `TranslationProgress` 完成面板（含
  通過/需檢視徽章、BIoU、截斷與殘留計數）；`warnings` 清單也一併在
  完成面板顯示（先前後端有回傳但前端未呈現）。
- **開關**：`LAYOUT_QA_ENABLED`（預設開，runtime 讀取，比照
  `LAYOUT_DETECTOR_ENABLED`）；已同步 `contracts/env/` 三個工件
  （env-contract.md、env.schema.json、.env.example.template）。
- **契約**：`contracts/api/api-contract.md` 新增 `LayoutQAEntry` schema 與
  `JobStatus.layout_qa` 欄位；`openapi.yml` 已重新匯出並通過同步檢查。
- **新測試**：`tests/test_layout_qa.py`（12 項：真實 fitz 輸出量測、殘留
  原文偵測與譯文不誤報、side_by_side 降級、fail-soft、接線與開關、
  job record 去重、API 傳遞）。

## 4. 其餘觀察（未在本次處理，建議後續追蹤）

| 項目 | 位置 | 說明 |
|---|---|---|
| `InlineRenderer` 未接線 | `renderers/inline_renderer.py` | 僅由 `renderers/__init__.py` 匯出與測試引用；實際 PDF→DOCX inline 輸出直接用 `python-docx` 建構。屬孤兒程式碼。 |
| `LayoutReader` 未接線 | `layout_detector.py:591` | runtime 實際用的是 `LayoutDetector._assign_reading_order`；`LayoutReader` 只有測試引用。 |
| ReportLab 備援不標記截斷 | `coordinate_renderer.py` | 備援路徑經 `render_text_regions` 串接 cascade，但未把 `truncated` 回寫到 IR 元素；備援渲染時截斷警告不會觸發（主路徑已涵蓋絕大多數情況；輸出側 QA 的 BIoU/殘留檢查不受影響）。 |
