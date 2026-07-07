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
)
from app.backend.renderers.base import RenderMode
from app.backend.renderers.bbox_reflow import reflow_document
from app.backend.renderers.text_region_renderer import (
    TextRegion,
    _wrap_lines_simple,
    create_text_regions_from_elements,
    fit_text_cascade,
    render_text_region,
)
from app.backend.services.metrics import record_font_cache_hit, record_font_cache_miss
from app.backend.utils.font_utils import get_font_for_language, register_fonts

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableDocument

logger = logging.getLogger(__name__)

# Lazy import for fitz (PyMuPDF)
fitz = None

# Sentinel for PDFGenerator._font_file_resolved ("not yet looked up")
_FONT_FILE_UNSET = object()


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
        # Lazily-resolved font file path; sentinel distinguishes "not looked up"
        # from "looked up, not found" so the disk search runs at most once.
        self._font_file_resolved: object = _FONT_FILE_UNSET

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

            # Bbox-exact whitening (D-1, BR-84): separate whitening rects from text items.
            # search_for is NOT used — the element's IR bbox is the single source of truth.
            whitening_rects = []   # fitz.Rect objects to whiten (may be >1 per paragraph elem)
            text_items = []        # (text_rect, translated_text, element) for insertion

            for element in elements:
                placement = placement_by_id.get(element.element_id)
                if placement is None:
                    # Skipped by reflow (null bbox or should_translate=False)
                    continue

                # Resolve the translated text: the translations dict override takes
                # priority; the Placement text is used only when it is an actual
                # translation (translated_content), not its content fallback.
                # When no translation exists at all, the element is skipped BEFORE
                # any whitening rect is queued — the original text stays visible
                # instead of being redacted to a blank box or re-typeset verbatim.
                original_text = element.content.strip()
                translated_text = translations.get(original_text)
                if translated_text is None and placement.text != element.content:
                    translated_text = placement.text
                if translated_text is None or not str(translated_text).strip():
                    self._missing_translations.append(original_text[:50])
                    continue

                # Bbox-exact whitening: use IR bbox directly; no search_for (D-1).
                # For paragraph-aggregated elements, whiten each original line bbox
                # (stored by the parser as metadata["lines"]) so table borders are spared.
                margin = PDF_MASK_MARGIN_PT
                line_bboxes = element.metadata.get("lines", [])
                if line_bboxes:
                    for lb in line_bboxes:
                        r = fitz.Rect(
                            lb[0] + margin, lb[1] + margin,
                            lb[2] - margin, lb[3] - margin,
                        )
                        if r.width >= 1 and r.height >= 1:
                            whitening_rects.append(r)
                else:
                    r = fitz.Rect(
                        placement.x0 + margin, placement.y0 + margin,
                        placement.x1 - margin, placement.y1 - margin,
                    )
                    if r.width >= 1 and r.height >= 1:
                        whitening_rects.append(r)

                # Text insertion rect comes from the Placement (shared reflow output).
                # This is the single source of placement truth for both backends (BR-35).
                text_rect = fitz.Rect(
                    placement.x0,
                    placement.y0,
                    placement.x1,
                    placement.y1,
                )
                # AC-9/BR-36 note: carry the Placement's real whitespace-below
                # (computed once in bbox_reflow.py) through to the cascade call.
                text_items.append((text_rect, translated_text, element, placement.available_whitespace_below))

            # Apply redactions if mask is enabled
            if self.draw_mask and whitening_rects:
                # Add all redaction annotations first
                for redact_rect in whitening_rects:
                    # Add redaction annotation with white fill
                    page.add_redact_annot(redact_rect, fill=(1, 1, 1))

                # Apply all redactions at once (removes text from PDF).
                # graphics=0 preserves vector strokes (table border lines) that
                # overlap the redaction rect — fixes Bug (a) table border erasure
                # (p2-table-border-protection, AC-1).
                page.apply_redactions(graphics=0)

            # Now insert all translated text; pass element so truncation marker (BR-38) can be set
            for text_rect, translated_text, elem_ref, ws_below in text_items:
                self._insert_text_in_rect(
                    page, text_rect, translated_text, element=elem_ref,
                    available_whitespace_below=ws_below,
                )

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

        The disk search is memoized per generator instance — this method is
        called once per inserted text block, and the answer never changes
        within a generation run.

        Returns:
            Path to font file or None if not found.
        """
        if self._font_file_resolved is not _FONT_FILE_UNSET:
            return self._font_file_resolved  # type: ignore[return-value]

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
                self._font_file_resolved = str(font_path)
                return self._font_file_resolved

        self.log(f"[PDF] No font file found for {self.target_lang} (code: {lang_code})")
        self._font_file_resolved = None
        return None

    def _insert_text_in_rect(
        self,
        page,
        rect,
        text: str,
        element=None,
        available_whitespace_below: float = 0.0,
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
            available_whitespace_below: Real vertical whitespace below this
                rect (points), computed once in bbox_reflow.py and carried on
                the Placement for this element (AC-9, BR-36 note). Defaults to
                0.0 for any call-site that does not have Placement geometry.
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

        # Starting font size: prefer the ORIGINAL text's size (from the parsed
        # element style) so translated text matches the surrounding typography;
        # fall back to the language config max when style info is unavailable.
        initial_size = float(fc["max"])
        elem_style = getattr(element, "style", None) if element is not None else None
        if elem_style is not None and getattr(elem_style, "font_size", None):
            try:
                orig_size = float(elem_style.font_size)
                if orig_size > 0:
                    initial_size = orig_size
            except (TypeError, ValueError):
                pass

        # Measure with the actual registered font for the target language so
        # the cascade's wrap/height decisions match what will be rendered.
        # (get_font_for_language falls back to Helvetica, whose CJK widths are
        # em-estimated by calculate_text_width.)
        measure_font_name = get_font_for_language(self.target_lang)

        style = StyleInfo(
            font_size=initial_size,
            font_name=measure_font_name,
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
            available_whitespace_below=available_whitespace_below,  # AC-9: real Placement gap, not a literal 0.0
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
        final_font_size = decision.font_size
        line_spacing = decision.line_spacing

        # Render via fitz TextWriter using the cascade decision.
        # Line breaks come from the SAME wrap function the cascade measured with,
        # so the rendered line count matches the fit decision; the overflow guard
        # below is a last-resort safety net, not the primary fit mechanism.
        try:
            wrapped_lines = _wrap_lines_simple(
                render_text, measure_font_name, final_font_size, rect.width
            )
            tw = fitz.TextWriter(page.rect)
            x = rect.x0
            y = rect.y0 + final_font_size  # Baseline offset
            bottom_limit = rect.y1 + final_font_size * 0.25  # small descender tolerance

            for line in wrapped_lines:
                if y > bottom_limit:
                    logger.debug(
                        "[cascade] render overflow guard fired in bbox "
                        f"({rect.width:.1f}×{rect.height:.1f}); dropping remaining lines"
                    )
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

            # Build the translated overlay regions FIRST so the source-text mask
            # covers exactly the areas that will receive a translated overlay.
            # Elements without a translation (or with should_translate=False)
            # keep their source text visible on the right panel instead of being
            # redacted to a blank white box.
            regions = (
                create_text_regions_from_elements(elements, translations, self.target_lang)
                if elements
                else []
            )

            if regions and self.draw_mask:
                # Bug (b) fix (p2-table-border-protection, AC-2): mask source text
                # on the right-panel copy before the translated overlay is placed.
                # Without this pass, source text copied via show_pdf_page bleeds
                # through around/under the translated overlay rectangles.
                # Use redact annotations so the text content stream is actually
                # removed (draw_rect only visually covers text but does not remove
                # it from the PDF text layer queried by get_text()).
                # Each region's rect is offset by src_rect.width (right-half origin).
                for region in regions:
                    mask_rect = fitz.Rect(
                        region.x0 + src_rect.width,
                        region.y0,
                        region.x1 + src_rect.width,
                        region.y1,
                    )
                    new_page.draw_rect(mask_rect, color=None, fill=(1, 1, 1))
                    new_page.add_redact_annot(mask_rect, fill=(1, 1, 1))
                new_page.apply_redactions(graphics=0)

            if regions:
                # Create translation overlay for right side
                overlay_pdf = self._create_page_overlay(
                    regions,
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
        regions: List[TextRegion],
        page_width: float,
        page_height: float,
        x_offset: float = 0,
    ) -> Optional[bytes]:
        """Create a PDF overlay for a single page from pre-built text regions.

        Args:
            regions: TextRegions to render (from create_text_regions_from_elements).
            page_width: Page width in points.
            page_height: Page height in points.
            x_offset: X offset for positioning (for side-by-side).

        Returns:
            PDF bytes or None if no regions to render.
        """
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
