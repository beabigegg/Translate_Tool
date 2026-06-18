"""Backward-compatibility shim for pdf_generator (p2-renderer-convergence).

The canonical module is now ``app.backend.renderers.fitz_renderer``.
All public names are re-exported from there so that existing callers of
``app.backend.renderers.pdf_generator`` continue to work without change.

New code should import from ``fitz_renderer`` directly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

# Re-export everything from the canonical fitz primary renderer module.
from app.backend.renderers.fitz_renderer import (  # noqa: F401
    PDFGenerator,
    generate_translated_pdf,
    _ensure_fitz,
    _load_font_buffer,
    _get_lang_code,
    clear_font_cache,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableDocument
