"""Fitz (PyMuPDF) primary PDF renderer for layout-preserved translation output.

This module is the fitz primary backend adapter (p2-renderer-convergence,
Decision D). It was previously named pdf_generator.py; the rename makes the
primary/fallback pair (fitz primary / ReportLab fallback) legible.

Both the fitz primary renderer and the ReportLab fallback renderer consume
TranslatableDocument via the shared IR-bbox reflow component (bbox_reflow.py)
per BR-34 and the data-shape-contract § Renderer IR-consumption contract.
"""

from __future__ import annotations

import functools
import io
import logging
import os
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
from app.backend.renderers.bbox_reflow import reflow_document
from app.backend.renderers.text_region_renderer import (
    TextRegion,
    create_text_regions_from_elements,
    fit_text_cascade,
    render_text_region,
)
from app.backend.services.metrics import record_font_cache_hit, record_font_cache_miss
from app.backend.utils.font_utils import register_fonts

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableDocument

logger = logging.getLogger(__name__)

# Lazy import for fitz (PyMuPDF)
fitz = None


# ---------------------------------------------------------------------------
# Font-buffer LRU cache
# No locking is applied here deliberately: the PDF render pipeline is
# single-threaded (one job at a time), so concurrent cache access is not
# expected.  If that assumption ever changes, add a threading.Lock guard.
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _load_font_buffer(font_path: str) -> bytes:
    """Load and return the raw bytes of a font file, caching the result.

    The cache key is always the absolute resolved path produced by
    ``os.path.realpath``, so that relative and absolute references to the
    same file share a single cache entry.

    Exceptions from ``open()`` propagate unchanged.  ``lru_cache`` does NOT
    cache exceptions, so a failing call leaves no stale entry in the cache.
    """
    resolved = os.path.realpath(font_path)
    with open(resolved, "rb") as f:
        return f.read()


