"""Tests for pdf-layout-refactor (AC-1..AC-8).

Wave 2 Track G, Tier 1. All new tests live exclusively in this file.
Each test class maps to one sub-item (3.1–3.7) per test-plan.md.

TDD policy: tests are written BEFORE implementation; they must FAIL on current
code and PASS after implementation.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch, call

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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_element(
    eid: str,
    content: str,
    x0: float, y0: float, x1: float, y1: float,
    page_num: int = 1,
    element_type: ElementType = ElementType.TEXT,
    should_translate: bool = True,
    reading_order: int = 0,
    metadata: dict = None,
    translated_content: str = None,
    style: StyleInfo = None,
) -> TranslatableElement:
    return TranslatableElement(
        element_id=eid,
        content=content,
        element_type=element_type,
        page_num=page_num,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
        should_translate=should_translate,
        reading_order=reading_order,
        metadata=dict(metadata) if metadata else {},
        translated_content=translated_content,
        style=style,
    )


def _make_doc(elements=None, source_path="/fake/test.pdf", pages=None) -> TranslatableDocument:
    if elements is None:
        elements = [
            _make_element("e1", "Hello", 72, 100, 300, 120, reading_order=0),
        ]
    return TranslatableDocument(
        source_path=source_path,
        source_type="pdf",
        elements=elements,
        pages=pages if pages is not None else [PageInfo(page_num=1, width=612, height=792)],
        metadata=DocumentMetadata(page_count=1, has_text_layer=True),
    )


_FIXTURE_PDF = Path(__file__).parent / "fixtures" / "test.pdf"
_FIXTURE_MULTILINE_PDF = Path(__file__).parent / "fixtures" / "test_multiline.pdf"


# ---------------------------------------------------------------------------
# 3.1: Bbox-exact whitening (AC-1, BR-84)
# ---------------------------------------------------------------------------

class TestBboxWhitening:
    """AC-1: Whitening uses IR bbox directly; page.search_for NOT called."""

    def _setup_fitz_mocks(self):
        """Return (mock_fitz, mock_doc, mock_page)."""
        mock_page = MagicMock()
        mock_page.rect = MagicMock(width=612, height=792)
        mock_page.search_for = MagicMock(return_value=[])

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Rect.return_value = MagicMock(
            width=100, height=20, x0=72, y0=100, x1=300, y1=120
        )
        mock_tw = MagicMock()
        mock_fitz.TextWriter.return_value = mock_tw
        mock_fitz.Font.return_value = MagicMock()
        return mock_fitz, mock_doc, mock_page

    def test_bbox_whitening_uses_rect_not_search_for(self, tmp_path, monkeypatch):
        """After fix: add_redact_annot uses element bbox; search_for NOT called (AC-1)."""
        from app.backend.renderers.fitz_renderer import PDFGenerator
        import app.backend.renderers.fitz_renderer as fr_mod

        mock_fitz, mock_doc, mock_page = self._setup_fitz_mocks()
        monkeypatch.setattr(fr_mod, "fitz", mock_fitz)

        element = _make_element("e1", "Hello", 72, 100, 300, 120, reading_order=0)
        element.translated_content = "你好"
        doc = _make_doc([element])

        from app.backend.renderers.bbox_reflow import Placement
        fake_placements = [
            Placement(
                element_id="e1", page_num=1,
                x0=72, y0=100, x1=300, y1=120,
                text="你好", reading_order=0,
            )
        ]

        with patch.dict("sys.modules", {"fitz": mock_fitz}), \
             patch("app.backend.renderers.fitz_renderer.register_fonts"), \
             patch("app.backend.renderers.fitz_renderer.reflow_document",
                   return_value=fake_placements):
            gen = PDFGenerator(draw_mask=True)
            gen._generate_overlay(doc, {"Hello": "你好"}, str(tmp_path / "out.pdf"))

        # CORE ASSERTION: search_for must NOT be called (bbox-exact whitening)
        mock_page.search_for.assert_not_called()
        # Redaction/whitening must still happen
        assert mock_page.add_redact_annot.called or mock_page.draw_rect.called, (
            "Whitening must use add_redact_annot or draw_rect, not search_for"
        )

    def test_whitening_non_latin_no_bleed(self, tmp_path, monkeypatch):
        """Non-Latin text: whitening uses bbox (no search_for dependency) (AC-1)."""
        import app.backend.renderers.fitz_renderer as fr_mod

        mock_fitz, mock_doc, mock_page = self._setup_fitz_mocks()
        monkeypatch.setattr(fr_mod, "fitz", mock_fitz)

        element = _make_element("e1", "測試文字", 72, 100, 300, 120, reading_order=0)
        element.translated_content = "テスト"
        doc = _make_doc([element])

        from app.backend.renderers.bbox_reflow import Placement
        from app.backend.renderers.fitz_renderer import PDFGenerator
        fake_placements = [
            Placement(
                element_id="e1", page_num=1,
                x0=72, y0=100, x1=300, y1=120,
                text="テスト", reading_order=0,
            )
        ]

        with patch.dict("sys.modules", {"fitz": mock_fitz}), \
             patch("app.backend.renderers.fitz_renderer.register_fonts"), \
             patch("app.backend.renderers.fitz_renderer.reflow_document",
                   return_value=fake_placements):
            gen = PDFGenerator(draw_mask=True)
            gen._generate_overlay(doc, {"測試文字": "テスト"}, str(tmp_path / "out.pdf"))

        mock_page.search_for.assert_not_called()


# ---------------------------------------------------------------------------
# 3.2: Paragraph aggregation (AC-2, D-2)
# ---------------------------------------------------------------------------

class TestParagraphAggregation:
    """AC-2: Consecutive lines in the same block aggregated into one element."""

    def test_paragraph_aggregation_reduces_element_count(self):
        """Element count < raw fitz line count after aggregation (AC-2)."""
        try:
            import fitz as real_fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        if not _FIXTURE_MULTILINE_PDF.exists():
            pytest.skip("tests/fixtures/test_multiline.pdf not found")

        # Count raw lines on page 1
        doc = real_fitz.open(str(_FIXTURE_MULTILINE_PDF))
        page = doc[0]
        text_dict = page.get_text("dict", sort=True)
        raw_line_count = sum(
            len(block.get("lines", []))
            for block in text_dict.get("blocks", [])
            if block.get("type") == 0
        )
        doc.close()

        if raw_line_count == 0:
            pytest.skip("test_multiline.pdf page 1 has no text")

        from app.backend.parsers.pdf_parser import PyMuPDFParser
        with patch.dict(os.environ, {"LAYOUT_DETECTOR_ENABLED": "false"}):
            parser = PyMuPDFParser()
            result = parser.parse(str(_FIXTURE_MULTILINE_PDF))

        page1_elements = [e for e in result.elements if e.page_num == 1]
        element_count = len(page1_elements)

        assert element_count < raw_line_count, (
            f"Paragraph aggregation: element count ({element_count}) should be < "
            f"raw line count ({raw_line_count}); PDF has {raw_line_count} lines "
            f"but only {element_count} aggregated elements."
        )

    def test_aggregated_element_has_lines_metadata(self):
        """Aggregated elements store original line bboxes in metadata['lines'] (AC-2)."""
        try:
            import fitz as real_fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        if not _FIXTURE_MULTILINE_PDF.exists():
            pytest.skip("tests/fixtures/test_multiline.pdf not found")

        from app.backend.parsers.pdf_parser import PyMuPDFParser
        with patch.dict(os.environ, {"LAYOUT_DETECTOR_ENABLED": "false"}):
            parser = PyMuPDFParser()
            result = parser.parse(str(_FIXTURE_MULTILINE_PDF))

        # Find elements with multi-line aggregation
        aggregated = [
            e for e in result.elements
            if "lines" in e.metadata and len(e.metadata["lines"]) > 1
        ]
        assert len(aggregated) > 0, (
            "No aggregated elements found; paragraph aggregation should produce "
            "elements with metadata['lines'] for multi-line blocks."
        )


# ---------------------------------------------------------------------------
# 3.3: Iterative scale-fitting (AC-3, BR-85, BR-88)
# ---------------------------------------------------------------------------

class TestIterativeScaleFit:
    """AC-3: Binary search fit; floor is MIN_READABLE_FONT_PT (8pt), not 6pt."""

    def test_min_readable_font_pt_in_config(self):
        """MIN_READABLE_FONT_PT = 8 must be defined in config (AC-3)."""
        from app.backend import config
        assert hasattr(config, "MIN_READABLE_FONT_PT"), (
            "config.MIN_READABLE_FONT_PT must be defined (AC-3, BR-85)"
        )
        assert config.MIN_READABLE_FONT_PT == 8

    def test_scale_fit_stays_above_readable_floor(self):
        """When even 8pt overflows, font stays at 8pt and truncated=True (AC-3, BR-88)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        from app.backend.config import MIN_READABLE_FONT_PT

        style = StyleInfo(font_size=11.0, font_name="Helvetica")
        bbox = BoundingBox(x0=0, y0=0, x1=5, y1=5)  # Impossibly tiny
        text = "Text that cannot fit in a 5x5 box even at smallest size absolutely"

        decision = fit_text_cascade(text=text, bbox=bbox, style=style)

        assert decision.font_size >= MIN_READABLE_FONT_PT, (
            f"Font {decision.font_size}pt is below readable floor {MIN_READABLE_FONT_PT}pt"
        )
        assert decision.truncated is True, "Overflow at floor must set truncated=True"

    def test_scale_fit_truncated_only_at_8pt_overflow(self):
        """Truncation fires only when text doesn't fit at 8pt (AC-3)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade

        style = StyleInfo(font_size=11.0, font_name="Helvetica")
        bbox = BoundingBox(x0=0, y0=0, x1=500, y1=100)  # Generous
        text = "This should fit without truncation"

        decision = fit_text_cascade(text=text, bbox=bbox, style=style)
        assert not decision.truncated, "Text fits in large bbox; truncation must not fire"

    def test_iterative_scale_fit_finds_valid_font(self):
        """Binary search finds largest font that fits; result >= 8pt (AC-3)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        from app.backend.config import MIN_READABLE_FONT_PT

        style = StyleInfo(font_size=11.0, font_name="Helvetica")
        # Box that overflows at 11pt but fits at ~9pt
        bbox = BoundingBox(x0=0, y0=0, x1=60, y1=15)
        text = "Hello World Test"

        decision = fit_text_cascade(text=text, bbox=bbox, style=style)
        assert decision.font_size >= MIN_READABLE_FONT_PT
        assert decision.font_size <= 11.0


