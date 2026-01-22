# Design: PDF 版面保留翻譯架構設計

## Context

Translate_Tool 目前使用 PyPDF2 進行 PDF 文字提取，僅能獲取純文字流，無法保留任何版面資訊。Tool_OCR 專案已實作完整的座標定位 PDF 生成能力，包括 `TextRegionRenderer`、`PDFGeneratorService` 等元件，可作為整合參考。

## Goals / Non-Goals

### Goals
- 提升 PDF 文字提取品質，包含座標、字型、閱讀順序
- 支援區分不同文件元素（標題、正文、頁首、頁尾、表格）
- 提供版面保留的輸出選項
- 維持向後相容，現有功能不受影響
- 支援漸進式升級，各 Phase 可獨立部署

### Non-Goals
- 不實作完整的 PDF 編輯功能
- 不支援 PDF 表單填寫
- 不處理 PDF 數位簽章
- 不強制要求 GPU 環境

## Decisions

### Decision 1: 採用 PyMuPDF 作為主要 PDF 解析庫

**Alternatives considered:**
| 選項 | 優點 | 缺點 |
|------|------|------|
| 保持 PyPDF2 | 無需變更 | 無 bbox 支援 |
| pdfplumber | 表格提取強 | 效能較差 |
| **PyMuPDF** | bbox + 表格 + 效能 | 需新增依賴 |
| pdf2image + OCR | 通用性最高 | 依賴重、慢 |

**決定理由：** PyMuPDF 提供完整的 bbox 座標、內建表格偵測、效能優異，且依賴輕量（單人非商業使用可接受）。

### Decision 1.5: 統一內部座標系統

**決定內容：**
- 內部座標統一為「左上為原點、x 向右、y 向下、單位為 points」。
- 解析層輸出的 bbox 一律轉為此座標系。
- PDF 輸出時，再轉回 PDF 座標系（左下為原點）。

**決定理由：** 內部一致的座標系可簡化排序、頁首/頁尾判定與渲染邏輯，避免不同庫的座標差異導致錯誤。

### Decision 2: 建立 TranslatableDocument 中間層

**架構圖：**
```
                    ┌─────────────────────────────────────┐
                    │           輸入層 (Parsers)           │
                    ├─────────┬─────────┬─────────┬───────┤
                    │  PDF    │  DOCX   │  PPTX   │ XLSX  │
                    │ Parser  │ Parser  │ Parser  │ Parser│
                    └────┬────┴────┬────┴────┬────┴───┬───┘
                         │         │         │        │
                         ▼         ▼         ▼        ▼
                    ┌─────────────────────────────────────┐
                    │      TranslatableDocument           │
                    │  ┌─────────────────────────────┐   │
                    │  │ elements: List[Element]     │   │
                    │  │   - element_id              │   │
                    │  │   - content                 │   │
                    │  │   - element_type            │   │
                    │  │   - bbox (optional)         │   │
                    │  │   - should_translate        │   │
                    │  │   - metadata                │   │
                    │  └─────────────────────────────┘   │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │           翻譯層 (Translator)       │
                    │  - 去重                             │
                    │  - 批次翻譯                         │
                    │  - 快取查詢                         │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │           輸出層 (Renderers)        │
                    ├─────────┬─────────┬─────────┬───────┤
                    │ Inline  │  Side   │ Overlay │ Dual  │
                    │ Insert  │  by     │ Replace │ Layer │
                    │ Renderer│  Side   │ Renderer│ PDF   │
                    └─────────┴─────────┴─────────┴───────┘
```

**決定理由：** 統一中間層可解耦解析與輸出，便於新增輸出格式，提升可測試性。

### Decision 3: 譯文呈現方式設計

提供四種輸出模式：

| 模式 | 實作優先級 | 說明 |
|------|------------|------|
| `inline` | Phase 1 | 段落式插入（現有方式，限 DOCX） |
| `side_by_side` | Phase 3 | 側邊對照（PDF） |
| `overlay` | Phase 3 | 覆蓋式替換（PDF） |
| `dual_layer` | Phase 4+ | 雙層 PDF |

**相容性規則：**
- `output_format=docx` 僅支援 `inline`
- `output_format=pdf` 需使用 `overlay` 或 `side_by_side`，否則回報錯誤

