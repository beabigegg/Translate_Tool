"""Renderers module for document output generation."""

from __future__ import annotations

from app.backend.renderers.base import BaseRenderer, RenderMode
from app.backend.renderers.coordinate_renderer import CoordinateRenderer
from app.backend.renderers.inline_renderer import InlineRenderer
from app.backend.renderers.fitz_renderer import PDFGenerator  # canonical; pdf_generator is shim

__all__ = [
    "BaseRenderer",
    "CoordinateRenderer",
    "InlineRenderer",
    "PDFGenerator",
    "RenderMode",
]