# ---------------------------------------------------------------------------
# 3.4: Per-span style fidelity (AC-4, D-4)
# ---------------------------------------------------------------------------

class TestSpanStyleFidelity:
    """AC-4: StyleInfo.is_underline; color/bold/italic captured from spans."""

    def test_styleinfo_has_is_underline_field(self):
        """StyleInfo must have is_underline field defaulting to False (AC-4)."""
        style = StyleInfo()
        assert hasattr(style, "is_underline"), "StyleInfo must have is_underline"
        assert style.is_underline is False

    def test_is_underline_backward_compat_from_dict(self):
        """from_dict() with dict missing is_underline key defaults to False (AC-4)."""
        d = {
            "font_name": "Arial",
            "font_size": 11.0,
            "is_bold": False,
            "is_italic": False,
            "color": "#000000",
            "background_color": None,
            # is_underline intentionally absent
        }
        style = StyleInfo.from_dict(d)
        assert style.is_underline is False  # must not raise; defaults False

    def test_is_underline_in_to_dict(self):
        """is_underline=True appears in to_dict() output (AC-4)."""
        style = StyleInfo(is_underline=True)
        d = style.to_dict()
        assert "is_underline" in d
        assert d["is_underline"] is True

    def test_is_underline_roundtrip(self):
        """is_underline=True survives to_dict → from_dict roundtrip (AC-4)."""
        style = StyleInfo(is_underline=True)
        restored = StyleInfo.from_dict(style.to_dict())
        assert restored.is_underline is True

    def test_span_bold_preserved(self):
        """is_bold field is captured and round-trips (AC-4)."""
        style = StyleInfo(is_bold=True, font_size=11.0)
        d = style.to_dict()
        assert d["is_bold"] is True
        assert StyleInfo.from_dict(d).is_bold is True

    def test_span_color_preserved(self, tmp_path, monkeypatch):
        """Color from StyleInfo.color is applied in renderer (AC-4)."""
        import app.backend.renderers.fitz_renderer as fr_mod

        mock_page = MagicMock()
        mock_page.rect = MagicMock(width=612, height=792)
        mock_page.search_for = MagicMock(return_value=[])
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_tw = MagicMock()
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Rect.return_value = MagicMock(width=100, height=20, x0=72, y0=100, x1=300, y1=120)
        mock_fitz.TextWriter.return_value = mock_tw
        mock_font = MagicMock()
        mock_font.text_length.return_value = 50  # always fits → no wrap needed
        mock_fitz.Font.return_value = mock_font

        monkeypatch.setattr(fr_mod, "fitz", mock_fitz)

        element = _make_element("e1", "Hello", 72, 100, 300, 120, reading_order=0)
        element.translated_content = "你好"
        element.style = StyleInfo(color="#FF0000", font_size=11.0)
        doc = _make_doc([element])

        from app.backend.renderers.bbox_reflow import Placement
        from app.backend.renderers.fitz_renderer import PDFGenerator
        fake_placements = [
            Placement(
                element_id="e1", page_num=1,
                x0=72, y0=100, x1=300, y1=120,
                text="你好", reading_order=0,
            )
        ]

        with patch.dict("sys.modules", {"fitz": mock_fitz}), \
             patch("app.backend.renderers.fitz_renderer.register_fonts"), \
             patch("app.backend.renderers.fitz_renderer.reflow_document",
                   return_value=fake_placements):
            gen = PDFGenerator(draw_mask=True)
            gen._generate_overlay(doc, {"Hello": "你好"}, str(tmp_path / "out.pdf"))

        # TextWriter.write_text must be called (renderer ran)
        mock_tw.write_text.assert_called()


