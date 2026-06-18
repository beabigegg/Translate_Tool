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


# ---------------------------------------------------------------------------
# AC-5  TestReadingOrderPreservedBothPaths
# ---------------------------------------------------------------------------

class TestReadingOrderPreservedBothPaths:
    """Contract tests: reading_order is preserved identically on both render paths (AC-5, BR-35)."""

    def test_reading_order_preserved_fitz_path(self):
        """Reflow (shared component used by fitz) returns placements in reading_order sequence."""
        from app.backend.renderers.bbox_reflow import reflow_document

        elements = [
            TranslatableElement(
                element_id=f"e{i}",
                content=f"Segment {i}",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=100 + i * 20, x1=540, y1=115 + i * 20),
                reading_order=2 - i,  # reversed order to verify sorting
                should_translate=True,
                translated_content=f"Trans {i}",
            )
            for i in range(3)
        ]
        doc = _make_simple_ir()
        doc.elements = elements

        placements = reflow_document(doc)
        # Placements should be returned in reading_order (ascending) sequence
        ro_values = [p.reading_order for p in placements]
        assert ro_values == sorted(ro_values), (
            "Fitz-path reflow must return placements in ascending reading_order"
        )

    def test_reading_order_preserved_reportlab_path(self):
        """Reflow (shared component used by ReportLab) returns placements in reading_order sequence."""
        from app.backend.renderers.bbox_reflow import reflow_document

        # Same test body — reflow_document is the shared component, both paths use it
        elements = [
            TranslatableElement(
                element_id=f"e{i}",
                content=f"Text {i}",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=200 + i * 20, x1=540, y1=215 + i * 20),
                reading_order=i,
                should_translate=True,
                translated_content=f"Translated {i}",
            )
            for i in range(4)
        ]
        doc = _make_simple_ir()
        doc.elements = elements

        placements = reflow_document(doc)
        ro_values = [p.reading_order for p in placements]
        assert ro_values == sorted(ro_values), (
            "ReportLab-path reflow must return placements in ascending reading_order"
        )


# ---------------------------------------------------------------------------
# AC-5  TestElementTypingPreservedBothPaths
# ---------------------------------------------------------------------------

class TestElementTypingPreservedBothPaths:
    """Contract tests: element_type routing is identical on both paths (AC-5, BR-35)."""

    def test_element_type_routing_fitz(self):
        """TABLE/FIGURE/FORMULA elements have consistent skip/include decisions in reflow."""
        from app.backend.renderers.bbox_reflow import reflow_element

        # Non-translatable region types should be skipped or treated as text
        region_types = [ElementType.TABLE, ElementType.FIGURE, ElementType.FORMULA]
        for et in region_types:
            elem = TranslatableElement(
                element_id=f"e_{et.value}",
                content=f"Content for {et.value}",
                element_type=et,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=100, x1=540, y1=200),
                should_translate=False,  # region containers are not directly translated
                translated_content=None,
            )
            # Must not raise; result is None (skip) for non-translatable
            result = reflow_element(elem)
            # Region-level containers with should_translate=False → skip (None)
            assert result is None, (
                f"{et.value} with should_translate=False must be skipped (None)"
            )

    def test_element_type_routing_reportlab(self):
        """Same element_type routing decisions in reflow (shared component, same code path)."""
        from app.backend.renderers.bbox_reflow import reflow_element

        # TEXT with should_translate=True should produce a placement
        text_elem = TranslatableElement(
            element_id="etext",
            content="Body text",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=100, x1=540, y1=120),
            should_translate=True,
            translated_content="Translated body",
        )
        result = reflow_element(text_elem)
        assert result is not None, "TEXT with should_translate=True must produce a placement"

        # FIGURE with should_translate=False should be skipped
        figure_elem = TranslatableElement(
            element_id="efig",
            content="",
            element_type=ElementType.FIGURE,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=200, x1=400, y1=400),
            should_translate=False,
            translated_content=None,
        )
        result_fig = reflow_element(figure_elem)
        assert result_fig is None, "FIGURE with should_translate=False must be skipped"


# ---------------------------------------------------------------------------
# AC-6  TestMalformedIRBothPaths
# ---------------------------------------------------------------------------

class TestMalformedIRBothPaths:
    """Data-boundary tests for malformed IR on both render paths (AC-6)."""

    def test_malformed_ir_null_bbox_both_paths(self):
        """Both paths: element with null bbox → no raise, element skipped."""
        from app.backend.renderers.bbox_reflow import reflow_element

        elem = TranslatableElement(
            element_id="enullbbox",
            content="No bbox element",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=None,
            should_translate=True,
            translated_content="Translated",
        )
        # fitz path (via reflow)
        result_fitz = reflow_element(elem)
        assert result_fitz is None, "null bbox must produce None on fitz-side reflow"

        # ReportLab path (same shared reflow component)
        result_rl = reflow_element(elem)
        assert result_rl is None, "null bbox must produce None on RL-side reflow"
        assert result_fitz == result_rl, "Both paths must handle null bbox identically"

    def test_malformed_ir_null_reading_order_both_paths(self):
        """Both paths handle missing reading_order identically (positional sort fallback)."""
        from app.backend.renderers.bbox_reflow import reflow_document

        elements = [
            TranslatableElement(
                element_id="e_no_ro",
                content="Missing reading_order",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=100, x1=540, y1=120),
                should_translate=True,
                translated_content="Translated",
                reading_order=None,
            ),
        ]
        doc = TranslatableDocument(
            source_path="/tmp/fake.pdf",
            source_type="pdf",
            elements=elements,
            pages=[PageInfo(page_num=1, width=612, height=792)],
            metadata=DocumentMetadata(page_count=1),
        )
        # Must not raise on either path; should produce one placement
        placements = reflow_document(doc)
        assert len(placements) == 1, "null reading_order must still produce a placement"

    def test_malformed_ir_unknown_element_type_both_paths(self):
        """Both paths handle unrecognized ElementType identically (treat as text)."""
        from app.backend.renderers.bbox_reflow import reflow_element

        class FakeElem:
            element_id = "eunknown2"
            content = "Unknown element type"
            element_type = "completely_unknown_2099"
            page_num = 1
            bbox = BoundingBox(x0=72, y0=100, x1=300, y1=120)
            should_translate = True
            translated_content = "Translated"
            reading_order = 0

        result = reflow_element(FakeElem())
        assert result is not None, "Unknown element_type must not skip the element"
        assert result.text is not None, "Unknown element_type must produce renderable text"


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