**不相容組合處理方式：**

當使用者指定 `output_format=pdf` + `layout_mode=inline` 時，系統採用「明確報錯」而非「自動 fallback」策略。

| 方案 | 優點 | 缺點 |
|------|------|------|
| 自動 fallback 到 overlay | 使用者體驗順暢 | 輸出結果與預期不符，可能造成混淆 |
| **明確報錯** | 行為透明可預期 | 需要使用者修正參數 |

**決定理由：**
1. **明確性原則**：使用者指定的參數應被尊重，而非被系統靜默修改
2. **避免意外輸出**：自動 fallback 可能導致大量文件被意外轉換為非預期格式
3. **錯誤訊息應具指導性**：錯誤訊息將明確說明支援的組合，引導使用者正確配置

```python
# 範例錯誤處理
class UnsupportedOutputModeError(ValueError):
    """當 output_format 與 layout_mode 組合不支援時拋出"""
    pass

def validate_output_mode(output_format: str, layout_mode: str) -> None:
    if output_format == "pdf" and layout_mode == "inline":
        raise UnsupportedOutputModeError(
            "output_format='pdf' requires layout_mode='overlay' or 'side_by_side'. "
            "Use output_format='docx' for inline mode."
        )
```

### Decision 4: 字型縮放策略

當譯文長度超過原文 bbox 寬度時：

```python
def fit_text_to_bbox(text: str, bbox_width: float,
                     initial_font_size: float) -> float:
    """動態縮放字型以適應 bbox 寬度"""
    MIN_FONT_SIZE = 6.0
    SHRINK_FACTOR = 0.9

    font_size = initial_font_size
    while calculate_text_width(text, font_size) > bbox_width:
        font_size *= SHRINK_FACTOR
        if font_size < MIN_FONT_SIZE:
            # 到達最小字型，記錄警告
            logger.warning(f"Text too long for bbox, using min font size")
            return MIN_FONT_SIZE
    return font_size
```

### Decision 5: OCR 模組設計為可選依賴

```python
# app/backend/processors/pdf_processor.py

# OCR 為可選功能
try:
    from app.backend.ocr import OCRProcessor
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    OCRProcessor = None

def translate_pdf(in_path, out_path, ..., use_ocr: bool = False):
    if use_ocr and not OCR_AVAILABLE:
        raise ImportError(
            "OCR module not installed. "
            "Install with: pip install paddleocr paddlex[ocr]"
        )
```

## Target Structure

```
app/backend/
├── models/
│   └── translatable_document.py    # NEW: 統一中間層模型
├── parsers/                         # NEW: 解析器模組
│   ├── __init__.py
│   ├── base.py                      # 解析器抽象介面
│   ├── pdf_parser.py                # PyMuPDF PDF 解析
│   ├── docx_parser.py               # DOCX 解析 (重構)
│   └── pptx_parser.py               # PPTX 解析 (重構)
├── renderers/                       # NEW: 輸出渲染器模組
│   ├── __init__.py
│   ├── base.py                      # 渲染器抽象介面
│   ├── inline_renderer.py           # 段落插入渲染
│   ├── coordinate_renderer.py       # 座標定位渲染
│   └── text_region_renderer.py      # 從 Tool_OCR 移植
├── processors/
│   ├── pdf_processor.py             # MODIFIED: 整合新架構
│   ├── docx_processor.py            # MODIFIED: 使用中間層
│   └── orchestrator.py              # MODIFIED: 支援輸出模式
├── ocr/                             # NEW: 可選 OCR 模組
│   ├── __init__.py
│   ├── document_detector.py         # 文件類型偵測
│   └── ocr_processor.py             # PaddleOCR 整合
├── utils/
│   ├── bbox_utils.py                # NEW: bbox 工具函式
│   └── font_utils.py                # NEW: 字型處理工具
└── fonts/                           # NEW: 字型檔案目錄
    ├── NotoSansSC-Regular.ttf
    ├── NotoSansKR-Regular.ttf
    └── NotoSansThai-Regular.ttf
```

## Data Models

### TranslatableElement

