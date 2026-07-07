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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from reportlab.lib.colors import Color, white
from reportlab.pdfgen.canvas import Canvas

from app.backend.config import FONT_SIZE_CONFIG, MIN_FONT_SIZE_PT, PDF_HEADER_FOOTER_MARGIN_PT
from app.backend.models.translatable_document import ElementType
from app.backend.utils.font_utils import (
    calculate_text_width,
    detect_text_direction,
    get_font_for_language,
    register_fonts,
)

if TYPE_CHECKING:
    from app.backend.models.translatable_document import (
        BoundingBox,
        StyleInfo,
        TranslatableDocument,
        TranslatableElement,
    )

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


def _split_oversized_token(
    token: str, font_name: str, font_size: float, max_width: float
) -> List[str]:
    """Split a token wider than ``max_width`` at character level.

    Needed for spaceless scripts (CJK) and long unbreakable runs (URLs), which
    have no word boundaries to wrap on.  Each returned piece fits within
    ``max_width`` (a single character wider than the box is emitted as-is).
    """
    pieces: List[str] = []
    current = ""
    for ch in token:
        test = current + ch
        if current and calculate_text_width(test, font_name, font_size) > max_width:
            pieces.append(current)
            current = ch
        else:
            current = test
    if current:
        pieces.append(current)
    return pieces


