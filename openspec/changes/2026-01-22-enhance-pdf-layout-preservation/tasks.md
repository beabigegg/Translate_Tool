# Tasks: PDF 版面保留翻譯實作任務

## Phase 1: 基礎升級 (PyMuPDF + Bbox 提取)

### 1.1 環境與依賴

- [x] 1.1.1 新增 `PyMuPDF>=1.23.0` 到 `requirements.txt`
- [x] 1.1.2 驗證 PyMuPDF 與現有依賴無衝突
- [ ] 1.1.3 更新 `SETUP.md` 安裝說明 (no SETUP.md exists)
- [x] 1.1.4 更新 `environment.yml` 依賴 (uses requirements.txt)

### 1.2 資料模型

- [x] 1.2.1 建立 `app/backend/models/__init__.py`
- [x] 1.2.2 建立 `app/backend/models/translatable_document.py`
  - [x] 實作 `BoundingBox` dataclass
  - [x] 實作 `StyleInfo` dataclass
  - [x] 實作 `ElementType` enum
  - [x] 實作 `TranslatableElement` dataclass
  - [x] 實作 `PageInfo` dataclass
  - [x] 實作 `TranslatableDocument` dataclass
  - [x] 實作 `to_dict()` / `from_dict()` 以支援序列化
- [x] 1.2.3 建立 `app/backend/utils/bbox_utils.py`
  - [x] 實作 `normalize_bbox()` - 統一 bbox 格式
  - [x] 實作 `calculate_iou()` - 計算重疊度
  - [x] 實作 `is_bbox_inside()` - 判斷包含關係

### 1.3 PDF 解析器

- [x] 1.3.1 建立 `app/backend/parsers/__init__.py`
- [x] 1.3.2 建立 `app/backend/parsers/base.py`
  - [x] 定義 `BaseParser` 抽象類別
  - [x] 定義 `parse()` 抽象方法
- [x] 1.3.3 建立 `app/backend/parsers/pdf_parser.py`
  - [x] 實作 `PyMuPDFParser` 類別
  - [x] 實作 `extract_text_blocks_with_bbox()` - 提取帶座標的文字區塊
  - [x] 統一輸出 bbox 至內部座標系 (左上原點)
  - [x] 實作 `classify_block_type()` - 根據位置判斷元素類型
  - [x] 實作 `detect_tables()` - 使用 PyMuPDF 內建表格偵測
  - [x] 實作 `sort_by_reading_order()` - (y0, x0) 排序
  - [x] 實作 `filter_header_footer()` - 過濾頁首頁尾

### 1.4 整合現有處理器

- [x] 1.4.1 修改 `app/backend/processors/pdf_processor.py`
  - [x] 新增 `use_pymupdf` 參數 (預設 True)
  - [x] 整合 `PyMuPDFParser`
  - [x] 保留 PyPDF2 作為 fallback
  - [x] 實作閱讀順序排序
  - [x] 實作頁首頁尾過濾選項
- [x] 1.4.2 修改 `app/backend/processors/orchestrator.py`
  - [x] 傳遞 `skip_header_footer` 參數到 `translate_pdf()`
- [x] 1.4.3 修改 `app/backend/config.py`
  - [x] 新增 `PDF_PARSER_ENGINE` 配置
  - [x] 新增 `PDF_SKIP_HEADER_FOOTER` 配置
  - [x] 新增 `PDF_HEADER_FOOTER_MARGIN_PT` 配置

### 1.5 測試

- [x] 1.5.1 建立 `tests/test_pdf_parser.py`
  - [x] 測試 bbox 提取正確性
  - [x] 測試閱讀順序排序
  - [x] 測試元素類型分類
  - [x] 測試表格偵測 (`_is_inside`, `_detect_and_mark_tables`)
- [x] 1.5.2 建立 `tests/test_translatable_document.py`
  - [x] 測試資料模型序列化/反序列化
- [x] 1.5.3 建立 `tests/test_bbox_utils.py`
  - [x] 測試 bbox 工具函式
- [x] 1.5.4 新增 pytest 依賴到 requirements.txt

---

## Phase 2: 架構重構 (統一中間層)

### 2.1 渲染器模組

- [x] 2.1.1 建立 `app/backend/renderers/__init__.py`
- [x] 2.1.2 建立 `app/backend/renderers/base.py`
  - [x] 定義 `BaseRenderer` 抽象類別
  - [x] 定義 `render()` 抽象方法
  - [x] 定義 `RenderMode` 列舉 (INLINE, SIDE_BY_SIDE, OVERLAY)
- [x] 2.1.3 建立 `app/backend/renderers/inline_renderer.py`
  - [x] 實作 `InlineRenderer` 類別
  - [x] 重構現有段落插入邏輯
  - [x] 支援從 `TranslatableDocument` 渲染
  - [x] 支援 `render_from_segments()` 向後相容方法

### 2.2 重構現有處理器

