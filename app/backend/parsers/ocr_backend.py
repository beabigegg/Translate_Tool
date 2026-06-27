"""OCR backend seam for scanned PDF pages (pdf-layout-refactor, AC-7, D-7).

This module is a lazy-import OCR seam.  The OCR library (surya or paddleocr)
is imported inside ``run_ocr()`` — never at module top level — so CI passes
without any OCR library installed.  When the library is absent and
``OCR_ENABLED=True``, a WARNING is emitted and an empty list is returned.

Design constraints:
  - Never import OCR at module level (D-7 lazy seam).
  - When OCR is disabled or library absent: return [], never raise.
  - Caller (pdf_parser.py) routes near-empty pages here only when OCR_ENABLED=True.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableElement

logger = logging.getLogger(__name__)


def run_ocr(page) -> List:
    """Attempt OCR on a fitz page; return list of TranslatableElement (or []).

    The OCR library (surya preferred; paddleocr fallback) is imported lazily.
    When the library is absent, a WARNING is logged and [] is returned — the
    caller must treat [] as "no text recovered from OCR".

    Args:
        page: PyMuPDF page object to rasterise and run OCR on.

    Returns:
        List of TranslatableElement for OCR-recovered text, or [] on any error.
    """
    try:
        # Try surya (pure-Python, preferred)
        import surya  # type: ignore[import]
        return _run_with_surya(page)
    except (ImportError, TypeError):
        pass  # surya not installed; try paddleocr

    try:
        import paddleocr  # type: ignore[import]
        return _run_with_paddleocr(page)
    except (ImportError, TypeError):
        pass  # paddleocr not installed either

    # Neither library available
    logger.warning(
        "OCR library not installed (tried surya, paddleocr); "
        "OCR_ENABLED=True has no effect for this page. "
        "Install surya (pip install surya-ocr) or paddleocr to enable OCR."
    )
    return []


def _run_with_surya(page) -> List:
    """Run OCR using surya; return [] (placeholder — surya integration TBD)."""
    # Placeholder: surya requires its own pipeline setup.
    # Returns [] until the real surya pipeline is wired (AC-7 seam, not full impl).
    logger.debug("surya OCR seam called (placeholder; no elements returned)")
    return []


def _run_with_paddleocr(page) -> List:
    """Run OCR using paddleocr; return [] (placeholder — paddleocr integration TBD)."""
    logger.debug("paddleocr OCR seam called (placeholder; no elements returned)")
    return []
