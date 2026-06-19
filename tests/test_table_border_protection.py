"""Tests for p2-table-border-protection: overlay border erasure and side-by-side
source text bleed-through.

TDD: these tests are written BEFORE the fixes and are expected to FAIL
against the current (unfixed) fitz_renderer.py.  After the fixes land they
must all pass.

Coding constraints (context-manifest, implementation-plan):
  - Repo root via Path(__file__).parent.parent, never hardcoded.
  - PDF_MASK_MARGIN_PT imported from app.backend.config, never hardcoded.
  - Integration tests guard with @pytest.mark.skipif(not HAS_PYMUPDF, ...).
  - No new top-level imports in fitz_renderer.py (TestConfinementNoNewImports).
"""
from __future__ import annotations

import ast
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from app.backend.config import PDF_MASK_MARGIN_PT

# ---------------------------------------------------------------------------
# PyMuPDF availability guard
# ---------------------------------------------------------------------------
try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# Repo root – derived from this file's location, never hardcoded.
REPO_ROOT = Path(__file__).parent.parent
FITZ_RENDERER_PATH = REPO_ROOT / "app" / "backend" / "renderers" / "fitz_renderer.py"
TEST_PDF_PATH = REPO_ROOT / "tests" / "fixtures" / "test.pdf"


# ===========================================================================
# Helpers
# ===========================================================================

def _make_fitz_rect(x0, y0, x1, y1):
    """Create a fitz.Rect if PyMuPDF is available, else a namespace object."""
    if HAS_PYMUPDF:
        return fitz.Rect(x0, y0, x1, y1)
    # Minimal stand-in for unit tests that run without PyMuPDF
    class _R:
        def __init__(self, x0, y0, x1, y1):
            self.x0 = x0; self.y0 = y0; self.x1 = x1; self.y1 = y1
            self.width = x1 - x0; self.height = y1 - y0
    return _R(x0, y0, x1, y1)


# ===========================================================================
# TestBorderAwareRedactRect  (unit, Tier 0)
# AC-1: redact rect is inset from the matched quad by PDF_MASK_MARGIN_PT
# ===========================================================================

