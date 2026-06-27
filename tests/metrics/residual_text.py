"""Residual-text detection metric for layout fidelity evaluation.

Public API
----------
check_residual_text(page, whiteover_bboxes) -> list[dict]
    Return a record for each whiteover bbox region that still contains text.

The ``page`` argument is duck-typed — any object implementing
``get_text(mode, clip=...)`` works (e.g. a fitz.Page or a test stub).
fitz is NOT imported at module level.
"""


def check_residual_text(page, whiteover_bboxes: list) -> list:
    """Detect text that remains visible inside white-over bounding-box regions.

    For each bbox in *whiteover_bboxes*, queries ``page.get_text("blocks",
    clip=(bbox.x0, bbox.y0, bbox.x1, bbox.y1))``.  If any text blocks are
    returned, a record is appended to the result list.

    Parameters
    ----------
    page:
        A page object with a ``get_text(mode, clip=...)`` method.
    whiteover_bboxes:
        Iterable of bbox objects with x0, y0, x1, y1 attributes.

    Returns
    -------
    list of dict
        Each dict has keys ``bbox``, ``text``, and ``blocks``.
        Empty list when no residual text is found.
    """
    records = []
    for bbox in whiteover_bboxes:
        blocks = page.get_text("blocks", clip=(bbox.x0, bbox.y0, bbox.x1, bbox.y1))
        if blocks:
            text = " ".join(b[4] for b in blocks if len(b) > 4)
            records.append({"bbox": bbox, "text": text, "blocks": blocks})
    return records