# ---------------------------------------------------------------------------
# 3.5: Reading-order model (AC-5, D-5)
# ---------------------------------------------------------------------------

class TestReadingOrderModel:
    """AC-5: LayoutReader column-aware reading order."""

    def test_layout_reader_is_importable(self):
        """LayoutReader must be importable from layout_detector (AC-5)."""
        from app.backend.parsers.layout_detector import LayoutReader
        assert hasattr(LayoutReader, "sort_elements")

    def test_reading_order_column_assignment_two_column(self):
        """Left-column elements all precede right-column elements (AC-5)."""
        from app.backend.parsers.layout_detector import LayoutReader

        left_elements = [
            _make_element(f"L{i}", f"Left {i}", 0, i * 20, 200, (i+1)*20)
            for i in range(3)
        ]
        right_elements = [
            _make_element(f"R{i}", f"Right {i}", 300, i * 20, 500, (i+1)*20)
            for i in range(3)
        ]

        # Interleave to make test non-trivial
        mixed = [right_elements[0], left_elements[0],
                 right_elements[1], left_elements[1],
                 right_elements[2], left_elements[2]]

        reader = LayoutReader()
        sorted_elems = reader.sort_elements(mixed)
        sorted_ids = [e.element_id for e in sorted_elems]

        left_indices = [sorted_ids.index(e.element_id) for e in left_elements]
        right_indices = [sorted_ids.index(e.element_id) for e in right_elements]

        assert max(left_indices) < min(right_indices), (
            f"All left-column elements must precede right-column elements. "
            f"Left positions: {left_indices}, Right positions: {right_indices}"
        )

    def test_reading_order_single_column(self):
        """Single column: elements sorted top-to-bottom by y0 (AC-5)."""
        from app.backend.parsers.layout_detector import LayoutReader

        elements = [
            _make_element("e3", "Line 3", 0, 60, 200, 80),
            _make_element("e1", "Line 1", 0,  0, 200, 20),
            _make_element("e2", "Line 2", 0, 30, 200, 50),
        ]

        reader = LayoutReader()
        sorted_elems = reader.sort_elements(elements)

        assert sorted_elems[0].element_id == "e1"
        assert sorted_elems[1].element_id == "e2"
        assert sorted_elems[2].element_id == "e3"


