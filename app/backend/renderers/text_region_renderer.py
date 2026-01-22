"""Text region renderer for coordinate-based PDF rendering.

This module renders text at specific coordinates within a PDF,
handling font sizing, rotation, and multi-line text.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

from reportlab.lib.colors import Color, white
from reportlab.pdfgen.canvas import Canvas

from app.backend.config import MIN_FONT_SIZE_PT
from app.backend.utils.font_utils import (
    calculate_text_width,
    detect_text_direction,
    fit_text_to_bbox,
    get_font_for_language,
    register_fonts,
)

if TYPE_CHECKING:
    from app.backend.models.translatable_document import BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class TextRegion:
    """Represents a text region to be rendered."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    rotation: float = 0.0
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    text_color: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # RGB, 0-1

    @property
    def width(self) -> float:
        """Width of the region."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Height of the region."""
        return self.y1 - self.y0

    @property
    def center_x(self) -> float:
        """X coordinate of center."""
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        """Y coordinate of center."""
        return (self.y0 + self.y1) / 2

    @classmethod
    def from_bbox(
        cls,
        bbox: "BoundingBox",
        text: str,
        rotation: float = 0.0,
        font_name: Optional[str] = None,
        font_size: Optional[float] = None,
    ) -> "TextRegion":
        """Create a TextRegion from a BoundingBox.

        Args:
            bbox: Source bounding box.
            text: Text to render.
            rotation: Rotation angle in degrees.
            font_name: Font to use.
            font_size: Font size in points.

        Returns:
            TextRegion instance.
        """
        return cls(
            text=text,
            x0=bbox.x0,
            y0=bbox.y0,
            x1=bbox.x1,
            y1=bbox.y1,
            rotation=rotation,
            font_name=font_name,
            font_size=font_size,
        )


def calculate_rotation_from_bbox(
    bbox: "BoundingBox",
    text: str,
) -> float:
    """Estimate rotation angle from bounding box aspect ratio and text.

    Args:
        bbox: Bounding box to analyze.
        text: Text content.

    Returns:
        Estimated rotation angle in degrees.
    """
    # If bbox is taller than wide and text is short, might be rotated
    aspect_ratio = bbox.width / bbox.height if bbox.height > 0 else 1.0

    # Very tall and narrow box might indicate 90° rotation
    if aspect_ratio < 0.3 and len(text) > 3:
        return 90.0
    # Very wide and short box might indicate -90° rotation
    if aspect_ratio > 3.0 and len(text) > 3:
        return 0.0

    return 0.0


def render_text_region(
    canvas: Canvas,
    region: TextRegion,
    target_lang: str,
    page_height: float,
    draw_background: bool = True,
    background_color: Color = white,
) -> None:
    """Render a single text region on the canvas.

    Args:
        canvas: ReportLab canvas to draw on.
        region: TextRegion to render.
        target_lang: Target language for font selection.
        page_height: Page height for Y-axis conversion.
        draw_background: Whether to draw a background rectangle.
        background_color: Background color to use.
    """
    # Ensure fonts are registered
    register_fonts()

    # Get appropriate font
    font_name = region.font_name or get_font_for_language(target_lang)

    # Calculate font size if not specified
    if region.font_size is None:
        font_size, _ = fit_text_to_bbox(
            region.text,
            region.width,
            region.height,
            font_name,
        )
    else:
        font_size = region.font_size

    # Ensure minimum font size
    font_size = max(font_size, MIN_FONT_SIZE_PT)

    # Convert coordinates (PDF uses bottom-left origin, our system uses top-left)
    # Y coordinate needs to be flipped
    pdf_y0 = page_height - region.y1  # Bottom of box in PDF coords
    pdf_y1 = page_height - region.y0  # Top of box in PDF coords

    # Save canvas state
    canvas.saveState()

    # Draw background if requested (to cover original text)
    if draw_background:
        canvas.setFillColor(background_color)
        canvas.rect(
            region.x0,
            pdf_y0,
            region.width,
            region.height,
            fill=1,
            stroke=0,
        )

    # Set text color
    canvas.setFillColorRGB(*region.text_color)

    # Handle rotation
    if region.rotation != 0:
        # Rotate around center of region
        center_x = region.center_x
        center_y = page_height - region.center_y
        canvas.translate(center_x, center_y)
        canvas.rotate(region.rotation)
        canvas.translate(-center_x, -center_y)

    # Set font
    try:
        canvas.setFont(font_name, font_size)
    except KeyError:
        logger.warning(f"Font {font_name} not available, using Helvetica")
        canvas.setFont("Helvetica", font_size)
        font_name = "Helvetica"

    # Handle text direction
    text_dir = detect_text_direction(region.text)

    # Split text into lines
    lines = region.text.split("\n")
    line_height = font_size * 1.2

    # Calculate starting Y position (center text vertically)
    total_text_height = line_height * len(lines)
    start_y = pdf_y1 - (region.height - total_text_height) / 2 - font_size

    # Draw each line
    for i, line in enumerate(lines):
        line_y = start_y - i * line_height

        if text_dir == "rtl":
            # Right-to-left: align to right edge
            text_width = calculate_text_width(line, font_name, font_size)
            line_x = region.x1 - text_width - 2  # Small padding
        else:
            # Left-to-right: align to left edge
            line_x = region.x0 + 2  # Small padding

        canvas.drawString(line_x, line_y, line)

    # Restore canvas state
    canvas.restoreState()


def render_text_regions(
    canvas: Canvas,
    regions: List[TextRegion],
    target_lang: str,
    page_height: float,
    draw_background: bool = True,
    background_color: Color = white,
) -> int:
    """Render multiple text regions on the canvas.

    Args:
        canvas: ReportLab canvas to draw on.
        regions: List of TextRegions to render.
        target_lang: Target language for font selection.
        page_height: Page height for Y-axis conversion.
        draw_background: Whether to draw background rectangles.
        background_color: Background color to use.

    Returns:
        Number of regions rendered.
    """
    rendered_count = 0

    for region in regions:
        try:
            render_text_region(
                canvas,
                region,
                target_lang,
                page_height,
                draw_background,
                background_color,
            )
            rendered_count += 1
        except Exception as exc:
            logger.error(f"Failed to render text region: {exc}")

    return rendered_count


def create_text_regions_from_elements(
    elements: list,
    translations: dict,
    target_lang: str,
) -> List[TextRegion]:
    """Create TextRegions from TranslatableElements with translations.

    Args:
        elements: List of TranslatableElement instances.
        translations: Dict mapping original text to translated text.
        target_lang: Target language code.

    Returns:
        List of TextRegion instances ready for rendering.
    """
    regions = []

    for element in elements:
        if not element.should_translate:
            continue
        if element.bbox is None:
            continue

        original_text = element.content.strip()
        translated_text = translations.get(original_text)

        if translated_text is None:
            logger.warning(f"No translation for: {original_text[:30]}...")
            continue

        # Calculate rotation if needed
        rotation = calculate_rotation_from_bbox(element.bbox, translated_text)

        region = TextRegion.from_bbox(
            element.bbox,
            translated_text,
            rotation=rotation,
        )
        regions.append(region)

    return regions
