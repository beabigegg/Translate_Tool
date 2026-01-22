# Reference Implementation: 核心程式碼範例

本文件提供各 Phase 的核心程式碼骨架，作為實作參考。

## Phase 1: 資料模型

### `app/backend/models/translatable_document.py`

```python
"""
Translatable Document Model

統一的可翻譯文件中間層格式，用於解耦解析與輸出。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ElementType(str, Enum):
    """文件元素類型"""
    TEXT = "text"
    TITLE = "title"
    HEADER = "header"
    FOOTER = "footer"
    TABLE = "table"
    TABLE_CELL = "table_cell"
    LIST_ITEM = "list_item"
    CAPTION = "caption"
    PAGE_NUMBER = "page_number"


@dataclass
class BoundingBox:
    """
    邊界框座標 (內部統一座標系)

    座標系定義：
    - 原點在左上角
    - x 向右增加
    - y 向下增加
    - 單位為 points
    """
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

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)

    def to_dict(self) -> Dict[str, float]:
        return {
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_tuple(cls, t: Tuple[float, float, float, float]) -> "BoundingBox":
        return cls(x0=t[0], y0=t[1], x1=t[2], y1=t[3])

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "BoundingBox":
        return cls(x0=d["x0"], y0=d["y0"], x1=d["x1"], y1=d["y1"])

    @classmethod
    def from_pdf_coords(
        cls, x0: float, y0: float, x1: float, y1: float, page_height: float
    ) -> "BoundingBox":
        """從 PDF 座標系 (左下原點) 轉換為內部座標系 (左上原點)"""
        return cls(
            x0=x0,
            y0=page_height - y1,  # PDF y1 (上) -> 內部 y0 (上)
            x1=x1,
            y1=page_height - y0,  # PDF y0 (下) -> 內部 y1 (下)
        )

    def to_pdf_coords(self, page_height: float) -> Tuple[float, float, float, float]:
        """轉換為 PDF 座標系 (左下原點)"""
        return (
            self.x0,
            page_height - self.y1,  # 內部 y1 (下) -> PDF y0 (下)
            self.x1,
            page_height - self.y0,  # 內部 y0 (上) -> PDF y1 (上)
        )


@dataclass
class StyleInfo:
    """文字樣式資訊"""
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    is_bold: bool = False
    is_italic: bool = False
    color: Optional[int] = None  # RGB as integer


@dataclass
class TranslatableElement:
    """可翻譯的文件元素"""
    element_id: str
    content: str
    element_type: ElementType
    page_num: int
    bbox: Optional[BoundingBox] = None
    style: Optional[StyleInfo] = None
    should_translate: bool = True
    translated_content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def mark_translated(self, translation: str) -> None:
        """標記元素已翻譯"""
        self.translated_content = translation


@dataclass
class PageInfo:
    """頁面資訊"""
    page_num: int
    width: float
    height: float
    rotation: int = 0


@dataclass
class TranslatableDocument:
    """可翻譯的文件"""
    source_path: str
    source_type: str  # pdf, docx, pptx, xlsx
    elements: List[TranslatableElement]
    pages: List[PageInfo]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_translatable_elements(self) -> List[TranslatableElement]:
        """取得需要翻譯的元素"""
        return [e for e in self.elements if e.should_translate]

    def get_unique_texts(self) -> List[str]:
        """取得去重後的待翻譯文字"""
        seen = set()
        result = []
        for e in self.get_translatable_elements():
            if e.content not in seen:
                seen.add(e.content)
                result.append(e.content)
        return result

    def get_elements_in_reading_order(self) -> List[TranslatableElement]:
        """按閱讀順序排列的元素 (上到下，左到右)"""
        def sort_key(e: TranslatableElement) -> Tuple[int, float, float]:
            if e.bbox:
                # 內部座標系：y0 是上邊界，直接排序
                return (e.page_num, e.bbox.y0, e.bbox.x0)
            return (e.page_num, 0, 0)
        return sorted(self.elements, key=sort_key)

    def apply_translations(self, translation_map: Dict[str, str]) -> None:
        """套用翻譯結果"""
        for element in self.elements:
            if element.content in translation_map:
                element.mark_translated(translation_map[element.content])

    def to_dict(self) -> Dict[str, Any]:
        """序列化為字典"""
        return {
            "source_path": self.source_path,
            "source_type": self.source_type,
            "elements": [
                {
                    "element_id": e.element_id,
                    "content": e.content,
                    "element_type": e.element_type.value,
                    "page_num": e.page_num,
                    "bbox": e.bbox.to_dict() if e.bbox else None,
                    "should_translate": e.should_translate,
                    "translated_content": e.translated_content,
                }
                for e in self.elements
            ],
            "pages": [
                {
                    "page_num": p.page_num,
                    "width": p.width,
                    "height": p.height,
                    "rotation": p.rotation,
                }
                for p in self.pages
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TranslatableDocument":
        """從字典反序列化"""
        elements = [
            TranslatableElement(
                element_id=e["element_id"],
                content=e["content"],
                element_type=ElementType(e["element_type"]),
                page_num=e["page_num"],
                bbox=BoundingBox.from_dict(e["bbox"]) if e.get("bbox") else None,
                should_translate=e.get("should_translate", True),
                translated_content=e.get("translated_content"),
            )
            for e in d.get("elements", [])
        ]
        pages = [
            PageInfo(
                page_num=p["page_num"],
                width=p["width"],
                height=p["height"],
                rotation=p.get("rotation", 0),
            )
            for p in d.get("pages", [])
        ]
        return cls(
            source_path=d["source_path"],
            source_type=d["source_type"],
            elements=elements,
            pages=pages,
            metadata=d.get("metadata", {}),
        )
```

