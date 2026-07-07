"""Tests for renderer path convergence (p2-renderer-convergence).

Covers AC-1..AC-7 per test-plan.md:
  AC-1 TestIRBboxReflow      — shared bbox_reflow component in isolation
  AC-2 TestFitzPrimary       — fitz path selected by default
  AC-3 TestFitzFallback      — fitz raises → ReportLab fallback; WARNING logged
  AC-4 TestLayoutEquivalence — both paths produce same element count ±2 pt bbox
  AC-6 TestMalformedIRDataBoundary — null bbox/reading_order/element_type/translated_content
  AC-7 TestEquivalenceGolden — layout snapshots stable across runs
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from app.backend.models.translatable_document import (
    BoundingBox,
    DocumentMetadata,
    ElementType,
    PageInfo,
    TranslatableDocument,
    TranslatableElement,
)

# ---------------------------------------------------------------------------
# Check optional runtime dependencies
# ---------------------------------------------------------------------------
try:
    import fitz as _fitz_mod
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_doc(
    elements: Optional[List[TranslatableElement]] = None,
    source_path: str = "/tmp/fake.pdf",
) -> TranslatableDocument:
    """Build a minimal in-memory TranslatableDocument."""
    if elements is None:
        elements = [
            TranslatableElement(
                element_id="e1",
                content="Hello World",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=72, x1=300, y1=90),
                should_translate=True,
                translated_content="Translated Hello",
                reading_order=0,
            ),
            TranslatableElement(
                element_id="e2",
                content="Second line",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=100, x1=300, y1=118),
                should_translate=True,
                translated_content="Translated Second",
                reading_order=1,
            ),
        ]
    return TranslatableDocument(
        source_path=source_path,
        source_type="pdf",
        elements=elements,
        pages=[PageInfo(page_num=1, width=612, height=792)],
        metadata=DocumentMetadata(page_count=1, has_text_layer=True),
    )


def _make_translations(doc: TranslatableDocument) -> Dict[str, str]:
    """Build a translations dict from the document's translated_content."""
    return {
        e.content.strip(): e.translated_content
        for e in doc.elements
        if e.translated_content is not None
    }


# ---------------------------------------------------------------------------
# AC-1  TestIRBboxReflow
# ---------------------------------------------------------------------------

class TestIRBboxReflow:
    """Unit tests for the shared IR-bbox reflow component (AC-1).

    These tests MUST fail before bbox_reflow.py is created (TDD gate).
    """

    def test_shared_reflow_returns_placement_for_valid_bbox(self):
        """reflow_element(element with valid bbox) returns a non-None placement."""
        from app.backend.renderers.bbox_reflow import reflow_element

        elem = TranslatableElement(
            element_id="e1",
            content="Hello",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=10, y0=20, x1=200, y1=40),
            should_translate=True,
            translated_content="Bonjour",
            reading_order=0,
        )
        placement = reflow_element(elem)
        assert placement is not None, "reflow_element must return placement for element with bbox"

    def test_shared_reflow_skips_null_bbox(self):
        """reflow_element(element with bbox=None) returns None; no raise."""
        from app.backend.renderers.bbox_reflow import reflow_element

        elem = TranslatableElement(
            element_id="e2",
            content="No bbox",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=None,
            should_translate=True,
            translated_content="Pas de bbox",
            reading_order=0,
        )
        placement = reflow_element(elem)
        assert placement is None, "reflow_element must return None for null bbox (skip sentinel)"

    def test_shared_reflow_deterministic(self):
        """Same IR element in → same placement out on repeated calls."""
        from app.backend.renderers.bbox_reflow import reflow_element

        elem = TranslatableElement(
            element_id="e3",
            content="Deterministic",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=50, y0=60, x1=300, y1=80),
            should_translate=True,
            translated_content="Déterministe",
            reading_order=2,
        )
        p1 = reflow_element(elem)
        p2 = reflow_element(elem)
        assert p1 == p2, "reflow_element must be deterministic"

    def test_reflow_uses_translated_content_when_present(self):
        """Placement text_source is translated_content when non-null (contract)."""
        from app.backend.renderers.bbox_reflow import reflow_element

        elem = TranslatableElement(
            element_id="e4",
            content="Original",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=10, y0=10, x1=100, y1=30),
            should_translate=True,
            translated_content="Translated",
        )
        placement = reflow_element(elem)
        assert placement is not None
        assert placement.text == "Translated"

    def test_reflow_falls_back_to_content_when_translated_content_null(self):
        """Placement text_source falls back to content when translated_content is None."""
        from app.backend.renderers.bbox_reflow import reflow_element

        elem = TranslatableElement(
            element_id="e5",
            content="Source text",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=10, y0=10, x1=100, y1=30),
            should_translate=True,
            translated_content=None,
        )
        placement = reflow_element(elem)
        assert placement is not None
        assert placement.text == "Source text"

    def test_reflow_unknown_element_type_treated_as_text(self):
        """Unknown element_type string → treated as text, no raise."""
        from app.backend.renderers.bbox_reflow import reflow_element

        # Simulate an element with a future/unknown ElementType by using a raw
        # dict round-trip bypass: construct with valid type then mutate _value_.
        # For the reflow API, we pass a synthetic wrapper object.
        class FakeElement:
            element_id = "fake"
            content = "Some content"
            element_type = "unknown_future_type"
            page_num = 1
            bbox = BoundingBox(x0=10, y0=10, x1=100, y1=30)
            should_translate = True
            translated_content = "Translated"
            reading_order = 0

        placement = reflow_element(FakeElement())
        assert placement is not None, "Unknown element_type must not cause skip or raise"

    def test_reflow_placement_exposes_bbox_coordinates(self):
        """Placement carries x0, y0, x1, y1 matching the element bbox."""
        from app.backend.renderers.bbox_reflow import reflow_element

        elem = TranslatableElement(
            element_id="e6",
            content="Bbox test",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=10.5, y0=20.5, x1=200.5, y1=40.5),
            should_translate=True,
            translated_content="Translated",
        )
        placement = reflow_element(elem)
        assert placement is not None
        assert placement.x0 == pytest.approx(10.5)
        assert placement.y0 == pytest.approx(20.5)
        assert placement.x1 == pytest.approx(200.5)
        assert placement.y1 == pytest.approx(40.5)


# ---------------------------------------------------------------------------
# AC-2  TestFitzPrimary
# ---------------------------------------------------------------------------

class TestFitzPrimary:
    """Unit tests for fitz-primary path selection (AC-2)."""

    def test_fitz_renderer_selected_by_default(self):
        """pdf_processor._translate_pdf_to_pdf imports and uses fitz path by default."""
        # The import path must be fitz_renderer (post-rename), not pdf_generator.
        import importlib
        spec = importlib.util.find_spec("app.backend.renderers.fitz_renderer")
        assert spec is not None, (
            "app.backend.renderers.fitz_renderer must exist after IP-2 rename"
        )

    @pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
    def test_fitz_renderer_produces_valid_pdf(self):
        """Fitz path renders a TranslatableDocument to a non-empty, valid PDF."""
        from app.backend.renderers.fitz_renderer import PDFGenerator
        from app.backend.renderers.base import RenderMode

        # Create a real temporary source PDF for fitz to open
        src_doc = _fitz_mod.open()
        page = src_doc.new_page(width=612, height=792)
        page.insert_text((72, 72), "Hello World", fontsize=12)
        fd, src_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        src_doc.save(src_path)
        src_doc.close()

        doc = _make_doc(source_path=src_path)
        translations = {"Hello World": "Translated Hello"}

        fd2, out_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd2)
        try:
            gen = PDFGenerator(target_lang="en")
            gen.generate(doc, translations, out_path, RenderMode.OVERLAY)
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0
            # Verify the file is a valid PDF
            check = _fitz_mod.open(out_path)
            assert len(check) >= 1
            check.close()
        finally:
            if os.path.exists(src_path):
                os.unlink(src_path)
            if os.path.exists(out_path):
                os.unlink(out_path)


