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
import os

from app.backend.config import LAYOUT_DETECTOR_MODEL_PATH, PDF_RENDER_DPI
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

            from app.backend.config import OCR_ENABLED as _OCR_ENABLED
            _NEAR_EMPTY_CHAR_THRESHOLD = 10  # chars per page below which OCR is attempted

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_info = PageInfo(
                    page_num=page_num + 1,
                    width=page.rect.width,
                    height=page.rect.height,
                    rotation=page.rotation,
                )
                pages.append(page_info)

                # Extract text blocks with bbox (paragraph-aggregated, AC-2)
                page_elements = self._extract_page_elements(
                    page, page_num + 1, page_info.height
                )

                # OCR routing for near-empty pages (AC-7, D-7)
                page_text = " ".join(e.content for e in page_elements).strip()
                if len(page_text) < _NEAR_EMPTY_CHAR_THRESHOLD:
                    # Re-check OCR_ENABLED at runtime (env var may differ per test)
                    _ocr_now = os.environ.get("OCR_ENABLED", "false").lower() in ("1", "true", "yes")
                    if _ocr_now:
                        from app.backend.parsers import ocr_backend
                        ocr_elements = ocr_backend.run_ocr(page)
                        if ocr_elements:
                            page_elements = ocr_elements
                    else:
                        logger.warning(
                            "Page %d: near-empty text (%d chars). "
                            "Set OCR_ENABLED=true to attempt OCR for scanned pages.",
                            page_num + 1,
                            len(page_text),
                        )

                elements.extend(page_elements)

                # Count chars for text layer detection
                total_chars += sum(len(e.content) for e in page_elements)

            # Detect tables and update element types
            self._detect_and_mark_tables(doc, elements)

            # Layout-detector path (native-PDF text-layer only):
            # Rasterise each page, run detector, write element_type + reading_order.
            # Falls back per-page to _sort_by_reading_order heuristic on any failure (D-2).
            # Read env var at runtime so tests can monkeypatch os.environ.
            _detector_enabled = os.environ.get(
                "LAYOUT_DETECTOR_ENABLED", "true"
            ).lower() in ("1", "true", "yes")
            if _detector_enabled:
                layout_viz = self._run_layout_detector(doc, elements)
            else:
                # Heuristic path (detector disabled or LAYOUT_DETECTOR_ENABLED=false)
                elements = self._sort_by_reading_order(elements)
                for idx, elem in enumerate(elements):
                    elem.reading_order = idx
                layout_viz = []

            # Table structure recognition (p3-table-structure, IP-5)
            # Run after layout detection so element_type is finalised.
            # Read env var at runtime so tests can monkeypatch os.environ.
            _table_rec_enabled = os.environ.get(
                "TABLE_RECOGNITION_ENABLED", "false"
            ).lower() in ("1", "true", "yes")
            if _table_rec_enabled:
                self._run_table_recognizer(doc, elements, file_path)

            # Build metadata
            metadata = self._extract_metadata(doc, len(pages), total_chars)

            return TranslatableDocument(
                source_path=file_path,
                source_type="pdf",
                elements=elements,
                pages=pages,
                metadata=metadata,
                layout_viz=layout_viz,
            )
        finally:
            doc.close()

    def _extract_page_elements(
        self,
        page: Any,  # fitz.Page
        page_num: int,
        page_height: float,
    ) -> List[TranslatableElement]:
        """Extract text elements from a page with paragraph aggregation (D-2, AC-2).

        Consecutive lines within the same fitz block are aggregated into one
        paragraph-level TranslatableElement.  The individual line bboxes are
        preserved in ``metadata["lines"]`` so the whitening step (D-1) can
        whiten each line independently.  This is the BabelDOC paradigm where
        the paragraph is the translation unit.

        Uses get_text("dict") for precise line-level bboxes, which prevents
        white rectangles from covering table borders and other content.

        Args:
            page: PyMuPDF page object.
            page_num: 1-based page number.
            page_height: Page height in points.

        Returns:
            List of TranslatableElement objects (one per block, not per line).
        """
        elements: List[TranslatableElement] = []

        # Use dict mode for block→line→span granularity
        text_dict = page.get_text("dict", sort=True)

        for block_no, block in enumerate(text_dict.get("blocks", [])):
            # Skip image blocks (type=1)
            if block.get("type") != 0:
                continue

            block_lines = block.get("lines", [])
            if not block_lines:
                continue

            # --- Paragraph aggregation: collect all lines in this block ---
            block_text_parts: List[str] = []
            block_line_bboxes: List[tuple] = []
            block_style: Optional[StyleInfo] = None

            for line in block_lines:
                line_bbox = line.get("bbox", (0, 0, 0, 0))

                # Collect text and style from all spans in this line
                line_text_parts: List[str] = []
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if span_text:
                        line_text_parts.append(span_text)
                        # Capture style from first span of the first line (block-level style)
                        if block_style is None:
                            font_name = span.get("font", "")
                            font_size = span.get("size", 0)
                            flags = span.get("flags", 0)
                            block_style = StyleInfo(
                                font_name=font_name,
                                font_size=font_size,
                                is_bold=bool(flags & 0x10),   # bit 4 = bold (PyMuPDF)
                                is_italic=bool(flags & 0x02), # bit 1 = italic
                                is_underline=False,           # underline not in fitz span flags
                                color=self._color_to_hex(span.get("color", 0)),
                            )

                line_text = "".join(line_text_parts)
                if line_text.strip():
                    block_text_parts.append(line_text)
                    block_line_bboxes.append(tuple(line_bbox))

            # Assemble paragraph text (join with space)
            para_text = " ".join(t.strip() for t in block_text_parts if t.strip())
            if len(para_text) < self.min_text_length:
                continue

            # Union of all line bboxes → paragraph bbox
            xs0 = [b[0] for b in block_line_bboxes]
            ys0 = [b[1] for b in block_line_bboxes]
            xs1 = [b[2] for b in block_line_bboxes]
            ys1 = [b[3] for b in block_line_bboxes]
            para_bbox = BoundingBox(
                x0=min(xs0), y0=min(ys0),
                x1=max(xs1), y1=max(ys1),
            )

            # Determine element type and translatability
            element_type = ElementType.TEXT
            should_translate = True

            is_hf, region = is_header_footer_region(
                para_bbox, page_height, self.header_footer_margin_pt
            )
            if is_hf:
                element_type = (
                    ElementType.HEADER if region == "header" else ElementType.FOOTER
                )
                if self.skip_header_footer:
                    should_translate = False

            element = TranslatableElement(
                element_id=f"p{page_num}_b{block_no}_{uuid.uuid4().hex[:8]}",
                content=para_text,
                element_type=element_type,
                page_num=page_num,
                bbox=para_bbox,
                style=block_style,
                should_translate=should_translate,
                metadata={
                    "block_no": block_no,
                    # Preserve individual line bboxes for bbox-exact whitening (D-1)
                    "lines": block_line_bboxes,
                },
            )
            elements.append(element)

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

        table_counter = 0
        elements_changed = False
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
                    table_id = f"p{page_num + 1}_t{table_counter}"
                    table_counter += 1

                    # Map detected cell rects to (row, col) grid positions so the
                    # translation layer can serialize the whole table as context
                    # (table-context-translation for PDF).  Fail-soft: any error
                    # degrades to the legacy in_table marking without grid coords.
                    try:
                        cell_grid = self._build_cell_grid(table)
                    except Exception:
                        cell_grid = []

                    page_elems = page_elements.get(page_num + 1, [])
                    inside = [
                        elem for elem in page_elems
                        if elem.bbox and self._is_inside(elem.bbox, table_bbox)
                    ]

                    # fitz text blocks frequently merge a whole table ROW into one
                    # block.  When any element spans multiple cells, rebuild this
                    # table's elements from span geometry so each grid cell becomes
                    # its own element (correct translation unit AND overlay bbox).
                    rebuilt: List[TranslatableElement] = []
                    if cell_grid and inside and any(
                        self._spans_multiple_cells(elem.bbox, cell_grid) for elem in inside
                    ):
                        try:
                            rebuilt = self._split_elements_by_cells(
                                page, page_num + 1, table_id, cell_grid
                            )
                        except Exception as exc:
                            logger.debug(
                                f"Per-cell split failed for {table_id}: {exc}; "
                                "keeping merged elements."
                            )
                            rebuilt = []

                    if rebuilt:
                        inside_ids = {id(e) for e in inside}
                        page_elems[:] = [
                            e for e in page_elems if id(e) not in inside_ids
                        ] + rebuilt
                        page_elements[page_num + 1] = page_elems
                        elements_changed = True
                        continue

                    # Mark elements inside table bbox as table cells
                    for elem in inside:
                        elem.element_type = ElementType.TABLE_CELL
                        elem.metadata["in_table"] = True
                        elem.metadata["table_id"] = table_id
                        rc = self._locate_cell(elem.bbox, cell_grid)
                        if rc is not None:
                            elem.metadata["table_row"] = rc[0]
                            elem.metadata["table_col"] = rc[1]

            except Exception as e:
                logger.debug(f"Table detection failed on page {page_num + 1}: {e}")

        if elements_changed:
            # Rebuild the flat element list from the per-page lists (replaced
            # merged row-blocks with per-cell elements).  Downstream reading-order
            # sorting re-sequences globally, so intra-page append order is fine.
            rebuilt_all: List[TranslatableElement] = []
            for pg in sorted(page_elements.keys()):
                rebuilt_all.extend(page_elements[pg])
            elements[:] = rebuilt_all

    @staticmethod
    def _spans_multiple_cells(
        bbox: Optional[BoundingBox],
        cell_grid: List[Tuple[int, int, Tuple[float, float, float, float]]],
    ) -> bool:
        """Return True when bbox meaningfully overlaps more than one table cell."""
        if bbox is None:
            return False
        hit = 0
        for _, _, rect in cell_grid:
            ix0 = max(bbox.x0, rect[0])
            iy0 = max(bbox.y0, rect[1])
            ix1 = min(bbox.x1, rect[2])
            iy1 = min(bbox.y1, rect[3])
            # Require a non-trivial overlap (> 4 pt²) to ignore border grazing.
            if ix1 - ix0 > 2.0 and iy1 - iy0 > 2.0:
                hit += 1
                if hit > 1:
                    return True
        return False

    def _split_elements_by_cells(
        self,
        page: Any,  # fitz.Page
        page_num: int,
        table_id: str,
        cell_grid: List[Tuple[int, int, Tuple[float, float, float, float]]],
    ) -> List[TranslatableElement]:
        """Build one TranslatableElement per table cell from span geometry.

        Used when fitz block aggregation merged text across cell boundaries.
        Each span on the page whose center falls inside a cell rect is assigned
        to that cell; spans are regrouped into lines and joined the same way
        paragraph aggregation joins them.

        Returns:
            One element per non-empty cell (element_type=TABLE_CELL, with
            table_id/table_row/table_col metadata).  Empty list when no spans
            land in any cell.
        """
        text_dict = page.get_text("dict")
        spans_by_cell: Dict[Tuple[int, int], List[Tuple[tuple, str, dict]]] = {}

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if not span_text.strip():
                        continue
                    sb = span.get("bbox", (0, 0, 0, 0))
                    cx = (sb[0] + sb[2]) / 2.0
                    cy = (sb[1] + sb[3]) / 2.0
                    for ri, ci, rect in cell_grid:
                        if rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]:
                            spans_by_cell.setdefault((ri, ci), []).append(
                                (tuple(sb), span_text, span)
                            )
                            break

        rect_by_cell = {(ri, ci): rect for ri, ci, rect in cell_grid}

        new_elements: List[TranslatableElement] = []
        for (ri, ci), spans in sorted(spans_by_cell.items()):
            # Group spans into visual lines by rounded top edge, then x.
            spans.sort(key=lambda s: (round(s[0][1] / 3.0), s[0][0]))
            line_groups: List[List[Tuple[tuple, str, dict]]] = []
            last_y_key = None
            for s in spans:
                y_key = round(s[0][1] / 3.0)
                if last_y_key is None or y_key != last_y_key:
                    line_groups.append([])
                    last_y_key = y_key
                line_groups[-1].append(s)

            line_texts: List[str] = []
            line_bboxes: List[tuple] = []
            for group in line_groups:
                text = "".join(g[1] for g in group).strip()
                if not text:
                    continue
                line_texts.append(text)
                line_bboxes.append((
                    min(g[0][0] for g in group),
                    min(g[0][1] for g in group),
                    max(g[0][2] for g in group),
                    max(g[0][3] for g in group),
                ))

            content = " ".join(line_texts)
            if len(content) < self.min_text_length or not line_bboxes:
                continue

            # Tight text bbox from the spans, then extend right/bottom to the
            # cell rect (minus a border padding) so translations that run longer
            # than the source can use the cell's empty space instead of being
            # shrunk/truncated inside the source text's tight bbox.  Whitening
            # stays tight via metadata["lines"], sparing the cell borders.
            tight_x0 = min(b[0] for b in line_bboxes)
            tight_y0 = min(b[1] for b in line_bboxes)
            tight_x1 = max(b[2] for b in line_bboxes)
            tight_y1 = max(b[3] for b in line_bboxes)
            cell_rect = rect_by_cell.get((ri, ci))
            if cell_rect is not None:
                _pad = 2.0
                tight_x1 = max(tight_x1, cell_rect[2] - _pad)
                tight_y1 = max(tight_y1, cell_rect[3] - _pad)
            cell_bbox = BoundingBox(x0=tight_x0, y0=tight_y0, x1=tight_x1, y1=tight_y1)

            first_span = line_groups[0][0][2]
            flags = first_span.get("flags", 0)
            style = StyleInfo(
                font_name=first_span.get("font", ""),
                font_size=first_span.get("size", 0),
                is_bold=bool(flags & 0x10),
                is_italic=bool(flags & 0x02),
                is_underline=False,
                color=self._color_to_hex(first_span.get("color", 0)),
            )

            new_elements.append(TranslatableElement(
                element_id=f"p{page_num}_{table_id}_r{ri}c{ci}_{uuid.uuid4().hex[:8]}",
                content=content,
                element_type=ElementType.TABLE_CELL,
                page_num=page_num,
                bbox=cell_bbox,
                style=style,
                should_translate=True,
                metadata={
                    "in_table": True,
                    "table_id": table_id,
                    "table_row": ri,
                    "table_col": ci,
                    # Per-line bboxes for bbox-exact whitening (D-1)
                    "lines": line_bboxes,
                },
            ))

        return new_elements

    @staticmethod
    def _build_cell_grid(table: Any) -> List[Tuple[int, int, Tuple[float, float, float, float]]]:
        """Map each detected table-cell rect to a (row, col) grid position.

        fitz Table.cells is an unordered list of cell rect tuples (merged cells
        may appear as None).  Row/column indices are derived by clustering the
        cell top edges (rows) and left edges (columns) with a small tolerance.

        Returns:
            List of (row, col, rect) triples; empty list when no cells found.
        """
        rects = [r for r in (getattr(table, "cells", None) or []) if r is not None]
        if not rects:
            return []

        def _cluster(vals: List[float], tol: float = 2.0) -> List[float]:
            out: List[float] = []
            for v in sorted(vals):
                if not out or v - out[-1] > tol:
                    out.append(v)
            return out

        def _idx(sorted_vals: List[float], v: float, tol: float = 2.0) -> Optional[int]:
            for i, s in enumerate(sorted_vals):
                if abs(v - s) <= tol:
                    return i
            return None

        row_ys = _cluster([r[1] for r in rects])
        col_xs = _cluster([r[0] for r in rects])

        grid: List[Tuple[int, int, Tuple[float, float, float, float]]] = []
        for r in rects:
            ri = _idx(row_ys, r[1])
            ci = _idx(col_xs, r[0])
            if ri is not None and ci is not None:
                grid.append((ri, ci, tuple(r)))
        return grid

    @staticmethod
    def _locate_cell(
        bbox: BoundingBox,
        cell_grid: List[Tuple[int, int, Tuple[float, float, float, float]]],
    ) -> Optional[Tuple[int, int]]:
        """Return the (row, col) of the table cell containing the bbox center."""
        cx = (bbox.x0 + bbox.x1) / 2.0
        cy = (bbox.y0 + bbox.y1) / 2.0
        for ri, ci, rect in cell_grid:
            if rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]:
                return (ri, ci)
        return None

    def _is_inside(self, inner: BoundingBox, outer: BoundingBox) -> bool:
        """Check if inner bbox is inside outer bbox (with tolerance)."""
        tolerance = 5.0  # points
        return (
            inner.x0 >= outer.x0 - tolerance
            and inner.y0 >= outer.y0 - tolerance
            and inner.x1 <= outer.x1 + tolerance
            and inner.y1 <= outer.y1 + tolerance
        )

    def _run_layout_detector(
        self,
        doc: Any,  # fitz.Document
        elements: List[TranslatableElement],
    ) -> List[dict]:
        """Run the layout detector on each page; write element_type + reading_order.

        Rasterises each page via page.get_pixmap(), passes the numpy array to
        LayoutDetector.detect() together with that page's elements.  On any per-page
        failure the heuristic fallback is applied for that page (D-2).  The page
        pixmap array is never stored on self (D-3).

        Args:
            doc: PyMuPDF document.
            elements: All elements (all pages); mutated in-place.

        Returns:
            List[dict]: one viz dict per processed page.
        """
        import numpy as np

        try:
            from app.backend.parsers.layout_detector import LayoutDetector
            detector = LayoutDetector(model_path=LAYOUT_DETECTOR_MODEL_PATH)
        except Exception as exc:
            logger.warning(
                "PyMuPDFParser: could not import LayoutDetector (%s); "
                "falling back to heuristic for all pages.",
                exc,
            )
            elements[:] = self._sort_by_reading_order(elements)
            for idx, elem in enumerate(elements):
                elem.reading_order = idx
            return []

        # Build page → elements lookup
        page_elements: Dict[int, List[TranslatableElement]] = {}
        for elem in elements:
            page_elements.setdefault(elem.page_num, []).append(elem)

        viz_pages: List[dict] = []

        for page_num_0 in range(len(doc)):
            page_num_1 = page_num_0 + 1
            page_elems = page_elements.get(page_num_1, [])
            if not page_elems:
                continue

            page = doc[page_num_0]

            # Rasterise page to numpy array (pixmap created, consumed, not stored)
            try:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(PDF_RENDER_DPI / 72, PDF_RENDER_DPI / 72))
                page_array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, pixmap.n
                )
                # Ensure 3-channel (drop alpha if present)
                if page_array.shape[2] == 4:
                    page_array = page_array[:, :, :3]
                elif page_array.shape[2] == 1:
                    page_array = np.repeat(page_array, 3, axis=2)
            except Exception as exc:
                logger.warning(
                    "PyMuPDFParser: failed to rasterise page %d (%s); "
                    "applying heuristic for that page.",
                    page_num_1,
                    exc,
                )
                sorted_page = self._sort_by_reading_order(page_elems)
                # Assign reading_order using a page-local offset
                current_max = max(
                    (e.reading_order for e in elements if e.reading_order is not None),
                    default=-1,
                )
                for i, elem in enumerate(sorted_page):
                    elem.reading_order = current_max + 1 + i
                continue

            # Run detector (fail-soft: LayoutDetector.detect never raises, D-2)
            # Pass page rect in points so normalized region boxes are correctly
            # mapped back to element bbox coordinates regardless of render DPI.
            page_viz = detector.detect(
                page_array,
                page_elems,
                page_width_pt=page.rect.width,
                page_height_pt=page.rect.height,
            )
            # page_array goes out of scope here; GC reclaims it

            if page_viz is not None:
                page_viz["page_num"] = page_num_1
                page_viz["width"] = float(page.rect.width)
                page_viz["height"] = float(page.rect.height)
                # For heuristic fallback, build boxes from elements
                if page_viz.get("detector") == "heuristic":
                    page_viz["boxes"] = [
                        {
                            "type": e.element_type.value if e.element_type else "text",
                            "bbox": [
                                float(e.bbox.x0 / page.rect.width) if e.bbox else 0.0,
                                float(e.bbox.y0 / page.rect.height) if e.bbox else 0.0,
                                float(e.bbox.x1 / page.rect.width) if e.bbox else 1.0,
                                float(e.bbox.y1 / page.rect.height) if e.bbox else 1.0,
                            ],
                            "score": 1.0,
                            "preview": (e.content or "")[:60],
                        }
                        for e in page_elems if e.bbox is not None
                    ]
                else:
                    # For ONNX detections, leave preview empty (hard to match exactly)
                    for box_entry in page_viz.get("boxes", []):
                        box_entry["preview"] = ""
                viz_pages.append(page_viz)

        # Re-sequence globally: detect() assigns 0-based reading_order per page;
        # after all pages we must produce a single 0..N-1 sequence across the document.
        # Sort by (page_num, local reading_order) then reassign global sequential index.
        def _global_sort_key(e: TranslatableElement):
            ro = e.reading_order if e.reading_order is not None else 999999
            y0 = e.bbox.y0 if e.bbox else 0.0
            x0 = e.bbox.x0 if e.bbox else 0.0
            return (e.page_num, ro, y0, x0)

        all_sorted = sorted(elements, key=_global_sort_key)
        for idx, elem in enumerate(all_sorted):
            elem.reading_order = idx

        return viz_pages

    def _run_table_recognizer(
        self,
        doc: Any,  # fitz.Document
        elements: List[TranslatableElement],
        doc_id: str = "",
    ) -> None:
        """For each table-typed element, run the table recognizer and attach TableStructure.

        Fail-soft per BR-71: on any per-element error, log WARNING and leave the
        element as a plain table region (no metadata["table_structure"] attached).

        The page pixmap is rasterised per-page identically to _run_layout_detector;
        the table bbox crop is created inside table_recognizer.recognize() and
        discarded there (privacy boundary D1, BR-32).

        Args:
            doc: PyMuPDF document.
            elements: All elements (all pages); mutated in-place.
            doc_id: File path used in WARNING messages.
        """
        import numpy as np

        try:
            from app.backend.parsers.table_recognizer import TableRecognizer
            from app.backend.config import TABLE_RECOGNITION_MODEL_PATH
            recognizer = TableRecognizer(model_path=TABLE_RECOGNITION_MODEL_PATH)
        except Exception as exc:
            logger.warning(
                "PyMuPDFParser: could not import TableRecognizer (%s); "
                "table regions will be plain elements (BR-71).",
                exc,
            )
            return

        # Collect table-typed elements
        table_elements = [
            e for e in elements
            if e.element_type.value == "table" and e.bbox is not None
        ]
        if not table_elements:
            return

        # Build page → table-elements lookup
        page_table_elements: Dict[int, List[TranslatableElement]] = {}
        for elem in table_elements:
            page_table_elements.setdefault(elem.page_num, []).append(elem)

        for page_num_0 in range(len(doc)):
            page_num_1 = page_num_0 + 1
            page_elems = page_table_elements.get(page_num_1, [])
            if not page_elems:
                continue

            page = doc[page_num_0]

            # Rasterise page (same pattern as _run_layout_detector)
            try:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(PDF_RENDER_DPI / 72, PDF_RENDER_DPI / 72))
                page_array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, pixmap.n
                )
                if page_array.shape[2] == 4:
                    page_array = page_array[:, :, :3]
                elif page_array.shape[2] == 1:
                    page_array = np.repeat(page_array, 3, axis=2)
            except Exception as exc:
                logger.warning(
                    "PyMuPDFParser: failed to rasterise page %d for table recognition (%s); "
                    "table elements on this page remain plain (BR-71).",
                    page_num_1,
                    exc,
                )
                continue

            for elem in page_elems:
                try:
                    ts = recognizer.recognize(
                        element=elem,
                        page_pixmap_array=page_array,
                        doc_id=doc_id,
                    )
                    if ts is not None:
                        elem.metadata["table_structure"] = ts.to_dict()
                except Exception as exc:
                    logger.warning(
                        "PyMuPDFParser: table recognition failed for element '%s' in '%s': %s. "
                        "Element remains a plain table region (BR-71).",
                        elem.element_id,
                        doc_id,
                        exc,
                    )
            # page_array goes out of scope here; GC reclaims it

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
