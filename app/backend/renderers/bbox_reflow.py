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
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableDocument

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


def reflow_element(element) -> Optional[Placement]:
    """Produce a backend-neutral Placement for a single IR element.

    Parameters
    ----------
    element : TranslatableElement-compatible object
        Must expose: element_id, content, element_type, page_num, bbox,
        should_translate, translated_content, reading_order.
        element_type may be an ElementType enum member OR a raw string
        (future/unknown values are treated as "text", never raise).

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

    return Placement(
        element_id=element.element_id,
        page_num=element.page_num,
        x0=element.bbox.x0,
        y0=element.bbox.y0,
        x1=element.bbox.x1,
        y1=element.bbox.y1,
        text=text,
        reading_order=reading_order,
    )


def reflow_document(document: "TranslatableDocument") -> List[Placement]:
    """Produce ordered Placement list for an entire TranslatableDocument.

    Elements are processed in reading_order (ascending), with positional
    fallback (page_num, y0, x0) for elements where reading_order is None.
    Elements with null bbox or should_translate=False are excluded from the
    result; no exception is raised for them.

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

    placements: List[Placement] = []
    for elem in ordered_elements:
        p = reflow_element(elem)
        if p is not None:
            placements.append(p)

    return placements