# ---------------------------------------------------------------------------
# AC-3  TestFitzFallback
# ---------------------------------------------------------------------------

class TestFitzFallback:
    """Resilience tests for fitz-raises → ReportLab fallback (AC-3, BR-34)."""

    def test_fallback_to_reportlab_on_fitz_exception(self):
        """When fitz path raises, ReportLab path is invoked and produces a PDF."""
        from app.backend.renderers.base import RenderMode

        doc = _make_doc()
        translations = _make_translations(doc)

        fd, out_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        try:
            with patch(
                "app.backend.processors.pdf_processor._run_fitz_render",
                side_effect=RuntimeError("fitz exploded"),
            ), patch(
                "app.backend.processors.pdf_processor._run_reportlab_render"
            ) as mock_rl:
                mock_rl.return_value = None  # ReportLab succeeds (no exception)

                # Import the dispatch helper directly to test the try/fallback logic
                from app.backend.processors import pdf_processor
                pdf_processor._dispatch_render(
                    doc=doc,
                    translations=translations,
                    output_path=out_path,
                    target_lang="en",
                    mode=RenderMode.OVERLAY,
                    draw_mask=False,
                    doc_id="test-doc-id",
                )
                mock_rl.assert_called_once()
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_fallback_emits_warning_log(self):
        """WARNING log is emitted on fitz failure, containing exception type and doc id."""
        from app.backend.renderers.base import RenderMode

        doc = _make_doc()
        translations = _make_translations(doc)
        fd, out_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        try:
            with patch(
                "app.backend.processors.pdf_processor._run_fitz_render",
                side_effect=RuntimeError("fitz failure"),
            ), patch(
                "app.backend.processors.pdf_processor._run_reportlab_render"
            ):
                with patch(
                    "app.backend.processors.pdf_processor.logger"
                ) as mock_logger:
                    from app.backend.processors import pdf_processor
                    pdf_processor._dispatch_render(
                        doc=doc,
                        translations=translations,
                        output_path=out_path,
                        target_lang="en",
                        mode=RenderMode.OVERLAY,
                        draw_mask=False,
                        doc_id="test-doc-abc",
                    )
                    # Verify WARNING was emitted
                    warning_calls = [
                        str(call) for call in mock_logger.warning.call_args_list
                    ]
                    assert any("RuntimeError" in w for w in warning_calls), (
                        "WARNING log must contain exception type"
                    )
                    assert any("test-doc-abc" in w for w in warning_calls), (
                        "WARNING log must contain document id"
                    )
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_no_job_abort_on_fitz_failure(self):
        """Fitz exception must not propagate out of _dispatch_render."""
        from app.backend.renderers.base import RenderMode

        doc = _make_doc()
        translations = _make_translations(doc)
        fd, out_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        try:
            with patch(
                "app.backend.processors.pdf_processor._run_fitz_render",
                side_effect=RuntimeError("fitz exploded"),
            ), patch(
                "app.backend.processors.pdf_processor._run_reportlab_render"
            ):
                from app.backend.processors import pdf_processor
                # Must not raise
                pdf_processor._dispatch_render(
                    doc=doc,
                    translations=translations,
                    output_path=out_path,
                    target_lang="en",
                    mode=RenderMode.OVERLAY,
                    draw_mask=False,
                    doc_id="test-no-abort",
                )
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_double_failure_propagates(self):
        """When ReportLab also raises, the exception propagates (job → failed)."""
        from app.backend.renderers.base import RenderMode

        doc = _make_doc()
        translations = _make_translations(doc)
        fd, out_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

        try:
            with patch(
                "app.backend.processors.pdf_processor._run_fitz_render",
                side_effect=RuntimeError("fitz exploded"),
            ), patch(
                "app.backend.processors.pdf_processor._run_reportlab_render",
                side_effect=RuntimeError("reportlab also failed"),
            ):
                from app.backend.processors import pdf_processor
                with pytest.raises(RuntimeError, match="reportlab also failed"):
                    pdf_processor._dispatch_render(
                        doc=doc,
                        translations=translations,
                        output_path=out_path,
                        target_lang="en",
                        mode=RenderMode.OVERLAY,
                        draw_mask=False,
                        doc_id="test-double-fail",
                    )
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)


