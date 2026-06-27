"""Bounding-box IoU (BIoU) metric for layout fidelity evaluation.

Public API
----------
BIOU_REGRESSION_BUDGET : float
    Minimum acceptable mean BIoU score (0.8).
compute_biou(source_bboxes, rendered_bboxes) -> float
    Mean of per-source best-match IoU across all rendered bboxes.

No third-party imports: stdlib only.
Duck-typed inputs: any object with x0, y0, x1, y1 float attributes.
"""

BIOU_REGRESSION_BUDGET: float = 0.8


def _iou(a, b) -> float:
    """Compute IoU between two bounding boxes (duck-typed x0/y0/x1/y1)."""
    inter_x = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    inter_y = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    intersection = inter_x * inter_y
    area_a = (a.x1 - a.x0) * (a.y1 - a.y0)
    area_b = (b.x1 - b.x0) * (b.y1 - b.y0)
    union = area_a + area_b - intersection
    if union == 0.0:
        return 0.0
    return intersection / union


def compute_biou(source_bboxes: list, rendered_bboxes: list) -> float:
    """Return mean best-match IoU for each source bbox against rendered bboxes.

    For each source bbox, find the rendered bbox with the highest IoU.
    Return the mean of those per-source best-match scores.

    Returns 0.0 when either list is empty.
    """
    if not source_bboxes or not rendered_bboxes:
        return 0.0

    total = 0.0
    for src in source_bboxes:
        best = max(_iou(src, rnd) for rnd in rendered_bboxes)
        total += best
    return total / len(source_bboxes)