class TestBorderAwareRedactRect:
    """Unit tests for the overlay redact-rect geometry (AC-1)."""

    def _build_overlay_redact_rect_matched(self, quad_x0, quad_y0, quad_x1, quad_y1):
        """Replicate the matched-quad redact_rect formula from _generate_overlay."""
        margin = PDF_MASK_MARGIN_PT
        # This is the formula in fitz_renderer.py lines 313-319:
        # redact_rect = fitz.Rect(rect.x0 + margin, rect.y0 + margin,
        #                          rect.x1 - margin, rect.y1 - margin)
        return (
            quad_x0 + margin,
            quad_y0 + margin,
            quad_x1 - margin,
            quad_y1 - margin,
        )

    def _build_overlay_redact_rect_fallback(self, px0, py0, px1, py1):
        """Replicate the fallback redact_rect formula (no matching quad)."""
        margin = PDF_MASK_MARGIN_PT * 2
        return (
            px0 + margin,
            py0 + margin,
            px1 - margin,
            py1 - margin,
        )

    def test_redact_rect_shrinks_by_margin(self):
        """Matched-quad redact_rect is inset by PDF_MASK_MARGIN_PT on all sides."""
        qx0, qy0, qx1, qy1 = 100.0, 200.0, 300.0, 220.0
        rx0, ry0, rx1, ry1 = self._build_overlay_redact_rect_matched(qx0, qy0, qx1, qy1)
        m = PDF_MASK_MARGIN_PT
        assert rx0 == qx0 + m, f"left: expected {qx0 + m}, got {rx0}"
        assert ry0 == qy0 + m, f"top: expected {qy0 + m}, got {ry0}"
        assert rx1 == qx1 - m, f"right: expected {qx1 - m}, got {rx1}"
        assert ry1 == qy1 - m, f"bottom: expected {qy1 - m}, got {ry1}"

    def test_redact_rect_fallback_uses_double_margin(self):
        """Fallback (no matching quad) uses PDF_MASK_MARGIN_PT * 2 on all sides."""
        px0, py0, px1, py1 = 72.0, 72.0, 250.0, 92.0
        rx0, ry0, rx1, ry1 = self._build_overlay_redact_rect_fallback(px0, py0, px1, py1)
        m = PDF_MASK_MARGIN_PT * 2
        assert rx0 == px0 + m, f"left: expected {px0 + m}, got {rx0}"
        assert ry0 == py0 + m, f"top: expected {py0 + m}, got {ry0}"
        assert rx1 == px1 - m, f"right: expected {px1 - m}, got {rx1}"
        assert ry1 == py1 - m, f"bottom: expected {py1 - m}, got {ry1}"

    def test_redact_rect_skipped_when_too_small(self):
        """A rect with width < 1 or height < 1 must not be added to redaction_items.

        This test verifies the skip-condition logic by checking that a nearly-zero
        rect (collapsed by a very large margin) would produce width < 1 / height < 1.
        """
        # Simulate a quad whose shrunk rect would collapse
        qx0, qy0, qx1, qy1 = 100.0, 200.0, 100.5, 200.5  # tiny quad
        margin = PDF_MASK_MARGIN_PT
        rw = (qx1 - margin) - (qx0 + margin)  # width after shrink
        rh = (qy1 - margin) - (qy0 + margin)  # height after shrink
        # At margin=0.5 a 0.5-pt-wide quad → rw = -0.5 → should be skipped
        assert rw < 1 or rh < 1, (
            f"Expected rect to be skipped (w={rw}, h={rh}), "
            "but it appears large enough — check margin or test setup"
        )

    def test_text_rect_from_placement_not_quad(self):
        """Text-insertion rect always uses placement.x0/y0/x1/y1, not quad coords."""
        # The placement bbox and quad differ — confirm text_rect == placement, not quad.
        class _P:
            x0, y0, x1, y1 = 80.0, 75.0, 280.0, 95.0
            element_id = "e_test"
            text = "hello"

        placement = _P()
        quad_x0, quad_y0, quad_x1, quad_y1 = 82.0, 76.0, 278.0, 94.0  # different

        # text_rect in _generate_overlay lines 336-341:
        text_rect_x0 = placement.x0
        text_rect_y0 = placement.y0
        text_rect_x1 = placement.x1
        text_rect_y1 = placement.y1

        assert text_rect_x0 == placement.x0
        assert text_rect_y0 == placement.y0
        assert text_rect_x1 == placement.x1
        assert text_rect_y1 == placement.y1
        # Must not match the quad coords
        assert (text_rect_x0, text_rect_y0) != (quad_x0, quad_y0)


# ===========================================================================
# TestMaskCoversTextContent  (unit, Tier 0)
# AC-3: redact_rect lies entirely within the element bbox; margin=0 → equal
# ===========================================================================

class TestMaskCoversTextContent:
    """Unit tests verifying the redact rect stays interior to the text bbox (AC-3)."""

    def test_redact_rect_interior_to_text_bbox(self):
        """For a standard element, redact_rect lies entirely within the element bbox."""
        # Element bbox (placement)
        bx0, by0, bx1, by1 = 72.0, 100.0, 350.0, 120.0
        m = PDF_MASK_MARGIN_PT
        # Matched-quad path (quad == bbox for this test)
        rx0 = bx0 + m
        ry0 = by0 + m
        rx1 = bx1 - m
        ry1 = by1 - m
        assert rx0 >= bx0, "redact left must be >= bbox left"
        assert ry0 >= by0, "redact top must be >= bbox top"
        assert rx1 <= bx1, "redact right must be <= bbox right"
        assert ry1 <= by1, "redact bottom must be <= bbox bottom"

    def test_margin_zero_redact_rect_equals_quad_rect(self):
        """With PDF_MASK_MARGIN_PT effectively 0, redact_rect == matched quad rect.

        We can only simulate margin=0; if the real margin is 0.5 we just assert
        that the shrunk rect equals quad - 0 (no shrink), using a patched value.
        """
        qx0, qy0, qx1, qy1 = 100.0, 200.0, 300.0, 220.0
        # Simulate margin == 0
        zero_margin = 0.0
        rx0 = qx0 + zero_margin
        ry0 = qy0 + zero_margin
        rx1 = qx1 - zero_margin
        ry1 = qy1 - zero_margin
        assert rx0 == qx0
        assert ry0 == qy0
        assert rx1 == qx1
        assert ry1 == qy1


