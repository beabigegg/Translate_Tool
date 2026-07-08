"""Bounding-box IoU (BIoU) metric for layout fidelity evaluation.

Re-export shim (layout-qa-safety-net, ADR-0015): the implementation now lives
in ``app.backend.services.layout_qa`` (single source of truth shared by the
runtime layout-QA safety net and this CI-gate test harness). This module
re-exports every public name -- including the private ``_iou`` and the
``BIOU_REGRESSION_BUDGET`` constant -- so existing ``tests.metrics.biou``
import sites (e.g. ``tests/test_layout_metrics.py``) keep working unchanged.
"""

from app.backend.services.layout_qa import (  # noqa: F401  (re-export)
    BIOU_REGRESSION_BUDGET,
    _iou,
    compute_biou,
)