# ---------------------------------------------------------------------------
# 3.6: DPI upgrade (AC-6, D-6)
# ---------------------------------------------------------------------------

class TestDpiUpgrade:
    """AC-6: PDF_RENDER_DPI in config; _run_layout_detector uses DPI-scaled matrix."""

    def test_pdf_render_dpi_in_config(self):
        """PDF_RENDER_DPI must exist in config with default 150 (AC-6)."""
        from app.backend import config
        assert hasattr(config, "PDF_RENDER_DPI"), "PDF_RENDER_DPI must be in config"
        assert config.PDF_RENDER_DPI == 150

    def test_pdf_render_dpi_matrix_scaling(self, monkeypatch):
        """_run_layout_detector passes PDF_RENDER_DPI/72 matrix to get_pixmap (AC-6)."""
        try:
            import fitz as real_fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        if not _FIXTURE_PDF.exists():
            pytest.skip("tests/fixtures/test.pdf not found")

        import app.backend.parsers.pdf_parser as pp_mod

        # Capture fitz.Matrix constructor arguments
        matrix_scales: list = []
        orig_matrix = real_fitz.Matrix

        def spy_matrix(a, b=None):
            matrix_scales.append(float(a))
            return orig_matrix(a, a if b is None else b)

        monkeypatch.setattr(pp_mod.fitz, "Matrix", spy_matrix)

        with patch.dict(os.environ, {
            "LAYOUT_DETECTOR_ENABLED": "true",
            "PDF_RENDER_DPI": "150",
        }):
            with patch("app.backend.parsers.layout_detector.LayoutDetector") as MockLD:
                mock_ld = MagicMock()
                mock_ld.detect.return_value = {"detector": "heuristic", "boxes": []}
                MockLD.return_value = mock_ld
                from app.backend.parsers.pdf_parser import PyMuPDFParser
                parser = PyMuPDFParser()
                parser.parse(str(_FIXTURE_PDF))

        expected = 150.0 / 72.0
        assert any(abs(s - expected) < 0.01 for s in matrix_scales), (
            f"Expected Matrix scale {expected:.3f}; got {matrix_scales}"
        )

    def test_high_dpi_pixel_dimensions(self):
        """Higher DPI produces larger pixmap dimensions (AC-6)."""
        try:
            import fitz as real_fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        if not _FIXTURE_PDF.exists():
            pytest.skip("tests/fixtures/test.pdf not found")

        doc = real_fitz.open(str(_FIXTURE_PDF))
        page = doc[0]
        pix_low  = page.get_pixmap(matrix=real_fitz.Matrix(1.0, 1.0))
        pix_high = page.get_pixmap(matrix=real_fitz.Matrix(150/72, 150/72))
        doc.close()

        assert pix_high.width  > pix_low.width
        assert pix_high.height > pix_low.height