## Phase 1: PDF 解析器

### `app/backend/parsers/pdf_parser.py`

```python
"""
PDF Parser using PyMuPDF

提取 PDF 文字與座標資訊。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

from app.backend.models.translatable_document import (
    BoundingBox,
    ElementType,
    PageInfo,
    StyleInfo,
    TranslatableDocument,
    TranslatableElement,
)

logger = logging.getLogger(__name__)


class PyMuPDFParser:
    """使用 PyMuPDF 解析 PDF 文件"""

    DEFAULT_HEADER_MARGIN = 50  # points
    DEFAULT_FOOTER_MARGIN = 50  # points

    def __init__(
        self,
        skip_header_footer: bool = True,
        header_margin: float = DEFAULT_HEADER_MARGIN,
        footer_margin: float = DEFAULT_FOOTER_MARGIN,
    ):
        self.skip_header_footer = skip_header_footer
        self.header_margin = header_margin
        self.footer_margin = footer_margin

    def parse(self, file_path: str) -> TranslatableDocument:
        """
        解析 PDF 檔案並提取帶座標的文字。

        Args:
            file_path: PDF 檔案路徑

        Returns:
            TranslatableDocument 實例
        """
        doc = fitz.open(file_path)
        elements: List[TranslatableElement] = []
        pages: List[PageInfo] = []
        element_counter = 0

        try:
            for page_num, page in enumerate(doc):
                # 記錄頁面資訊
                pages.append(PageInfo(
                    page_num=page_num,
                    width=page.rect.width,
                    height=page.rect.height,
                    rotation=page.rotation,
                ))

                # 偵測表格區域 (用於排除重複文字)
                table_bboxes = self._detect_tables(page)

                # 提取文字區塊
                text_dict = page.get_text("dict", sort=True)
                page_height = page.rect.height

                for block in text_dict.get("blocks", []):
                    if block.get("type") != 0:  # 非文字區塊
                        continue

                    # 將 PDF 座標轉換為內部座標系 (左上原點)
                    pdf_bbox = block["bbox"]
                    bbox = BoundingBox.from_pdf_coords(
                        pdf_bbox[0], pdf_bbox[1], pdf_bbox[2], pdf_bbox[3],
                        page_height
                    )
                    text = self._extract_block_text(block)

                    if not text.strip():
                        continue

                    # 檢查是否在表格區域內
                    if self._is_inside_tables(bbox, table_bboxes):
                        element_type = ElementType.TABLE_CELL
                    else:
                        element_type = self._classify_element_type(
                            bbox, page.rect.height, block
                        )

                    # 判斷是否需要翻譯
                    should_translate = True
                    if self.skip_header_footer and element_type in (
                        ElementType.HEADER,
                        ElementType.FOOTER,
                        ElementType.PAGE_NUMBER,
                    ):
                        should_translate = False

                    # 提取樣式資訊
                    style = self._extract_style(block)

                    elements.append(TranslatableElement(
                        element_id=f"elem_{page_num}_{element_counter}",
                        content=text,
                        element_type=element_type,
                        page_num=page_num,
                        bbox=bbox,
                        style=style,
                        should_translate=should_translate,
                    ))
                    element_counter += 1

        finally:
            doc.close()

        return TranslatableDocument(
            source_path=file_path,
            source_type="pdf",
            elements=elements,
            pages=pages,
            metadata={
                "parser": "pymupdf",
                "total_pages": len(pages),
                "total_elements": len(elements),
            },
        )

    def _extract_block_text(self, block: dict) -> str:
        """從區塊中提取文字"""
        lines = []
        for line in block.get("lines", []):
            spans_text = []
            for span in line.get("spans", []):
                spans_text.append(span.get("text", ""))
            lines.append("".join(spans_text))
        return "\n".join(lines)

    def _extract_style(self, block: dict) -> Optional[StyleInfo]:
        """從區塊中提取樣式資訊"""
        # 取第一個 span 的樣式作為代表
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                flags = span.get("flags", 0)
                return StyleInfo(
                    font_name=span.get("font"),
                    font_size=span.get("size"),
                    is_bold=bool(flags & 2**4),  # superscript as bold approximation
                    is_italic=bool(flags & 2**1),
                    color=span.get("color"),
                )
        return None

    def _classify_element_type(
        self,
        bbox: BoundingBox,
        page_height: float,
        block: dict,
    ) -> ElementType:
        """根據位置和樣式分類元素類型"""
        # 內部座標系：y0 是上邊界，y1 是下邊界
        # 頁首判定：y0 小於上邊距
        if bbox.y0 < self.header_margin:
            return ElementType.HEADER

        # 頁尾判定：y1 大於 (頁高 - 下邊距)
        if bbox.y1 > (page_height - self.footer_margin):
            # 檢查是否為頁碼
            text = self._extract_block_text(block).strip()
            if text.isdigit() or self._is_page_number_pattern(text):
                return ElementType.PAGE_NUMBER
            return ElementType.FOOTER

        # 標題判定 (基於字型大小)
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("size", 0) > 14:  # 大字型視為標題
                    return ElementType.TITLE

        return ElementType.TEXT

    def _is_page_number_pattern(self, text: str) -> bool:
        """判斷是否為頁碼格式"""
        import re
        patterns = [
            r"^\d+$",  # 純數字
            r"^Page\s+\d+$",  # Page N
            r"^第\s*\d+\s*頁$",  # 第 N 頁
            r"^\d+\s*/\s*\d+$",  # N / M
        ]
        return any(re.match(p, text, re.IGNORECASE) for p in patterns)

    def _detect_tables(self, page: fitz.Page) -> List[BoundingBox]:
        """偵測頁面中的表格區域"""
        table_bboxes = []
        try:
            tables = page.find_tables()
            for table in tables:
                table_bboxes.append(BoundingBox.from_tuple(table.bbox))
        except Exception as e:
            logger.warning(f"Table detection failed: {e}")
        return table_bboxes

    def _is_inside_tables(
        self,
        bbox: BoundingBox,
        table_bboxes: List[BoundingBox],
    ) -> bool:
        """判斷區塊是否在表格內"""
        for table_bbox in table_bboxes:
            # 使用 50% 重疊閾值
            overlap = self._calculate_overlap_ratio(bbox, table_bbox)
            if overlap > 0.5:
                return True
        return False

    def _calculate_overlap_ratio(
        self,
        inner: BoundingBox,
        outer: BoundingBox,
    ) -> float:
        """計算重疊比例"""
        # 計算交集
        x0 = max(inner.x0, outer.x0)
        y0 = max(inner.y0, outer.y0)
        x1 = min(inner.x1, outer.x1)
        y1 = min(inner.y1, outer.y1)

        if x0 >= x1 or y0 >= y1:
            return 0.0

        intersection = (x1 - x0) * (y1 - y0)
        inner_area = inner.width * inner.height

        if inner_area == 0:
            return 0.0

        return intersection / inner_area
```

