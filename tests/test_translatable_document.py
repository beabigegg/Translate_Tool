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


# ---------------------------------------------------------------------------
# New test classes added for p2-ir-document-model
# ---------------------------------------------------------------------------


class TestElementType:
    """Tests for ElementType enum additions (AC-1)."""

    def test_region_types_present(self):
        """TABLE, FIGURE, FORMULA, LIST exist on ElementType."""
        assert hasattr(ElementType, "TABLE")
        assert hasattr(ElementType, "FIGURE")
        assert hasattr(ElementType, "FORMULA")
        assert hasattr(ElementType, "LIST")

    def test_existing_types_unchanged(self):
        """All 8 pre-existing values still present with same string values."""
        expected = {
            "TEXT": "text",
            "TITLE": "title",
            "HEADER": "header",
            "FOOTER": "footer",
            "TABLE_CELL": "table_cell",
            "LIST_ITEM": "list_item",
            "CAPTION": "caption",
            "FOOTNOTE": "footnote",
        }
        for name, value in expected.items():
            assert hasattr(ElementType, name), f"ElementType.{name} missing"
            assert ElementType[name].value == value, (
                f"ElementType.{name}.value changed: expected {value!r}, "
                f"got {ElementType[name].value!r}"
            )

    def test_unknown_element_type_from_dict_raises(self):
        """ElementType('nonexistent') raises ValueError."""
        with pytest.raises(ValueError):
            ElementType("nonexistent")

    def test_element_type_values_are_strings(self):
        """Every .value is a lowercase string."""
        for member in ElementType:
            assert isinstance(member.value, str), (
                f"ElementType.{member.name}.value is not a str"
            )
            assert member.value == member.value.lower(), (
                f"ElementType.{member.name}.value is not lowercase: {member.value!r}"
            )


class TestTranslatableElementReadingOrder:
    """Tests for reading_order additions to TranslatableElement (AC-2)."""

    def test_reading_order_default_none(self):
        """New field defaults to None."""
        elem = TranslatableElement(
            element_id="e1",
            content="text",
            element_type=ElementType.TEXT,
            page_num=1,
        )
        assert elem.reading_order is None

    def test_reading_order_roundtrip(self):
        """Integer reading_order serializes/deserializes correctly."""
        elem = TranslatableElement(
            element_id="e2",
            content="text",
            element_type=ElementType.TEXT,
            page_num=1,
            reading_order=5,
        )
        d = elem.to_dict()
        assert d["reading_order"] == 5
        restored = TranslatableElement.from_dict(d)
        assert restored.reading_order == 5

    def test_reading_order_none_roundtrip(self):
        """None reading_order survives to_dict -> from_dict."""
        elem = TranslatableElement(
            element_id="e3",
            content="text",
            element_type=ElementType.TEXT,
            page_num=1,
            reading_order=None,
        )
        d = elem.to_dict()
        assert d["reading_order"] is None
        restored = TranslatableElement.from_dict(d)
        assert restored.reading_order is None

    def test_region_element_types_accepted(self):
        """element_type=TABLE/FIGURE/FORMULA/LIST constructs without error."""
        for et in (ElementType.TABLE, ElementType.FIGURE, ElementType.FORMULA, ElementType.LIST):
            elem = TranslatableElement(
                element_id=f"region_{et.value}",
                content="region content",
                element_type=et,
                page_num=1,
            )
            assert elem.element_type == et


class TestRoundTripFidelity:
    """Round-trip guarantee tests (AC-3)."""

    def _make_element(
        self,
        reading_order=None,
        element_type=ElementType.TEXT,
    ) -> TranslatableElement:
        return TranslatableElement(
            element_id="rt_elem",
            content="Sample text",
            element_type=element_type,
            page_num=2,
            bbox=BoundingBox(x0=10.5, y0=20.25, x1=200.75, y1=40.125),
            style=StyleInfo(
                font_name="Arial",
                font_size=12.5,
                is_bold=True,
                is_italic=False,
                color="#AABBCC",
                background_color="#FFFFFF",
            ),
            should_translate=True,
            translated_content="Translated text",
            metadata={"key": "value"},
            reading_order=reading_order,
        )

    def test_full_ir_roundtrip_preserves_bbox(self):
        """x0/y0/x1/y1 exact after to_dict -> from_dict."""
        original = self._make_element()
        restored = TranslatableElement.from_dict(original.to_dict())
        assert restored.bbox.x0 == original.bbox.x0
        assert restored.bbox.y0 == original.bbox.y0
        assert restored.bbox.x1 == original.bbox.x1
        assert restored.bbox.y1 == original.bbox.y1

    def test_full_ir_roundtrip_preserves_font_metadata(self):
        """font_name, font_size, is_bold, color preserved."""
        original = self._make_element()
        restored = TranslatableElement.from_dict(original.to_dict())
        assert restored.style.font_name == original.style.font_name
        assert restored.style.font_size == original.style.font_size
        assert restored.style.is_bold == original.style.is_bold
        assert restored.style.is_italic == original.style.is_italic
        assert restored.style.color == original.style.color
        assert restored.style.background_color == original.style.background_color

    def test_full_ir_roundtrip_preserves_element_type(self):
        """All ElementType values survive to_dict -> from_dict."""
        for et in ElementType:
            elem = TranslatableElement(
                element_id=f"e_{et.value}",
                content="x",
                element_type=et,
                page_num=1,
            )
            restored = TranslatableElement.from_dict(elem.to_dict())
            assert restored.element_type == et

    def test_full_ir_roundtrip_preserves_reading_order(self):
        """int and None reading_order both preserved."""
        for ro in (0, 1, 42, None):
            elem = self._make_element(reading_order=ro)
            restored = TranslatableElement.from_dict(elem.to_dict())
            assert restored.reading_order == ro

    def test_document_roundtrip_element_count(self):
        """Element list length unchanged after document round-trip."""
        elements = [
            TranslatableElement(
                element_id=f"e{i}",
                content=f"content {i}",
                element_type=ElementType.TEXT,
                page_num=1,
                reading_order=i,
            )
            for i in range(5)
        ]
        doc = TranslatableDocument(
            source_path="/tmp/test.pdf",
            source_type="pdf",
            elements=elements,
            pages=[PageInfo(page_num=1, width=612, height=792)],
            metadata=DocumentMetadata(page_count=1),
        )
        restored = TranslatableDocument.from_dict(doc.to_dict())
        assert len(restored.elements) == len(doc.elements)