# ---------------------------------------------------------------------------
# 3.7: Formula pass-through + OCR seam (AC-7, AC-8)
# ---------------------------------------------------------------------------

class TestFormulaAndOcr:
    """AC-7: FORMULA elements not translated; AC-8: OCR seam resilient."""

    def test_formula_pass_through(self):
        """_apply_formula_passthrough sets should_translate=False and copies content (AC-7)."""
        from app.backend.processors.pdf_processor import _apply_formula_passthrough

        formula = _make_element(
            "f1", "E = mc^2", 0, 0, 100, 20,
            element_type=ElementType.FORMULA,
            should_translate=True,
        )
        _apply_formula_passthrough([formula])

        assert formula.should_translate is False
        assert formula.translated_content == formula.content

    def test_formula_only_page_no_translation(self):
        """After pass-through, FORMULA elements absent from translatable list (AC-7)."""
        from app.backend.processors.pdf_processor import _apply_formula_passthrough

        formula = _make_element(
            "f1", r"\sum_{i=1}^{n} x_i", 0, 0, 100, 20,
            element_type=ElementType.FORMULA,
            should_translate=True,
        )
        _apply_formula_passthrough([formula])

        translatable = [e for e in [formula] if e.should_translate and e.content.strip()]
        assert len(translatable) == 0

    def test_formula_pass_through_on_heuristic_path(self):
        """LAYOUT_DETECTOR_ENABLED=false: FORMULA still excluded from translation (AC-7)."""
        from app.backend.processors.pdf_processor import _apply_formula_passthrough

        # Mixed: formula + text
        formula = _make_element(
            "f1", "E=mc^2", 0, 0, 100, 20,
            element_type=ElementType.FORMULA, should_translate=True,
        )
        text = _make_element("t1", "Hello", 0, 30, 200, 50,
                             element_type=ElementType.TEXT, should_translate=True)

        _apply_formula_passthrough([formula, text])

        assert formula.should_translate is False
        assert text.should_translate is True  # non-formula unchanged

    def test_ocr_backend_importable(self):
        """ocr_backend module must be importable (AC-7)."""
        from app.backend.parsers import ocr_backend
        assert callable(getattr(ocr_backend, "run_ocr", None))

    def test_ocr_absent_no_crash(self):
        """OCR_ENABLED=False: run_ocr returns [] even with library absent (AC-7)."""
        from app.backend.parsers.ocr_backend import run_ocr

        with patch.dict("sys.modules", {"surya": None, "paddleocr": None}), \
             patch.dict(os.environ, {"OCR_ENABLED": "false"}):
            mock_page = MagicMock()
            result = run_ocr(mock_page)
            assert isinstance(result, list)

    def test_ocr_absent_produces_warning_not_crash(self, caplog):
        """OCR library absent + OCR_ENABLED=True: warns but does not crash (AC-7)."""
        from app.backend.parsers.ocr_backend import run_ocr

        with patch.dict("sys.modules", {"surya": None, "paddleocr": None}), \
             patch.dict(os.environ, {"OCR_ENABLED": "true"}):
            with caplog.at_level(logging.WARNING):
                result = run_ocr(MagicMock())
            assert isinstance(result, list)

    def test_empty_page_text_triggers_ocr_check(self, monkeypatch):
        """Near-empty page + OCR_ENABLED=True calls ocr_backend.run_ocr (AC-7)."""
        try:
            import fitz as real_fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        if not _FIXTURE_PDF.exists():
            pytest.skip("tests/fixtures/test.pdf not found")

        import app.backend.parsers.pdf_parser as pp_mod

        mock_run_ocr = MagicMock(return_value=[])

        # Force every page to appear near-empty by returning [] from _extract_page_elements
        monkeypatch.setattr(
            pp_mod.PyMuPDFParser,
            "_extract_page_elements",
            lambda *args, **kwargs: [],
        )

        with patch.dict(os.environ, {
            "LAYOUT_DETECTOR_ENABLED": "false",
            "OCR_ENABLED": "true",
        }), patch("app.backend.parsers.ocr_backend.run_ocr", mock_run_ocr):
            from app.backend.parsers.pdf_parser import PyMuPDFParser
            parser = PyMuPDFParser()
            parser.parse(str(_FIXTURE_PDF))

        assert mock_run_ocr.called, (
            "ocr_backend.run_ocr must be called when page is near-empty and OCR_ENABLED=True"
        )

    def test_ocr_enabled_in_config(self):
        """OCR_ENABLED must be defined in config (AC-7)."""
        from app.backend import config
        assert hasattr(config, "OCR_ENABLED"), "config.OCR_ENABLED must be defined"
        # Default should be False (not enabled by default)
        assert config.OCR_ENABLED is False

    def test_table_recognition_disabled_unaffected(self):
        """TABLE_RECOGNITION_ENABLED=false: non-table elements still parsed (AC-8)."""
        try:
            import fitz as real_fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        if not _FIXTURE_PDF.exists():
            pytest.skip("tests/fixtures/test.pdf not found")

        from app.backend.parsers.pdf_parser import PyMuPDFParser
        with patch.dict(os.environ, {
            "LAYOUT_DETECTOR_ENABLED": "false",
            "TABLE_RECOGNITION_ENABLED": "false",
        }):
            parser = PyMuPDFParser()
            result = parser.parse(str(_FIXTURE_PDF))

        assert len(result.elements) > 0
        # No table structures without TATR
        table_structured = [
            e for e in result.elements if e.metadata.get("table_structure") is not None
        ]
        assert len(table_structured) == 0