## Phase 1: 整合到現有處理器

### `app/backend/processors/pdf_processor.py` (修改版)

```python
"""PDF translation processor with enhanced extraction."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, List, Optional

import docx

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import (
    PDF_PARSER_ENGINE,
    SKIP_HEADER_FOOTER,
    HEADER_FOOTER_MARGIN_PT,
)
from app.backend.processors.com_helpers import is_win32com_available, word_convert
from app.backend.processors.docx_processor import translate_docx
from app.backend.utils.translation_helpers import translate_block_sentencewise

# 嘗試載入 PyMuPDF 解析器
try:
    from app.backend.parsers.pdf_parser import PyMuPDFParser
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    PyMuPDFParser = None

# Fallback: PyPDF2
from PyPDF2 import PdfReader


class UnsupportedOutputModeError(ValueError):
    """不支援的輸出模式組合"""
    pass


def validate_output_mode(output_format: str, layout_mode: str) -> None:
    """
    驗證 output_format 與 layout_mode 的相容性。

    相容性規則：
    - output_format=docx 僅支援 layout_mode=inline
    - output_format=pdf 需使用 layout_mode=overlay 或 side_by_side

    Raises:
        UnsupportedOutputModeError: 當組合不支援時
    """
    if output_format == "docx" and layout_mode != "inline":
        raise UnsupportedOutputModeError(
            f"output_format='docx' only supports layout_mode='inline', "
            f"got layout_mode='{layout_mode}'"
        )
    if output_format == "pdf" and layout_mode == "inline":
        raise UnsupportedOutputModeError(
            f"output_format='pdf' requires layout_mode='overlay' or 'side_by_side', "
            f"got layout_mode='inline'. "
            f"Use output_format='docx' for inline mode."
        )


def translate_pdf(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
    # 新增參數
    use_pymupdf: bool = True,
    skip_header_footer: bool = SKIP_HEADER_FOOTER,
    output_format: str = "docx",
    layout_mode: str = "inline",
) -> bool:
    """
    翻譯 PDF 文件。

    Args:
        in_path: 輸入 PDF 路徑
        out_path: 輸出檔案路徑
        targets: 目標語言列表
        src_lang: 來源語言
        cache: 翻譯快取
        client: Ollama 客戶端
        stop_flag: 停止旗標
        log: 日誌函式
        use_pymupdf: 是否使用 PyMuPDF (預設 True)
        skip_header_footer: 是否跳過頁首頁尾
        output_format: 輸出格式 (docx 或 pdf)
        layout_mode: 版面模式 (inline, overlay, side_by_side)

    Returns:
        是否被中斷

    Raises:
        UnsupportedOutputModeError: 當 output_format 與 layout_mode 組合不支援時
    """
    # 驗證輸出模式相容性
    validate_output_mode(output_format, layout_mode)

    # 優先使用 Word COM 轉換 (僅適用於 docx 輸出)
    temp_docx = str(Path(out_path).with_suffix("")) + "__from_pdf.docx"
    if is_win32com_available():
        try:
            word_convert(in_path, temp_docx, 16)
            stopped = translate_docx(
                temp_docx,
                out_path,
                targets,
                src_lang,
                cache,
                client,
                include_headers_shapes_via_com=False,
                stop_flag=stop_flag,
                log=log,
            )
            try:
                os.remove(temp_docx)
            except OSError:
                pass
            return stopped
        except (OSError, RuntimeError) as exc:
            log(f"[PDF] Word import failed, fallback to text extract: {exc}")

    # 使用增強的 PyMuPDF 解析器
    if use_pymupdf and PYMUPDF_AVAILABLE:
        return _translate_pdf_with_pymupdf(
            in_path, out_path, targets, src_lang,
            cache, client, stop_flag, log,
            skip_header_footer, output_format,
        )

    # Fallback: 原有的 PyPDF2 處理
    return _translate_pdf_with_pypdf2(
        in_path, out_path, targets, src_lang,
        cache, client, stop_flag, log,
    )


def _translate_pdf_with_pymupdf(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    stop_flag: Optional[threading.Event],
    log: Callable[[str], None],
    skip_header_footer: bool,
    output_format: str,
) -> bool:
    """使用 PyMuPDF 解析並翻譯 PDF"""
    log("[PDF] Using PyMuPDF enhanced parser")

    # 解析 PDF
    parser = PyMuPDFParser(
        skip_header_footer=skip_header_footer,
        header_margin=HEADER_FOOTER_MARGIN_PT,
        footer_margin=HEADER_FOOTER_MARGIN_PT,
    )
    document = parser.parse(in_path)

    log(f"[PDF] Extracted {len(document.elements)} elements "
        f"({len(document.get_translatable_elements())} translatable)")

    # 取得待翻譯的唯一文字
    unique_texts = document.get_unique_texts()
    log(f"[PDF] {len(unique_texts)} unique texts to translate")

    # 翻譯
    translation_map = {}
    stopped = False

    for i, text in enumerate(unique_texts):
        if stop_flag and stop_flag.is_set():
            log(f"[STOP] PDF stopped at {i}/{len(unique_texts)} texts")
            stopped = True
            break

        for tgt in targets:
            if stop_flag and stop_flag.is_set():
                stopped = True
                break

            ok, tr = translate_block_sentencewise(text, tgt, src_lang, cache, client)
            if not ok:
                tr = f"[Translation failed|{tgt}] {text}"

            key = (tgt, text)
            translation_map[key] = tr

        if stopped:
            break

    # 生成輸出 (目前仍使用 DOCX 格式)
    doc = docx.Document()

    # 按閱讀順序處理元素
    for element in document.get_elements_in_reading_order():
        # 頁面分隔標記
        if element.page_num > 0 and element.element_id.endswith("_0"):
            doc.add_heading(f"-- Page {element.page_num + 1} --", level=1)

        # 加入原文
        if element.content.strip():
            p = doc.add_paragraph()
            # 根據元素類型設定樣式
            if element.element_type == ElementType.TITLE:
                p.style = "Heading 2"
            p.add_run(element.content)

            # 加入譯文
            if element.should_translate:
                for tgt in targets:
                    key = (tgt, element.content)
                    if key in translation_map:
                        tp = doc.add_paragraph()
                        run = tp.add_run(translation_map[key])
                        run.italic = True

    doc.save(out_path)
    log(f"[PDF] output: {os.path.basename(out_path)}")

    return stopped


def _translate_pdf_with_pypdf2(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    stop_flag: Optional[threading.Event],
    log: Callable[[str], None],
) -> bool:
    """原有的 PyPDF2 處理邏輯 (fallback)"""
    doc = docx.Document()
    stopped = False

    try:
        reader = PdfReader(in_path)
        total_pages = len(reader.pages)

        for i, page in enumerate(reader.pages, start=1):
            if stop_flag and stop_flag.is_set():
                stopped = True
                break

            doc.add_heading(f"-- Page {i} --", level=1)
            text = page.extract_text() or ""

            if text.strip():
                doc.add_paragraph(text)
                for tgt in targets:
                    if stop_flag and stop_flag.is_set():
                        stopped = True
                        break
                    ok, tr = translate_block_sentencewise(
                        text, tgt, src_lang, cache, client
                    )
                    if not ok:
                        tr = f"[Translation failed|{tgt}] {text}"
                    doc.add_paragraph(tr)

            if stopped:
                break

    except Exception as exc:
        doc.add_paragraph(f"[PDF extract error] {exc}")

    doc.save(out_path)
    log(f"[PDF] output: {os.path.basename(out_path)}")

    return stopped
```

