"""PDF parser using PyMuPDF (fitz).

This module provides PDF parsing with bounding box extraction,
reading order sorting, and header/footer detection.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from app.backend.models.translatable_document import (
    BoundingBox,
    DocumentMetadata,
    ElementType,
    PageInfo,
    StyleInfo,
    TranslatableDocument,
    TranslatableElement,
)
from app.backend.parsers.base import BaseParser
from app.backend.utils.bbox_utils import is_header_footer_region, normalize_bbox

logger = logging.getLogger(__name__)


class PyMuPDFParser(BaseParser):
    """PDF parser using PyMuPDF library.

    Features:
    - Text extraction with bounding box coordinates
    - Reading order sorting
    - Header/footer detection and filtering
    - Table region detection
    - Style information extraction
    """

    def __init__(
        self,
        skip_header_footer: bool = False,
        header_footer_margin_pt: float = 50.0,
        min_text_length: int = 1,
    ):
        """Initialize the parser.

        Args:
            skip_header_footer: If True, mark header/footer elements as non-translatable.
            header_footer_margin_pt: Margin in points for header/footer detection.
            min_text_length: Minimum text length to include (filters noise).
        """
        if fitz is None:
            raise ImportError(
                "PyMuPDF is not installed. Install with: pip install pymupdf"
            )

        self.skip_header_footer = skip_header_footer
        self.header_footer_margin_pt = header_footer_margin_pt
        self.min_text_length = min_text_length

    @property
    def supported_extensions(self) -> list[str]:
        """Supported file extensions."""
        return [".pdf"]

    def parse(self, file_path: str) -> TranslatableDocument:
        """Parse a PDF file.

        Args:
            file_path: Path to the PDF file.

        Returns:
            TranslatableDocument with extracted elements.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file is not a PDF.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {file_path}")

        doc = fitz.open(file_path)
        try:
            elements: List[TranslatableElement] = []
            pages: List[PageInfo] = []
            total_chars = 0

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_info = PageInfo(
                    page_num=page_num + 1,
                    width=page.rect.width,
                    height=page.rect.height,
                    rotation=page.rotation,
                )
                pages.append(page_info)

                # Extract text blocks with bbox
                page_elements = self._extract_page_elements(
                    page, page_num + 1, page_info.height
                )
                elements.extend(page_elements)

                # Count chars for text layer detection
                total_chars += sum(len(e.content) for e in page_elements)

            # Detect tables and update element types
            self._detect_and_mark_tables(doc, elements)

            # Sort by reading order
            elements = self._sort_by_reading_order(elements)

            # Build metadata
            metadata = self._extract_metadata(doc, len(pages), total_chars)

            return TranslatableDocument(
                source_path=file_path,
                source_type="pdf",
                elements=elements,
                pages=pages,
                metadata=metadata,
            )
        finally:
            doc.close()

    def _extract_page_elements(
        self,
        page: Any,  # fitz.Page
        page_num: int,
        page_height: float,
    ) -> List[TranslatableElement]:
        """Extract text elements from a page using line-level granularity.

        Uses get_text("dict") for precise line-level bboxes, which prevents
        white rectangles from covering table borders and other content.

        Args:
            page: PyMuPDF page object.
            page_num: 1-based page number.
            page_height: Page height in points.

        Returns:
            List of TranslatableElement objects.
        """
        elements: List[TranslatableElement] = []

        # Use dict mode for line-level granularity
        # This gives us: blocks -> lines -> spans
        text_dict = page.get_text("dict", sort=True)
        element_counter = 0

        for block_no, block in enumerate(text_dict.get("blocks", [])):
            # Skip image blocks (type=1)
            if block.get("type") != 0:
                continue

            # Process each line in the block for smaller, more precise bboxes
            for line_no, line in enumerate(block.get("lines", [])):
                line_bbox = line.get("bbox", [0, 0, 0, 0])

                # Collect text and style from all spans in the line
                line_text_parts = []
                line_style = None

                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if span_text:
                        line_text_parts.append(span_text)

                        # Capture style from first span
                        if line_style is None:
                            font_name = span.get("font", "")
                            font_size = span.get("size", 0)
                            flags = span.get("flags", 0)
                            line_style = StyleInfo(
                                font_name=font_name,
                                font_size=font_size,
                                is_bold=bool(flags & 2**4),
                                is_italic=bool(flags & 2**1),
                                color=self._color_to_hex(span.get("color", 0)),
                            )

                # Join spans to form line text
                line_text = "".join(line_text_parts).strip()
                if len(line_text) < self.min_text_length:
                    continue

                # Create bbox for the line
                bbox = BoundingBox(
                    x0=line_bbox[0],
                    y0=line_bbox[1],
                    x1=line_bbox[2],
                    y1=line_bbox[3],
                )

                # Determine element type and translatability
                element_type = ElementType.TEXT
                should_translate = True

                is_hf, region = is_header_footer_region(
                    bbox, page_height, self.header_footer_margin_pt
                )
                if is_hf:
                    element_type = (
                        ElementType.HEADER if region == "header" else ElementType.FOOTER
                    )
                    if self.skip_header_footer:
                        should_translate = False

                element = TranslatableElement(
                    element_id=f"p{page_num}_b{block_no}_l{line_no}_{uuid.uuid4().hex[:8]}",
                    content=line_text,
                    element_type=element_type,
                    page_num=page_num,
                    bbox=bbox,
                    style=line_style,
                    should_translate=should_translate,
                    metadata={"block_no": block_no, "line_no": line_no},
                )
                elements.append(element)
                element_counter += 1

        return elements

    def _extract_style_info(
        self,
        page: Any,  # fitz.Page
        bbox: BoundingBox,
    ) -> Optional[StyleInfo]:
        """Extract style information for text in a region.

        Args:
            page: PyMuPDF page object.
            bbox: Bounding box of the text region.

        Returns:
            StyleInfo if available, None otherwise.
        """
        try:
            # Get detailed text info (dict form)
            rect = fitz.Rect(bbox.x0, bbox.y0, bbox.x1, bbox.y1)
            text_dict = page.get_text("dict", clip=rect)

            if not text_dict.get("blocks"):
                return None

            # Get font info from first span
            for block in text_dict["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_name = span.get("font", "")
                        font_size = span.get("size", 0)
                        flags = span.get("flags", 0)

                        return StyleInfo(
                            font_name=font_name,
                            font_size=font_size,
                            is_bold=bool(flags & 2**4),  # bit 4: bold
                            is_italic=bool(flags & 2**1),  # bit 1: italic
                            color=self._color_to_hex(span.get("color", 0)),
                        )

        except Exception as e:
            logger.debug(f"Failed to extract style: {e}")

        return None

    def _color_to_hex(self, color: int) -> str:
        """Convert integer color to hex string.

        Args:
            color: RGB color as integer.

        Returns:
            Hex color string (e.g., "#FF0000").
        """
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        return f"#{r:02X}{g:02X}{b:02X}"

    def _detect_and_mark_tables(
        self,
        doc: Any,  # fitz.Document
        elements: List[TranslatableElement],
    ) -> None:
        """Detect tables and mark elements as table cells.

        Uses PyMuPDF's built-in table detection.

        Args:
            doc: PyMuPDF document object.
            elements: List of elements to update in-place.
        """
        # Build page -> elements lookup
        page_elements: Dict[int, List[TranslatableElement]] = {}
        for elem in elements:
            if elem.page_num not in page_elements:
                page_elements[elem.page_num] = []
            page_elements[elem.page_num].append(elem)

        for page_num in range(len(doc)):
            page = doc[page_num]
            try:
                # find_tables() returns a TableFinder object
                tables = page.find_tables()
                if not tables or not tables.tables:
                    continue

                for table in tables.tables:
                    table_bbox = BoundingBox(
                        x0=table.bbox[0],
                        y0=table.bbox[1],
                        x1=table.bbox[2],
                        y1=table.bbox[3],
                    )

                    # Mark elements inside table bbox as table cells
                    for elem in page_elements.get(page_num + 1, []):
                        if elem.bbox and self._is_inside(elem.bbox, table_bbox):
                            elem.element_type = ElementType.TABLE_CELL
                            elem.metadata["in_table"] = True

            except Exception as e:
                logger.debug(f"Table detection failed on page {page_num + 1}: {e}")

    def _is_inside(self, inner: BoundingBox, outer: BoundingBox) -> bool:
        """Check if inner bbox is inside outer bbox (with tolerance)."""
        tolerance = 5.0  # points
        return (
            inner.x0 >= outer.x0 - tolerance
            and inner.y0 >= outer.y0 - tolerance
            and inner.x1 <= outer.x1 + tolerance
            and inner.y1 <= outer.y1 + tolerance
        )

    def _sort_by_reading_order(
        self,
        elements: List[TranslatableElement],
    ) -> List[TranslatableElement]:
        """Sort elements by reading order.

        Args:
            elements: List of elements to sort.

        Returns:
            Sorted list of elements.
        """

        def sort_key(e: TranslatableElement) -> Tuple[int, float, float]:
            if e.bbox:
                # Round y to group elements on same line
                y_rounded = round(e.bbox.y0 / 10) * 10
                return (e.page_num, y_rounded, e.bbox.x0)
            return (e.page_num, 0, 0)

        return sorted(elements, key=sort_key)

    def _extract_metadata(
        self,
        doc: Any,  # fitz.Document
        page_count: int,
        total_chars: int,
    ) -> DocumentMetadata:
        """Extract document metadata.

        Args:
            doc: PyMuPDF document object.
            page_count: Number of pages.
            total_chars: Total characters extracted.

        Returns:
            DocumentMetadata object.
        """
        meta = doc.metadata or {}

        # Determine if document has meaningful text layer
        # Heuristic: less than 20 chars per page suggests scanned PDF
        has_text_layer = (total_chars / max(page_count, 1)) >= 20

        return DocumentMetadata(
            title=meta.get("title"),
            author=meta.get("author"),
            subject=meta.get("subject"),
            creator=meta.get("creator"),
            producer=meta.get("producer"),
            creation_date=meta.get("creationDate"),
            modification_date=meta.get("modDate"),
            page_count=page_count,
            has_text_layer=has_text_layer,
        )


def extract_text_with_bbox(file_path: str) -> TranslatableDocument:
    """Convenience function to extract text with bbox from a PDF.

    Args:
        file_path: Path to the PDF file.

    Returns:
        TranslatableDocument with extracted elements.
    """
    parser = PyMuPDFParser()
    return parser.parse(file_path)
