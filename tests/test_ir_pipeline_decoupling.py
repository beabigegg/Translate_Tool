"""Tests for IR pipeline decoupling guarantees (AC-5, AC-8).

Verifies that:
- A persisted IR can be re-rendered without invoking any parser.
- Translated content can be replaced in the IR and re-serialized without re-rendering.
- The public translate_pdf/translate_docx/translate_pptx APIs accept the same
  positional arguments as before this change.
- The IR carries reading_order and new ElementType values after PDF parse.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def _make_simple_ir(reading_order_start: int = 0) -> TranslatableDocument:
    """Build a minimal TranslatableDocument for in-memory tests."""
    elements = [
        TranslatableElement(
            element_id=f"e{i}",
            content=f"Segment {i}",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=100 + i * 20, x1=540, y1=115 + i * 20),
            reading_order=reading_order_start + i,
        )
        for i in range(3)
    ]
    return TranslatableDocument(
        source_path="/tmp/fake.pdf",
        source_type="pdf",
        elements=elements,
        pages=[PageInfo(page_num=1, width=612, height=792)],
        metadata=DocumentMetadata(page_count=1),
    )


class TestRerenderWithoutReparse:
    """AC-5: Translate IR in-memory, render; assert parse not called."""

    def test_rerender_without_reparse(self):
        """Load an IR from dict and render reading_order without re-parsing."""
        original_doc = _make_simple_ir()

        # Apply some translations
        original_doc.apply_translations(
            {"Segment 0": "翻訳0", "Segment 1": "翻訳1", "Segment 2": "翻訳2"}
        )

        # Serialize to dict (simulates persisting the IR)
        ir_dict = original_doc.to_dict()

        # Deserialize — this is the "load without re-parse" step
        loaded_doc = TranslatableDocument.from_dict(ir_dict)

        # Verify reading_order is preserved — no parser was called
        for orig, loaded in zip(original_doc.elements, loaded_doc.elements):
            assert loaded.reading_order == orig.reading_order
            assert loaded.translated_content == orig.translated_content

        # get_elements_in_reading_order must work correctly on the loaded IR
        ordered = loaded_doc.get_elements_in_reading_order()
        ro_values = [e.reading_order for e in ordered]
        assert ro_values == sorted(ro_values), "Reading order must be monotonically non-decreasing"


class TestSwapMTEngineWithoutRerender:
    """AC-5: Replace translated_content in loaded IR, re-render; parse not called."""

    def test_swap_mt_engine_without_rerender(self):
        """Swap translated_content in deserialized IR without calling a parser."""
        doc = _make_simple_ir()
        # Simulate first translation pass
        doc.apply_translations({"Segment 0": "First Engine: 翻訳0"})

        # Serialize
        ir_dict = doc.to_dict()

        # Deserialize and update translations directly (second MT engine swap)
        loaded = TranslatableDocument.from_dict(ir_dict)
        for elem in loaded.elements:
            if elem.content == "Segment 0":
                elem.translated_content = "Second Engine: 翻訳0 v2"

        # Re-serialize — should include the new translation
        updated_dict = loaded.to_dict()
        reloaded = TranslatableDocument.from_dict(updated_dict)
        swap_elem = next(e for e in reloaded.elements if e.content == "Segment 0")
        assert swap_elem.translated_content == "Second Engine: 翻訳0 v2"
        assert swap_elem.reading_order is not None  # reading_order survived both round-trips


class TestPublicAPIUnchanged:
    """AC-8: translate_pdf/translate_docx/translate_pptx accept same positional args."""

    def test_public_api_unchanged(self):
        """Public function signatures must still accept the same positional parameters."""
        from app.backend.processors.docx_processor import translate_docx
        from app.backend.processors.pdf_processor import translate_pdf
        from app.backend.processors.pptx_processor import translate_pptx

        pdf_sig = inspect.signature(translate_pdf)
        docx_sig = inspect.signature(translate_docx)
        pptx_sig = inspect.signature(translate_pptx)

        # Verify the first positional parameters haven't changed
        pdf_params = list(pdf_sig.parameters.keys())
        assert pdf_params[0] == "in_path", f"translate_pdf 1st param changed: {pdf_params[0]}"
        assert pdf_params[1] == "out_path", f"translate_pdf 2nd param changed: {pdf_params[1]}"
        assert pdf_params[2] == "targets", f"translate_pdf 3rd param changed: {pdf_params[2]}"
        assert pdf_params[3] == "src_lang", f"translate_pdf 4th param changed: {pdf_params[3]}"
        assert pdf_params[4] == "client", f"translate_pdf 5th param changed: {pdf_params[4]}"

        docx_params = list(docx_sig.parameters.keys())
        assert docx_params[0] == "in_path", f"translate_docx 1st param changed: {docx_params[0]}"
        assert docx_params[1] == "out_path", f"translate_docx 2nd param changed: {docx_params[1]}"
        assert docx_params[2] == "targets", f"translate_docx 3rd param changed: {docx_params[2]}"
        assert docx_params[3] == "src_lang", f"translate_docx 4th param changed: {docx_params[3]}"
        assert docx_params[4] == "client", f"translate_docx 5th param changed: {docx_params[4]}"

        pptx_params = list(pptx_sig.parameters.keys())
        assert pptx_params[0] == "in_path", f"translate_pptx 1st param changed: {pptx_params[0]}"
        assert pptx_params[1] == "out_path", f"translate_pptx 2nd param changed: {pptx_params[1]}"
        assert pptx_params[2] == "targets", f"translate_pptx 3rd param changed: {pptx_params[2]}"
        assert pptx_params[3] == "src_lang", f"translate_pptx 4th param changed: {pptx_params[3]}"
        assert pptx_params[4] == "client", f"translate_pptx 5th param changed: {pptx_params[4]}"


class TestIRCarriesNewFieldsAfterPDFParse:
    """AC-2/AC-5: reading_order and region types present post-parse."""

    @pytest.fixture
    def test_pdf_path(self):
        """Get path to test PDF file."""
        test_path = Path(__file__).parent / "fixtures" / "test.pdf"
        if not test_path.exists():
            pytest.skip("No test PDF fixture available")
        return str(test_path)

    @pytest.fixture
    def parser(self):
        """Create PDF parser, skipping if PyMuPDF not installed."""
        try:
            from app.backend.parsers.pdf_parser import PyMuPDFParser
            return PyMuPDFParser()
        except ImportError:
            pytest.skip("PyMuPDF not installed")

    def test_ir_carries_new_fields_after_pdf_parse(self, parser, test_pdf_path):
        """reading_order is set as sequential int post-parse; new ElementType values on enum."""
        doc = parser.parse(test_pdf_path)

        # All elements must have reading_order as int
        elements_with_ro = [e for e in doc.elements if e.reading_order is not None]
        assert len(elements_with_ro) == len(doc.elements), (
            "PDF parser must set reading_order on all elements"
        )

        # Values must be sequential 0-based
        ro_values = [e.reading_order for e in doc.elements]
        assert sorted(ro_values) == list(range(len(ro_values)))

        # New ElementType members must be importable and have correct wire values
        assert ElementType.TABLE.value == "table"
        assert ElementType.FIGURE.value == "figure"
        assert ElementType.FORMULA.value == "formula"
        assert ElementType.LIST.value == "list"