## Phase 3: 座標渲染器 (從 Tool_OCR 簡化移植)

### `app/backend/renderers/text_region_renderer.py`

```python
"""
Text Region Renderer

根據 bbox 座標將文字渲染到 PDF。
簡化自 Tool_OCR 專案。
"""

from __future__ import annotations

import math
import logging
from typing import Dict, List, Optional, Tuple

from reportlab.pdfgen import canvas
from reportlab.lib.colors import black

from app.backend.models.translatable_document import BoundingBox

logger = logging.getLogger(__name__)


class TextRegionRenderer:
    """座標定位文字渲染器"""

    MIN_FONT_SIZE = 6.0
    MAX_FONT_SIZE = 72.0
    FONT_SIZE_FACTOR = 0.75
    SHRINK_FACTOR = 0.9

    def __init__(
        self,
        font_name: str = "Helvetica",
        debug: bool = False,
    ):
        self.font_name = font_name
        self.debug = debug

    def estimate_font_size(
        self,
        bbox: BoundingBox,
        scale_factor: float = 1.0,
    ) -> float:
        """根據 bbox 高度估算字型大小"""
        font_size = bbox.height * scale_factor * self.FONT_SIZE_FACTOR
        return max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, font_size))

    def fit_text_to_bbox(
        self,
        pdf_canvas: canvas.Canvas,
        text: str,
        bbox: BoundingBox,
        initial_font_size: float,
    ) -> float:
        """動態縮放字型以適應 bbox 寬度"""
        font_size = initial_font_size

        while font_size > self.MIN_FONT_SIZE:
            text_width = pdf_canvas.stringWidth(text, self.font_name, font_size)
            if text_width <= bbox.width:
                return font_size
            font_size *= self.SHRINK_FACTOR

        if self.debug:
            logger.warning(f"Text too long for bbox: '{text[:20]}...'")

        return self.MIN_FONT_SIZE

    def render_text_at_position(
        self,
        pdf_canvas: canvas.Canvas,
        text: str,
        bbox: BoundingBox,
        page_height: float,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ) -> bool:
        """
        在指定座標渲染文字。

        Args:
            pdf_canvas: ReportLab canvas
            text: 要渲染的文字
            bbox: 目標位置 (內部座標系：左上原點)
            page_height: 頁面高度 (用於座標轉換)
            scale_x: X 軸縮放因子
            scale_y: Y 軸縮放因子

        Returns:
            是否成功渲染
        """
        if not text.strip():
            return False

        try:
            # 計算字型大小
            initial_size = self.estimate_font_size(bbox, scale_y)
            font_size = self.fit_text_to_bbox(
                pdf_canvas, text, bbox, initial_size
            )

            # 內部座標系 (左上原點) -> PDF 座標系 (左下原點)
            pdf_coords = bbox.to_pdf_coords(page_height)
            pdf_x = pdf_coords[0] * scale_x
            # 文字基線在左下，使用 PDF y0 (下邊界)
            pdf_y = pdf_coords[1] * scale_y

            # 儲存狀態
            pdf_canvas.saveState()

            # 設定字型
            try:
                pdf_canvas.setFont(self.font_name, font_size)
            except KeyError:
                pdf_canvas.setFont("Helvetica", font_size)

            pdf_canvas.setFillColor(black)

            # 繪製文字
            pdf_canvas.drawString(pdf_x, pdf_y, text)

            # 恢復狀態
            pdf_canvas.restoreState()

            if self.debug:
                logger.debug(
                    f"Rendered '{text[:20]}...' at ({pdf_x:.1f}, {pdf_y:.1f}), "
                    f"size={font_size:.1f}pt"
                )

            return True

        except Exception as e:
            logger.warning(f"Failed to render text: {e}")
            return False
```

