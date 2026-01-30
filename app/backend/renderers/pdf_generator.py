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

from app.backend.config import (
    FONT_SIZE_CONFIG,
    LANG_CODE_MAP,
    PDF_MASK_MARGIN_PT,
    PDF_SHOW_MISSING_PLACEHOLDER,
)
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
        self._font_config = self._get_font_config()
        self._missing_translations: List[str] = []  # Track missing translations

    @property
    def missing_translation_count(self) -> int:
        """Get the number of missing translations after generation."""
        return len(self._missing_translations)

    @property
    def missing_translations(self) -> List[str]:
        """Get the list of texts that had no translation."""
        return self._missing_translations.copy()

    def _get_font_config(self) -> dict:
        """Get language-aware font configuration.

        Returns:
            Dict with max, min, height_ratio, shrink_factor keys.
        """
        lang_code = _get_lang_code(self.target_lang).lower()
        config = FONT_SIZE_CONFIG.get(lang_code, FONT_SIZE_CONFIG.get("default", {}))
        # Ensure all required keys exist with defaults
        return {
            "max": config.get("max", 11),
            "min": config.get("min", 4),
            "height_ratio": config.get("height_ratio", 0.75),
            "shrink_factor": config.get("shrink_factor", 0.88),
        }

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

        # Reset missing translations tracking for new generation
        self._missing_translations = []

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

        Uses redaction to remove original text and insert translations:
        1. Search for exact text positions using page.search_for()
        2. Add redaction annotations to remove original text (preserves table borders)
        3. Apply all redactions at once per page
        4. Insert translated text at the original bbox position

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

            # Collect redaction areas and translations for this page
            redaction_items = []  # List of (redact_rect, text_rect, translated_text)

            # Process each element
            for element in elements:
                if not element.should_translate or element.bbox is None:
                    continue

                original_text = element.content.strip()
                translated_text = translations.get(original_text)
                if translated_text is None:
                    # Track missing translation
                    self._missing_translations.append(original_text[:50])
                    if PDF_SHOW_MISSING_PLACEHOLDER:
                        translated_text = f"[未翻譯] {original_text[:20]}..."
                    else:
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
                    # Use the precise quad rect for redaction
                    # Shrink by configurable margin to preserve adjacent table lines
                    rect = matched_quad.rect
                    margin = PDF_MASK_MARGIN_PT
                    redact_rect = fitz.Rect(
                        rect.x0 + margin,
                        rect.y0 + margin,
                        rect.x1 - margin,
                        rect.y1 - margin,
                    )
                else:
                    # Fallback: use element bbox with larger margin
                    margin = PDF_MASK_MARGIN_PT * 2
                    redact_rect = fitz.Rect(
                        element.bbox.x0 + margin,
                        element.bbox.y0 + margin,
                        element.bbox.x1 - margin,
                        element.bbox.y1 - margin,
                    )

                # Skip invalid rectangles
                if redact_rect.width < 1 or redact_rect.height < 1:
                    continue

                # Text insertion rect (use full element bbox)
                text_rect = fitz.Rect(
                    element.bbox.x0,
                    element.bbox.y0,
                    element.bbox.x1,
                    element.bbox.y1,
                )

                redaction_items.append((redact_rect, text_rect, translated_text))

            # Apply redactions if mask is enabled
            if self.draw_mask and redaction_items:
                # Add all redaction annotations first
                for redact_rect, _, _ in redaction_items:
                    # Add redaction annotation with white fill
                    page.add_redact_annot(redact_rect, fill=(1, 1, 1))

                # Apply all redactions at once (removes text from PDF)
                page.apply_redactions()

            # Now insert all translated text
            for _, text_rect, translated_text in redaction_items:
                self._insert_text_in_rect(page, text_rect, translated_text)

        # Subset fonts to embed only used glyphs (important for CJK fonts)
        try:
            src_doc.subset_fonts()
        except Exception as e:
            logger.debug(f"Font subsetting warning: {e}")

        # Save output
        src_doc.save(output_path, garbage=4, deflate=True)
        src_doc.close()

        # Report missing translations
        if self._missing_translations:
            self.log(f"[PDF] Warning: {len(self._missing_translations)} text(s) without translation")
            if len(self._missing_translations) <= 5:
                for text in self._missing_translations:
                    self.log(f"[PDF]   - {text}...")

        self.log(f"[PDF] Saved overlay PDF: {Path(output_path).name}")

    def _get_font_file(self) -> Optional[str]:
        """Get the font file path for the target language.

        Returns:
            Path to font file or None if not found.
        """
        from app.backend.utils.font_utils import find_font_file

        # Map language codes to font file patterns
        # Supports TTF and OTF formats (prefer Variable TTF for consistency)
        # Vietnamese uses Latin script with diacritics - NotoSans covers it
        font_file_map = {
            "zh-tw": ["NotoSansTC-Regular.ttf"],
            "zh-cn": ["NotoSansSC-Regular.ttf"],
            "ja": ["NotoSansJP-Variable.ttf", "NotoSansJP-Regular.otf"],
            "ko": ["NotoSansKR-Variable.ttf", "NotoSansKR-Regular.otf"],
            "th": ["NotoSansThai-Regular.ttf"],
            "ar": ["NotoSansArabic-Regular.ttf"],
            "he": ["NotoSansHebrew-Regular.ttf"],
            "vi": ["NotoSans-Regular.ttf", "NotoSans[wght].ttf", "DejaVuSans.ttf"],
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

    def _wrap_text(self, text: str, font, fontsize: float, max_width: float) -> List[str]:
        """Wrap text to fit within max_width.

        Args:
            text: Text to wrap.
            font: PyMuPDF font object.
            fontsize: Font size in points.
            max_width: Maximum width in points.

        Returns:
            List of wrapped lines.
        """
        if not text:
            return [""]

        wrapped_lines = []
        for line in text.split("\n"):
            if not line:
                wrapped_lines.append("")
                continue

            # Check if line fits
            if font.text_length(line, fontsize=fontsize) <= max_width:
                wrapped_lines.append(line)
                continue

            # Need to wrap this line
            current_line = ""
            for char in line:
                test_line = current_line + char
                if font.text_length(test_line, fontsize=fontsize) <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        wrapped_lines.append(current_line)
                    current_line = char

            if current_line:
                wrapped_lines.append(current_line)

        return wrapped_lines if wrapped_lines else [""]

    def _insert_text_in_rect(
        self,
        page,
        rect,
        text: str,
    ) -> None:
        """Insert text into a rectangle with automatic font sizing and text wrapping.

        Uses TextWriter for proper Unicode support (especially Vietnamese diacritics).
        Wraps long text lines to fit within the rectangle width.

        Args:
            page: PyMuPDF page object.
            rect: Target fitz.Rect.
            text: Text to insert.
        """
        import fitz

        # Try to get actual font file first (required for proper Unicode support)
        font_file = self._get_font_file()

        # Get language-aware font configuration
        fc = self._font_config

        # Create font object using fontbuffer for proper embedding
        # Note: Using fontbuffer instead of fontfile ensures CJK fonts are embedded in the PDF
        try:
            if font_file:
                # Read font file into buffer for proper embedding
                with open(font_file, "rb") as f:
                    font_buffer = f.read()
                font = fitz.Font(fontbuffer=font_buffer)
            else:
                # Fallback to built-in font
                lang_code = _get_lang_code(self.target_lang).lower()
                font_map = {
                    "zh-tw": "china-ts",
                    "zh-cn": "china-ss",
                    "ja": "japan",
                    "ko": "korea",
                }
                fontname = font_map.get(lang_code, "helv")
                font = fitz.Font(fontname)
        except Exception as e:
            logger.warning(f"Failed to create font: {e}, using default")
            font = fitz.Font("helv")

        # Start with max font size and decrease until text fits
        font_size = fc["max"]
        line_spacing = 1.15

        # Try inserting with decreasing font sizes until it fits
        for _ in range(25):
            if font_size < fc["min"]:
                font_size = fc["min"]
                break

            try:
                # Wrap text to fit within rect width
                wrapped_lines = self._wrap_text(text, font, font_size, rect.width)

                # Calculate total height needed
                total_height = len(wrapped_lines) * font_size * line_spacing

                # Check if wrapped text fits vertically
                if total_height <= rect.height:
                    # Text fits! Insert it
                    tw = fitz.TextWriter(page.rect)
                    x = rect.x0
                    y = rect.y0 + font_size  # Baseline offset

                    for line in wrapped_lines:
                        if y > rect.y1:
                            break
                        tw.append((x, y), line, font=font, fontsize=font_size)
                        y += font_size * line_spacing

                    tw.write_text(page)
                    return

                # Text didn't fit vertically, try smaller size
                font_size *= fc["shrink_factor"]

            except Exception as e:
                logger.debug(f"TextWriter failed: {e}")
                font_size *= fc["shrink_factor"]

        # Final attempt with minimum size - truncate if needed
        try:
            final_size = max(font_size, fc["min"])
            wrapped_lines = self._wrap_text(text, font, final_size, rect.width)

            tw = fitz.TextWriter(page.rect)
            y = rect.y0 + final_size

            for line in wrapped_lines:
                if y > rect.y1:
                    # Log overflow warning
                    logger.debug(
                        f"Text does not fit in bbox even at minimum font size {final_size}pt: "
                        f"text='{text[:50]}...', bbox=({rect.width:.1f}, {rect.height:.1f})"
                    )
                    break
                tw.append((rect.x0, y), line, font=font, fontsize=final_size)
                y += final_size * line_spacing

            tw.write_text(page)
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