- [x] 2.2.1 建立 `app/backend/parsers/docx_parser.py`
  - [x] 抽取 DOCX 解析邏輯
  - [x] 輸出 `TranslatableDocument` 格式
  - [x] 支援段落、表格、SDT、文字方塊提取
- [x] 2.2.2 重構 `app/backend/processors/docx_processor.py`
  - [x] 保持向後相容 (現有 processor 邏輯保留)
  - [ ] 完全遷移至 `DocxParser` + `InlineRenderer` (延後至 Phase 3)
- [x] 2.2.3 建立 `app/backend/parsers/pptx_parser.py`
  - [x] 抽取 PPTX 解析邏輯
  - [x] 支援投影片、形狀、表格提取
  - [x] 提取 bbox 座標
- [x] 2.2.4 重構 `app/backend/processors/pptx_processor.py`
  - [x] 保持向後相容 (現有 processor 邏輯保留)
  - [ ] 完全遷移至 `PptxParser` + `InlineRenderer` (延後至 Phase 3)

### 2.3 配置與介面

- [x] 2.3.1 修改 `app/backend/config.py`
  - [x] 新增 `LAYOUT_PRESERVATION_MODE` 配置
  - [x] 支援 `inline`, `side_by_side`, `overlay` 模式
  - [x] 新增 `DEFAULT_FONT_FAMILY`, `MIN_FONT_SIZE_PT`, `MAX_FONT_SIZE_PT` 等配置
- [x] 2.3.2 修改 `app/backend/processors/orchestrator.py`
  - [x] 新增 `layout_mode` 與 `output_format` 參數
  - [x] 傳遞參數至 `translate_pdf()`
  - [x] 支援 PDF 輸出檔名 (_translated.pdf)
- [x] 2.3.3 修改 `app/backend/processors/pdf_processor.py`
  - [x] 新增 `output_format` 與 `layout_mode` 參數
  - [x] 驗證不支援的組合 (inline + pdf output)

### 2.4 測試

- [x] 2.4.1 建立 `tests/test_inline_renderer.py`
- [x] 2.4.2 建立 `tests/test_docx_parser.py`
- [x] 2.4.3 建立 `tests/test_pptx_parser.py`
- [x] 2.4.4 驗證重構後功能正確 (89 passed, 4 skipped)

---

## Phase 3: 高級版面保留 (座標渲染)

### 3.1 依賴與資源

- [x] 3.1.1 新增 `reportlab>=4.0.0` 到 `requirements.txt`
- [x] 3.1.2 建立 `app/backend/fonts/` 目錄 (使用系統字型)
- [x] 3.1.3 支援 NotoSans 字型
  - [x] NotoSansCJK (簡繁中文、日韓文)
  - [x] NotoSansThai (泰文)
  - [x] NotoSansArabic, NotoSansHebrew (RTL)
- [x] 3.1.4 建立 `app/backend/utils/font_utils.py`
  - [x] 實作 `register_fonts()` - 註冊字型
  - [x] 實作 `get_font_for_language()` - 語言字型映射
  - [x] 實作 `calculate_text_width()` - 計算文字寬度
  - [x] 實作 `fit_text_to_bbox()` - 字型縮放
  - [x] 實作 `detect_text_direction()` - RTL 文字偵測

### 3.2 座標渲染器

- [x] 3.2.1 建立 `app/backend/renderers/text_region_renderer.py`
  - [x] 實作 `TextRegion` dataclass
  - [x] 實作 `calculate_rotation_from_bbox()` - 旋轉角度計算
  - [x] 實作 `render_text_region()` - 單一區域渲染
  - [x] 實作 `render_text_regions()` - 批次渲染
  - [x] 實作 `create_text_regions_from_elements()` - 從元素建立區域
- [x] 3.2.2 建立 `app/backend/renderers/coordinate_renderer.py`
  - [x] 實作 `CoordinateRenderer` 類別
  - [x] 實作 PDF 座標轉換 (Y 軸翻轉)
  - [x] 實作遮罩層繪製 (draw_background)
  - [x] 實作譯文層繪製
  - [x] 支援 OVERLAY 模式
  - [x] 支援 SIDE_BY_SIDE 模式

### 3.3 PDF 生成

- [x] 3.3.1 建立 `app/backend/renderers/pdf_generator.py`
  - [x] 實作 `PDFGenerator` 類別
  - [x] 支援從 `TranslatableDocument` 生成 PDF
  - [x] 支援 `overlay` 模式 - 覆蓋原文
  - [x] 支援 `side_by_side` 模式 - 並列對照
  - [x] 使用 PyMuPDF 合併原始 PDF 與譯文層
- [x] 3.3.2 整合到處理流程
  - [x] 修改 `pdf_processor.py` 支援 PDF 輸出
  - [x] 新增 `output_format` 參數 (docx | pdf)
  - [x] 新增 `layout_mode` 參數並檢查相容性
  - [x] 實作 `_translate_pdf_to_pdf()` 函式