class TestBackwardCompat:
    """Backward-compatibility tests (AC-4)."""

    def _old_format_element_dict(self) -> dict:
        """Return a dict in old format (no reading_order key)."""
        return {
            "element_id": "old_elem",
            "content": "Old content",
            "element_type": "text",
            "page_num": 1,
            "bbox": {"x0": 10.0, "y0": 20.0, "x1": 100.0, "y1": 40.0},
            "style": {
                "font_name": "Times",
                "font_size": 11.0,
                "is_bold": False,
                "is_italic": False,
                "color": "#000000",
                "background_color": None,
            },
            "should_translate": True,
            "translated_content": None,
            "metadata": {},
        }

    def test_from_dict_missing_reading_order_defaults_none(self):
        """Old dict without reading_order deserializes cleanly with None."""
        d = self._old_format_element_dict()
        assert "reading_order" not in d
        elem = TranslatableElement.from_dict(d)
        assert elem.reading_order is None

    def test_from_dict_missing_bbox_ok(self):
        """Old element without bbox key -> bbox=None."""
        d = self._old_format_element_dict()
        del d["bbox"]
        elem = TranslatableElement.from_dict(d)
        assert elem.bbox is None

    def test_from_dict_missing_style_ok(self):
        """Old element without style key -> style=None."""
        d = self._old_format_element_dict()
        del d["style"]
        elem = TranslatableElement.from_dict(d)
        assert elem.style is None

    def test_from_dict_missing_font_metadata_fields_ok(self):
        """StyleInfo.from_dict with absent keys uses defaults."""
        partial_style = {"is_bold": True}
        style = StyleInfo.from_dict(partial_style)
        assert style.font_name is None
        assert style.font_size is None
        assert style.is_bold is True
        assert style.is_italic is False
        assert style.color is None

    def test_to_dict_keys_are_superset_of_old_keys(self):
        """No key removals from to_dict output."""
        old_keys = {
            "element_id",
            "content",
            "element_type",
            "page_num",
            "bbox",
            "style",
            "should_translate",
            "translated_content",
            "metadata",
        }
        elem = TranslatableElement(
            element_id="e_compat",
            content="compat",
            element_type=ElementType.TEXT,
            page_num=1,
        )
        d = elem.to_dict()
        assert old_keys.issubset(d.keys()), (
            f"Missing keys: {old_keys - d.keys()}"
        )

    def test_empty_elements_list_roundtrip(self):
        """Document with zero elements round-trips cleanly."""
        doc = TranslatableDocument(
            source_path="/tmp/empty.pdf",
            source_type="pdf",
            elements=[],
            pages=[PageInfo(page_num=1, width=612, height=792)],
            metadata=DocumentMetadata(page_count=1),
        )
        restored = TranslatableDocument.from_dict(doc.to_dict())
        assert restored.elements == []

    def test_partial_ir_missing_translated_content(self):
        """Element dict without translated_content -> None."""
        d = self._old_format_element_dict()
        del d["translated_content"]
        elem = TranslatableElement.from_dict(d)
        assert elem.translated_content is None

    def test_from_dict_unknown_key_in_metadata_field_ignored(self):
        """Unknown key in metadata dict does not raise."""
        d = self._old_format_element_dict()
        d["metadata"] = {"unknown_key_xyz": "some_value", "another_unknown": 42}
        elem = TranslatableElement.from_dict(d)
        assert elem.metadata["unknown_key_xyz"] == "some_value"
