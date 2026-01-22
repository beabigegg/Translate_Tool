"""Tests for PDF generator."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from app.backend.renderers.base import RenderMode
from app.backend.renderers.pdf_generator import (
    PDFGenerator,
    generate_translated_pdf,
    _ensure_fitz,
)
from app.backend.models.translatable_document import (
    BoundingBox,
    DocumentMetadata,
    ElementType,
    PageInfo,
    TranslatableDocument,
    TranslatableElement,
)


# Check if PyMuPDF is available
try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


def create_test_pdf() -> str:
    """Create a test PDF file and return its path."""
    if not HAS_PYMUPDF:
        pytest.skip("PyMuPDF not installed")

    # Create a simple PDF
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Hello World", fontsize=12)
    page.insert_text((72, 100), "This is a test document", fontsize=12)

    # Add second page
    page2 = doc.new_page(width=612, height=792)
    page2.insert_text((72, 72), "Page two content", fontsize=12)

    # Save to temp file
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(path)
    doc.close()

    return path


def create_test_document(pdf_path: str) -> TranslatableDocument:
    """Create a test TranslatableDocument pointing to the given PDF."""
    elements = [
        TranslatableElement(
            element_id="e1",
            content="Hello World",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=72, x1=200, y1=92),
            should_translate=True,
        ),
        TranslatableElement(
            element_id="e2",
            content="This is a test document",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=100, x1=350, y1=120),
            should_translate=True,
        ),
        TranslatableElement(
            element_id="e3",
            content="Page two content",
            element_type=ElementType.TEXT,
            page_num=2,
            bbox=BoundingBox(x0=72, y0=72, x1=250, y1=92),
            should_translate=True,
        ),
    ]

    pages = [
        PageInfo(page_num=1, width=612, height=792),
        PageInfo(page_num=2, width=612, height=792),
    ]

    doc = TranslatableDocument(
        source_path=pdf_path,
        source_type="pdf",
        elements=elements,
        pages=pages,
        metadata=DocumentMetadata(
            page_count=2,
            has_text_layer=True,
        ),
    )

    return doc


@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
class TestEnsureFitz:
    """Tests for _ensure_fitz function."""

    def test_ensure_fitz_returns_module(self):
        """Test that _ensure_fitz returns the fitz module."""
        result = _ensure_fitz()
        assert result is not None
        assert hasattr(result, "open")


@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
class TestPDFGenerator:
    """Tests for PDFGenerator class."""

    def test_init_default(self):
        """Test default initialization."""
        generator = PDFGenerator()
        assert generator.target_lang == "zh-TW"
        assert generator.draw_mask is True

    def test_init_custom(self):
        """Test custom initialization."""
        generator = PDFGenerator(
            target_lang="ja",
            draw_mask=False,
        )
        assert generator.target_lang == "ja"
        assert generator.draw_mask is False

    def test_generate_overlay_mode(self):
        """Test generating PDF in overlay mode."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {
                "Hello World": "你好世界",
                "This is a test document": "這是一份測試文件",
                "Page two content": "第二頁內容",
            }

            generator = PDFGenerator(target_lang="zh-TW")

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generator.generate(doc, translations, output_path, RenderMode.OVERLAY)
                assert os.path.exists(output_path)
                assert os.path.getsize(output_path) > 0

                # Verify it's a valid PDF
                out_doc = fitz.open(output_path)
                assert len(out_doc) == 2  # Should have 2 pages
                out_doc.close()
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_generate_side_by_side_mode(self):
        """Test generating PDF in side-by-side mode."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {
                "Hello World": "你好世界",
                "This is a test document": "這是一份測試文件",
                "Page two content": "第二頁內容",
            }

            generator = PDFGenerator(target_lang="zh-TW")

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generator.generate(doc, translations, output_path, RenderMode.SIDE_BY_SIDE)
                assert os.path.exists(output_path)
                assert os.path.getsize(output_path) > 0

                # Verify it's a valid PDF with double-width pages
                out_doc = fitz.open(output_path)
                assert len(out_doc) == 2
                # Side-by-side should have double width
                page = out_doc[0]
                assert page.rect.width > 612  # Should be roughly 2x original
                out_doc.close()
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_generate_inline_mode_raises(self):
        """Test that INLINE mode raises ValueError."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {"Hello World": "你好世界"}

            generator = PDFGenerator()

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                with pytest.raises(ValueError, match="does not support INLINE"):
                    generator.generate(doc, translations, output_path, RenderMode.INLINE)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_generate_source_not_found(self):
        """Test that missing source file raises FileNotFoundError."""
        doc = TranslatableDocument(
            source_path="/nonexistent/file.pdf",
            source_type="pdf",
            elements=[],
            pages=[],
            metadata=DocumentMetadata(page_count=1, has_text_layer=True),
        )
        translations = {}

        generator = PDFGenerator()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            with pytest.raises(FileNotFoundError):
                generator.generate(doc, translations, output_path, RenderMode.OVERLAY)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_generate_with_log_callback(self):
        """Test generation with log callback."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {"Hello World": "你好世界"}

            log_messages = []
            generator = PDFGenerator(log=log_messages.append)

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generator.generate(doc, translations, output_path, RenderMode.OVERLAY)
                # Should have logged messages
                assert len(log_messages) > 0
                assert any("overlay" in msg.lower() for msg in log_messages)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_generate_empty_translations(self):
        """Test generation with empty translations."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {}

            generator = PDFGenerator()

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                # Should not raise, just create PDF with no overlays
                generator.generate(doc, translations, output_path, RenderMode.OVERLAY)
                assert os.path.exists(output_path)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_generate_partial_translations(self):
        """Test generation with partial translations."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            # Only translate some elements
            translations = {
                "Hello World": "你好世界",
                # "This is a test document" intentionally missing
            }

            generator = PDFGenerator()

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generator.generate(doc, translations, output_path, RenderMode.OVERLAY)
                assert os.path.exists(output_path)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_generate_without_mask(self):
        """Test generation without drawing mask."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {"Hello World": "你好世界"}

            generator = PDFGenerator(draw_mask=False)

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generator.generate(doc, translations, output_path, RenderMode.OVERLAY)
                assert os.path.exists(output_path)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)