def clear_font_cache() -> None:
    """Clear all entries from the font-buffer cache.

    Call this in test fixtures to prevent cross-test state bleed.
    """
    _load_font_buffer.cache_clear()


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

        # Obtain ordered placements via the shared IR-bbox reflow component (AC-1/BR-35).
        # Both the fitz and ReportLab paths consume this same placement sequence,
        # guaranteeing identical element-level include/exclude, reading-order, and
        # text-source decisions (BR-35, data-shape-contract § Renderer IR-consumption contract).
        placements = reflow_document(document)
        # Build a lookup so we can correlate element.content (for quad search) with placement.
        placement_by_id = {p.element_id: p for p in placements}

        # Open source PDF
        src_doc = fitz.open(document.source_path)

        # Group elements by page for quad-search refinement (fitz-specific; Decision B/Open Risk).
        # The reflow Placement carries the IR bbox; the quad search may refine the
        # *redaction* rect but must NOT override the Placement bbox for text insertion.
        elements_by_page = document.get_all_elements_by_page()

        # Process each page
        for page_num in range(len(src_doc)):
            page = src_doc[page_num]

            # Get elements for this page (1-indexed in our system)
            elements = elements_by_page.get(page_num + 1, [])
            if not elements:
                continue

            # Collect redaction areas and translations for this page
            redaction_items = []  # List of (redact_rect, text_rect, translated_text, element)

            # Process each element — use Placement for text_rect; fitz quad for redact_rect.
            for element in elements:
                placement = placement_by_id.get(element.element_id)
                if placement is None:
                    # Skipped by reflow (null bbox or should_translate=False)
                    continue

                # The reflow Placement already resolved the translated text (or fell back
                # to content).  Use the translations dict override when available so that
                # external translation results still take priority, then fall back to the
                # Placement text (which itself falls back to content).
                original_text = element.content.strip()
                translated_text = translations.get(original_text, placement.text)
                if translated_text is None:
                    # Track missing translation
                    self._missing_translations.append(original_text[:50])
                    if PDF_SHOW_MISSING_PLACEHOLDER:
                        translated_text = f"[未翻譯] {original_text[:20]}..."
                    else:
                        continue

                # Search for exact text position to get precise quads for the redaction rect.
                # This is fitz-specific quad-precise redaction; it does NOT affect text_rect.
                text_quads = page.search_for(original_text, quads=True)

                # Element bbox for quad search validation (±2 pt tolerance, Decision C).
                elem_rect = fitz.Rect(
                    placement.x0 - 2,
                    placement.y0 - 2,
                    placement.x1 + 2,
                    placement.y1 + 2,
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
                    # Fallback: use placement bbox with larger margin
                    margin = PDF_MASK_MARGIN_PT * 2
                    redact_rect = fitz.Rect(
                        placement.x0 + margin,
                        placement.y0 + margin,
                        placement.x1 - margin,
                        placement.y1 - margin,
                    )

                # Skip invalid rectangles
                if redact_rect.width < 1 or redact_rect.height < 1:
                    continue

                # Text insertion rect comes from the Placement (shared reflow output).
                # This is the single source of placement truth for both backends (BR-35).
                text_rect = fitz.Rect(
                    placement.x0,
                    placement.y0,
                    placement.x1,
                    placement.y1,
                )

                redaction_items.append((redact_rect, text_rect, translated_text, element))

            # Apply redactions if mask is enabled
            if self.draw_mask and redaction_items:
                # Add all redaction annotations first
                for redact_rect, _, _, _ in redaction_items:
                    # Add redaction annotation with white fill
                    page.add_redact_annot(redact_rect, fill=(1, 1, 1))

                # Apply all redactions at once (removes text from PDF).
                # graphics=0 preserves vector strokes (table border lines) that
                # overlap the redaction rect — fixes Bug (a) table border erasure
                # (p2-table-border-protection, AC-1).
                page.apply_redactions(graphics=0)

            # Now insert all translated text; pass element so truncation marker (BR-38) can be set
            for _, text_rect, translated_text, elem_ref in redaction_items:
                self._insert_text_in_rect(page, text_rect, translated_text, element=elem_ref)

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
        element=None,
    ) -> None:
        """Insert text into a rectangle using the BR-36 fit cascade.

        Replaces the previous 25-iteration shrink loop with a call to the
        shared ``fit_text_cascade`` helper (text_region_renderer.py).  The
        cascade returns a ``CascadeDecision``; this method drives fitz
        TextWriter from that decision.

        When the cascade fires step (e) truncation, ``element.render_truncated``
        is set ``True`` (BR-38, AC-5).  ``element`` may be ``None`` (legacy
        call-sites that pre-date IR element access); in that case truncation is
        logged but the marker cannot be set.

        Args:
            page: PyMuPDF page object.
            rect: Target fitz.Rect.
            text: Text to insert.
            element: Optional TranslatableElement; when provided, receives the
                render_truncated marker on truncation (BR-38).
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
                # Load font bytes through the module-level LRU cache so repeated
                # calls for the same font path avoid redundant disk reads.
                # Metrics hook (BR-24): detect hit vs miss via cache_info() delta.
                _hits_before = _load_font_buffer.cache_info().hits
                font_buffer = _load_font_buffer(font_file)
                try:
                    if _load_font_buffer.cache_info().hits > _hits_before:
                        record_font_cache_hit()
                    else:
                        record_font_cache_miss()
                except Exception:
                    pass  # instrumentation must never break font loading
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

        # --- Invoke the shared BR-36 fit cascade ---
        # Build a minimal StyleInfo-compatible dict for the cascade.
        from app.backend.models.translatable_document import StyleInfo, BoundingBox as _BBox

        style = StyleInfo(
            font_size=float(fc["max"]),
            font_name=None,  # cascade uses calculate_text_width (ReportLab); font object for I/O
        )
        bbox_obj = _BBox(
            x0=float(rect.x0),
            y0=float(rect.y0),
            x1=float(rect.x1),
            y1=float(rect.y1),
        )

        decision = fit_text_cascade(
            text=text,
            bbox=bbox_obj,
            style=style,
            available_whitespace_below=0.0,  # neighbor geometry not exposed by fitz (design Open Risk)
        )

        # Mark truncation on IR element (BR-38, AC-5)
        if decision.truncated:
            if element is not None:
                element.render_truncated = True
            logger.debug(
                f"[cascade] Truncated text in bbox ({rect.width:.1f}×{rect.height:.1f}): "
                f"'{text[:30]}…' → '{decision.fitted_text[:30]}'"
            )

        render_text = decision.fitted_text if decision.fitted_text else text
        final_font_size = max(decision.font_size, float(fc["min"]))
        line_spacing = decision.line_spacing

        # Render via fitz TextWriter using the cascade decision
        try:
            wrapped_lines = self._wrap_text(render_text, font, final_font_size, rect.width)
            tw = fitz.TextWriter(page.rect)
            x = rect.x0
            y = rect.y0 + final_font_size  # Baseline offset

            for line in wrapped_lines:
                if y > rect.y1:
                    break
                tw.append((x, y), line, font=font, fontsize=final_font_size)
                y += final_font_size * line_spacing

            tw.write_text(page)
        except Exception as e:
            logger.warning(f"Failed to insert text via cascade decision: {e}")

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

            if elements and self.draw_mask:
                # Bug (b) fix (p2-table-border-protection, AC-2): mask source text
                # on the right-panel copy before the translated overlay is placed.
                # Without this pass, source text copied via show_pdf_page bleeds
                # through around/under the translated overlay rectangles.
                # Use redact annotations so the text content stream is actually
                # removed (draw_rect only visually covers text but does not remove
                # it from the PDF text layer queried by get_text()).
                # Each element's bbox is offset by src_rect.width (right-half origin).
                for elem in elements:
                    if elem.bbox is None:
                        continue
                    mask_rect = fitz.Rect(
                        elem.bbox.x0 + src_rect.width,
                        elem.bbox.y0,
                        elem.bbox.x1 + src_rect.width,
                        elem.bbox.y1,
                    )
                    new_page.draw_rect(mask_rect, color=None, fill=(1, 1, 1))
                    new_page.add_redact_annot(mask_rect, fill=(1, 1, 1))
                new_page.apply_redactions(graphics=0)

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
