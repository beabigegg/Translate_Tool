# Tasks: PDF 版面保留翻譯實作任務

## Phase 1: 基礎升級 (PyMuPDF + Bbox 提取)

### 1.1 環境與依賴

- [ ] 1.1.1 新增 `PyMuPDF>=1.23.0` 到 `requirements.txt`
- [ ] 1.1.2 驗證 PyMuPDF 與現有依賴無衝突
- [ ] 1.1.3 更新 `SETUP.md` 安裝說明
- [ ] 1.1.4 更新 `environment.yml` 依賴

### 1.2 資料模型

- [ ] 1.2.1 建立 `app/backend/models/__init__.py`
- [ ] 1.2.2 建立 `app/backend/models/translatable_document.py`
  - [ ] 實作 `BoundingBox` dataclass
  - [ ] 實作 `StyleInfo` dataclass
  - [ ] 實作 `ElementType` enum
  - [ ] 實作 `TranslatableElement` dataclass
  - [ ] 實作 `PageInfo` dataclass
  - [ ] 實作 `TranslatableDocument` dataclass
  - [ ] 實作 `to_dict()` / `from_dict()` 以支援序列化
- [ ] 1.2.3 建立 `app/backend/utils/bbox_utils.py`
  - [ ] 實作 `normalize_bbox()` - 統一 bbox 格式
  - [ ] 實作 `calculate_iou()` - 計算重疊度
  - [ ] 實作 `is_bbox_inside()` - 判斷包含關係

### 1.3 PDF 解析器

- [ ] 1.3.1 建立 `app/backend/parsers/__init__.py`
- [ ] 1.3.2 建立 `app/backend/parsers/base.py`
  - [ ] 定義 `BaseParser` 抽象類別
  - [ ] 定義 `parse()` 抽象方法
- [ ] 1.3.3 建立 `app/backend/parsers/pdf_parser.py`
  - [ ] 實作 `PyMuPDFParser` 類別
  - [ ] 實作 `extract_text_blocks_with_bbox()` - 提取帶座標的文字區塊
  - [ ] 統一輸出 bbox 至內部座標系 (左上原點)
  - [ ] 實作 `classify_block_type()` - 根據位置判斷元素類型
  - [ ] 實作 `detect_tables()` - 使用 PyMuPDF 內建表格偵測
  - [ ] 實作 `sort_by_reading_order()` - (y0, x0) 排序
  - [ ] 實作 `filter_header_footer()` - 過濾頁首頁尾

### 1.4 整合現有處理器

- [ ] 1.4.1 修改 `app/backend/processors/pdf_processor.py`
  - [ ] 新增 `use_pymupdf` 參數 (預設 True)
  - [ ] 整合 `PyMuPDFParser`
  - [ ] 保留 PyPDF2 作為 fallback
  - [ ] 實作閱讀順序排序
  - [ ] 實作頁首頁尾過濾選項
- [ ] 1.4.2 修改 `app/backend/processors/orchestrator.py`
  - [ ] 傳遞新參數到 `translate_pdf()`
- [ ] 1.4.3 修改 `app/backend/config.py`
  - [ ] 新增 `PDF_PARSER_ENGINE` 配置
  - [ ] 新增 `SKIP_HEADER_FOOTER` 配置
  - [ ] 新增 `HEADER_FOOTER_MARGIN_PT` 配置

### 1.5 測試

- [ ] 1.5.1 建立 `tests/test_pdf_parser.py`
  - [ ] 測試 bbox 提取正確性
  - [ ] 測試閱讀順序排序
  - [ ] 測試元素類型分類
  - [ ] 測試表格偵測
- [ ] 1.5.2 建立 `tests/test_translatable_document.py`
  - [ ] 測試資料模型序列化/反序列化
- [ ] 1.5.3 更新整合測試
  - [ ] 驗證與現有 PDF 翻譯行為相容

---

## Phase 2: 架構重構 (統一中間層)

### 2.1 渲染器模組

- [ ] 2.1.1 建立 `app/backend/renderers/__init__.py`
- [ ] 2.1.2 建立 `app/backend/renderers/base.py`
  - [ ] 定義 `BaseRenderer` 抽象類別
  - [ ] 定義 `render()` 抽象方法
- [ ] 2.1.3 建立 `app/backend/renderers/inline_renderer.py`
  - [ ] 實作 `InlineRenderer` 類別
  - [ ] 重構現有段落插入邏輯
  - [ ] 支援從 `TranslatableDocument` 渲染

### 2.2 重構現有處理器

- [ ] 2.2.1 建立 `app/backend/parsers/docx_parser.py`
  - [ ] 抽取 DOCX 解析邏輯
  - [ ] 輸出 `TranslatableDocument` 格式
- [ ] 2.2.2 重構 `app/backend/processors/docx_processor.py`
  - [ ] 使用 `DocxParser` + `InlineRenderer`
  - [ ] 保持向後相容