def _wrap_lines_simple(text: str, font_name: str, font_size: float, max_width: float) -> List[str]:
    """Word-wrap ``text`` to fit within ``max_width`` points.

    Returns a list of output lines.  Words are split on spaces; a word that
    alone exceeds the width (e.g. a CJK run, which has no spaces at all) is
    split at character level so measured line counts match what a renderer
    doing character wrapping will actually produce.
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
                continue
            if current:
                result.append(current)
                current = ""
            if calculate_text_width(word, font_name, font_size) <= max_width:
                current = word
            else:
                pieces = _split_oversized_token(word, font_name, font_size, max_width)
                result.extend(pieces[:-1])
                current = pieces[-1] if pieces else ""
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
    """Clip ``text`` to the longest prefix that fits, appending "…".

    Prefers a word boundary when the text contains spaces; falls back to a
    character boundary for spaceless scripts (CJK) so the result is never an
    empty clip of otherwise-renderable text.

    The returned string always ends with "…" (U+2026 HORIZONTAL ELLIPSIS).
    If the ellipsis alone does not fit in the bbox, the empty string is returned
    (degenerate bbox; the renderer may choose to skip rendering).
    """
    ellipsis = "…"
    ellipsis_w = calculate_text_width(ellipsis, font_name, font_size)

    def _fits(candidate: str) -> bool:
        lines = _wrap_lines_simple(candidate, font_name, font_size, max_width)
        _, h = _measure_text_block(lines, font_name, font_size, line_spacing)
        return h <= max_height and all(
            calculate_text_width(line, font_name, font_size) <= max_width
            for line in lines
        )

    # Binary-search the longest character prefix that fits with the ellipsis.
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _fits(text[:mid].rstrip() + ellipsis):
            lo = mid
        else:
            hi = mid - 1

    prefix = text[:lo].rstrip()
    # Prefer a whole-word boundary when the cut lands mid-word in spaced text.
    if prefix and lo < len(text) and not text[lo].isspace() and " " in prefix:
        prefix = prefix.rsplit(" ", 1)[0].rstrip()

    if prefix:
        return prefix + ellipsis
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

    (a) Binary-search font-size from style.font_size down to MIN_READABLE_FONT_PT
        (8 pt floor) — finds the largest fitting size in O(log N) steps.
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
    bbox_w = bbox.x1 - bbox.x0
    bbox_h = bbox.y1 - bbox.y0

    font_name = (style.font_name or "Helvetica") if style else "Helvetica"
    initial_size = (style.font_size or MIN_FONT_SIZE_PT) if style else MIN_FONT_SIZE_PT
    # Clamp initial size to at least the readable floor
    initial_size = max(initial_size, float(MIN_FONT_SIZE_PT))

    # We track the effective max height; may expand in step (d)
    effective_max_height = bbox_h

    # --- step (a): binary-search font-size in [MIN_FONT_SIZE_PT, initial_size] (AC-3) ---
    line_spacing = 1.15

    # Quick check: does initial size fit?
    lines = _wrap_lines_simple(text, font_name, initial_size, bbox_w)
    _, h = _measure_text_block(lines, font_name, initial_size, line_spacing)
    if h <= bbox_h:
        return CascadeDecision(
            font_size=initial_size,
            line_spacing=line_spacing,
            letter_spacing=0.0,
            overflow=False,
            truncated=False,
            fitted_text=text,
        )

    # Binary search: find the largest font size in [floor, initial_size] that fits.
    # At most 20 iterations → precision within 0.5 pt.
    lo = float(MIN_FONT_SIZE_PT)
    hi = float(initial_size)
    for _ in range(20):
        if hi - lo < 0.5:
            break
        mid = (lo + hi) / 2.0
        lines = _wrap_lines_simple(text, font_name, mid, bbox_w)
        _, h = _measure_text_block(lines, font_name, mid, line_spacing)
        if h <= bbox_h:
            lo = mid
        else:
            hi = mid

    # lo is the best-fitting lower bound found; verify it fits
    font_size = lo
    lines = _wrap_lines_simple(text, font_name, font_size, bbox_w)
    _, h = _measure_text_block(lines, font_name, font_size, line_spacing)
    if h <= bbox_h and font_size >= MIN_FONT_SIZE_PT:
        return CascadeDecision(
            font_size=font_size,
            line_spacing=line_spacing,
            letter_spacing=0.0,
            overflow=False,
            truncated=False,
            fitted_text=text,
        )

    # Step (a) exhausted at MIN_READABLE_FONT_PT floor; proceed to step (b)
    font_size = float(MIN_FONT_SIZE_PT)
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
    style: Optional["StyleInfo"] = None  # IP-1: source style; cascade starting font (BR-40)
    element: Optional[Any] = None  # IP-1: source element ref; render_truncated marker target (BR-38)

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
        style: Optional["StyleInfo"] = None,
        element: Optional[Any] = None,
    ) -> "TextRegion":
        """Create a TextRegion from a BoundingBox.

        Args:
            bbox: Source bounding box.
            text: Text to render.
            rotation: Rotation angle in degrees.
            font_name: Font to use.
            font_size: Font size in points.
            style: Source StyleInfo (IP-1); gives the cascade a faithful starting
                font size instead of the FONT_SIZE_CONFIG fallback.
            element: Source element reference (IP-1); receives render_truncated
                when the cascade truncates (BR-38).

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
            style=style,
            element=element,
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

    # Get appropriate font (measurement/render font is always language-aware,
    # matching fitz_renderer._insert_text_in_rect — the source font NAME is
    # never used for measurement, only its size).
    font_name = region.font_name or get_font_for_language(target_lang)

    # --- BR-40 (ADR-0012): fit_text_cascade is the single shared fit/wrap
    # authority for ALL PDF renderer paths. Mirrors fitz_renderer.py:473-552.
    from app.backend.models.translatable_document import BoundingBox as _BBox
    from app.backend.models.translatable_document import StyleInfo as _StyleInfo

    initial_size: Optional[float] = None
    if region.style is not None and getattr(region.style, "font_size", None):
        try:
            candidate = float(region.style.font_size)
            if candidate > 0:
                initial_size = candidate
        except (TypeError, ValueError):
            pass
    if initial_size is None:
        if region.font_size is not None:
            initial_size = region.font_size
        else:
            # No threaded style (e.g. create_text_regions_from_placements — the
            # Placement type does not carry StyleInfo): degrade to the language
            # FONT_SIZE_CONFIG max (design.md Open Risk — acceptable, less faithful).
            initial_size = FONT_SIZE_CONFIG.get("default", {}).get("max", 11)

    cascade_style = _StyleInfo(font_name=font_name, font_size=initial_size)
    bbox_obj = _BBox(x0=region.x0, y0=region.y0, x1=region.x1, y1=region.y1)

    decision = fit_text_cascade(
        text=region.text,
        bbox=bbox_obj,
        style=cascade_style,
        available_whitespace_below=0.0,
    )

    # Mark truncation on the IR element (BR-38) when an element ref was
    # threaded (IP-1); create_text_regions_from_placements does not carry one,
    # so that sub-path degrades to log-only (matches the fitz legacy
    # element=None behavior — a bounded, documented BR-38 gap).
    if decision.truncated:
        if region.element is not None:
            region.element.render_truncated = True
        logger.debug(
            f"[cascade] Truncated text in ReportLab bbox ({region.width:.1f}×{region.height:.1f}): "
            f"'{region.text[:30]}…' -> '{decision.fitted_text[:30]}'"
            + ("" if region.element is not None else " (no element ref threaded; BR-38 marker not set)")
        )

    render_text = decision.fitted_text if decision.fitted_text else region.text
    font_size = max(decision.font_size, MIN_FONT_SIZE_PT)
    line_spacing = decision.line_spacing

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

    # Word-wrap via the SAME shared cascade helper the fitz path draws from
    # (BR-40, ADR-0012) — no separate wrap pass, no literal "\n"-only split.
    lines = _wrap_lines_simple(render_text, font_name, font_size, region.width)
    line_height = font_size * line_spacing

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
            # Fall back to the IR-resolved translation when it is an actual
            # translation (not the content itself).
            ir_translation = getattr(element, "translated_content", None)
            if ir_translation is not None and ir_translation != element.content:
                translated_text = ir_translation

        if translated_text is None or not str(translated_text).strip():
            logger.warning(f"No translation for: {original_text[:30]}...")
            continue

        # Calculate rotation if needed
        rotation = calculate_rotation_from_bbox(element.bbox, translated_text)

        region = TextRegion.from_bbox(
            element.bbox,
            translated_text,
            rotation=rotation,
            style=element.style,
            element=element,
        )
        regions.append(region)

    return regions


