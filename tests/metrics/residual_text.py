"""Residual-text detection metric for layout fidelity evaluation.

Re-export shim (layout-qa-safety-net, ADR-0015): the implementation now lives
in ``app.backend.services.layout_qa`` (single source of truth shared by the
runtime layout-QA safety net and this CI-gate test harness).
"""

from app.backend.services.layout_qa import check_residual_text  # noqa: F401  (re-export)
