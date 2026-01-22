"""Bounding box utility functions.

This module provides utility functions for working with bounding boxes,
including normalization, overlap calculation, and containment checks.
"""

from __future__ import annotations

from typing import List, Tuple

from app.backend.models.translatable_document import BoundingBox


def normalize_bbox(
    bbox: Tuple[float, float, float, float],
    page_height: float,
    from_pdf_coords: bool = True,
) -> BoundingBox:
    """Normalize bbox to internal coordinate system.

    Internal coordinate system: top-left origin, x right, y down, unit points.

    Args:
        bbox: (x0, y0, x1, y1) coordinates.
        page_height: Page height in points (needed for PDF coordinate conversion).
        from_pdf_coords: If True, convert from PDF coords (bottom-left origin).

    Returns:
        Normalized BoundingBox.
    """
    x0, y0, x1, y1 = bbox

    if from_pdf_coords:
        # PDF coordinates: origin at bottom-left, y increases upward
        # Convert to: origin at top-left, y increases downward
        y0_new = page_height - y1
        y1_new = page_height - y0
        y0, y1 = y0_new, y1_new

    # Ensure x0 < x1 and y0 < y1
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0

    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def calculate_iou(bbox1: BoundingBox, bbox2: BoundingBox) -> float:
    """Calculate Intersection over Union (IoU) between two bboxes.

    Args:
        bbox1: First bounding box.
        bbox2: Second bounding box.

    Returns:
        IoU value between 0 and 1.
    """
    # Calculate intersection
    x0_inter = max(bbox1.x0, bbox2.x0)
    y0_inter = max(bbox1.y0, bbox2.y0)
    x1_inter = min(bbox1.x1, bbox2.x1)
    y1_inter = min(bbox1.y1, bbox2.y1)

    if x0_inter >= x1_inter or y0_inter >= y1_inter:
        return 0.0

    intersection_area = (x1_inter - x0_inter) * (y1_inter - y0_inter)

    # Calculate union
    area1 = bbox1.width * bbox1.height
    area2 = bbox2.width * bbox2.height
    union_area = area1 + area2 - intersection_area

    if union_area <= 0:
        return 0.0

    return intersection_area / union_area


def is_bbox_inside(inner: BoundingBox, outer: BoundingBox, tolerance: float = 0.0) -> bool:
    """Check if inner bbox is contained within outer bbox.

    Args:
        inner: The potentially contained bbox.
        outer: The potentially containing bbox.
        tolerance: Allow this much overhang in points.

    Returns:
        True if inner is inside outer (within tolerance).
    """
    return (
        inner.x0 >= outer.x0 - tolerance
        and inner.y0 >= outer.y0 - tolerance
        and inner.x1 <= outer.x1 + tolerance
        and inner.y1 <= outer.y1 + tolerance
    )


def merge_bboxes(bboxes: List[BoundingBox]) -> BoundingBox:
    """Merge multiple bboxes into one encompassing bbox.

    Args:
        bboxes: List of bounding boxes to merge.

    Returns:
        A single bbox that encompasses all input bboxes.

    Raises:
        ValueError: If bboxes list is empty.
    """
    if not bboxes:
        raise ValueError("Cannot merge empty list of bboxes")

    x0 = min(b.x0 for b in bboxes)
    y0 = min(b.y0 for b in bboxes)
    x1 = max(b.x1 for b in bboxes)
    y1 = max(b.y1 for b in bboxes)

    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def bbox_distance(bbox1: BoundingBox, bbox2: BoundingBox) -> float:
    """Calculate minimum distance between two bboxes.

    Args:
        bbox1: First bounding box.
        bbox2: Second bounding box.

    Returns:
        Minimum distance in points (0 if overlapping).
    """
    # Calculate horizontal distance
    if bbox1.x1 < bbox2.x0:
        dx = bbox2.x0 - bbox1.x1
    elif bbox2.x1 < bbox1.x0:
        dx = bbox1.x0 - bbox2.x1
    else:
        dx = 0

    # Calculate vertical distance
    if bbox1.y1 < bbox2.y0:
        dy = bbox2.y0 - bbox1.y1
    elif bbox2.y1 < bbox1.y0:
        dy = bbox1.y0 - bbox2.y1
    else:
        dy = 0

    return (dx**2 + dy**2) ** 0.5


def is_header_footer_region(
    bbox: BoundingBox,
    page_height: float,
    margin_pt: float = 50.0,
) -> Tuple[bool, str]:
    """Check if bbox is in header or footer region.

    Args:
        bbox: The bounding box to check.
        page_height: Page height in points.
        margin_pt: Margin size in points for header/footer detection.

    Returns:
        Tuple of (is_header_or_footer, region_type).
        region_type is "header", "footer", or "body".
    """
    if bbox.y0 < margin_pt:
        return True, "header"
    if bbox.y1 > page_height - margin_pt:
        return True, "footer"
    return False, "body"


def sort_bboxes_by_reading_order(
    bboxes: List[BoundingBox],
    column_threshold: float = 50.0,
) -> List[int]:
    """Sort bboxes by reading order (top-to-bottom, left-to-right).

    Uses a simple heuristic: group by horizontal position first (columns),
    then sort by vertical position within each column.

    Args:
        bboxes: List of bounding boxes.
        column_threshold: Horizontal distance threshold for column grouping.

    Returns:
        List of indices in reading order.
    """
    if not bboxes:
        return []

    # Simple sorting: primarily by y0, secondarily by x0
    # This works for single-column and simple multi-column layouts
    indexed_bboxes = list(enumerate(bboxes))

    def sort_key(item: Tuple[int, BoundingBox]) -> Tuple[float, float]:
        _, bbox = item
        # Round y0 to group elements on the same "line"
        y_rounded = round(bbox.y0 / 10) * 10
        return (y_rounded, bbox.x0)

    indexed_bboxes.sort(key=sort_key)

    return [idx for idx, _ in indexed_bboxes]
