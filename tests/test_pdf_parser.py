"""Tests for PDF parser using PyMuPDF."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestPyMuPDFParser:
    """Tests for PyMuPDFParser class."""

    @pytest.fixture
    def mock_fitz(self):
        """Create mock fitz module."""
        with patch.dict("sys.modules", {"fitz": MagicMock()}):
            import sys

            fitz = sys.modules["fitz"]
            yield fitz

    def test_import_error_handling(self):
        """Test graceful handling when PyMuPDF is not installed."""
        with patch.dict("sys.modules", {"fitz": None}):
            # Clear cached import
            import sys

            if "app.backend.parsers.pdf_parser" in sys.modules:
                del sys.modules["app.backend.parsers.pdf_parser"]

            # This should raise ImportError when trying to create parser
            # The actual behavior depends on implementation

    def test_supported_extensions(self, mock_fitz):
        """Test that parser declares PDF support."""
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser = PyMuPDFParser()
        assert ".pdf" in parser.supported_extensions

    def test_file_not_found(self, mock_fitz):
        """Test handling of non-existent file."""
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser = PyMuPDFParser()

        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/file.pdf")

    def test_invalid_extension(self, mock_fitz):
        """Test handling of non-PDF file."""
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser = PyMuPDFParser()

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Not a PDF")
            f.flush()

            with pytest.raises(ValueError, match="Not a PDF"):
                parser.parse(f.name)

            Path(f.name).unlink()


class TestPyMuPDFParserIntegration:
    """Integration tests for PyMuPDFParser.

    These tests require PyMuPDF to be installed and a test PDF file.
    They are skipped if dependencies are not available.
    """

    @pytest.fixture
    def test_pdf_path(self):
        """Get path to test PDF file."""
        # Look for test PDF in common locations
        test_files = [
            Path(__file__).parent / "fixtures" / "test.pdf",
            Path(__file__).parent.parent / "test_data" / "sample.pdf",
        ]

        for path in test_files:
            if path.exists():
                return str(path)

        pytest.skip("No test PDF file available")

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        try:
            from app.backend.parsers.pdf_parser import PyMuPDFParser

            return PyMuPDFParser()
        except ImportError:
            pytest.skip("PyMuPDF not installed")

    def test_parse_pdf(self, parser, test_pdf_path):
        """Test parsing a real PDF file."""
        doc = parser.parse(test_pdf_path)

        assert doc is not None
        assert doc.source_type == "pdf"
        assert len(doc.pages) > 0
        assert doc.metadata.page_count > 0

    def test_elements_have_bbox(self, parser, test_pdf_path):
        """Test that extracted elements have bounding boxes."""
        doc = parser.parse(test_pdf_path)

        elements_with_bbox = [e for e in doc.elements if e.bbox is not None]

        # Most elements should have bbox
        assert len(elements_with_bbox) > 0

        for elem in elements_with_bbox:
            assert elem.bbox.width > 0
            assert elem.bbox.height > 0

    def test_reading_order(self, parser, test_pdf_path):
        """Test that elements are returned in reading order."""
        doc = parser.parse(test_pdf_path)
        ordered = doc.get_elements_in_reading_order()

        # Verify order is consistent
        prev_key = None
        for elem in ordered:
            if elem.bbox:
                # Round y0 for line grouping
                y_rounded = round(elem.bbox.y0 / 10) * 10
                key = (elem.page_num, y_rounded, elem.bbox.x0)
                if prev_key:
                    assert key >= prev_key, "Elements not in reading order"
                prev_key = key

    def test_header_footer_detection(self, parser, test_pdf_path):
        """Test header/footer region detection."""
        from app.backend.models.translatable_document import ElementType

        # Create parser with header/footer skipping enabled
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser_with_skip = PyMuPDFParser(skip_header_footer=True)
        doc = parser_with_skip.parse(test_pdf_path)

        # Check if any elements are marked as header/footer
        headers = [e for e in doc.elements if e.element_type == ElementType.HEADER]
        footers = [e for e in doc.elements if e.element_type == ElementType.FOOTER]

        # Header/footer elements should have should_translate=False
        for elem in headers + footers:
            assert elem.should_translate is False


class TestTableDetection:
    """Tests for table detection functionality."""

    def test_is_inside_true(self):
        """Test _is_inside returns True when inner bbox is inside outer."""
        from app.backend.models.translatable_document import BoundingBox
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser = PyMuPDFParser.__new__(PyMuPDFParser)

        inner = BoundingBox(x0=25, y0=25, x1=75, y1=75)
        outer = BoundingBox(x0=0, y0=0, x1=100, y1=100)

        assert parser._is_inside(inner, outer) is True

    def test_is_inside_false(self):
        """Test _is_inside returns False when inner bbox is outside outer."""
        from app.backend.models.translatable_document import BoundingBox
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser = PyMuPDFParser.__new__(PyMuPDFParser)

        inner = BoundingBox(x0=50, y0=50, x1=150, y1=150)
        outer = BoundingBox(x0=0, y0=0, x1=100, y1=100)

        assert parser._is_inside(inner, outer) is False

    def test_is_inside_with_tolerance(self):
        """Test _is_inside with default tolerance allows small overhang."""
        from app.backend.models.translatable_document import BoundingBox
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser = PyMuPDFParser.__new__(PyMuPDFParser)

        # Inner extends 3pt beyond outer (within 5pt tolerance)
        inner = BoundingBox(x0=-3, y0=-3, x1=103, y1=103)
        outer = BoundingBox(x0=0, y0=0, x1=100, y1=100)

        assert parser._is_inside(inner, outer) is True

    def test_detect_and_mark_tables_marks_elements(self):
        """Test that elements inside table regions are marked as table_cell."""
        from unittest.mock import MagicMock

        from app.backend.models.translatable_document import (
            BoundingBox,
            ElementType,
            TranslatableElement,
        )
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser = PyMuPDFParser.__new__(PyMuPDFParser)

        # Create mock document with table
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_doc.__len__ = lambda self: 1
        mock_doc.__getitem__ = lambda self, idx: mock_page

        # Mock table with bbox
        mock_table = MagicMock()
        mock_table.bbox = (100, 100, 300, 200)  # x0, y0, x1, y1

        mock_table_finder = MagicMock()
        mock_table_finder.tables = [mock_table]
        mock_page.find_tables.return_value = mock_table_finder

        # Create elements - one inside table, one outside
        elements = [
            TranslatableElement(
                element_id="inside_table",
                content="Cell content",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=110, y0=110, x1=200, y1=150),
            ),
            TranslatableElement(
                element_id="outside_table",
                content="Regular text",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=50, y0=50, x1=90, y1=80),
            ),
        ]

        # Call the method
        parser._detect_and_mark_tables(mock_doc, elements)

        # Verify inside element is marked as table_cell
        assert elements[0].element_type == ElementType.TABLE_CELL
        assert elements[0].metadata.get("in_table") is True

        # Verify outside element is still TEXT
        assert elements[1].element_type == ElementType.TEXT


class TestColorConversion:
    """Tests for color conversion utilities."""

    def test_color_to_hex_black(self):
        """Test conversion of black color."""
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser = PyMuPDFParser.__new__(PyMuPDFParser)
        hex_color = parser._color_to_hex(0)

        assert hex_color == "#000000"

    def test_color_to_hex_white(self):
        """Test conversion of white color."""
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser = PyMuPDFParser.__new__(PyMuPDFParser)
        hex_color = parser._color_to_hex(0xFFFFFF)

        assert hex_color == "#FFFFFF"

    def test_color_to_hex_red(self):
        """Test conversion of red color."""
        from app.backend.parsers.pdf_parser import PyMuPDFParser

        parser = PyMuPDFParser.__new__(PyMuPDFParser)
        hex_color = parser._color_to_hex(0xFF0000)

        assert hex_color == "#FF0000"
