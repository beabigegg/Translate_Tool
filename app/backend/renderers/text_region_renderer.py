"""Text region renderer for coordinate-based PDF rendering.

This module renders text at specific coordinates within a PDF,
handling font sizing, rotation, and multi-line text.

p2-text-expansion additions:
  - CascadeDecision: structured result from fit_text_cascade
  - fit_text_cascade: the BR-36 5-step cascade (font-size → line-spacing →
    letter-spacing → controlled overflow → truncation)

The cascade is backend-neutral; both the fitz primary adapter and the
ReportLab adapter consume CascadeDecision.  No cascade logic may exist in
coordinate_renderer.py, inline_renderer.py, or pdf_generator.py (BR-40).
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
    from app.backend.models.translatable_document import BoundingBox, StyleInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CascadeDecision — structured result from fit_text_cascade (BR-36, AC-4)
# ---------------------------------------------------------------------------


@dataclass
class CascadeDecision:
    """Structured result returned by fit_text_cascade.

    Carries the final rendering parameters decided by the 5-step BR-36 cascade
    so that both the fitz primary adapter and the ReportLab adapter can render
    from an identical decision without re-deriving fit logic.

    Fields
    ------
    font_size : float
        Final font size in points (≥ ``MIN_FONT_SIZE_PT``).
    line_spacing : float
        Final line-spacing multiplier (1.0 – 1.15 range per BR-36 step b).
    letter_spacing : float
        Final letter-spacing as a fraction of em (0.0 to -0.005 per BR-36 step c).
    overflow : bool
        True when step (d) controlled-overflow was applied (text rect expanded
        downward into adjacent whitespace ≤ 15% bbox height).
    truncated : bool
        True when step (e) truncation fired.  The renderer must set
        ``element.render_truncated = True`` when this flag is set (BR-38).
    fitted_text : str
        The text to be rendered (possibly truncated with "…" appended).
    """

    font_size: float
    line_spacing: float
    letter_spacing: float
    overflow: bool
    truncated: bool
    fitted_text: str


# ---------------------------------------------------------------------------
# Line-height helper (backend-neutral)
# ---------------------------------------------------------------------------

def _text_line_height(font_name: str, font_size: float, line_spacing: float) -> float:
    """Return rendered line height for given font and line-spacing multiplier."""
    return font_size * line_spacing


def _measure_text_block(
    lines: List[str],
    font_name: str,
    font_size: float,
    line_spacing: float,
) -> Tuple[float, float]:
    """Return (max_line_width, total_height) for a list of lines.

    Uses ReportLab pdfmetrics for width measurement (backend-neutral).
    Falls back to a character-count heuristic when the font is not registered.
    """
    max_w = 0.0
    for line in lines:
        w = calculate_text_width(line, font_name, font_size)
        if w > max_w:
            max_w = w
    total_h = font_size * line_spacing * len(lines)
    return max_w, total_h


def _wrap_lines_simple(text: str, font_name: str, font_size: float, max_width: float) -> List[str]:
    """Word-wrap ``text`` to fit within ``max_width`` points.

    Returns a list of output lines.  Words are split on spaces; a word that
    alone exceeds the width is placed on its own line (no mid-word split).
    """
    result: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            result.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            test = (current + " " + word).strip() if current else word
            if calculate_text_width(test, font_name, font_size) <= max_width:
                current = test
            else:
                if current:
                    result.append(current)
                current = word
        if current:
            result.append(current)
    return result if result else [""]


def _truncate_to_fit(
    text: str,
    font_name: str,
    font_size: float,
    line_spacing: float,
    max_width: float,
    max_height: float,
) -> str:
    """Clip ``text`` to the last whole word that fits, appending "…".

    The returned string always ends with "…" (U+2026 HORIZONTAL ELLIPSIS).
    If the ellipsis alone does not fit in the bbox, the empty string is returned
    (degenerate bbox; the renderer may choose to skip rendering).
    """
    ellipsis = "…"
    ellipsis_w = calculate_text_width(ellipsis, font_name, font_size)

    words = text.split()
    candidate = ""
    for word in words:
        test = (candidate + " " + word).strip() if candidate else word
        lines = _wrap_lines_simple(test + ellipsis, font_name, font_size, max_width)
        _, h = _measure_text_block(lines, font_name, font_size, line_spacing)
        # Also check max width of each line candidate
        ok = all(
            calculate_text_width(line, font_name, font_size) <= max_width
            for line in lines
        )
        if ok and h <= max_height:
            candidate = test
        else:
            break

    if candidate:
        return candidate + ellipsis
    # Nothing fits — return bare ellipsis if it fits, else empty string
    if ellipsis_w <= max_width and font_size * line_spacing <= max_height:
        return ellipsis
    return ""


# ---------------------------------------------------------------------------
# fit_text_cascade — BR-36 5-step cascade (IP-1)
# ---------------------------------------------------------------------------

def fit_text_cascade(
    text: str,
    bbox: "BoundingBox",
    style: "StyleInfo",
    available_whitespace_below: float = 0.0,
) -> CascadeDecision:
    """Apply the BR-36 ordered fit cascade to ``text`` within ``bbox``.

    Cascade steps, applied in order (each only when prior steps are exhausted):

    (a) Font-size shrink from style.font_size (or MAX_FONT_SIZE_PT) down to
        MIN_FONT_SIZE_PT (4 pt floor) using FONT_SIZE_SHRINK_FACTOR.
    (b) Line-spacing compression from 1.15 down to 1.0 floor.
    (c) Letter-spacing reduction to -0.005 em floor (negative tracking capped
        to avoid glyph collision; currently advisory).
    (d) Controlled downward overflow into adjacent whitespace only (≤ 15% bbox
        height), provided ``available_whitespace_below > 0``.  Never sideways.
    (e) Word-boundary truncation with "…" appended; always marked via
        ``CascadeDecision.truncated = True`` (BR-38).

    Parameters
    ----------
    text:
        The text to fit (translated content).
    bbox:
        Target bounding box.
    style:
        StyleInfo carrying font_name and starting font_size.
    available_whitespace_below:
        Vertical whitespace available below the bbox (in points).  Set to 0.0
        when neighbor geometry is unavailable (step d degrades to skip; BR-36
        Table L row "step d: adjacent whitespace not available").

    Returns
    -------
    CascadeDecision
        Structured fit decision; consume fields to drive rendering.
    """
    from app.backend.config import FONT_SIZE_SHRINK_FACTOR as _SHRINK

    bbox_w = bbox.x1 - bbox.x0
    bbox_h = bbox.y1 - bbox.y0

    font_name = (style.font_name or "Helvetica") if style else "Helvetica"
    initial_size = (style.font_size or MIN_FONT_SIZE_PT) if style else MIN_FONT_SIZE_PT
    # Clamp initial size to a positive value
    initial_size = max(initial_size, MIN_FONT_SIZE_PT)

    # We track the effective max height; may expand in step (d)
    effective_max_height = bbox_h

    # --- step (a): font-size shrink ---
    font_size = initial_size
    line_spacing = 1.15

    while font_size > MIN_FONT_SIZE_PT:
        lines = _wrap_lines_simple(text, font_name, font_size, bbox_w)
        _, h = _measure_text_block(lines, font_name, font_size, line_spacing)
        if h <= bbox_h:
            return CascadeDecision(
                font_size=font_size,
                line_spacing=line_spacing,
                letter_spacing=0.0,
                overflow=False,
                truncated=False,
                fitted_text=text,
            )
        font_size = max(font_size * _SHRINK, MIN_FONT_SIZE_PT)

    # At minimum font size — check once more
    font_size = MIN_FONT_SIZE_PT
    lines = _wrap_lines_simple(text, font_name, font_size, bbox_w)
    _, h = _measure_text_block(lines, font_name, font_size, line_spacing)
    if h <= bbox_h:
        return CascadeDecision(
            font_size=font_size,
            line_spacing=line_spacing,
            letter_spacing=0.0,
            overflow=False,
            truncated=False,
            fitted_text=text,
        )

    # --- step (b): line-spacing compression ---
    # Walk from 1.15 down to 1.0 in small steps
    ls_steps = [1.10, 1.05, 1.0]
    for ls in ls_steps:
        lines = _wrap_lines_simple(text, font_name, font_size, bbox_w)
        _, h = _measure_text_block(lines, font_name, font_size, ls)
        if h <= bbox_h:
            return CascadeDecision(
                font_size=font_size,
                line_spacing=ls,
                letter_spacing=0.0,
                overflow=False,
                truncated=False,
                fitted_text=text,
            )
    line_spacing = 1.0  # at floor

    # --- step (c): letter-spacing reduction ---
    # Letter-spacing is advisory (applied by the renderer via TextWriter spacing).
    # Floor is -0.005 em (BR-36).  We check if the text fits with letter-spacing
    # as a signal; the actual rendering adjustment is in the renderer adapter.
    for ls_track in [-0.002, -0.005]:
        # Estimate: letter-spacing of -0.005 em at 4pt = -0.02pt per char.
        # We approximate the width reduction as letter_spacing * font_size * char_count.
        char_count = len(text)
        extra_width = -ls_track * font_size * char_count  # positive value = width reduction
        adjusted_bbox_w = bbox_w + extra_width
        lines = _wrap_lines_simple(text, font_name, font_size, adjusted_bbox_w)
        _, h = _measure_text_block(lines, font_name, font_size, line_spacing)
        if h <= bbox_h:
            return CascadeDecision(
                font_size=font_size,
                line_spacing=line_spacing,
                letter_spacing=ls_track,
                overflow=False,
                truncated=False,
                fitted_text=text,
            )
    letter_spacing = -0.005  # at floor

    # --- step (d): controlled downward overflow (≤ 15% bbox height) ---
    if available_whitespace_below > 0:
        max_overflow = min(bbox_h * 0.15, available_whitespace_below)
        extended_h = bbox_h + max_overflow
        lines = _wrap_lines_simple(text, font_name, font_size, bbox_w)
        _, h = _measure_text_block(lines, font_name, font_size, line_spacing)
        if h <= extended_h:
            return CascadeDecision(
                font_size=font_size,
                line_spacing=line_spacing,
                letter_spacing=letter_spacing,
                overflow=True,
                truncated=False,
                fitted_text=text,
            )
    # step (d): adjacent whitespace not available → skip, proceed to (e)

    # --- step (e): word-boundary truncation ---
    fitted = _truncate_to_fit(text, font_name, font_size, line_spacing, bbox_w, bbox_h)
    return CascadeDecision(
        font_size=font_size,
        line_spacing=line_spacing,
        letter_spacing=letter_spacing,
        overflow=False,
        truncated=True,
        fitted_text=fitted,
    )


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

    # Set font; on miss use metric-compatible registered fallback (BR-39)
    try:
        canvas.setFont(font_name, font_size)
    except KeyError:
        from app.backend.utils.font_utils import get_metric_compatible_fallback
        from reportlab.pdfbase import pdfmetrics as _pdfmetrics
        _registered = list(_pdfmetrics.getRegisteredFontNames())
        fallback_name = get_metric_compatible_fallback(
            font_name,
            region.text[0] if region.text else " ",
            _registered,
        )
        logger.warning(f"Font {font_name} not available, using metric-compatible fallback: {fallback_name}")
        canvas.setFont(fallback_name, font_size)
        font_name = fallback_name

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


def create_text_regions_from_placements(placements: list) -> List[TextRegion]:
    """Create TextRegions from Placement objects produced by bbox_reflow.

    This is the ReportLab draw helper that consumes pre-computed Placement
    decisions from the shared IR-bbox reflow component (bbox_reflow.py).  It
    contains NO IR logic — inclusion/exclusion, reading_order sorting, and
    text-source selection are already resolved by reflow_document.

    Args:
        placements: List of Placement objects from bbox_reflow.reflow_document.

    Returns:
        List of TextRegion instances ready for rendering.  One TextRegion per
        Placement; never raises for any individual Placement.
    """
    regions = []
    for placement in placements:
        # No IR decisions here: reflow already resolved text, bbox, and skip logic.
        region = TextRegion(
            text=placement.text,
            x0=placement.x0,
            y0=placement.y0,
            x1=placement.x1,
            y1=placement.y1,
        )
        regions.append(region)
    return regions