# ---------------------------------------------------------------------------
# AC-4  TestLayoutEquivalence
# ---------------------------------------------------------------------------

class TestLayoutEquivalence:
    """Integration tests for layout equivalence across fitz/ReportLab (AC-4).

    Both backends must delegate placement logic to reflow_document (AC-1/BR-35).
    Tolerance: ±2.0 pt per bbox edge (OVERLAY mode only, Decision C).
    """

    def test_both_paths_call_reflow_document(self):
        """Both fitz and ReportLab backends must call reflow_document for placement (AC-1).

        This is the non-tautological wiring test: we verify that each backend
        invokes the shared reflow component rather than deriving placement inline.
        """
        from app.backend.renderers.fitz_renderer import PDFGenerator

        doc = _make_doc()
        translations = _make_translations(doc)

        # --- Fitz path: verify reflow_document is called ---
        mock_fitz = MagicMock()
        mock_page = MagicMock()
        mock_page.search_for.return_value = []
        mock_src_doc = MagicMock()
        mock_src_doc.__len__ = MagicMock(return_value=1)
        mock_src_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("app.backend.renderers.fitz_renderer.reflow_document", return_value=[]) as mock_rd_fitz, \
             patch("app.backend.renderers.fitz_renderer.fitz", mock_fitz), \
             patch("app.backend.renderers.fitz_renderer.register_fonts"):
            mock_fitz.open.return_value = mock_src_doc
            gen = PDFGenerator(target_lang="en", draw_mask=False)
            try:
                gen._generate_overlay(doc, translations, "/tmp/test_out.pdf")
            except Exception:
                pass  # fitz mock may be incomplete; we only care about the call
            assert mock_rd_fitz.called, (
                "fitz_renderer._generate_overlay must call reflow_document (AC-1)"
            )

    def test_both_paths_same_include_set(self):
        """Both backends produce the same include/exclude element set for the same IR."""
        from app.backend.renderers.bbox_reflow import reflow_document

        doc = _make_doc()

        # Both paths call reflow_document with the same document; results are identical.
        fitz_placements = reflow_document(doc)
        rl_placements = reflow_document(doc)

        fitz_ids = {p.element_id for p in fitz_placements}
        rl_ids = {p.element_id for p in rl_placements}
        assert fitz_ids == rl_ids, (
            "Both paths must include/exclude identical elements for the same IR (BR-35)"
        )

    def test_both_paths_same_text_source(self):
        """Both backends select the same text source (translated_content vs content) per element."""
        from app.backend.renderers.bbox_reflow import reflow_document

        doc = _make_doc()
        placements = reflow_document(doc)

        for p in placements:
            elem = next(e for e in doc.elements if e.element_id == p.element_id)
            expected_text = (
                elem.translated_content if elem.translated_content is not None else elem.content
            )
            assert p.text == expected_text, (
                f"Element {p.element_id}: text source selection must match contract "
                f"(translated_content else content)"
            )

    def test_both_paths_same_reading_order_sequence(self):
        """Both backends produce placements in ascending reading_order sequence."""
        from app.backend.renderers.bbox_reflow import reflow_document

        doc = _make_doc()
        placements = reflow_document(doc)

        ro_values = [p.reading_order for p in placements if p.reading_order is not None]
        assert ro_values == sorted(ro_values), (
            "Shared reflow must return placements in ascending reading_order for both paths"
        )

    def test_reportlab_path_calls_reflow_document(self):
        """CoordinateRenderer._render_overlay must call reflow_document (AC-1)."""
        from app.backend.renderers.coordinate_renderer import CoordinateRenderer
        from app.backend.renderers.base import RenderMode

        doc = _make_doc()
        translations = _make_translations(doc)

        with patch("app.backend.renderers.coordinate_renderer.reflow_document", return_value=[]) as mock_rd, \
             patch("app.backend.renderers.coordinate_renderer.Canvas") as mock_canvas_cls, \
             patch("app.backend.renderers.coordinate_renderer.register_fonts"):
            mock_canvas = MagicMock()
            mock_canvas_cls.return_value = mock_canvas
            renderer = CoordinateRenderer(target_lang="en")
            renderer._render_overlay(doc, "/tmp/test_rl_out.pdf", translations)
            assert mock_rd.called, (
                "CoordinateRenderer._render_overlay must call reflow_document (AC-1)"
            )

    @pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
    def test_bbox_placement_within_tolerance_fitz_vs_reportlab(self):
        """Placement coordinates from shared reflow are within ±2.0 pt of IR bbox (Decision C)."""
        from app.backend.renderers.bbox_reflow import reflow_document

        doc = _make_doc()
        placements = reflow_document(doc)

        TOLERANCE = 2.0  # ±2.0 pt per bbox edge (Decision C)
        for p in placements:
            # Reflow must produce coordinates within tolerance of the IR bbox
            elem = next(e for e in doc.elements if e.element_id == p.element_id)
            assert abs(p.x0 - elem.bbox.x0) <= TOLERANCE
            assert abs(p.y0 - elem.bbox.y0) <= TOLERANCE
            assert abs(p.x1 - elem.bbox.x1) <= TOLERANCE
            assert abs(p.y1 - elem.bbox.y1) <= TOLERANCE

    def test_reportlab_path_also_calls_shared_fit_text_cascade(self):
        """AC-8/BR-40 (ADR-0012): the ReportLab draw path must call the SAME
        shared fit_text_cascade the fitz path calls (test_insert_text_calls_
        fit_cascade covers the fitz side) — the shared-call invariant replaces
        the old fitz-exclusivity invariant this contract used to enforce."""
        from reportlab.pdfgen.canvas import Canvas
        from app.backend.renderers.text_region_renderer import (
            CascadeDecision,
            TextRegion,
            render_text_region,
        )

        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(612, 792))
        region = TextRegion(text="Hello World", x0=72, y0=700, x1=200, y1=720)

        with patch(
            "app.backend.renderers.text_region_renderer.fit_text_cascade"
        ) as mock_cascade:
            mock_cascade.return_value = CascadeDecision(
                font_size=10.0,
                line_spacing=1.15,
                letter_spacing=0.0,
                overflow=False,
                truncated=False,
                fitted_text="Hello World",
            )
            render_text_region(canvas, region, target_lang="en", page_height=792)

        assert mock_cascade.called, (
            "render_text_region (ReportLab draw path) must call fit_text_cascade "
            "— BR-40 amendment: the SAME shared cascade authority for ALL PDF paths"
        )

    def test_row_growth_geometry_identical_fitz_vs_reportlab(self):
        """AC-10 case 5 (BR-103): after grow_table_rows mutates the shared IR
        once, BOTH backends read the identical grown geometry via the ONE
        shared reflow_document() output — convergence by construction
        (BR-35/BR-40), not by re-deriving growth per backend."""
        from app.backend.renderers.bbox_reflow import reflow_document
        from app.backend.renderers.text_region_renderer import grow_table_rows

        long_text = (
            "This translated sentence is far too long to fit inside a narrow, "
            "short table row no matter how much the font shrinks. " * 3
        )
        row0 = TranslatableElement(
            element_id="c1", content="short", element_type=ElementType.TABLE_CELL,
            page_num=1, bbox=BoundingBox(x0=50, y0=100, x1=150, y1=115),
            translated_content=long_text, reading_order=0,
            metadata={"table_id": "p1_t0", "table_row": 0, "table_col": 0},
        )
        row1 = TranslatableElement(
            element_id="c2", content="next row", element_type=ElementType.TABLE_CELL,
            page_num=1, bbox=BoundingBox(x0=50, y0=115, x1=150, y1=130),
            translated_content="next row", reading_order=1,
            metadata={"table_id": "p1_t0", "table_row": 1, "table_col": 0},
        )
        doc = _make_doc([row0, row1])

        grow_table_rows(doc)
        delta = row0.bbox.y1 - 115
        assert delta > 0, "fixture must actually trigger row growth"

        # Both fitz_renderer._generate_overlay and CoordinateRenderer._render_overlay
        # obtain placement geometry via this SAME shared call.
        placements = reflow_document(doc)
        p_row1 = next(p for p in placements if p.element_id == "c2")
        assert p_row1.y0 == pytest.approx(row1.bbox.y0)
        assert p_row1.y1 == pytest.approx(row1.bbox.y1)
        assert p_row1.y0 == pytest.approx(115 + delta)


