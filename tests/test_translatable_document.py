"""Tests for TranslatableDocument and related models."""

from __future__ import annotations

import pytest

from app.backend.models.translatable_document import (
    BoundingBox,
    DocumentMetadata,
    ElementType,
    PageInfo,
    StyleInfo,
    TranslatableDocument,
    TranslatableElement,
)


class TestBoundingBox:
    """Tests for BoundingBox dataclass."""

    def test_basic_properties(self):
        """Test width, height, center calculations."""
        bbox = BoundingBox(x0=10, y0=20, x1=110, y1=70)

        assert bbox.width == 100
        assert bbox.height == 50
        assert bbox.center_x == 60
        assert bbox.center_y == 45

    def test_to_dict(self):
        """Test serialization to dictionary."""
        bbox = BoundingBox(x0=10, y0=20, x1=110, y1=70)
        d = bbox.to_dict()

        assert d == {"x0": 10, "y0": 20, "x1": 110, "y1": 70}

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        d = {"x0": 10, "y0": 20, "x1": 110, "y1": 70}
        bbox = BoundingBox.from_dict(d)

        assert bbox.x0 == 10
        assert bbox.y0 == 20
        assert bbox.x1 == 110
        assert bbox.y1 == 70

    def test_from_tuple(self):
        """Test creation from tuple."""
        bbox = BoundingBox.from_tuple((10, 20, 110, 70))

        assert bbox.x0 == 10
        assert bbox.y0 == 20
        assert bbox.x1 == 110
        assert bbox.y1 == 70

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = BoundingBox(x0=10.5, y0=20.5, x1=110.5, y1=70.5)
        restored = BoundingBox.from_dict(original.to_dict())

        assert original == restored


class TestStyleInfo:
    """Tests for StyleInfo dataclass."""

    def test_default_values(self):
        """Test default style values."""
        style = StyleInfo()

        assert style.font_name is None
        assert style.font_size is None
        assert style.is_bold is False
        assert style.is_italic is False
        assert style.color is None

    def test_with_values(self):
        """Test style with explicit values."""
        style = StyleInfo(
            font_name="Arial",
            font_size=12.0,
            is_bold=True,
            is_italic=False,
            color="#FF0000",
        )

        assert style.font_name == "Arial"
        assert style.font_size == 12.0
        assert style.is_bold is True
        assert style.color == "#FF0000"

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = StyleInfo(
            font_name="Times",
            font_size=14.0,
            is_bold=True,
            is_italic=True,
            color="#000000",
        )
        restored = StyleInfo.from_dict(original.to_dict())

        assert original.font_name == restored.font_name
        assert original.font_size == restored.font_size
        assert original.is_bold == restored.is_bold
        assert original.is_italic == restored.is_italic


class TestTranslatableElement:
    """Tests for TranslatableElement dataclass."""

    def test_basic_element(self):
        """Test creating a basic element."""
        element = TranslatableElement(
            element_id="p1_b0_abc123",
            content="Hello world",
            element_type=ElementType.TEXT,
            page_num=1,
        )

        assert element.element_id == "p1_b0_abc123"
        assert element.content == "Hello world"
        assert element.element_type == ElementType.TEXT
        assert element.page_num == 1
        assert element.should_translate is True
        assert element.bbox is None
        assert element.translated_content is None

    def test_element_with_bbox(self):
        """Test element with bounding box."""
        bbox = BoundingBox(x0=0, y0=0, x1=100, y1=20)
        element = TranslatableElement(
            element_id="p1_b1",
            content="Text with bbox",
            element_type=ElementType.TITLE,
            page_num=1,
            bbox=bbox,
        )

        assert element.bbox is not None
        assert element.bbox.width == 100

    def test_header_footer_types(self):
        """Test header and footer element types."""
        header = TranslatableElement(
            element_id="h1",
            content="Page Header",
            element_type=ElementType.HEADER,
            page_num=1,
            should_translate=False,
        )

        footer = TranslatableElement(
            element_id="f1",
            content="Page 1",
            element_type=ElementType.FOOTER,
            page_num=1,
            should_translate=False,
        )

        assert header.element_type == ElementType.HEADER
        assert header.should_translate is False
        assert footer.element_type == ElementType.FOOTER

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = TranslatableElement(
            element_id="test_id",
            content="Test content",
            element_type=ElementType.TABLE_CELL,
            page_num=2,
            bbox=BoundingBox(x0=10, y0=20, x1=100, y1=40),
            style=StyleInfo(font_name="Arial", font_size=10),
            should_translate=True,
            translated_content="Translated",
            metadata={"in_table": True},
        )

        restored = TranslatableElement.from_dict(original.to_dict())

        assert original.element_id == restored.element_id
        assert original.content == restored.content
        assert original.element_type == restored.element_type
        assert original.page_num == restored.page_num
        assert original.bbox.width == restored.bbox.width
        assert original.style.font_name == restored.style.font_name
        assert original.translated_content == restored.translated_content
        assert original.metadata == restored.metadata


