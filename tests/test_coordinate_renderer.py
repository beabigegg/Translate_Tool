"""Tests for coordinate renderer."""

from __future__ import annotations

import os
import tempfile

import pytest

from app.backend.renderers.base import RenderMode
from app.backend.renderers.coordinate_renderer import (
    CoordinateRenderer,
    render_to_pdf,
)
from app.backend.models.translatable_document import (
    BoundingBox,
    DocumentMetadata,
    ElementType,
    PageInfo,
    TranslatableDocument,
    TranslatableElement,
)


def create_test_document() -> TranslatableDocument:
    """Create a test document with sample elements."""
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
            bbox=BoundingBox(x0=72, y0=120, x1=350, y1=140),
            should_translate=True,
        ),
        # Page 2
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
        source_path="/test/sample.pdf",
        source_type="pdf",
        elements=elements,
        pages=pages,
        metadata=DocumentMetadata(
            page_count=2,
            has_text_layer=True,
        ),
    )

    return doc


class TestCoordinateRenderer:
    """Tests for CoordinateRenderer class."""

    def test_init_default(self):
        """Test default initialization."""
        renderer = CoordinateRenderer()
        assert renderer.target_lang == "zh-TW"
        assert renderer.draw_background is True

    def test_init_custom(self):
        """Test custom initialization."""
        renderer = CoordinateRenderer(
            target_lang="ja",
            draw_background=False,
        )
        assert renderer.target_lang == "ja"
        assert renderer.draw_background is False

    def test_supported_modes(self):
        """Test supported rendering modes."""
        renderer = CoordinateRenderer()
        modes = renderer.supported_modes
        assert RenderMode.OVERLAY in modes
        assert RenderMode.SIDE_BY_SIDE in modes
        assert RenderMode.INLINE not in modes

    def test_output_extension(self):
        """Test output file extension."""
        renderer = CoordinateRenderer()
        assert renderer.output_extension == ".pdf"

    def test_render_overlay_mode(self):
        """Test rendering in overlay mode."""
        doc = create_test_document()
        translations = {
            "Hello World": "你好世界",
            "This is a test document": "這是一份測試文件",
            "Page two content": "第二頁內容",
        }

        renderer = CoordinateRenderer(target_lang="zh-TW")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(doc, output_path, translations, RenderMode.OVERLAY)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_side_by_side_mode(self):
        """Test rendering in side-by-side mode."""
        doc = create_test_document()
        translations = {
            "Hello World": "你好世界",
            "This is a test document": "這是一份測試文件",
            "Page two content": "第二頁內容",
        }

        renderer = CoordinateRenderer(target_lang="zh-TW")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(doc, output_path, translations, RenderMode.SIDE_BY_SIDE)
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_unsupported_mode(self):
        """Test that unsupported mode raises ValueError."""
        doc = create_test_document()
        translations = {"Hello World": "你好世界"}

        renderer = CoordinateRenderer()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            with pytest.raises(ValueError, match="does not support"):
                renderer.render(doc, output_path, translations, RenderMode.INLINE)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_empty_translations(self):
        """Test rendering with empty translations dict."""
        doc = create_test_document()
        translations = {}

        renderer = CoordinateRenderer()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            # Should not raise, just create PDF with no translated content
            renderer.render(doc, output_path, translations, RenderMode.OVERLAY)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_partial_translations(self):
        """Test rendering with partial translations."""
        doc = create_test_document()
        # Only translate some elements
        translations = {
            "Hello World": "你好世界",
            # "This is a test document" intentionally missing
        }

        renderer = CoordinateRenderer()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(doc, output_path, translations, RenderMode.OVERLAY)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_with_log_callback(self):
        """Test rendering with log callback."""
        doc = create_test_document()
        translations = {"Hello World": "你好世界"}

        log_messages = []
        renderer = CoordinateRenderer(log=log_messages.append)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(doc, output_path, translations, RenderMode.OVERLAY)
            # Should have logged messages
            assert len(log_messages) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_side_by_side_mode_wraps_long_text(self):
        """AC-1: side-by-side mode wraps long translated text across
        multiple lines within its bbox, not a single overflowing line
        (BR-40 shared cascade — this fallback path inherits wrap via
        render_text_region with zero per-path cascade duplication)."""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        long_translation = (
            "This is a considerably long piece of translated text that must "
            "wrap across multiple lines instead of overflowing horizontally "
            "past its narrow allotted column width no matter what."
        )
        elements = [
            TranslatableElement(
                element_id="e1",
                content="Short",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=100, x1=220, y1=200),
                should_translate=True,
            ),
        ]
        pages = [PageInfo(page_num=1, width=612, height=792)]
        doc = TranslatableDocument(
            source_path="/test/sample.pdf",
            source_type="pdf",
            elements=elements,
            pages=pages,
            metadata=DocumentMetadata(page_count=1, has_text_layer=True),
        )
        translations = {"Short": long_translation}
        renderer = CoordinateRenderer(target_lang="en")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(doc, output_path, translations, RenderMode.SIDE_BY_SIDE)

            result_doc = fitz.open(output_path)
            page_dict = result_doc[0].get_text("dict")
            original_width = pages[0].width
            line_ys = {
                round(line["bbox"][1], 1)
                for block in page_dict.get("blocks", [])
                for line in block.get("lines", [])
                if line["bbox"][0] >= original_width - 5
            }
            result_doc.close()

            assert len(line_ys) > 1, (
                "expected the long translation to wrap across multiple lines in "
                f"the right (translated) column, got {len(line_ys)} distinct line(s)"
            )
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_overlay_mode_fallback_wraps_long_text(self):
        """AC-2: overlay-mode fallback (used when fitz crashes, BR-34) wraps
        long translated text within its bbox identically to the side-by-side
        path (BR-40 shared cascade)."""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        long_translation = (
            "This is a considerably long piece of translated text that must "
            "wrap across multiple lines instead of overflowing horizontally "
            "past its narrow allotted column width no matter what."
        )
        # Overlay mode resolves text via reflow_document()/Placement (which
        # reads translated_content), not the `translations` dict argument —
        # so translated_content must be set directly on the element.
        elements = [
            TranslatableElement(
                element_id="e1",
                content="Short",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=300, x1=220, y1=400),
                should_translate=True,
                translated_content=long_translation,
            ),
        ]
        pages = [PageInfo(page_num=1, width=612, height=792)]
        doc = TranslatableDocument(
            source_path="/test/sample.pdf",
            source_type="pdf",
            elements=elements,
            pages=pages,
            metadata=DocumentMetadata(page_count=1, has_text_layer=True),
        )
        translations = {"Short": long_translation}
        renderer = CoordinateRenderer(target_lang="en")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(doc, output_path, translations, RenderMode.OVERLAY)

            result_doc = fitz.open(output_path)
            page_dict = result_doc[0].get_text("dict")
            line_ys = {
                round(line["bbox"][1], 1)
                for block in page_dict.get("blocks", [])
                for line in block.get("lines", [])
            }
            result_doc.close()

            assert len(line_ys) > 1, (
                f"expected the long translation to wrap across multiple lines, got {len(line_ys)}"
            )
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestRenderToPdf:
    """Tests for render_to_pdf convenience function."""

    def test_render_to_pdf_overlay(self):
        """Test convenience function with overlay mode."""
        doc = create_test_document()
        translations = {
            "Hello World": "你好世界",
            "This is a test document": "這是一份測試文件",
            "Page two content": "第二頁內容",
        }

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            render_to_pdf(doc, translations, output_path, mode="overlay", target_lang="zh-TW")
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_to_pdf_side_by_side(self):
        """Test convenience function with side_by_side mode."""
        doc = create_test_document()
        translations = {"Hello World": "你好世界"}

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            render_to_pdf(doc, translations, output_path, mode="side_by_side", target_lang="ja")
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_render_to_pdf_invalid_mode(self):
        """Test convenience function with invalid mode."""
        doc = create_test_document()
        translations = {"Hello World": "你好世界"}

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            with pytest.raises(ValueError):
                render_to_pdf(doc, translations, output_path, mode="invalid")
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestCoordinateRendererEdgeCases:
    """Edge case tests for CoordinateRenderer."""

    def test_document_without_pages_info(self):
        """Test rendering document without page info (uses default)."""
        elements = [
            TranslatableElement(
                element_id="e1",
                content="Test",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=72, x1=150, y1=92),
                should_translate=True,
            ),
        ]
        doc = TranslatableDocument(
            source_path="/test/sample.pdf",
            source_type="pdf",
            elements=elements,
            pages=[],  # No page info
            metadata=DocumentMetadata(
                page_count=1,
                has_text_layer=True,
            ),
        )

        translations = {"Test": "測試"}
        renderer = CoordinateRenderer()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(doc, output_path, translations, RenderMode.OVERLAY)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_elements_without_bbox(self):
        """Test that elements without bbox are handled gracefully."""
        elements = [
            TranslatableElement(
                element_id="e1",
                content="Has bbox",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=72, x1=150, y1=92),
                should_translate=True,
            ),
            TranslatableElement(
                element_id="e2",
                content="No bbox",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=None,  # No bbox
                should_translate=True,
            ),
        ]
        pages = [PageInfo(page_num=1, width=612, height=792)]
        doc = TranslatableDocument(
            source_path="/test/sample.pdf",
            source_type="pdf",
            elements=elements,
            pages=pages,
            metadata=DocumentMetadata(page_count=1, has_text_layer=True),
        )

        translations = {
            "Has bbox": "有邊界框",
            "No bbox": "無邊界框",
        }
        renderer = CoordinateRenderer()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            # Should not raise, just skip element without bbox
            renderer.render(doc, output_path, translations, RenderMode.OVERLAY)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_multipage_document(self):
        """Test rendering multi-page document."""
        elements = [
            TranslatableElement(
                element_id=f"e{i}",
                content=f"Page {i} content",
                element_type=ElementType.TEXT,
                page_num=i,
                bbox=BoundingBox(x0=72, y0=72, x1=200, y1=92),
                should_translate=True,
            )
            for i in range(1, 4)
        ]
        pages = [
            PageInfo(page_num=1, width=612, height=792),
            PageInfo(page_num=2, width=612, height=792),
            PageInfo(page_num=3, width=612, height=792),
        ]
        doc = TranslatableDocument(
            source_path="/test/sample.pdf",
            source_type="pdf",
            elements=elements,
            pages=pages,
            metadata=DocumentMetadata(page_count=3, has_text_layer=True),
        )

        translations = {
            "Page 1 content": "第一頁內容",
            "Page 2 content": "第二頁內容",
            "Page 3 content": "第三頁內容",
        }
        renderer = CoordinateRenderer()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(doc, output_path, translations, RenderMode.OVERLAY)
            assert os.path.exists(output_path)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_side_by_side_unfittable_text_sets_render_truncated(self):
        """AC-3: side-by-side mode sets render_truncated=True on the source
        element when translated text cannot fit even at floor size (BR-38),
        via the element ref threaded through the manually-built TextRegion."""
        elem = TranslatableElement(
            element_id="e1",
            content="short",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=72, x1=77, y1=77),  # 5x5pt — impossibly tiny
            should_translate=True,
        )
        doc = TranslatableDocument(
            source_path="/test/sample.pdf",
            source_type="pdf",
            elements=[elem],
            pages=[PageInfo(page_num=1, width=612, height=792)],
            metadata=DocumentMetadata(page_count=1, has_text_layer=True),
        )
        very_long = (
            "This is an extremely long piece of text that cannot possibly "
            "fit inside a five by five point box no matter what happens."
        )
        translations = {"short": very_long}
        renderer = CoordinateRenderer(target_lang="en")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            output_path = f.name

        try:
            renderer.render(doc, output_path, translations, RenderMode.SIDE_BY_SIDE)
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

        assert elem.render_truncated is True