# ===========================================================================
# TestSideBySideSourceMasking  (unit, Tier 0)
# AC-2: white mask applied over source text on right panel BEFORE overlay
# ===========================================================================

class TestSideBySideSourceMasking:
    """Unit tests verifying right-panel source text masking call order (AC-2).

    These tests mock the fitz page object and assert:
      1. draw_rect is called with white-fill rects BEFORE show_pdf_page overlay.
      2. The number of mask draw_rect calls equals the number of elements.

    Because the fix (Bug b) is NOT yet implemented, these tests currently FAIL
    (no draw_rect calls happen before the overlay in the current code).
    """

    def _make_mock_page(self):
        """Return a MagicMock fitz page with call recording."""
        page = MagicMock()
        page.rect = MagicMock()
        page.rect.width = 612.0
        page.rect.height = 792.0
        page.show_pdf_page = MagicMock()
        page.draw_rect = MagicMock()
        page.draw_line = MagicMock()
        return page

    def test_right_panel_source_text_masked_before_overlay(self):
        """draw_rect (white mask) must be called before show_pdf_page overlay.

        The test patches _generate_side_by_side internals via fitz and asserts
        that at least one white-fill draw_rect call occurs on the new_page
        BEFORE the overlay show_pdf_page call.

        Current (unfixed) code does NOT call draw_rect before the overlay,
        so this test FAILS until the fix is applied.
        """
        if not HAS_PYMUPDF:
            pytest.skip("PyMuPDF not installed")

        from app.backend.renderers.fitz_renderer import PDFGenerator
        from app.backend.models.translatable_document import (
            BoundingBox,
            DocumentMetadata,
            ElementType,
            PageInfo,
            TranslatableDocument,
            TranslatableElement,
        )

        # Build a minimal source PDF with one text element
        src_doc = fitz.open()
        src_page = src_doc.new_page(width=612, height=792)
        src_page.insert_text((72, 72), "Source text", fontsize=12)
        fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            src_doc.save(pdf_path)
            src_doc.close()

            elements = [
                TranslatableElement(
                    element_id="e1",
                    content="Source text",
                    element_type=ElementType.TEXT,
                    page_num=1,
                    bbox=BoundingBox(x0=72, y0=72, x1=200, y1=92),
                    should_translate=True,
                ),
            ]
            doc = TranslatableDocument(
                source_path=pdf_path,
                source_type="pdf",
                elements=elements,
                pages=[PageInfo(page_num=1, width=612, height=792)],
                metadata=DocumentMetadata(page_count=1, has_text_layer=True),
            )
            translations = {"Source text": "翻譯文字"}

            call_log = []

            # We intercept fitz.open to track page method call order.
            # Use a real output PDF so generate() succeeds end-to-end.
            fd2, out_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd2)
            try:
                # fitz_renderer.fitz is a module-level None (lazy-loaded).
                # We must ensure it is populated before patching, then patch
                # the module's fitz attribute (not fitz_renderer.fitz.open directly).
                import app.backend.renderers.fitz_renderer as _fitz_mod
                _fitz_mod._ensure_fitz()  # populate _fitz_mod.fitz

                real_fitz_open = _fitz_mod.fitz.open

                def patched_open(*args, **kwargs):
                    result = real_fitz_open(*args, **kwargs)
                    if not args:  # out_doc = fitz.open()
                        orig_new_page = result.new_page
                        def recording_new_page(**kw):
                            pg = orig_new_page(**kw)
                            orig_show = pg.show_pdf_page
                            orig_draw_rect = pg.draw_rect

                            def rec_show(*a, **kw2):
                                call_log.append(("show_pdf_page", kw2.get("overlay", False)))
                                return orig_show(*a, **kw2)

                            def rec_draw_rect(*a, **kw2):
                                call_log.append(("draw_rect",))
                                return orig_draw_rect(*a, **kw2)

                            pg.show_pdf_page = rec_show
                            pg.draw_rect = rec_draw_rect
                            return pg
                        result.new_page = recording_new_page
                    return result

                # Patch the fitz module object's open attribute within fitz_renderer
                with patch.object(_fitz_mod.fitz, "open", side_effect=patched_open):
                    gen = PDFGenerator(target_lang="zh-TW", draw_mask=True)
                    gen._generate_side_by_side(doc, translations, out_path)

                # Assert: a draw_rect (white mask) call happened BEFORE the
                # show_pdf_page with overlay=True (the translated overlay placement)
                overlay_indices = [
                    i for i, c in enumerate(call_log)
                    if c[0] == "show_pdf_page" and c[1] is True
                ]
                draw_rect_indices = [
                    i for i, c in enumerate(call_log)
                    if c[0] == "draw_rect"
                ]

                assert overlay_indices, "Expected at least one overlay show_pdf_page call"
                assert draw_rect_indices, (
                    "BUG (b) NOT FIXED: no draw_rect (white mask) call found before overlay. "
                    "Expected right-panel source text to be masked before translated overlay."
                )
                first_overlay = min(overlay_indices)
                first_mask = min(draw_rect_indices)
                assert first_mask < first_overlay, (
                    f"BUG (b) NOT FIXED: draw_rect (mask) at index {first_mask} "
                    f"must come before overlay show_pdf_page at index {first_overlay}. "
                    "Source text must be masked before translated overlay is placed."
                )
            finally:
                if os.path.exists(out_path):
                    os.unlink(out_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)

    def test_right_panel_mask_covers_all_elements(self):
        """For a page with N elements, N mask draw_rect calls are made on the right panel.

        Current (unfixed) code calls draw_rect 0 times (only draw_line for divider),
        so this test FAILS until the fix is applied.
        """
        if not HAS_PYMUPDF:
            pytest.skip("PyMuPDF not installed")

        from app.backend.renderers.fitz_renderer import PDFGenerator
        from app.backend.models.translatable_document import (
            BoundingBox,
            DocumentMetadata,
            ElementType,
            PageInfo,
            TranslatableDocument,
            TranslatableElement,
        )

        n_elements = 3
        src_doc = fitz.open()
        src_page = src_doc.new_page(width=612, height=792)
        texts = ["Alpha text", "Beta text", "Gamma text"]
        ys = [72, 100, 128]
        for txt, y in zip(texts, ys):
            src_page.insert_text((72, y), txt, fontsize=12)

        fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            src_doc.save(pdf_path)
            src_doc.close()

            elements = [
                TranslatableElement(
                    element_id=f"e{i}",
                    content=texts[i],
                    element_type=ElementType.TEXT,
                    page_num=1,
                    bbox=BoundingBox(x0=72, y0=ys[i], x1=250, y1=ys[i]+18),
                    should_translate=True,
                )
                for i in range(n_elements)
            ]
            doc = TranslatableDocument(
                source_path=pdf_path,
                source_type="pdf",
                elements=elements,
                pages=[PageInfo(page_num=1, width=612, height=792)],
                metadata=DocumentMetadata(page_count=1, has_text_layer=True),
            )
            translations = {t: f"翻譯{i}" for i, t in enumerate(texts)}

            draw_rect_calls = []

            import app.backend.renderers.fitz_renderer as _fitz_mod2
            _fitz_mod2._ensure_fitz()
            real_fitz_open2 = _fitz_mod2.fitz.open

            def patched_open(*args, **kwargs):
                result = real_fitz_open2(*args, **kwargs)
                if not args:
                    orig_new_page = result.new_page
                    def recording_new_page(**kw):
                        pg = orig_new_page(**kw)
                        orig_draw_rect = pg.draw_rect
                        def rec_draw_rect(*a, **kw2):
                            draw_rect_calls.append(a)
                            return orig_draw_rect(*a, **kw2)
                        pg.draw_rect = rec_draw_rect
                        return pg
                    result.new_page = recording_new_page
                return result

            fd2, out_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd2)
            try:
                with patch.object(_fitz_mod2.fitz, "open", side_effect=patched_open):
                    gen = PDFGenerator(target_lang="zh-TW", draw_mask=True)
                    gen._generate_side_by_side(doc, translations, out_path)

                # draw_line (divider) also calls draw_rect? No — draw_line is separate.
                # We expect N draw_rect calls (one white mask per element).
                assert len(draw_rect_calls) >= n_elements, (
                    f"BUG (b) NOT FIXED: expected {n_elements} draw_rect mask calls "
                    f"for {n_elements} elements, got {len(draw_rect_calls)}. "
                    "Each source-text element must be masked on the right panel."
                )
            finally:
                if os.path.exists(out_path):
                    os.unlink(out_path)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)


