"""PDF generator for layout-preserved translation output.

This module generates translated PDFs by overlaying translation layers
onto the original PDF, preserving images, backgrounds, and formatting.
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from reportlab.lib.colors import white
from reportlab.pdfgen.canvas import Canvas

from app.backend.config import LANG_CODE_MAP
from app.backend.renderers.base import RenderMode
from app.backend.renderers.text_region_renderer import (
    TextRegion,
    create_text_regions_from_elements,
    render_text_region,
)
from app.backend.utils.font_utils import register_fonts

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableDocument

logger = logging.getLogger(__name__)

# Lazy import for fitz (PyMuPDF)
fitz = None


def _get_lang_code(lang: str) -> str:
    """Convert language name to ISO code.

    Args:
        lang: Language name (e.g., "Traditional Chinese") or code (e.g., "zh-TW").

    Returns:
        ISO language code (e.g., "zh-TW").
    """
    # If already a code (contains hyphen or is short), return as-is
    if "-" in lang or len(lang) <= 3:
        return lang.lower()

    # Look up in LANG_CODE_MAP
    if lang in LANG_CODE_MAP:
        return LANG_CODE_MAP[lang][1]

    # Case-insensitive lookup
    lang_lower = lang.lower()
    for name, (_, code) in LANG_CODE_MAP.items():
        if name.lower() == lang_lower:
            return code

    # Fallback: return as-is
    return lang


def _ensure_fitz():
    """Ensure PyMuPDF is available."""
    global fitz
    if fitz is None:
        try:
            import fitz as _fitz
            fitz = _fitz
        except ImportError:
            raise ImportError(
                "PyMuPDF (fitz) is required for PDF generation. "
                "Install with: pip install pymupdf"
            )
    return fitz


class PDFGenerator:
    """Generates translated PDFs with layout preservation.

    This generator creates PDF output by:
    1. Parsing the original PDF
    2. Creating a translation overlay layer
    3. Merging the overlay with the original (preserving images/backgrounds)

    Supports overlay and side-by-side modes.
    """

    def __init__(
        self,
        target_lang: str = "zh-TW",
        draw_mask: bool = True,
        log: Callable[[str], None] = lambda s: None,
    ):
        """Initialize the PDF generator.

        Args:
            target_lang: Target language for font selection.
            draw_mask: Whether to draw white masks over original text regions.
            log: Logging callback function.
        """
        self.target_lang = target_lang
        self.draw_mask = draw_mask
        self.log = log

    def generate(
        self,
        document: "TranslatableDocument",
        translations: Dict[str, str],
        output_path: str,
        mode: RenderMode = RenderMode.OVERLAY,
    ) -> None:
        """Generate translated PDF.

        Args:
            document: Source TranslatableDocument with bbox information.
            translations: Mapping from original text to translated text.
            output_path: Path for output PDF file.
            mode: OVERLAY or SIDE_BY_SIDE mode.

        Raises:
            ValueError: If mode is not supported.
            FileNotFoundError: If source PDF not found.
        """
        _ensure_fitz()

        if mode == RenderMode.INLINE:
            raise ValueError(
                "PDFGenerator does not support INLINE mode. "
                "Use OVERLAY or SIDE_BY_SIDE mode."
            )

        source_path = document.source_path
        if not Path(source_path).exists():
            raise FileNotFoundError(f"Source PDF not found: {source_path}")

        if mode == RenderMode.OVERLAY:
            self._generate_overlay(document, translations, output_path)
        else:
            self._generate_side_by_side(document, translations, output_path)

    def _generate_overlay(
        self,
        document: "TranslatableDocument",
        translations: Dict[str, str],
        output_path: str,
    ) -> None:
        """Generate overlay mode PDF.

        Uses a hybrid approach:
        1. Search for exact text positions using page.search_for()
        2. Draw white rectangles only over found text quads (preserves table borders)
        3. Insert translated text at the original bbox position

        Args:
            document: Source document.
            translations: Text translations.
            output_path: Output file path.
        """
        self.log(f"[PDF] Generating overlay PDF: {Path(output_path).name}")
        register_fonts()

        # Open source PDF
        src_doc = fitz.open(document.source_path)

        # Group elements by page
        elements_by_page = document.get_all_elements_by_page()

        # Process each page
        for page_num in range(len(src_doc)):
            page = src_doc[page_num]

            # Get elements for this page (1-indexed in our system)
            elements = elements_by_page.get(page_num + 1, [])
            if not elements:
                continue

            # Process each element
            for element in elements:
                if not element.should_translate or element.bbox is None:
                    continue

                original_text = element.content.strip()
                translated_text = translations.get(original_text)
                if translated_text is None:
                    continue

                # Search for exact text position to get precise quads
                text_quads = page.search_for(original_text, quads=True)

                # Element bbox for validation
                elem_rect = fitz.Rect(
                    element.bbox.x0 - 2,
                    element.bbox.y0 - 2,
                    element.bbox.x1 + 2,
                    element.bbox.y1 + 2,
                )

                # Find the quad that matches our element's position
                matched_quad = None
                for quad in text_quads:
                    if quad.rect.intersects(elem_rect):
                        matched_quad = quad
                        break

                if matched_quad:
                    # Use the precise quad rect for white rectangle
                    # Shrink slightly to preserve adjacent table lines
                    rect = matched_quad.rect
                    cover_rect = fitz.Rect(
                        rect.x0 + 0.2,
                        rect.y0 + 0.2,
                        rect.x1 - 0.2,
                        rect.y1 - 0.2,
                    )
                else:
                    # Fallback: use element bbox with margin
                    cover_rect = fitz.Rect(
                        element.bbox.x0 + 0.5,
                        element.bbox.y0 + 0.5,
                        element.bbox.x1 - 0.5,
                        element.bbox.y1 - 0.5,
                    )

                # Skip invalid rectangles
                if cover_rect.width < 1 or cover_rect.height < 1:
                    continue

                # Draw white rectangle to cover original text
                shape = page.new_shape()
                shape.draw_rect(cover_rect)
                shape.finish(color=None, fill=(1, 1, 1))  # White fill, no border
                shape.commit()

                # Insert translated text at original bbox position
                text_rect = fitz.Rect(
                    element.bbox.x0,
                    element.bbox.y0,
                    element.bbox.x1,
                    element.bbox.y1,
                )
                self._insert_text_in_rect(page, text_rect, translated_text)

        # Save output
        src_doc.save(output_path, garbage=4, deflate=True)
        src_doc.close()

        self.log(f"[PDF] Saved overlay PDF: {Path(output_path).name}")

    def _get_font_file(self) -> Optional[str]:
        """Get the font file path for the target language.

        Returns:
            Path to font file or None if not found.
        """
        from app.backend.utils.font_utils import find_font_file

        # Map language codes to font file patterns
        # Supports TTF and OTF formats
        font_file_map = {
            "zh-tw": ["NotoSansTC-Regular.ttf"],
            "zh-cn": ["NotoSansSC-Regular.ttf"],
            "ja": ["NotoSansJP-Regular.otf", "NotoSansJP-Regular.ttf"],
            "ko": ["NotoSansKR-Regular.otf", "NotoSansKR-Regular.ttf"],
            "th": ["NotoSansThai-Regular.ttf"],
            "ar": ["NotoSansArabic-Regular.ttf"],
            "he": ["NotoSansHebrew-Regular.ttf"],
        }

        lang_code = _get_lang_code(self.target_lang).lower()
        patterns = font_file_map.get(lang_code, [])

        if patterns:
            font_path = find_font_file(patterns)
            if font_path:
                self.log(f"[PDF] Using font file: {font_path}")
                return str(font_path)

        self.log(f"[PDF] No font file found for {self.target_lang} (code: {lang_code})")
        return None

    def _insert_text_in_rect(
        self,
        page,
        rect,
        text: str,
    ) -> None:
        """Insert text into a rectangle with automatic font sizing.

        Args:
            page: PyMuPDF page object.
            rect: Target fitz.Rect.
            text: Text to insert.
        """
        # Convert language name to code (e.g., "Traditional Chinese" -> "zh-TW")
        lang_code = _get_lang_code(self.target_lang).lower()

        # Try to get actual font file first (more reliable for CJK)
        font_file = self._get_font_file()

        # Fallback to PyMuPDF built-in fonts if no file found
        font_map = {
            "zh-tw": "china-ts",
            "zh-cn": "china-ss",
            "ja": "japan",
            "ko": "korea",
        }
        fontname = font_map.get(lang_code, "helv")

        logger.debug(
            f"Font selection: target_lang={self.target_lang}, "
            f"lang_code={lang_code}, fontname={fontname}, font_file={font_file}"
        )

        # Estimate initial font size based on rect height and line count
        lines = text.split("\n")
        line_count = max(len(lines), 1)
        max_font_size = rect.height / line_count * 0.75
        font_size = min(max_font_size, 11)  # Cap at 11pt

        # Try inserting with decreasing font sizes until it fits
        for _ in range(15):
            if font_size < 4:
                font_size = 4
                break
            try:
                # insert_textbox returns remaining text length if it doesn't fit
                # Use font_file if available for better CJK support
                if font_file:
                    result = page.insert_textbox(
                        rect,
                        text,
                        fontsize=font_size,
                        fontfile=font_file,
                        fontname="F0",  # PyMuPDF requires a name when using fontfile
                        align=0,  # Left align
                    )
                else:
                    result = page.insert_textbox(
                        rect,
                        text,
                        fontsize=font_size,
                        fontname=fontname,
                        align=0,  # Left align
                    )
                if result >= 0:  # Success (all text fits)
                    return
                # Text didn't fit, try smaller size
                font_size *= 0.88
            except Exception as e:
                logger.debug(f"insert_textbox failed: {e}")
                font_size *= 0.88

        # Final attempt with minimum size
        try:
            if font_file:
                page.insert_textbox(
                    rect,
                    text,
                    fontsize=max(font_size, 4),
                    fontfile=font_file,
                    fontname="F0",
                    align=0,
                )
            else:
                page.insert_textbox(
                    rect,
                    text,
                    fontsize=max(font_size, 4),
                    fontname=fontname,
                    align=0,
                )
        except Exception as e:
            logger.warning(f"Failed to insert text: {e}")

    def _generate_side_by_side(
        self,
        document: "TranslatableDocument",
        translations: Dict[str, str],
        output_path: str,
    ) -> None:
        """Generate side-by-side mode PDF.

        Args:
            document: Source document.
            translations: Text translations.
            output_path: Output file path.
        """
        self.log(f"[PDF] Generating side-by-side PDF: {Path(output_path).name}")
        register_fonts()

        # Open source PDF
        src_doc = fitz.open(document.source_path)

        # Create new document with double-width pages
        out_doc = fitz.open()

        # Group elements by page
        elements_by_page = document.get_all_elements_by_page()

        for page_num in range(len(src_doc)):
            src_page = src_doc[page_num]
            src_rect = src_page.rect

            # Create double-width page
            new_width = src_rect.width * 2
            new_height = src_rect.height
            new_page = out_doc.new_page(width=new_width, height=new_height)

            # Copy original page to left side
            new_page.show_pdf_page(
                fitz.Rect(0, 0, src_rect.width, src_rect.height),
                src_doc,
                page_num,
            )

            # Copy original page to right side as background
            new_page.show_pdf_page(
                fitz.Rect(src_rect.width, 0, new_width, new_height),
                src_doc,
                page_num,
            )

            # Get elements for this page
            elements = elements_by_page.get(page_num + 1, [])

            if elements:
                # Create translation overlay for right side
                overlay_pdf = self._create_page_overlay(
                    elements,
                    translations,
                    src_rect.width,
                    src_rect.height,
                    x_offset=0,  # Will be placed at right side
                )

                if overlay_pdf:
                    overlay_doc = fitz.open("pdf", overlay_pdf)
                    # Overlay translation on right side (on top of the copied original)
                    new_page.show_pdf_page(
                        fitz.Rect(src_rect.width, 0, new_width, new_height),
                        overlay_doc,
                        0,
                        overlay=True,
                    )
                    overlay_doc.close()

            # Draw center divider
            new_page.draw_line(
                fitz.Point(src_rect.width, 0),
                fitz.Point(src_rect.width, new_height),
                color=(0.8, 0.8, 0.8),
                width=0.5,
            )

        # Save output
        out_doc.save(output_path, garbage=4, deflate=True)
        out_doc.close()
        src_doc.close()

        self.log(f"[PDF] Saved side-by-side PDF: {Path(output_path).name}")

    def _create_page_overlay(
        self,
        elements: list,
        translations: Dict[str, str],
        page_width: float,
        page_height: float,
        x_offset: float = 0,
    ) -> Optional[bytes]:
        """Create a PDF overlay for a single page.

        Args:
            elements: TranslatableElements for this page.
            translations: Text translations.
            page_width: Page width in points.
            page_height: Page height in points.
            x_offset: X offset for positioning (for side-by-side).

        Returns:
            PDF bytes or None if no regions to render.
        """
        # Create text regions
        regions = create_text_regions_from_elements(
            elements, translations, self.target_lang
        )

        if not regions:
            return None

        # Apply x offset if needed
        if x_offset != 0:
            for region in regions:
                region.x0 += x_offset
                region.x1 += x_offset

        # Create PDF in memory
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(page_width, page_height))

        # Render each region
        for region in regions:
            render_text_region(
                canvas,
                region,
                self.target_lang,
                page_height,
                draw_background=self.draw_mask,
                background_color=white,
            )

        canvas.save()
        return buffer.getvalue()


def generate_translated_pdf(
    document: "TranslatableDocument",
    translations: Dict[str, str],
    output_path: str,
    mode: str = "overlay",
    target_lang: str = "zh-TW",
    log: Callable[[str], None] = lambda s: None,
) -> None:
    """Convenience function to generate translated PDF.

    Args:
        document: Source TranslatableDocument.
        translations: Dict mapping original text to translated text.
        output_path: Output PDF file path.
        mode: Rendering mode ("overlay" or "side_by_side").
        target_lang: Target language for font selection.
        log: Logging callback.

    Raises:
        ValueError: If mode is invalid.
    """
    mode_enum = RenderMode(mode)
    generator = PDFGenerator(target_lang=target_lang, log=log)
    generator.generate(document, translations, output_path, mode_enum)