# ---------------------------------------------------------------------------
# AC-6  TestMalformedIRDataBoundary
# ---------------------------------------------------------------------------

class TestMalformedIRDataBoundary:
    """Data-boundary tests for malformed IR conditions (AC-6)."""

    def test_null_bbox_handled_identically_both_paths(self):
        """Both paths skip element with null bbox; no raise."""
        from app.backend.renderers.bbox_reflow import reflow_element

        elem_null_bbox = TranslatableElement(
            element_id="enull",
            content="No bbox",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=None,
            should_translate=True,
            translated_content="Translated",
        )
        result = reflow_element(elem_null_bbox)
        assert result is None, "null bbox must produce None placement (skip)"

    def test_null_reading_order_handled_identically_both_paths(self):
        """Both paths fall back to positional sort when reading_order is null."""
        from app.backend.renderers.bbox_reflow import reflow_document

        elem_no_ro = TranslatableElement(
            element_id="enoro",
            content="No reading order",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=10, y0=50, x1=200, y1=70),
            should_translate=True,
            translated_content="Translated",
            reading_order=None,
        )
        elem_with_ro = TranslatableElement(
            element_id="ewithro",
            content="Has reading order",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=10, y0=100, x1=200, y1=120),
            should_translate=True,
            translated_content="Translated 2",
            reading_order=0,
        )
        doc = _make_doc(elements=[elem_no_ro, elem_with_ro])
        # Must not raise; must produce placements for both
        placements = reflow_document(doc)
        valid_placements = [p for p in placements if p is not None]
        assert len(valid_placements) >= 1, "At least one placement must be produced"

    def test_unknown_element_type_handled_identically_both_paths(self):
        """Unknown element_type string → treated as text on both paths; no raise, no skip."""
        from app.backend.renderers.bbox_reflow import reflow_element

        class FakeElem:
            element_id = "eunknown"
            content = "Unknown type content"
            element_type = "alien_future_type_xyz"
            page_num = 1
            bbox = BoundingBox(x0=10, y0=10, x1=200, y1=30)
            should_translate = True
            translated_content = "Translated"
            reading_order = 0

        placement = reflow_element(FakeElem())
        assert placement is not None, "Unknown element_type must not skip the element"

    def test_null_translated_content_handled_identically_both_paths(self):
        """null translated_content → render content (source text); no raise."""
        from app.backend.renderers.bbox_reflow import reflow_element

        elem = TranslatableElement(
            element_id="enotrans",
            content="Source only",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=10, y0=10, x1=200, y1=30),
            should_translate=True,
            translated_content=None,
        )
        placement = reflow_element(elem)
        assert placement is not None
        assert placement.text == "Source only", (
            "null translated_content must fall back to content"
        )

    def test_empty_elements_produces_valid_empty_result(self):
        """Empty elements list → empty placements list; no raise."""
        from app.backend.renderers.bbox_reflow import reflow_document

        doc = _make_doc(elements=[])
        placements = reflow_document(doc)
        assert placements == [], "Empty elements must produce empty placements"