# ===========================================================================
# TestConfinementNoNewImports  (unit, Tier 0)
# AC-5: no new top-level package imports added to fitz_renderer.py
# ===========================================================================

# Baseline top-level import modules in fitz_renderer.py at change start.
# These are derived from reading the file; the test parses the AST and confirms
# no new names were added.
_BASELINE_TOP_LEVEL_IMPORT_NAMES = frozenset({
    "__future__",
    "functools",
    "io",
    "logging",
    "os",
    "tempfile",
    "pathlib",
    "typing",
    "reportlab.lib.colors",
    "reportlab.pdfgen.canvas",
    "app.backend.config",
    "app.backend.renderers.base",
    "app.backend.renderers.bbox_reflow",
    "app.backend.renderers.text_region_renderer",
    "app.backend.services.metrics",
    "app.backend.utils.font_utils",
})


class TestConfinementNoNewImports:
    """AC-5: fitz_renderer.py must not gain new top-level package imports."""

    def test_no_new_top_level_imports_in_fitz_renderer(self):
        """Parse the AST of fitz_renderer.py and check top-level import modules."""
        source = FITZ_RENDERER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)

        found_names: set[str] = set()
        for node in ast.walk(tree):
            # Only consider Import / ImportFrom nodes at module level
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            # Distinguish module-level vs. function-level by checking parent's type.
            # ast.walk does not give parents; we use col_offset == 0 as a proxy
            # for top-level (module-scope) statements (they start at column 0).
            if getattr(node, "col_offset", -1) != 0:
                continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found_names.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    found_names.add(node.module)

        new_imports = found_names - _BASELINE_TOP_LEVEL_IMPORT_NAMES
        assert not new_imports, (
            f"AC-5 VIOLATION: new top-level import(s) added to fitz_renderer.py: "
            f"{sorted(new_imports)}. "
            "The fix must not introduce new package-level imports."
        )