### 3.4 測試

- [x] 3.4.1 建立 `tests/test_font_utils.py` (36 tests)
- [x] 3.4.2 建立 `tests/test_text_region_renderer.py` (24 tests)
- [x] 3.4.3 建立 `tests/test_coordinate_renderer.py` (15 tests)
- [x] 3.4.4 建立 `tests/test_pdf_generator.py` (22 tests)
- [x] 3.4.5 所有測試通過 (187 passed, 4 skipped)
- [x] 3.4.6 視覺驗證測試
  - [x] 準備測試 PDF 檔案 (test_document/edit.pdf)
  - [x] 驗證輸出版面正確性 (test_output/edit_translated_overlay.pdf, edit_translated_side_by_side.pdf)

---

## Phase 4: OCR 支援 (可選模組)

### 4.1 可選依賴結構

- [ ] 4.1.1 建立 `requirements-ocr.txt`
  ```
  paddleocr>=3.0.0
  paddlex[ocr]>=3.0.0
  python-magic>=0.4.27
  pdf2image>=1.17.0
  opencv-python>=4.8.0
  ```
- [ ] 4.1.2 更新安裝說明
  - [ ] 說明 OCR 為可選功能
  - [ ] 提供 GPU/CPU 安裝指引

### 4.2 文件類型偵測

- [ ] 4.2.1 建立 `app/backend/ocr/__init__.py`
- [ ] 4.2.2 建立 `app/backend/ocr/document_detector.py`
  - [ ] 從 Tool_OCR 移植核心邏輯
  - [ ] 實作 `DocumentType` enum
  - [ ] 實作 `ProcessingTrackRecommendation` dataclass
  - [ ] 實作 `DocumentTypeDetector` 類別
  - [ ] 實作 `detect()` - 偵測文件類型
  - [ ] 實作 `_analyze_pdf()` - PDF 類型分析
  - [ ] 加入文字層門檻判定 (平均每頁字元數)

### 4.3 OCR 處理器

- [ ] 4.3.1 建立 `app/backend/ocr/ocr_processor.py`
  - [ ] 實作 `OCRProcessor` 類別
  - [ ] 實作懶載入 PaddleOCR 引擎
  - [ ] 實作 `recognize_text()` - 文字識別
  - [ ] 實作 `extract_with_layout()` - 版面分析
  - [ ] 輸出 `TranslatableDocument` 格式

### 4.4 整合

- [ ] 4.4.1 修改 `app/backend/processors/pdf_processor.py`
  - [ ] 新增 `use_ocr` 參數
  - [ ] 自動偵測 PDF 類型
  - [ ] 根據類型選擇處理軌道
- [ ] 4.4.2 修改 `app/backend/config.py`
  - [ ] 新增 `OCR_ENABLED` 配置
  - [ ] 新增 `OCR_DEFAULT_LANG` 配置
  - [ ] 新增 `OCR_USE_GPU` 配置
  - [ ] 新增 `OCR_TEXT_MIN_CHARS_PER_PAGE` 配置

### 4.5 測試

- [ ] 4.5.1 建立 `tests/test_document_detector.py`
- [ ] 4.5.2 建立 `tests/test_ocr_processor.py`
- [ ] 4.5.3 準備測試資料
  - [ ] 可編輯 PDF 樣本
  - [ ] 掃描型 PDF 樣本
  - [ ] 混合型 PDF 樣本

---

## 驗收檢查清單

### Phase 1 驗收
- [x] PDF 文字提取包含 bbox 座標
- [x] 多欄 PDF 閱讀順序正確
- [x] 頁首/頁尾可被識別
- [x] 表格區域可被偵測
- [x] 現有翻譯功能無退化

### Phase 2 驗收
- [x] DOCX/PPTX 解析器建立完成 (DocxParser, PptxParser)
- [x] 渲染器架構建立完成 (BaseRenderer, InlineRenderer)
- [x] 輸出模式可配置 (LAYOUT_PRESERVATION_MODE)
- [x] layout_mode/output_format 參數傳遞完成
- [x] 測試覆蓋 (89 passed, 4 skipped)
- [ ] 完全遷移 processor 至新架構 (延後至 Phase 3)

### Phase 3 驗收
- [x] 可生成座標定位的 PDF (PDFGenerator)
- [x] 譯文長度超過時自動縮小字型 (fit_text_to_bbox)
- [x] 多語言字型正確顯示 (NotoSansCJK + 語言映射)
- [x] overlay/side_by_side 模式可用 (CoordinateRenderer)
- [x] 測試覆蓋完整 (187 passed, 4 skipped)

### Phase 4 驗收 (可選)
- [ ] 可自動偵測 PDF 類型
- [ ] 掃描型 PDF 可通過 OCR 處理
- [ ] OCR 模組可獨立安裝/卸載
- [ ] OCR 觸發門檻可配置
