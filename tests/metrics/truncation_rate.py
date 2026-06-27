"""Truncation-rate metric for layout fidelity evaluation.

Public API
----------
compute_truncation_rate(elements) -> dict
    Returns count, total, ratio, and overflow_area_sum for truncated elements.

Duck-typed inputs: elements must have ``render_truncated`` (bool) and
``metadata`` (dict, may be absent) attributes.  ``bbox`` may be None.
"""


def compute_truncation_rate(elements: list) -> dict:
    """Compute the truncation rate across a list of translatable elements.

    Parameters
    ----------
    elements:
        Iterable of element objects.  Each must have:
        - ``render_truncated`` (bool)
        - ``metadata`` (dict, optional via .get)
        - ``bbox`` (may be None; does not affect counting)

    Returns
    -------
    dict with keys:
        count             -- number of elements where render_truncated is True
        total             -- total number of elements
        ratio             -- count / total (0.0 when total == 0)
        overflow_area_sum -- sum of metadata["overflow_area"] for truncated elements
    """
    total = len(elements)
    count = 0
    overflow_area_sum = 0.0

    for el in elements:
        if el.render_truncated:
            count += 1
            overflow_area_sum += getattr(el, "metadata", {}).get("overflow_area", 0.0)

    ratio = count / total if total > 0 else 0.0

    return {
        "count": count,
        "total": total,
        "ratio": ratio,
        "overflow_area_sum": overflow_area_sum,
    }