## 配置更新

### `app/backend/config.py` (新增配置)

```python
# ===== PDF 解析設定 =====
PDF_PARSER_ENGINE = "pymupdf"  # pymupdf | pypdf2
SKIP_HEADER_FOOTER = True
HEADER_FOOTER_MARGIN_PT = 50

# ===== 版面保留設定 =====
LAYOUT_PRESERVATION_MODE = "inline"  # inline | overlay | side_by_side
OUTPUT_FORMAT = "docx"  # docx | pdf

# ===== 字型設定 =====
DEFAULT_FONT_FAMILY = "NotoSansSC"
MIN_FONT_SIZE_PT = 6
MAX_FONT_SIZE_PT = 72
FONT_SIZE_SHRINK_FACTOR = 0.9

# ===== OCR 設定 (可選) =====
OCR_ENABLED = False
OCR_DEFAULT_LANG = "ch"
OCR_USE_GPU = False
OCR_TEXT_MIN_CHARS_PER_PAGE = 20  # 平均每頁少於此字數時建議 OCR
```

## 使用範例

### 基本使用

```python
from app.backend.parsers.pdf_parser import PyMuPDFParser

# 解析 PDF
parser = PyMuPDFParser(skip_header_footer=True)
document = parser.parse("input.pdf")

# 檢視提取結果
for element in document.get_elements_in_reading_order():
    print(f"[{element.element_type.value}] {element.content[:50]}...")
    if element.bbox:
        print(f"  Bbox: {element.bbox.to_tuple()}")
    print(f"  Translate: {element.should_translate}")
```

### 完整翻譯流程

```python
from app.backend.processors.pdf_processor import translate_pdf

# 翻譯 PDF
stopped = translate_pdf(
    in_path="input.pdf",
    out_path="output_translated.docx",
    targets=["繁體中文", "English"],
    src_lang="Auto",
    cache=cache,
    client=client,
    use_pymupdf=True,
    skip_header_footer=True,
)
```
