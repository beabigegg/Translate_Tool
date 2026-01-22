"""Parsers module for document parsing."""

from __future__ import annotations

from app.backend.parsers.base import BaseParser
from app.backend.parsers.docx_parser import DocxParser
from app.backend.parsers.pdf_parser import PyMuPDFParser
from app.backend.parsers.pptx_parser import PptxParser

__all__ = [
    "BaseParser",
    "DocxParser",
    "PptxParser",
    "PyMuPDFParser",
]