def create_text_regions_from_placements(placements: list) -> List[TextRegion]:
    """Create TextRegions from Placement objects produced by bbox_reflow.

    This is the ReportLab draw helper that consumes pre-computed Placement
    decisions from the shared IR-bbox reflow component (bbox_reflow.py).  It
    contains NO IR logic — inclusion/exclusion, reading_order sorting, and
    text-source selection are already resolved by reflow_document.

    NOTE (IP-1 Open Risk): ``Placement`` (bbox_reflow.py) does not carry a
    source ``StyleInfo`` or an element reference — only element_id/bbox/text/
    reading_order. So this sub-path cannot thread a starting font or a
    render_truncated marker target; ``render_text_region`` degrades to the
    language FONT_SIZE_CONFIG max starting size and a log-only truncation
    notice on this path (a bounded, documented BR-38 gap — matches the
    pre-existing fitz legacy ``element=None`` behavior).

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


# ---------------------------------------------------------------------------
# grow_table_rows — bounded local row-growth pre-pass (BR-103, ADR-0013, AC-10)
# ---------------------------------------------------------------------------


def _shift_cell_down(cell: "TranslatableElement", dy: float) -> None:
    """Shift a table-cell element's bbox and metadata['lines'] whitening
    rects down by ``dy`` (points).  No-op for dy<=0.  Mutates in place.
    """
    if dy <= 0 or cell.bbox is None:
        return
    cell.bbox.y0 += dy
    cell.bbox.y1 += dy
    lines = cell.metadata.get("lines")
    if lines:
        cell.metadata["lines"] = [
            (ln[0], ln[1] + dy, ln[2], ln[3] + dy) for ln in lines
        ]


def _required_row_height(cell: "TranslatableElement") -> float:
    """Measure the vertical space ``cell``'s (untruncated) text needs at the
    cascade's settled font size, reusing fit_text_cascade/_wrap_lines_simple
    (ADR-0012) rather than duplicating fit logic."""
    text = cell.translated_content if cell.translated_content is not None else cell.content
    if not text or not str(text).strip() or cell.bbox is None:
        return 0.0
    decision = fit_text_cascade(text=text, bbox=cell.bbox, style=cell.style)
    font_name = (cell.style.font_name if cell.style else None) or "Helvetica"
    lines = _wrap_lines_simple(text, font_name, decision.font_size, cell.bbox.width)
    _, required_h = _measure_text_block(lines, font_name, decision.font_size, decision.line_spacing)
    return required_h


def grow_table_rows(document: "TranslatableDocument") -> None:
    """Bounded local table row-growth pre-pass (BR-103, ADR-0013, AC-10).

    Groups TABLE_CELL elements by ``(page_num, metadata["table_id"])`` then by
    ``metadata["table_row"]``.  For each row (in ascending row order), measures
    every cell's required height for its FULL (untruncated) translated text at
    the cascade's settled font size (``_required_row_height``, reusing the
    SAME ``fit_text_cascade``/``_wrap_lines_simple`` authority both renderer
    backends draw from — ADR-0012).  When the row max required height exceeds
    the row's current height, the row's cells grow (``y1 += delta``) and every
    LOWER row in the SAME table is shifted down by the cumulative delta — bbox
    AND ``metadata["lines"]`` whitening rects together (BR-84 parity) — so
    both PDF backends inherit the identical grown geometry from the one shared
    IR mutation point (BR-35/BR-40).

    Growth is capped at the table's remaining local page budget: the top of
    the first non-table element below the table on the same page, else the
    page bottom margin (``PDF_HEADER_FOOTER_MARGIN_PT``, reused).  A row whose
    required delta exceeds the remaining budget grows by the budget only; the
    residual falls through to the normal BR-36 cascade (shrink/truncate) at
    render time, surfaced by the BR-104 disclosure sweep.  Best-effort, never
    a new hard fit guarantee (ADR-0013).

    Elements without ``table_id``/``table_row`` metadata (table detection
    fully failed; no ``cell_grid``) are skipped entirely — those cells keep
    the existing cascade-only (shrink/truncate) behavior.

    Mutates ``document`` elements in place; returns ``None``.
    """
    elements_by_page: Dict[int, list] = {}
    for elem in document.elements:
        elements_by_page.setdefault(elem.page_num, []).append(elem)

    for page_num, page_elements in elements_by_page.items():
        page_info = next((p for p in document.pages if p.page_num == page_num), None)
        page_height = page_info.height if page_info is not None else None

        # Group TABLE_CELL elements with row/table metadata by table_id -> row.
        tables: Dict[Any, Dict[Any, list]] = {}
        for elem in page_elements:
            if elem.element_type != ElementType.TABLE_CELL or elem.bbox is None:
                continue
            table_id = elem.metadata.get("table_id")
            row = elem.metadata.get("table_row")
            if table_id is None or row is None:
                continue  # BR-103 no-metadata skip
            tables.setdefault(table_id, {}).setdefault(row, []).append(elem)

        for table_id, rows_by_index in tables.items():
            all_cells = [c for cells in rows_by_index.values() for c in cells]
            if not all_cells:
                continue
            table_bottom = max(c.bbox.y1 for c in all_cells)

            # Table's remaining local page budget (ADR-0013 step 4).
            below_others = [
                e for e in page_elements
                if e.bbox is not None
                and e.metadata.get("table_id") != table_id
                and e.bbox.y0 >= table_bottom - 0.01
            ]
            if below_others:
                budget_bottom = min(e.bbox.y0 for e in below_others)
            elif page_height is not None:
                budget_bottom = page_height - PDF_HEADER_FOOTER_MARGIN_PT
            else:
                budget_bottom = table_bottom  # no page info; no room to grow

            remaining_budget = max(0.0, budget_bottom - table_bottom)
            cumulative_delta = 0.0

            for row_idx in sorted(rows_by_index.keys()):
                row_cells = rows_by_index[row_idx]

                # Rows below an already-grown row inherit the cumulative shift
                # (both bbox and BR-84 whitening rects) before being measured.
                for cell in row_cells:
                    _shift_cell_down(cell, cumulative_delta)

                row_top = min(c.bbox.y0 for c in row_cells)
                row_bottom = max(c.bbox.y1 for c in row_cells)
                row_height = row_bottom - row_top
                row_required = max(_required_row_height(c) for c in row_cells)

                delta = row_required - row_height
                if delta <= 0 or remaining_budget <= 0:
                    continue

                applied_delta = min(delta, remaining_budget)
                remaining_budget -= applied_delta
                cumulative_delta += applied_delta

                for cell in row_cells:
                    cell.bbox.y1 += applied_delta