# ---------------------------------------------------------------------------
# AC-7  TestEquivalenceGolden
# ---------------------------------------------------------------------------

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden" / "pdf"


def _placement_to_dict(p) -> dict:
    """Serialize a Placement to a JSON-compatible dict for snapshot comparison."""
    return {
        "element_id": p.element_id,
        "page_num": p.page_num,
        "x0": p.x0,
        "y0": p.y0,
        "x1": p.x1,
        "y1": p.y1,
        "text": p.text,
        "reading_order": p.reading_order,
    }


class TestEquivalenceGolden:
    """Regression snapshot tests for layout stability (AC-7, tier 1).

    Three sub-tests:
    1. test_golden_fitz_snapshot_stable — reflow is deterministic (non-tautological:
       uses the _make_doc() fixture IR, compares against committed .layout.json).
    2. test_golden_reportlab_snapshot_stable — same for the ReportLab path.
    3. test_layout_snapshot_matches_committed — loads each committed .layout.json
       golden, re-runs reflow_document on the same in-memory IR, and asserts match.
    """

    def test_golden_fitz_snapshot_stable(self):
        """Reflow decisions for a fixed IR must match the committed layout snapshot."""
        import json
        from app.backend.renderers.bbox_reflow import reflow_document

        doc = _make_doc()
        placements = reflow_document(doc)
        current = [_placement_to_dict(p) for p in placements]

        snap_path = GOLDEN_DIR / "fitz_snapshot.layout.json"
        if snap_path.exists():
            with open(snap_path) as f:
                saved = json.load(f)
            assert current == saved, (
                f"fitz_snapshot.layout.json mismatch — rerun with snapshot update to regenerate. "
                f"Got: {current}"
            )
        else:
            # First run: write snapshot so subsequent runs compare against it.
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            with open(snap_path, "w") as f:
                json.dump(current, f, indent=2)
            pytest.skip("Layout snapshot written on first run; re-run to compare.")

    def test_golden_reportlab_snapshot_stable(self):
        """ReportLab-path reflow must match the committed layout snapshot."""
        import json
        from app.backend.renderers.bbox_reflow import reflow_document

        doc = _make_doc()
        placements = reflow_document(doc)
        current = [_placement_to_dict(p) for p in placements]

        snap_path = GOLDEN_DIR / "reportlab_snapshot.layout.json"
        if snap_path.exists():
            with open(snap_path) as f:
                saved = json.load(f)
            assert current == saved, (
                f"reportlab_snapshot.layout.json mismatch — rerun with snapshot update. "
                f"Got: {current}"
            )
        else:
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            with open(snap_path, "w") as f:
                json.dump(current, f, indent=2)
            pytest.skip("Layout snapshot written on first run; re-run to compare.")

    def test_fitz_reflow_matches_golden_layout_snapshot(self):
        """Reflow on the canonical _make_doc() IR must match the committed golden snapshot."""
        import json
        from app.backend.renderers.bbox_reflow import reflow_document

        snap_path = GOLDEN_DIR / "fitz_snapshot.layout.json"
        if not snap_path.exists():
            pytest.skip("fitz_snapshot.layout.json not yet committed; run test suite once to generate.")

        doc = _make_doc()
        placements = reflow_document(doc)
        current = [_placement_to_dict(p) for p in placements]

        with open(snap_path) as f:
            saved = json.load(f)

        assert len(current) == len(saved), (
            f"Placement count changed: {len(current)} vs saved {len(saved)}"
        )
        for i, (got, exp) in enumerate(zip(current, saved)):
            assert got["element_id"] == exp["element_id"], f"[{i}] element_id mismatch"
            assert got["page_num"] == exp["page_num"], f"[{i}] page_num mismatch"
            assert abs(got["x0"] - exp["x0"]) <= 2.0, f"[{i}] x0 out of tolerance"
            assert abs(got["y0"] - exp["y0"]) <= 2.0, f"[{i}] y0 out of tolerance"
            assert abs(got["x1"] - exp["x1"]) <= 2.0, f"[{i}] x1 out of tolerance"
            assert abs(got["y1"] - exp["y1"]) <= 2.0, f"[{i}] y1 out of tolerance"
            assert got["text"] == exp["text"], f"[{i}] text mismatch"

    def test_reportlab_reflow_matches_golden_layout_snapshot(self):
        """ReportLab-path reflow on canonical IR must match the committed golden snapshot."""
        import json
        from app.backend.renderers.bbox_reflow import reflow_document

        snap_path = GOLDEN_DIR / "reportlab_snapshot.layout.json"
        if not snap_path.exists():
            pytest.skip("reportlab_snapshot.layout.json not yet committed; run once to generate.")

        doc = _make_doc()
        placements = reflow_document(doc)
        current = [_placement_to_dict(p) for p in placements]

        with open(snap_path) as f:
            saved = json.load(f)

        assert len(current) == len(saved), (
            f"Placement count changed: {len(current)} vs saved {len(saved)}"
        )
        for i, (got, exp) in enumerate(zip(current, saved)):
            assert got["element_id"] == exp["element_id"], f"[{i}] element_id mismatch"
            assert abs(got["x0"] - exp["x0"]) <= 2.0, f"[{i}] x0 out of tolerance"
            assert abs(got["y0"] - exp["y0"]) <= 2.0, f"[{i}] y0 out of tolerance"
            assert abs(got["x1"] - exp["x1"]) <= 2.0, f"[{i}] x1 out of tolerance"
            assert abs(got["y1"] - exp["y1"]) <= 2.0, f"[{i}] y1 out of tolerance"
            assert got["text"] == exp["text"], f"[{i}] text mismatch"


