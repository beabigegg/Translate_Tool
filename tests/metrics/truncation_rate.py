"""Truncation-rate metric — re-export shim.

The implementation moved to ``app/backend/services/layout_qa.py`` when the
metric was promoted to a runtime component (post-render layout QA). This shim
keeps the historical import path (and the ci-gate-contract pytest commands)
working.
"""

from app.backend.services.layout_qa import compute_truncation_rate  # noqa: F401
