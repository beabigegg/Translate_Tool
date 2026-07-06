"""Tests for post-render layout-confirmation surfacing (BR-38 no-silent-truncation).

Verifies that:
- AC-1: the fitz render overflow guard marks ``element.render_truncated`` when it
        drops lines (previously it only logged at debug — silent truncation).
- AC-2: the guard does NOT mark elements when the rendered lines fit (the
        data-shape contract forbids setting the flag for any other reason).
- AC-3: _translate_pdf_to_pdf emits render_truncation_warning via
        warnings_callback when a rendered element carries render_truncated.
- AC-4: no truncation → no layout-check warning.
- AC-5: truncation flags are reset per language render — a flag set during the
        first language's render must not leak into the second language's count,
        and stale pre-render flags must not produce a warning.
- AC-6: full-chain integration — a real fitz render of an oversized translation
        in a one-line bbox produces the job warning (proves element identity
        holds through bbox_reflow → renderer → post-render count).

Anti-tautology guards per CLAUDE.md:
- Wiring tests (AC-3..5) enter via _translate_pdf_to_pdf — the actual emit
  point — patching _dispatch_render at the consumer binding (pdf_processor
  module), NOT the renderer module.
- Guard tests (AC-1/2) enter via PDFGenerator._insert_text_in_rect with
  fit_text_cascade patched at the consumer binding (fitz_renderer module) to
  force a wrap/fit mismatch that only the render-time guard can catch.
- AC-6 patches nothing on the render path (real cascade, real TextWriter).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
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


def _make_doc(source_path: str, n_elements: int = 1) -> TranslatableDocument:
    elements = [
        TranslatableElement(
            element_id=f"e{i}",
            content=f"Hello World {i}",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=72 + 30 * i, x1=300, y1=90 + 30 * i),
            should_translate=True,
            reading_order=i,
        )
        for i in range(n_elements)
    ]
    return TranslatableDocument(
        source_path=source_path,
        source_type="pdf",
        elements=elements,
        pages=[PageInfo(page_num=1, width=612, height=792)],
        metadata=DocumentMetadata(page_count=1, has_text_layer=True),
        layout_viz=[],
    )


def _call_translate_pdf_to_pdf(_mod, in_path, out_path, captured, targets=None):
    """Invoke _translate_pdf_to_pdf with the standard test arguments."""
    return _mod._translate_pdf_to_pdf(
        in_path=in_path,
        out_path=out_path,
        targets=targets or ["English"],
        src_lang=None,
        client=MagicMock(),
        stop_flag=None,
        log=lambda s: None,
        skip_header_footer=False,
        layout_mode="overlay",
        warnings_callback=captured.append,
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-2: render overflow guard marks render_truncated (BR-38)
# ---------------------------------------------------------------------------

class TestOverflowGuardMarksTruncation:
    """The last-resort render overflow guard must not truncate silently."""

    def _render(self, fitted_text: str, rect_height: float):
        import fitz
        import app.backend.renderers.fitz_renderer as _fr
        from app.backend.renderers.text_region_renderer import CascadeDecision

        pdf = fitz.open()
        try:
            page = pdf.new_page(width=612, height=792)
            rect = fitz.Rect(72, 72, 300, 72 + rect_height)
            element = SimpleNamespace(render_truncated=False, style=None)

            decision = CascadeDecision(
                font_size=12.0,
                line_spacing=1.2,
                letter_spacing=0.0,
                overflow=False,
                truncated=False,
                fitted_text=fitted_text,
            )

            generator = _fr.PDFGenerator(
                target_lang="English", draw_mask=False, log=lambda s: None
            )
            # Consumer-binding patch: fitz_renderer's own fit_text_cascade name,
            # so _insert_text_in_rect renders from OUR decision and the guard is
            # the only mechanism left to catch the overflow.
            with patch.object(_fr, "fit_text_cascade", return_value=decision):
                generator._insert_text_in_rect(page, rect, "source", element=element)
            return element
        finally:
            pdf.close()

    def test_overflow_guard_sets_render_truncated(self):
        """AC-1: lines beyond the bbox bottom are dropped AND marked (BR-38)."""
        # ~28 pt tall rect fits at most 2 lines at 12 pt; 300 words wrap to many.
        element = self._render(fitted_text="word " * 300, rect_height=28.0)
        assert element.render_truncated is True, (
            "render overflow guard dropped lines without setting "
            "render_truncated — silent truncation violates BR-38"
        )

    def test_fitting_text_does_not_set_render_truncated(self):
        """AC-2: the guard must not over-mark when everything fits."""
        element = self._render(fitted_text="short line", rect_height=200.0)
        assert element.render_truncated is False, (
            "render_truncated was set even though no line was dropped — "
            "the data-shape contract forbids setting it for any other reason"
        )


# ---------------------------------------------------------------------------
# AC-3 / AC-4 / AC-5: post-render layout-confirmation warning wiring
# ---------------------------------------------------------------------------

class TestTruncationWarningWiring:
    """_translate_pdf_to_pdf surfaces render_truncated as a job warning."""

    def _run(self, tmp_path, fake_dispatch, targets=None, doc=None):
        import app.backend.processors.pdf_processor as _mod

        in_dir = tmp_path / "input"
        in_dir.mkdir(exist_ok=True)
        in_path = str(in_dir / "sample.pdf")
        Path(in_path).write_bytes(b"")  # stub; parser is mocked below
        out_path = str(tmp_path / "output.pdf")

        fake_doc = doc if doc is not None else _make_doc(in_path)
        fake_parser = MagicMock()
        fake_parser.parse.return_value = fake_doc

        captured = []
        # Lazy import inside _translate_pdf_to_pdf → patch the definition module.
        with patch(
            "app.backend.parsers.pdf_parser.PyMuPDFParser",
            return_value=fake_parser,
        ):
            with patch.object(
                _mod, "translate_blocks_batch",
                return_value=[(True, "translated")],
            ):
                with patch.object(_mod, "_dispatch_render", side_effect=fake_dispatch):
                    _call_translate_pdf_to_pdf(
                        _mod, in_path, out_path, captured, targets=targets
                    )
        return captured, fake_doc

    def test_truncation_emits_layout_warning(self, tmp_path):
        """AC-3: one truncated element → exactly one layout-check warning."""
        import app.backend.processors.pdf_processor as _mod

        def fake_dispatch(**kwargs):
            kwargs["doc"].elements[0].render_truncated = True

        captured, _ = self._run(tmp_path, fake_dispatch)
        assert captured == [_mod.render_truncation_warning(1, "English")], (
            f"expected the exact layout-check warning, got {captured!r}"
        )

    def test_truncation_count_reflects_all_marked_elements(self, tmp_path):
        """AC-3: the warning carries the number of truncated blocks."""
        import app.backend.processors.pdf_processor as _mod

        def fake_dispatch(**kwargs):
            for e in kwargs["doc"].elements:
                e.render_truncated = True

        doc = _make_doc(str(tmp_path / "input" / "sample.pdf"), n_elements=3)
        captured, _ = self._run(tmp_path, fake_dispatch, doc=doc)
        assert captured == [_mod.render_truncation_warning(3, "English")]

    def test_no_truncation_no_warning(self, tmp_path):
        """AC-4: clean render → warnings_callback never called."""
        captured, _ = self._run(tmp_path, lambda **kwargs: None)
        assert captured == [], f"expected no warnings, got {captured!r}"

    def test_flags_reset_between_languages(self, tmp_path):
        """AC-5: a flag set during language 1's render must not leak into
        language 2's count — only one warning, for the first language."""
        import app.backend.processors.pdf_processor as _mod

        calls = {"n": 0}

        def fake_dispatch(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                kwargs["doc"].elements[0].render_truncated = True

        captured, _ = self._run(
            tmp_path, fake_dispatch, targets=["English", "Japanese"]
        )
        assert calls["n"] == 2, "both languages must render"
        assert captured == [_mod.render_truncation_warning(1, "English")], (
            f"flag from language 1 leaked into language 2: {captured!r}"
        )

    def test_stale_pre_render_flags_cleared(self, tmp_path):
        """AC-5: a stale flag present BEFORE rendering (e.g. from deserialized
        IR) must be cleared and must not produce a warning on a clean render."""
        doc = _make_doc(str(tmp_path / "input" / "sample.pdf"))
        doc.elements[0].render_truncated = True

        captured, fake_doc = self._run(tmp_path, lambda **kwargs: None, doc=doc)
        assert captured == [], (
            f"stale pre-render flag produced a phantom warning: {captured!r}"
        )
        assert fake_doc.elements[0].render_truncated is False


# ---------------------------------------------------------------------------
# AC-6: full-chain integration (real parse + real fitz render)
# ---------------------------------------------------------------------------

class TestRealRenderTruncationIntegration:
    """End-to-end: oversized translation in a one-line bbox → job warning.

    Nothing on the render path is patched: real PyMuPDFParser.parse, real
    bbox_reflow, real fit_text_cascade, real fitz TextWriter. This proves the
    renderer marks the SAME element instances the processor counts afterwards.
    """

    def test_real_render_truncation_emits_warning(self, tmp_path, monkeypatch):
        import fitz
        import app.backend.processors.pdf_processor as _mod

        # Deterministic heuristic path (no ONNX download attempt in CI).
        monkeypatch.setenv("LAYOUT_DETECTOR_ENABLED", "false")

        in_dir = tmp_path / "input"
        in_dir.mkdir()
        in_path = str(in_dir / "sample.pdf")
        pdf = fitz.open()
        page = pdf.new_page(width=612, height=792)
        page.insert_text((72, 200), "Hello world sample text", fontsize=11)
        pdf.save(in_path)
        pdf.close()

        out_path = str(tmp_path / "out.pdf")
        captured = []

        # A translation far too long for a one-line bbox: the cascade exhausts
        # steps (a)-(d) and truncates at step (e), or the overflow guard fires.
        long_translation = "translated overflowing content " * 200
        overrides = {f"pdf:sample:{i}": long_translation for i in range(10)}

        stopped = _mod._translate_pdf_to_pdf(
            in_path=in_path,
            out_path=out_path,
            targets=["English"],
            src_lang=None,
            client=MagicMock(),
            stop_flag=None,
            log=lambda s: None,
            skip_header_footer=False,
            layout_mode="overlay",
            block_overrides=overrides,
            warnings_callback=captured.append,
        )

        assert stopped is False
        assert Path(out_path).exists(), "output PDF was not generated"
        assert _mod.FITZ_FALLBACK_WARNING not in captured, (
            "fitz primary render failed; this test requires the primary path"
        )
        layout_warnings = [w for w in captured if w.startswith("Layout check")]
        assert len(layout_warnings) == 1, (
            f"expected exactly one layout-check warning, got {captured!r} — "
            "truncation happened in the real render but was never surfaced"
        )
        assert "(English)" in layout_warnings[0]
        assert "truncated" in layout_warnings[0]