```python
@dataclass
class TranslatableElement:
    """可翻譯的文件元素"""
    element_id: str
    content: str
    element_type: ElementType  # text, title, header, footer, table_cell
    page_num: int
    bbox: Optional[BoundingBox] = None
    style: Optional[StyleInfo] = None
    should_translate: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### BoundingBox

```python
@dataclass
class BoundingBox:
    """邊界框座標"""
    x0: float  # 左
    y0: float  # 上
    x1: float  # 右
    y1: float  # 下

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0
```

### TranslatableDocument

```python
@dataclass
class TranslatableDocument:
    """可翻譯的文件"""
    source_path: str
    source_type: str  # pdf, docx, pptx, xlsx
    elements: List[TranslatableElement]
    pages: List[PageInfo]
    metadata: DocumentMetadata

    def get_translatable_elements(self) -> List[TranslatableElement]:
        """取得需要翻譯的元素"""
        return [e for e in self.elements if e.should_translate]

    def get_elements_in_reading_order(self) -> List[TranslatableElement]:
        """按閱讀順序排列的元素"""
        return sorted(self.elements, key=lambda e: (e.page_num, e.bbox.y0, e.bbox.x0))
```

## Configuration

```python
# app/backend/config.py

# PDF 解析設定
PDF_PARSER_ENGINE = "pymupdf"  # pymupdf | pypdf2 (fallback)

# 版面保留設定
LAYOUT_PRESERVATION_MODE = "inline"  # inline | side_by_side | overlay
HEADER_FOOTER_MARGIN_PT = 50  # 頁首/頁尾判定邊距 (points)
SKIP_HEADER_FOOTER = True  # 是否跳過頁首/頁尾翻譯

# 字型設定
DEFAULT_FONT_FAMILY = "NotoSansSC"
MIN_FONT_SIZE_PT = 6
MAX_FONT_SIZE_PT = 72
FONT_SIZE_SHRINK_FACTOR = 0.9

# OCR 設定 (可選)
OCR_ENABLED = False
OCR_DEFAULT_LANG = "ch"
OCR_USE_GPU = False
OCR_TEXT_MIN_CHARS_PER_PAGE = 20
```

## Risks / Trade-offs

| 風險 | 等級 | 緩解措施 |
|------|------|----------|
| 譯文超長導致文字重疊 | 中 | 字型縮放 + 最小字型閾值 + 截斷警告 |
| 多語言字型檔案大 | 低 | 按需下載，非必要依賴 |
| PyMuPDF 與 PyPDF2 行為差異 | 低 | 保留 PyPDF2 作為 fallback |
| OCR 依賴過重 | 中 | 設為完全可選模組 |
| 座標計算錯誤 | 低 | 複用 Tool_OCR 已驗證的演算法 |
| 效能下降 | 低 | bbox 提取比純文字略慢，但可接受 |

## Migration Plan

### Phase 1 遷移步驟
1. 新增 `PyMuPDF` 依賴
2. 建立 `models/translatable_document.py`
3. 建立 `parsers/pdf_parser.py`
4. 修改 `pdf_processor.py` 使用新解析器
5. 新增單元測試
6. 驗證與現有行為相容

### Phase 2 遷移步驟
1. 建立 `renderers/` 模組
2. 重構 `docx_processor.py` 使用中間層
3. 新增 `layout_mode` 與 `output_format` 配置
4. 更新 orchestrator 支援輸出模式

### Phase 3 遷移步驟
1. 從 Tool_OCR 移植 `TextRegionRenderer`
2. 新增 `reportlab` 依賴
3. 新增字型檔案
4. 實作 `coordinate_renderer.py`
5. 整合測試

### Phase 4 遷移步驟 (可選)
1. 新增 OCR 相關依賴 (可選安裝)
2. 從 Tool_OCR 移植 `DocumentTypeDetector`
3. 實作 `ocr_processor.py`
4. 新增 PDF 類型自動偵測

## Open Questions

1. **字型授權**：NotoSans 字型是否可直接包含在專案中？
   - **答案**：NotoSans 採用 OFL 授權，可自由使用和分發。

2. **是否需要支援 PDF/A 輸出格式？**
   - **暫定**：Phase 1-3 不支援，視需求在後續版本考慮。

3. **OCR 模組是否需要支援離線模型？**
   - **暫定**：PaddleOCR 模型在首次使用時自動下載，可考慮提供離線安裝腳本。