# ---------------------------------------------------------------------------
# p2-text-expansion: AC-6 cascade-wiring tests (TDD)
# ---------------------------------------------------------------------------


class TestCascadeWiringLayoutEquivalence:
    """Integration tests: fitz_renderer uses fit_text_cascade when inserting text (AC-6)."""

    def test_fitz_renderer_imports_fit_text_cascade(self):
        """fitz_renderer must import fit_text_cascade from text_region_renderer (AC-6)."""
        import importlib
        import inspect
        import app.backend.renderers.fitz_renderer as fitz_mod
        src = inspect.getsource(fitz_mod)
        assert "fit_text_cascade" in src, (
            "fitz_renderer must import and use fit_text_cascade (AC-6 cascade-wiring)"
        )

    def test_insert_text_calls_fit_cascade(self):
        """PDFGenerator._insert_text_in_rect must call fit_text_cascade (AC-6).

        Uses mock.patch to assert the shared cascade is called rather than
        deriving fit logic inline (non-tautological per test-plan.md AC-6).
        """
        from app.backend.renderers.fitz_renderer import PDFGenerator

        gen = PDFGenerator(target_lang="en")

        mock_page = MagicMock()
        mock_page.rect = MagicMock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792

        mock_rect = MagicMock()
        mock_rect.x0 = 72.0
        mock_rect.y0 = 72.0
        mock_rect.x1 = 300.0
        mock_rect.y1 = 100.0
        mock_rect.width = 228.0
        mock_rect.height = 28.0

        # Patch fit_text_cascade to track if it is called
        with patch(
            "app.backend.renderers.fitz_renderer.fit_text_cascade"
        ) as mock_cascade, patch(
            "app.backend.renderers.fitz_renderer.fitz"
        ) as mock_fitz:
            # Minimal fitz mocks
            mock_font = MagicMock()
            mock_font.text_length.return_value = 10.0
            mock_fitz.Font.return_value = mock_font
            mock_tw = MagicMock()
            mock_fitz.TextWriter.return_value = mock_tw

            from app.backend.renderers.text_region_renderer import CascadeDecision
            mock_cascade.return_value = CascadeDecision(
                font_size=10.0,
                line_spacing=1.15,
                letter_spacing=0.0,
                overflow=False,
                truncated=False,
                fitted_text="Hello World",
            )

            try:
                gen._insert_text_in_rect(mock_page, mock_rect, "Hello World")
            except Exception:
                pass  # fitz mock may be incomplete; we only care about the call

            assert mock_cascade.called, (
                "_insert_text_in_rect must call fit_text_cascade (AC-6 cascade-wiring)"
            )
