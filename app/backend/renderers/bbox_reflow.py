"""Shared IR-bbox reflow component for PDF rendering (p2-renderer-convergence).

This module is the single source of element-placement logic consumed by both
the fitz primary renderer and the ReportLab fallback renderer, ensuring BR-35
(identical element-level decisions on both paths).

No fitz or ReportLab imports are present; this is backend-neutral IR→placement
logic that reuses `utils/bbox_utils` geometry primitives only.

Contract (data-shape-contract.md § Renderer IR-consumption contract):
  - bbox is null  → skip (return None); no raise.
  - reading_order is null → positional sort fallback (page_num, y0, x0); no raise.
  - element_type is unknown string → treat as text; no raise; no skip.
  - translated_content is null → use content as fallback; no raise.
  - should_translate is False → skip (return None).
  - elements list empty → empty placements; no raise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional

from app.backend.models.translatable_document import ElementType

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableDocument, TranslatableElement

# Known non-translatable region-level ElementType string values.
# These are the region containers that parsers mark as should_translate=False.
# The reflow component respects should_translate; this set is kept for
# documentation purposes only — the actual skip gate is should_translate.
_REGION_TYPES = frozenset({"table", "figure", "formula", "list"})


@dataclass(frozen=True, eq=True)
class Placement:
    """Backend-neutral placement decision produced by bbox_reflow.

    Carries the IR bbox coordinates, resolved text, element identity, and
    reading_order so both the fitz and ReportLab adapters can operate from
    an identical placement sequence.
    """

    element_id: str
    page_num: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    reading_order: Optional[int]
    # AC-9/BR-36 note: real vertical whitespace below this placement (points),
    # computed once here (not re-derived per renderer — BR-40/ADR-0012) and
    # consumed by fit_text_cascade's controlled-overflow step (d).  Additive
    # field with a default so existing Placement(...) call sites stay green.
    available_whitespace_below: float = 0.0


def _x_ranges_overlap(a: "TranslatableElement", b: "TranslatableElement") -> bool:
    """True when a's and b's bbox x-ranges overlap (not merely touch)."""
    return max(a.bbox.x0, b.bbox.x0) < min(a.bbox.x1, b.bbox.x1)


def _compute_whitespace_below(
    element: "TranslatableElement",
    page_elements: List["TranslatableElement"],
    page_height: Optional[float],
) -> float:
    """Real available vertical whitespace below ``element`` on its page (AC-9).

    - TABLE_CELL: distance from this cell's y1 to the nearest y0 of the next
      row in the SAME table_id/table_col; else the page bottom margin (the
      cell is effectively at the table's bottom edge when no same-column
      neighbor exists below it); else 0.0 when page geometry is unknown.
    - Non-table element: distance to the next element below whose x-range
      overlaps this one; no horizontal collision → no constraint (0.0).

    Never raises; degenerate/missing geometry degrades to 0.0 (BR-36 Table L
    "step d: adjacent whitespace not available").
    """
    if element.bbox is None:
        return 0.0

    if element.element_type == ElementType.TABLE_CELL:
        table_id = element.metadata.get("table_id")
        table_col = element.metadata.get("table_col")
        candidates = [
            other.bbox.y0
            for other in page_elements
            if other is not element
            and other.bbox is not None
            and other.metadata.get("table_id") == table_id
            and other.metadata.get("table_col") == table_col
            and other.bbox.y0 >= element.bbox.y1 - 0.01
        ]
        if candidates:
            return max(0.0, min(candidates) - element.bbox.y1)
        if page_height is not None:
            return max(0.0, page_height - element.bbox.y1)
        return 0.0

    candidates = [
        other.bbox.y0
        for other in page_elements
        if other is not element
        and other.bbox is not None
        and other.bbox.y0 >= element.bbox.y1 - 0.01
        and _x_ranges_overlap(element, other)
    ]
    if candidates:
        return max(0.0, min(candidates) - element.bbox.y1)
    return 0.0


def reflow_element(
    element,
    page_elements: Optional[List["TranslatableElement"]] = None,
    page_height: Optional[float] = None,
) -> Optional[Placement]:
    """Produce a backend-neutral Placement for a single IR element.

    Parameters
    ----------
    element : TranslatableElement-compatible object
        Must expose: element_id, content, element_type, page_num, bbox,
        should_translate, translated_content, reading_order.
        element_type may be an ElementType enum member OR a raw string
        (future/unknown values are treated as "text", never raise).
    page_elements : optional list of sibling elements on the same page.
        When provided, used to compute ``available_whitespace_below`` (AC-9);
        when omitted (the default), the field stays at its 0.0 default —
        this keeps ``reflow_element(elem)`` backward-compatible for callers
        that only need placement, not whitespace geometry.
    page_height : optional page height (points), for the TABLE_CELL
        page-bottom-margin fallback when no same-column neighbor exists.

    Returns
    -------
    Placement | None
        None if the element should be skipped (null bbox, should_translate=False).
        A Placement instance otherwise.

    Contract
    --------
    - null bbox → return None (skip); no raise.
    - should_translate=False → return None (skip); no raise.
    - null translated_content → use content as fallback; no raise.
    - unknown element_type → treat as text (passthrough); no raise; no skip.
    """
    # Skip gate 1: no bbox → cannot place; contract mandates skip, not raise.
    if element.bbox is None:
        return None

    # Skip gate 2: element is not translatable.
    if not element.should_translate:
        return None

    # Resolve text: use translated_content if present, fall back to content.
    text = element.translated_content if element.translated_content is not None else element.content

    # Resolve reading_order: may be None (handled by reflow_document sort).
    reading_order = getattr(element, "reading_order", None)

    gap = 0.0
    if page_elements is not None:
        gap = _compute_whitespace_below(element, page_elements, page_height)

    return Placement(
        element_id=element.element_id,
        page_num=element.page_num,
        x0=element.bbox.x0,
        y0=element.bbox.y0,
        x1=element.bbox.x1,
        y1=element.bbox.y1,
        text=text,
        reading_order=reading_order,
        available_whitespace_below=gap,
    )


def reflow_document(document: "TranslatableDocument") -> List[Placement]:
    """Produce ordered Placement list for an entire TranslatableDocument.

    Elements are processed in reading_order (ascending), with positional
    fallback (page_num, y0, x0) for elements where reading_order is None.
    Elements with null bbox or should_translate=False are excluded from the
    result; no exception is raised for them.

    AC-9/BR-36 note: elements are grouped by page (once) so
    ``available_whitespace_below`` can be computed from real sibling
    geometry — this is the "page-grouping" this component previously lacked
    (it was element-at-a-time); the existing ordering/skip contract above is
    unchanged.

    Parameters
    ----------
    document : TranslatableDocument
        The IR document to process.

    Returns
    -------
    List[Placement]
        Ordered list of Placement objects ready for rendering.  An empty
        document produces an empty list; no exception is raised.
    """
    # Use the document's own authoritative reading-order sort.
    ordered_elements = document.get_elements_in_reading_order()

    elements_by_page: Dict[int, List["TranslatableElement"]] = {}
    for elem in document.elements:
        elements_by_page.setdefault(elem.page_num, []).append(elem)
    page_heights: Dict[int, float] = {p.page_num: p.height for p in document.pages}

    placements: List[Placement] = []
    for elem in ordered_elements:
        page_elems = elements_by_page.get(elem.page_num, [])
        page_height = page_heights.get(elem.page_num)
        p = reflow_element(elem, page_elements=page_elems, page_height=page_height)
        if p is not None:
            placements.append(p)

    return placements