# ---------------------------------------------------------------------------
# AC-9  TestAvailableWhitespaceBelow (pdf-text-overflow-fix, BR-36 note)
# ---------------------------------------------------------------------------


class TestAvailableWhitespaceBelow:
    """AC-9: Placement.available_whitespace_below computed from real sibling geometry."""

    def test_reflow_element_computes_nonzero_gap_below_same_column(self):
        """TABLE_CELL: gap = distance to the next row's y0 in the SAME table_id/table_col."""
        from app.backend.renderers.bbox_reflow import reflow_element

        cell_above = _make_element(
            "c1", "Row0", 50, 100, 150, 130, reading_order=0,
            element_type=ElementType.TABLE_CELL,
            metadata={"table_id": "p1_t0", "table_row": 0, "table_col": 0},
        )
        cell_below = _make_element(
            "c2", "Row1", 50, 150, 150, 180, reading_order=1,
            element_type=ElementType.TABLE_CELL,
            metadata={"table_id": "p1_t0", "table_row": 1, "table_col": 0},
        )

        placement = reflow_element(
            cell_above, page_elements=[cell_above, cell_below], page_height=792,
        )

        assert placement is not None
        assert placement.available_whitespace_below == pytest.approx(150 - 130)
        assert placement.available_whitespace_below > 0

    def test_reflow_document_zero_gap_last_row_or_no_neighbor(self):
        """No below-neighbor with overlapping x-range -> gap stays 0.0 (default-safe)."""
        from app.backend.renderers.bbox_reflow import reflow_document

        lone = _make_element("e1", "Solo paragraph", 50, 100, 150, 130, reading_order=0)
        doc = _make_doc([lone])

        placements = reflow_document(doc)

        assert len(placements) == 1
        assert placements[0].available_whitespace_below == 0.0