class TestTranslatableDocument:
    """Tests for TranslatableDocument dataclass."""

    @pytest.fixture
    def sample_document(self):
        """Create a sample document for testing."""
        elements = [
            TranslatableElement(
                element_id="header1",
                content="Page Header",
                element_type=ElementType.HEADER,
                page_num=1,
                bbox=BoundingBox(x0=0, y0=0, x1=612, y1=30),
                should_translate=False,
            ),
            TranslatableElement(
                element_id="title1",
                content="Document Title",
                element_type=ElementType.TITLE,
                page_num=1,
                bbox=BoundingBox(x0=100, y0=100, x1=500, y1=130),
            ),
            TranslatableElement(
                element_id="text1",
                content="First paragraph.",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=150, x1=540, y1=180),
            ),
            TranslatableElement(
                element_id="text2",
                content="Second paragraph.",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=200, x1=540, y1=230),
            ),
            TranslatableElement(
                element_id="text3",
                content="First paragraph.",  # Duplicate text
                element_type=ElementType.TEXT,
                page_num=2,
                bbox=BoundingBox(x0=72, y0=100, x1=540, y1=130),
            ),
            TranslatableElement(
                element_id="footer1",
                content="Page 1",
                element_type=ElementType.FOOTER,
                page_num=1,
                bbox=BoundingBox(x0=0, y0=762, x1=612, y1=792),
                should_translate=False,
            ),
        ]

        pages = [
            PageInfo(page_num=1, width=612, height=792),
            PageInfo(page_num=2, width=612, height=792),
        ]

        metadata = DocumentMetadata(
            title="Test Document",
            page_count=2,
            has_text_layer=True,
        )

        return TranslatableDocument(
            source_path="/test/doc.pdf",
            source_type="pdf",
            elements=elements,
            pages=pages,
            metadata=metadata,
        )

    def test_get_translatable_elements(self, sample_document):
        """Test filtering to translatable elements only."""
        translatable = sample_document.get_translatable_elements()

        # Should exclude header and footer
        assert len(translatable) == 4
        for elem in translatable:
            assert elem.should_translate is True

    def test_get_elements_by_page(self, sample_document):
        """Test getting elements for a specific page."""
        page1_elements = sample_document.get_elements_by_page(1)
        page2_elements = sample_document.get_elements_by_page(2)

        assert len(page1_elements) == 5
        assert len(page2_elements) == 1
        assert all(e.page_num == 1 for e in page1_elements)
        assert all(e.page_num == 2 for e in page2_elements)

    def test_get_elements_in_reading_order(self, sample_document):
        """Test sorting by reading order."""
        ordered = sample_document.get_elements_in_reading_order()

        # Check that elements are sorted by (page_num, y0, x0)
        prev_key = None
        for elem in ordered:
            if elem.bbox:
                key = (elem.page_num, elem.bbox.y0, elem.bbox.x0)
                if prev_key:
                    assert key >= prev_key
                prev_key = key

    def test_get_unique_texts(self, sample_document):
        """Test deduplication of text content."""
        unique = sample_document.get_unique_texts()

        # "First paragraph." appears twice but should only be listed once
        assert "First paragraph." in unique
        assert unique.count("First paragraph.") == 1
        assert "Document Title" in unique
        assert "Second paragraph." in unique

    def test_apply_translations(self, sample_document):
        """Test applying translations to elements."""
        translations = {
            "Document Title": "文件標題",
            "First paragraph.": "第一段。",
            "Second paragraph.": "第二段。",
        }

        sample_document.apply_translations(translations)

        for elem in sample_document.elements:
            if elem.should_translate:
                original = elem.content.strip()
                if original in translations:
                    assert elem.translated_content == translations[original]

    def test_roundtrip(self, sample_document):
        """Test serialization roundtrip."""
        data = sample_document.to_dict()
        restored = TranslatableDocument.from_dict(data)

        assert restored.source_path == sample_document.source_path
        assert restored.source_type == sample_document.source_type
        assert len(restored.elements) == len(sample_document.elements)
        assert len(restored.pages) == len(sample_document.pages)
        assert restored.metadata.title == sample_document.metadata.title


class TestDocumentMetadata:
    """Tests for DocumentMetadata dataclass."""

    def test_default_values(self):
        """Test default metadata values."""
        meta = DocumentMetadata()

        assert meta.title is None
        assert meta.page_count == 0
        assert meta.has_text_layer is True

    def test_scanned_pdf_detection(self):
        """Test metadata for scanned PDF."""
        meta = DocumentMetadata(
            page_count=10,
            has_text_layer=False,
        )

        assert meta.has_text_layer is False

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = DocumentMetadata(
            title="Test",
            author="Author",
            page_count=5,
            has_text_layer=True,
        )

        restored = DocumentMetadata.from_dict(original.to_dict())

        assert original.title == restored.title
        assert original.author == restored.author
        assert original.page_count == restored.page_count


class TestPageInfo:
    """Tests for PageInfo dataclass."""

    def test_standard_page(self):
        """Test standard letter-size page."""
        page = PageInfo(page_num=1, width=612, height=792)

        assert page.page_num == 1
        assert page.width == 612
        assert page.height == 792
        assert page.rotation == 0

    def test_rotated_page(self):
        """Test rotated page."""
        page = PageInfo(page_num=1, width=792, height=612, rotation=90)

        assert page.rotation == 90

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = PageInfo(page_num=3, width=612, height=792, rotation=180)
        restored = PageInfo.from_dict(original.to_dict())

        assert original.page_num == restored.page_num
        assert original.width == restored.width
        assert original.rotation == restored.rotation