- [ ] 2.2.3 建立 `app/backend/parsers/pptx_parser.py`
  - [ ] 抽取 PPTX 解析邏輯
- [ ] 2.2.4 重構 `app/backend/processors/pptx_processor.py`
  - [ ] 使用新架構

### 2.3 配置與介面

- [ ] 2.3.1 修改 `app/backend/config.py`
  - [ ] 新增 `LAYOUT_PRESERVATION_MODE` 配置
  - [ ] 支援 `inline`, `side_by_side`, `overlay` 模式
- [ ] 2.3.2 修改 `app/backend/processors/orchestrator.py`
  - [ ] 新增 `layout_mode` 與 `output_format` 參數
  - [ ] 根據模式選擇渲染器

### 2.4 測試

- [ ] 2.4.1 建立 `tests/test_inline_renderer.py`
- [ ] 2.4.2 更新 `tests/test_docx_processor.py`
- [ ] 2.4.3 驗證重構後功能正確

---

## Phase 3: 高級版面保留 (座標渲染)

### 3.1 依賴與資源

- [ ] 3.1.1 新增 `reportlab>=4.0.0` 到 `requirements.txt`
- [ ] 3.1.2 建立 `app/backend/fonts/` 目錄
- [ ] 3.1.3 下載 NotoSans 字型檔案
  - [ ] NotoSansSC-Regular.ttf (簡繁中文)
  - [ ] NotoSansKR-Regular.ttf (韓文)
  - [ ] NotoSansThai-Regular.ttf (泰文)
- [ ] 3.1.4 建立 `app/backend/utils/font_utils.py`
  - [ ] 實作 `register_fonts()` - 註冊字型
  - [ ] 實作 `get_font_for_language()` - 語言字型映射
  - [ ] 實作 `calculate_text_width()` - 計算文字寬度
  - [ ] 實作 `fit_text_to_bbox()` - 字型縮放

### 3.2 座標渲染器

- [ ] 3.2.1 建立 `app/backend/renderers/text_region_renderer.py`
  - [ ] 從 Tool_OCR 移植核心邏輯
  - [ ] 實作 `calculate_rotation()` - 旋轉角度計算
  - [ ] 實作 `estimate_font_size()` - 字型大小估算
  - [ ] 實作 `render_text_region()` - 單一區域渲染
  - [ ] 實作 `render_all_regions()` - 批次渲染
- [ ] 3.2.2 建立 `app/backend/renderers/coordinate_renderer.py`
  - [ ] 實作 `CoordinateRenderer` 類別
  - [ ] 實作 PDF 座標轉換 (Y 軸翻轉)
  - [ ] 實作遮罩層繪製 (可選)
  - [ ] 實作譯文層繪製

### 3.3 PDF 生成

- [ ] 3.3.1 建立 `app/backend/renderers/pdf_generator.py`
  - [ ] 實作 `PDFGenerator` 類別
  - [ ] 支援從 `TranslatableDocument` 生成 PDF
  - [ ] 支援 `overlay` 模式 - 覆蓋原文
  - [ ] 支援 `side_by_side` 模式 - 並列對照
- [ ] 3.3.2 整合到處理流程
  - [ ] 修改 `pdf_processor.py` 支援 PDF 輸出
  - [ ] 新增 `output_format` 參數 (docx | pdf)
  - [ ] 新增 `layout_mode` 參數並檢查相容性

### 3.4 測試

- [ ] 3.4.1 建立 `tests/test_text_region_renderer.py`
  - [ ] 測試座標計算
  - [ ] 測試字型縮放
  - [ ] 測試旋轉處理
- [ ] 3.4.2 建立 `tests/test_coordinate_renderer.py`
- [ ] 3.4.3 建立 `tests/test_pdf_generator.py`
- [ ] 3.4.4 視覺驗證測試
  - [ ] 準備測試 PDF 檔案
  - [ ] 驗證輸出版面正確性

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
- [ ] PDF 文字提取包含 bbox 座標
- [ ] 多欄 PDF 閱讀順序正確
- [ ] 頁首/頁尾可被識別
- [ ] 表格區域可被偵測
- [ ] 現有翻譯功能無退化

### Phase 2 驗收
- [ ] DOCX/PPTX 使用新架構處理
- [ ] 輸出模式可配置
- [ ] 程式碼覆蓋率 > 80%

### Phase 3 驗收
- [ ] 可生成座標定位的 PDF
- [ ] 譯文長度超過時自動縮小字型
- [ ] 多語言字型正確顯示
- [ ] overlay/side_by_side 模式可用

### Phase 4 驗收 (可選)
- [ ] 可自動偵測 PDF 類型
- [ ] 掃描型 PDF 可通過 OCR 處理
- [ ] OCR 模組可獨立安裝/卸載
- [ ] OCR 觸發門檻可配置