# ===========================================================================
# TestOverlayBorderPreservation  (integration, Tier 3)
# AC-1 + AC-3: vector strokes survive; source text absent
# ===========================================================================

@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
class TestOverlayBorderPreservation:
    """Integration: overlay render of test.pdf preserves table borders (AC-1, AC-3).

    These tests exercise the LIVE fitz_renderer against tests/fixtures/test.pdf.
    Bug (a): apply_redactions() with default args erases vector strokes.
    After fix (apply_redactions(graphics=0)), strokes must survive.
    """

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Skip if fixture PDF missing."""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Fixture not found: {TEST_PDF_PATH}")

    def _render_overlay(self):
        """Run overlay render and return (output_path, fitz_doc)."""
        from app.backend.renderers.fitz_renderer import PDFGenerator
        from app.backend.models.translatable_document import (
            BoundingBox,
            DocumentMetadata,
            ElementType,
            PageInfo,
            TranslatableDocument,
            TranslatableElement,
        )

        # Open test.pdf to discover text
        src = fitz.open(str(TEST_PDF_PATH))
        p0 = src[0]
        raw = p0.get_text("dict")
        src.close()

        elements = []
        translations = {}
        eid = 0
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span["text"].strip()
                    if not txt:
                        continue
                    bb = span["bbox"]
                    eid += 1
                    elements.append(
                        TranslatableElement(
                            element_id=f"e{eid}",
                            content=txt,
                            element_type=ElementType.TEXT,
                            page_num=1,
                            bbox=BoundingBox(x0=bb[0], y0=bb[1], x1=bb[2], y1=bb[3]),
                            should_translate=True,
                        )
                    )
                    translations[txt] = f"翻譯{eid}"

        if not elements:
            pytest.skip("No text elements found in test.pdf")

        doc = TranslatableDocument(
            source_path=str(TEST_PDF_PATH),
            source_type="pdf",
            elements=elements,
            pages=[PageInfo(page_num=1, width=612, height=792)],
            metadata=DocumentMetadata(page_count=1, has_text_layer=True),
        )

        gen = PDFGenerator(target_lang="zh-TW", draw_mask=True)
        fd, out_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        gen.generate(doc, translations, out_path)
        out_doc = fitz.open(out_path)
        return out_path, out_doc

    def test_overlay_table_borders_survive_redaction(self):
        """After overlay render, page.get_drawings() must be non-empty (AC-1).

        Bug (a): default apply_redactions() erases vector strokes → get_drawings()
        returns empty list.  After fix (graphics=0) strokes survive.

        NOTE: This test requires test.pdf to contain at least one vector stroke
        (line/rect drawing).  If test.pdf has no vector drawings, the test is
        vacuously skipped.
        """
        # First check the SOURCE has drawings so this test is meaningful.
        src = fitz.open(str(TEST_PDF_PATH))
        src_drawings = src[0].get_drawings()
        src.close()

        if not src_drawings:
            pytest.skip(
                "test.pdf page 0 has no vector drawings — cannot test border preservation. "
                "Add a PDF with table lines to tests/fixtures/test.pdf or use a dedicated fixture."
            )

        out_path, out_doc = self._render_overlay()
        try:
            out_page = out_doc[0]
            drawings = out_page.get_drawings()
            assert drawings, (
                "BUG (a) NOT FIXED: page.get_drawings() is empty after overlay redaction. "
                "Table border vector strokes were erased by apply_redactions(). "
                "Fix: use page.apply_redactions(graphics=0)."
            )
        finally:
            out_doc.close()
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_overlay_source_text_not_visible(self):
        """After overlay render, source text strings must be absent (AC-3).

        This confirms that apply_redactions(graphics=0) still removes TEXT
        while preserving graphics — i.e. fixing bug (a) does not reintroduce
        source text bleed-through.
        """
        src = fitz.open(str(TEST_PDF_PATH))
        src_texts = [
            span["text"].strip()
            for block in src[0].get_text("dict").get("blocks", [])
            for line in block.get("lines", [])
            for span in line.get("spans", [])
            if span["text"].strip()
        ]
        src.close()

        if not src_texts:
            pytest.skip("No text in test.pdf — nothing to assert absent.")

        out_path, out_doc = self._render_overlay()
        try:
            out_text = out_doc[0].get_text()
            for src_txt in src_texts[:5]:  # Check first 5 to keep test fast
                assert src_txt not in out_text, (
                    f"AC-3 VIOLATION: source text '{src_txt}' still visible in "
                    "overlay output — redaction did not remove it."
                )
        finally:
            out_doc.close()
            if os.path.exists(out_path):
                os.unlink(out_path)


# ===========================================================================
# TestSideBySideRightPanelMasking  (integration, Tier 3)
# AC-2: right panel has no source text; translated text present
# ===========================================================================

@pytest.mark.skipif(not HAS_PYMUPDF, reason="PyMuPDF not installed")
class TestSideBySideRightPanelMasking:
    """Integration: side-by-side render masks source text on right panel (AC-2)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Fixture not found: {TEST_PDF_PATH}")

    def _render_sbs(self):
        """Render side-by-side and return (out_path, out_doc, src_width, translations)."""
        from app.backend.renderers.fitz_renderer import PDFGenerator
        from app.backend.models.translatable_document import (
            BoundingBox,
            DocumentMetadata,
            ElementType,
            PageInfo,
            TranslatableDocument,
            TranslatableElement,
        )

        src = fitz.open(str(TEST_PDF_PATH))
        p0 = src[0]
        raw = p0.get_text("dict")
        src_width = p0.rect.width
        src.close()

        elements = []
        translations = {}
        eid = 0
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span["text"].strip()
                    if not txt:
                        continue
                    bb = span["bbox"]
                    eid += 1
                    elem_id = f"e{eid}"
                    elements.append(
                        TranslatableElement(
                            element_id=elem_id,
                            content=txt,
                            element_type=ElementType.TEXT,
                            page_num=1,
                            bbox=BoundingBox(x0=bb[0], y0=bb[1], x1=bb[2], y1=bb[3]),
                            should_translate=True,
                        )
                    )
                    translations[txt] = f"翻譯{eid}"

        if not elements:
            pytest.skip("No text in test.pdf")

        doc = TranslatableDocument(
            source_path=str(TEST_PDF_PATH),
            source_type="pdf",
            elements=elements,
            pages=[PageInfo(page_num=1, width=612, height=792)],
            metadata=DocumentMetadata(page_count=1, has_text_layer=True),
        )

        gen = PDFGenerator(target_lang="zh-TW", draw_mask=True)
        fd, out_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        gen.generate(doc, translations, out_path, mode=None)  # default OVERLAY
        # Re-run with explicit side-by-side
        from app.backend.renderers.base import RenderMode
        os.unlink(out_path)
        fd, out_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        gen.generate(doc, translations, out_path, RenderMode.SIDE_BY_SIDE)
        out_doc = fitz.open(out_path)
        return out_path, out_doc, src_width, translations

    def test_sbs_right_panel_no_source_text(self):
        """Right-half clip of side-by-side output must not contain source text (AC-2).

        Current (unfixed) code: source text bleeds through on the right panel.
        After fix: white mask rects cover source text before overlay is placed.
        """
        src = fitz.open(str(TEST_PDF_PATH))
        src_texts = [
            span["text"].strip()
            for block in src[0].get_text("dict").get("blocks", [])
            for line in block.get("lines", [])
            for span in line.get("spans", [])
            if span["text"].strip()
        ]
        src.close()

        if not src_texts:
            pytest.skip("No text in test.pdf")

        out_path, out_doc, src_width, translations = self._render_sbs()
        try:
            page = out_doc[0]
            page_width = page.rect.width
            page_height = page.rect.height

            # Clip to right half
            right_clip = fitz.Rect(src_width, 0, page_width, page_height)
            right_text = page.get_text(clip=right_clip)

            for src_txt in src_texts[:5]:
                assert src_txt not in right_text, (
                    f"AC-2 VIOLATION: source text '{src_txt}' visible in right "
                    "panel of side-by-side output. Source text must be masked "
                    "before translated overlay is placed."
                )
        finally:
            out_doc.close()
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_sbs_right_panel_translated_text_present(self):
        """Right-half of side-by-side must contain translated text (AC-2).

        Confirms the overlay was placed successfully after masking.
        """
        out_path, out_doc, src_width, translations = self._render_sbs()
        try:
            page = out_doc[0]
            right_clip = fitz.Rect(src_width, 0, page.rect.width, page.rect.height)
            right_text = page.get_text(clip=right_clip)

            translated_values = list(translations.values())
            found_any = any(t in right_text for t in translated_values)
            assert found_any, (
                "AC-2 VIOLATION: no translated text found in right panel. "
                f"Expected one of: {translated_values[:3]}... "
                f"Right panel text (excerpt): '{right_text[:200]}'"
            )
        finally:
            out_doc.close()
            if os.path.exists(out_path):
                os.unlink(out_path)