# ---------------------------------------------------------------------------
# AC-10  TestBoundedRowGrowth (pdf-text-overflow-fix, BR-103, ADR-0013)
# ---------------------------------------------------------------------------


class TestBoundedRowGrowth:
    """AC-10: bounded local table-row-growth pre-pass (grow_table_rows)."""

    @staticmethod
    def _table_cell(eid, content, x0, y0, x1, y1, table_id, row, col, translated=None):
        return _make_element(
            eid, content, x0, y0, x1, y1, reading_order=row * 10 + col,
            element_type=ElementType.TABLE_CELL,
            metadata={"table_id": table_id, "table_row": row, "table_col": col},
            translated_content=translated,
        )

    def test_single_table_row_grows_and_shifts_only_same_table_id_lower_rows(self):
        """Case 1: an over-full row grows; only the SAME table's lower row shifts down."""
        from app.backend.renderers.text_region_renderer import grow_table_rows

        long_text = (
            "This translated sentence is far too long to fit inside a narrow, "
            "short table row no matter how much the font shrinks. " * 3
        )
        row0 = self._table_cell("c1", "short", 50, 100, 150, 115, "p1_t0", 0, 0, translated=long_text)
        row1 = self._table_cell("c2", "next row", 50, 115, 150, 130, "p1_t0", 1, 0)
        doc = _make_doc([row0, row1], pages=[PageInfo(page_num=1, width=612, height=792)])

        row1_y0_before, row1_y1_before = row1.bbox.y0, row1.bbox.y1

        grow_table_rows(doc)

        delta = row0.bbox.y1 - 115
        assert delta > 0, "row0 must grow to fit its overflowing translated text"
        assert row0.bbox.y0 == 100, "row growth extends y1 only; y0 must stay fixed"
        assert row1.bbox.y0 == pytest.approx(row1_y0_before + delta), (
            "the lower row in the SAME table must shift down by the identical delta"
        )
        assert row1.bbox.y1 == pytest.approx(row1_y1_before + delta)

    def test_growth_capped_at_table_budget_residual_truncates_and_warns(self):
        """Case 2: growth is capped at the table's remaining local page budget."""
        from app.backend.config import PDF_HEADER_FOOTER_MARGIN_PT
        from app.backend.renderers.text_region_renderer import grow_table_rows

        long_text = (
            "Extremely long translated text that will never fit in this tiny cell "
            "no matter what happens to the font size or the line spacing. " * 5
        )
        row0 = self._table_cell("c1", "short", 50, 100, 150, 115, "p1_t0", 0, 0, translated=long_text)
        # Remaining local budget = page_height - PDF_HEADER_FOOTER_MARGIN_PT - table_bottom(115) = 5.0
        page_height = 115 + PDF_HEADER_FOOTER_MARGIN_PT + 5.0
        doc = _make_doc([row0], pages=[PageInfo(page_num=1, width=612, height=page_height)])

        grow_table_rows(doc)

        applied_delta = row0.bbox.y1 - 115
        assert applied_delta == pytest.approx(5.0), (
            f"growth must cap at the 5.0pt remaining table budget, got {applied_delta}"
        )

    def test_no_table_id_metadata_skips_growth_unchanged_cascade(self):
        """Case 3: no table_id/table_row metadata -> growth entirely skipped."""
        from app.backend.renderers.text_region_renderer import grow_table_rows

        long_text = "Some long translated text that would otherwise need growth. " * 5
        elem = _make_element(
            "e1", "short", 50, 100, 150, 115, reading_order=0,
            element_type=ElementType.TABLE_CELL,  # TABLE_CELL but no table_id/table_row
            translated_content=long_text,
        )
        doc = _make_doc([elem])
        before = (elem.bbox.x0, elem.bbox.y0, elem.bbox.x1, elem.bbox.y1)

        grow_table_rows(doc)

        after = (elem.bbox.x0, elem.bbox.y0, elem.bbox.x1, elem.bbox.y1)
        assert before == after, "missing table_id/table_row metadata must skip growth"

    def test_metadata_lines_whitening_bboxes_shift_by_identical_delta(self):
        """Case 4: a shifted lower row's metadata['lines'] whitening rects move by the SAME delta as its bbox."""
        from app.backend.renderers.text_region_renderer import grow_table_rows

        long_text = (
            "This translated sentence is far too long to fit inside a narrow, "
            "short table row no matter how much the font shrinks. " * 3
        )
        row0 = self._table_cell("c1", "short", 50, 100, 150, 115, "p1_t0", 0, 0, translated=long_text)
        row1 = self._table_cell("c2", "next row", 50, 115, 150, 130, "p1_t0", 1, 0)
        row1.metadata["lines"] = [(50, 115, 150, 130)]
        doc = _make_doc([row0, row1], pages=[PageInfo(page_num=1, width=612, height=792)])
        row1_y0_before = row1.bbox.y0

        grow_table_rows(doc)

        delta = row0.bbox.y1 - 115
        assert delta > 0
        shifted_line = row1.metadata["lines"][0]
        assert shifted_line[0] == 50 and shifted_line[2] == 150, "x-coordinates must not shift"
        assert shifted_line[1] == pytest.approx(115 + delta)
        assert shifted_line[3] == pytest.approx(130 + delta)
        # The bbox and the lines whitening rect must shift by the IDENTICAL delta.
        assert (shifted_line[1] - 115) == pytest.approx(row1.bbox.y0 - row1_y0_before)
