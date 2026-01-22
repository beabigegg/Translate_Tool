"""Coordinate-based renderer for PDF output with layout preservation.

This renderer places translated text at the exact coordinates of the
original text, enabling overlay and side-by-side rendering modes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from reportlab.lib.colors import white
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from app.backend.renderers.base import BaseRenderer, RenderMode
from app.backend.renderers.text_region_renderer import (
    TextRegion,
    create_text_regions_from_elements,
    render_text_regions,
)
from app.backend.utils.font_utils import get_font_for_language, register_fonts

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableDocument

logger = logging.getLogger(__name__)


class CoordinateRenderer(BaseRenderer):
    """Renderer that places translations at original text coordinates.

    This renderer supports:
    - OVERLAY mode: Translations replace original text at same position
    - SIDE_BY_SIDE mode: Original and translation shown in parallel

    For PDF output with layout preservation.
    """

    def __init__(
        self,
        target_lang: str = "zh-TW",
        draw_background: bool = True,
        log: Callable[[str], None] = lambda s: None,
    ):
        """Initialize the coordinate renderer.

        Args:
            target_lang: Target language for font selection.
            draw_background: Whether to draw white background over original text.
            log: Logging callback function.
        """
        self.target_lang = target_lang
        self.draw_background = draw_background
        self.log = log

    @property
    def supported_modes(self) -> list[RenderMode]:
        """Supported rendering modes."""
        return [RenderMode.OVERLAY, RenderMode.SIDE_BY_SIDE]

    @property
    def output_extension(self) -> str:
        """Output file extension."""
        return ".pdf"

    def render(
        self,
        document: "TranslatableDocument",
        output_path: str,
        translations: Dict[str, str],
        mode: RenderMode = RenderMode.OVERLAY,
    ) -> None:
        """Render translated document to PDF with coordinate positioning.

        Args:
            document: Source TranslatableDocument with bbox information.
            output_path: Path for output PDF file.
            translations: Mapping from original text to translated text.
            mode: OVERLAY or SIDE_BY_SIDE mode.

        Raises:
            ValueError: If mode is not supported.
        """
        if mode not in self.supported_modes:
            raise ValueError(
                f"CoordinateRenderer does not support {mode.value} mode. "
                f"Supported modes: {[m.value for m in self.supported_modes]}"
            )

        # Ensure fonts are registered
        register_fonts()

        if mode == RenderMode.OVERLAY:
            self._render_overlay(document, output_path, translations)
        else:
            self._render_side_by_side(document, output_path, translations)

    def _render_overlay(
        self,
        document: "TranslatableDocument",
        output_path: str,
        translations: Dict[str, str],
    ) -> None:
        """Render in overlay mode - translations at original positions.

        Args:
            document: Source document.
            output_path: Output file path.
            translations: Original -> translated text mapping.
        """
        self.log(f"[Renderer] Generating overlay PDF: {Path(output_path).name}")

        # Group elements by page
        elements_by_page = document.get_all_elements_by_page()

        # Determine page size from document or use default
        if document.pages:
            page_width = document.pages[0].width
            page_height = document.pages[0].height
        else:
            page_width, page_height = letter

        # Create canvas
        canvas = Canvas(output_path, pagesize=(page_width, page_height))

        total_regions = 0

        for page_num in sorted(elements_by_page.keys()):
            elements = elements_by_page[page_num]

            # Get page-specific dimensions
            page_info = next((p for p in document.pages if p.page_num == page_num), None)
            if page_info:
                current_page_height = page_info.height
                canvas.setPageSize((page_info.width, page_info.height))
            else:
                current_page_height = page_height

            # Create text regions for this page
            regions = create_text_regions_from_elements(
                elements, translations, self.target_lang
            )

            # Render regions
            rendered = render_text_regions(
                canvas,
                regions,
                self.target_lang,
                current_page_height,
                draw_background=self.draw_background,
            )
            total_regions += rendered

            # Add new page (except for last page)
            if page_num < max(elements_by_page.keys()):
                canvas.showPage()

        # Save the PDF
        canvas.save()
        self.log(f"[Renderer] Rendered {total_regions} text regions to {Path(output_path).name}")

    def _render_side_by_side(
        self,
        document: "TranslatableDocument",
        output_path: str,
        translations: Dict[str, str],
    ) -> None:
        """Render in side-by-side mode - original and translation in columns.

        Args:
            document: Source document.
            output_path: Output file path.
            translations: Original -> translated text mapping.
        """
        self.log(f"[Renderer] Generating side-by-side PDF: {Path(output_path).name}")

        # For side-by-side, we create a wider page with two columns
        if document.pages:
            original_width = document.pages[0].width
            original_height = document.pages[0].height
        else:
            original_width, original_height = letter

        # Double the width for side-by-side
        page_width = original_width * 2
        page_height = original_height

        canvas = Canvas(output_path, pagesize=(page_width, page_height))

        # Group elements by page
        elements_by_page = document.get_all_elements_by_page()

        total_regions = 0

        for page_num in sorted(elements_by_page.keys()):
            elements = elements_by_page[page_num]

            # Get page-specific dimensions
            page_info = next((p for p in document.pages if p.page_num == page_num), None)
            if page_info:
                current_original_width = page_info.width
                current_page_height = page_info.height
                canvas.setPageSize((current_original_width * 2, current_page_height))
            else:
                current_original_width = original_width
                current_page_height = original_height

            # Left side: Original text (no background)
            original_regions = []
            for element in elements:
                if element.bbox is None:
                    continue
                region = TextRegion(
                    text=element.content.strip(),
                    x0=element.bbox.x0,
                    y0=element.bbox.y0,
                    x1=element.bbox.x1,
                    y1=element.bbox.y1,
                )
                original_regions.append(region)

            # Render original text (left side)
            render_text_regions(
                canvas,
                original_regions,
                "auto",  # Use auto-detect for original
                current_page_height,
                draw_background=False,
            )

            # Right side: Translated text (shifted by original_width)
            translation_regions = []
            for element in elements:
                if element.bbox is None:
                    continue
                if not element.should_translate:
                    continue

                original_text = element.content.strip()
                translated_text = translations.get(original_text)
                if translated_text is None:
                    continue

                # Shift to right column
                region = TextRegion(
                    text=translated_text,
                    x0=element.bbox.x0 + current_original_width,
                    y0=element.bbox.y0,
                    x1=element.bbox.x1 + current_original_width,
                    y1=element.bbox.y1,
                )
                translation_regions.append(region)

            # Render translations (right side)
            rendered = render_text_regions(
                canvas,
                translation_regions,
                self.target_lang,
                current_page_height,
                draw_background=True,  # White background on right side
            )
            total_regions += rendered

            # Draw center divider line
            canvas.setStrokeColorRGB(0.8, 0.8, 0.8)
            canvas.setLineWidth(0.5)
            canvas.line(
                current_original_width,
                0,
                current_original_width,
                current_page_height,
            )

            # Add new page (except for last page)
            if page_num < max(elements_by_page.keys()):
                canvas.showPage()

        # Save the PDF
        canvas.save()
        self.log(f"[Renderer] Rendered {total_regions} translation regions to {Path(output_path).name}")


def render_to_pdf(
    document: "TranslatableDocument",
    translations: Dict[str, str],
    output_path: str,
    mode: str = "overlay",
    target_lang: str = "en",
) -> None:
    """Convenience function to render translated document to PDF.

    Args:
        document: Source TranslatableDocument.
        translations: Dict mapping original text to translated text.
        output_path: Output PDF file path.
        mode: Rendering mode ("overlay" or "side_by_side").
        target_lang: Target language for font selection.

    Raises:
        ValueError: If mode is invalid.
    """
    mode_enum = RenderMode(mode)
    renderer = CoordinateRenderer(target_lang=target_lang)
    renderer.render(document, output_path, translations, mode_enum)