@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
class TestGenerateTranslatedPdf:
    """Tests for generate_translated_pdf convenience function."""

    def test_generate_translated_pdf_overlay(self):
        """Test convenience function with overlay mode."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {
                "Hello World": "你好世界",
                "This is a test document": "這是一份測試文件",
                "Page two content": "第二頁內容",
            }

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generate_translated_pdf(
                    doc, translations, output_path,
                    mode="overlay",
                    target_lang="zh-TW",
                )
                assert os.path.exists(output_path)
                assert os.path.getsize(output_path) > 0
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_generate_translated_pdf_side_by_side(self):
        """Test convenience function with side_by_side mode."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {"Hello World": "你好世界"}

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generate_translated_pdf(
                    doc, translations, output_path,
                    mode="side_by_side",
                    target_lang="ja",
                )
                assert os.path.exists(output_path)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_generate_translated_pdf_invalid_mode(self):
        """Test convenience function with invalid mode."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {"Hello World": "你好世界"}

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                with pytest.raises(ValueError):
                    generate_translated_pdf(
                        doc, translations, output_path,
                        mode="invalid_mode",
                    )
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_generate_translated_pdf_with_log(self):
        """Test convenience function with log callback."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {"Hello World": "你好世界"}

            log_messages = []

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generate_translated_pdf(
                    doc, translations, output_path,
                    mode="overlay",
                    log=log_messages.append,
                )
                assert len(log_messages) > 0
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)


@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
class TestPDFGeneratorEdgeCases:
    """Edge case tests for PDFGenerator."""

    def test_page_with_no_elements(self):
        """Test handling page with no translatable elements."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            # Remove all elements
            doc.elements = []
            translations = {}

            generator = PDFGenerator()

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generator.generate(doc, translations, output_path, RenderMode.OVERLAY)
                assert os.path.exists(output_path)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_elements_on_second_page_only(self):
        """Test document with elements only on second page."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            # Keep only second page elements
            doc.elements = [e for e in doc.elements if e.page_num == 2]
            translations = {"Page two content": "第二頁內容"}

            generator = PDFGenerator()

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generator.generate(doc, translations, output_path, RenderMode.OVERLAY)
                assert os.path.exists(output_path)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_multiline_text(self):
        """Test handling multiline text content."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            # Add element with multiline content
            doc.elements.append(
                TranslatableElement(
                    element_id="e4",
                    content="Line 1\nLine 2\nLine 3",
                    element_type=ElementType.TEXT,
                    page_num=1,
                    bbox=BoundingBox(x0=72, y0=150, x1=300, y1=200),
                    should_translate=True,
                )
            )
            translations = {
                "Hello World": "你好世界",
                "This is a test document": "這是一份測試文件",
                "Page two content": "第二頁內容",
                "Line 1\nLine 2\nLine 3": "第一行\n第二行\n第三行",
            }

            generator = PDFGenerator()

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generator.generate(doc, translations, output_path, RenderMode.OVERLAY)
                assert os.path.exists(output_path)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_different_target_languages(self):
        """Test generation with different target languages."""
        pdf_path = create_test_pdf()
        try:
            doc = create_test_document(pdf_path)
            translations = {"Hello World": "こんにちは世界"}  # Japanese

            generator = PDFGenerator(target_lang="ja")

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                generator.generate(doc, translations, output_path, RenderMode.OVERLAY)
                assert os.path.exists(output_path)
            finally:
                if os.path.exists(output_path):
                    os.unlink(output_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)
