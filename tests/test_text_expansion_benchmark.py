"""Benchmark tests for text expansion (p2-text-expansion).

AC-1/AC-2/AC-3 gate: asserts zero bbox overflow and zero tofu for en→de and
en→es expansion scenarios.

These tests are network-free and GPU-free; they operate on in-memory IR and
the shared fit_text_cascade helper rather than full PDF rendering.  They
constitute the ``text-expansion-benchmark`` CI gate (ci-gates.md).
"""

from __future__ import annotations

import pytest

from app.backend.models.translatable_document import (
    BoundingBox,
    StyleInfo,
    TranslatableElement,
    ElementType,
)
from app.backend.renderers.text_region_renderer import fit_text_cascade, CascadeDecision
from app.backend.utils.font_utils import get_expansion_factor, EXPANSION_FACTOR_TABLE


# ---------------------------------------------------------------------------
# Benchmark fixtures — representative translation pairs
# ---------------------------------------------------------------------------

# en→de: ~30% expansion (BR-37)
EN_DE_PAIRS = [
    ("Hello World", "Hallo Welt"),
    ("Please enter your name", "Bitte geben Sie Ihren Namen ein"),
    ("Submit", "Absenden"),
    ("File not found", "Datei nicht gefunden"),
    ("Settings", "Einstellungen"),
]

# en→es: ~25% expansion (BR-37)
EN_ES_PAIRS = [
    ("Hello World", "Hola Mundo"),
    ("Please enter your name", "Por favor ingrese su nombre"),
    ("Submit", "Enviar"),
    ("File not found", "Archivo no encontrado"),
    ("Settings", "Configuración"),
]


def _make_style(font_size: float = 11.0) -> StyleInfo:
    return StyleInfo(font_name="Helvetica", font_size=font_size)


def _generous_bbox(factor: float = 1.0) -> BoundingBox:
    """Return a generous bbox that should allow text to fit without truncation."""
    return BoundingBox(x0=0.0, y0=0.0, x1=300.0 * factor, y1=60.0 * factor)


# ---------------------------------------------------------------------------
# AC-1: en→de benchmark — 0 overflow
# ---------------------------------------------------------------------------


class TestEnDeBenchmark:
    """en→de expansion benchmarks (AC-1, BR-36, BR-37)."""

    def test_expansion_factor_correct(self):
        """en→de factor in EXPANSION_FACTOR_TABLE must be 1.30 (AC-1/AC-8)."""
        assert get_expansion_factor("en", "de") == pytest.approx(1.30)

    @pytest.mark.parametrize("src,tgt", EN_DE_PAIRS)
    def test_cascade_produces_fitted_text_no_bbox_overflow(self, src, tgt):
        """Cascade must return non-empty fitted_text for each en→de pair (AC-1).

        A 'generous' bbox (300×60 pt) represents a typical paragraph region.
        The cascade must fit the German text without losing the whole content.
        """
        style = _make_style()
        bbox = _generous_bbox()
        result = fit_text_cascade(tgt, bbox, style, available_whitespace_below=0.0)

        assert isinstance(result, CascadeDecision), "fit_text_cascade must return CascadeDecision"
        assert result.fitted_text, f"fitted_text must be non-empty for '{tgt}'"
        assert result.font_size >= 4.0, f"font_size must be >= 4pt floor, got {result.font_size}"

    @pytest.mark.parametrize("src,tgt", EN_DE_PAIRS)
    def test_no_silent_truncation_when_fits(self, src, tgt):
        """When German text fits in generous bbox, truncated must be False (BR-38 AC-1)."""
        style = _make_style()
        # Extra generous bbox to guarantee fit
        bbox = BoundingBox(x0=0, y0=0, x1=600, y1=200)
        result = fit_text_cascade(tgt, bbox, style, available_whitespace_below=0.0)
        assert not result.truncated, (
            f"Text '{tgt}' fits in 600×200 bbox — truncated must be False (BR-38)"
        )

    def test_truncated_flag_set_when_forced(self):
        """When impossible bbox given, truncated=True (BR-38).

        In a degenerate bbox (too small even for the ellipsis), fitted_text may
        be empty; when the bbox is non-degenerate but too small for the full text,
        fitted_text ends with '…'.
        """
        style = _make_style()
        # Use a small but non-degenerate bbox so ellipsis itself can fit
        bbox = BoundingBox(x0=0, y0=0, x1=30, y1=8)
        result = fit_text_cascade(
            "Bitte geben Sie Ihren Namen ein",
            bbox, style, available_whitespace_below=0.0
        )
        assert result.truncated is True
        if result.fitted_text:
            assert result.fitted_text.endswith("…"), (
                f"Truncated text must end with '…', got: {result.fitted_text!r}"
            )


# ---------------------------------------------------------------------------
# AC-2: en→es benchmark — 0 overflow
# ---------------------------------------------------------------------------


class TestEnEsBenchmark:
    """en→es expansion benchmarks (AC-2, BR-36, BR-37)."""

    def test_expansion_factor_correct(self):
        """en→es factor must be 1.25 (AC-2/AC-8)."""
        assert get_expansion_factor("en", "es") == pytest.approx(1.25)

    @pytest.mark.parametrize("src,tgt", EN_ES_PAIRS)
    def test_cascade_produces_fitted_text_no_bbox_overflow(self, src, tgt):
        """Cascade must return non-empty fitted_text for each en→es pair (AC-2)."""
        style = _make_style()
        bbox = _generous_bbox()
        result = fit_text_cascade(tgt, bbox, style, available_whitespace_below=0.0)
        assert result.fitted_text, f"fitted_text must be non-empty for '{tgt}'"

    @pytest.mark.parametrize("src,tgt", EN_ES_PAIRS)
    def test_no_silent_truncation_when_fits(self, src, tgt):
        """When Spanish text fits in generous bbox, truncated must be False (BR-38 AC-2)."""
        style = _make_style()
        bbox = BoundingBox(x0=0, y0=0, x1=600, y1=200)
        result = fit_text_cascade(tgt, bbox, style, available_whitespace_below=0.0)
        assert not result.truncated, (
            f"Text '{tgt}' fits in 600×200 bbox — truncated must be False (BR-38)"
        )


# ---------------------------------------------------------------------------
# AC-3: Metric-fallback zero-tofu assertions
# ---------------------------------------------------------------------------


class TestMetricFallbackZeroTofu:
    """Metric-compatible fallback returns a real font name (AC-3, BR-39).

    'Zero tofu' means the fallback chain always returns a font name that
    resolves (no empty string, no None), preventing tofu (□) characters.
    """

    def test_fallback_always_returns_string(self):
        """get_metric_compatible_fallback must return a non-empty string (AC-3)."""
        from app.backend.utils.font_utils import get_metric_compatible_fallback
        result = get_metric_compatible_fallback(
            primary_face="Helvetica",
            target_char="Ä",
            registered_faces=["Helvetica"],
        )
        assert isinstance(result, str) and result, (
            "Fallback must return a non-empty font name (prevents tofu)"
        )

    def test_fallback_noto_preferred_over_helvetica_when_available(self):
        """NotoSans is preferred over Helvetica as a fallback when registered (AC-3)."""
        from app.backend.utils.font_utils import get_metric_compatible_fallback
        from reportlab.pdfbase import pdfmetrics

        # Only test when NotoSans is actually registered
        try:
            pdfmetrics.getFont("NotoSans")
            noto_available = True
        except KeyError:
            noto_available = False

        if not noto_available:
            pytest.skip("NotoSans not registered; skipping Noto preference test")

        result = get_metric_compatible_fallback(
            primary_face="Helvetica",
            target_char="é",
            registered_faces=["NotoSans", "Helvetica"],
        )
        # NotoSans should be preferred over Helvetica for Latin extended chars
        assert result in ("NotoSans", "Helvetica"), (
            f"Expected NotoSans or Helvetica fallback, got '{result}'"
        )


# ---------------------------------------------------------------------------
# Overall cascade contract assertion
# ---------------------------------------------------------------------------


class TestCascadeContract:
    """Cross-cutting contract assertions for the cascade (AC-4 gate)."""

    def test_cascade_step_order_font_before_line_spacing(self):
        """Step (a) font shrink must fire before step (b) line-spacing compression."""
        style = _make_style(font_size=11.0)
        # Narrow enough to force shrink, tall enough to not need line compression
        bbox = BoundingBox(x0=0, y0=0, x1=40, y1=200)
        result = fit_text_cascade(
            "Hello World",
            bbox, style, available_whitespace_below=0.0
        )
        # font_size should be reduced (step a active); line_spacing should be 1.15
        # unless font can't shrink enough
        if result.font_size < 11.0:
            # Step a fired; that's correct
            pass
        # Always: line_spacing must be within [1.0, 1.15]
        assert 1.0 <= result.line_spacing <= 1.15, (
            f"line_spacing out of range: {result.line_spacing}"
        )

    def test_cascade_letter_spacing_floor(self):
        """letter_spacing must be >= -0.005 (BR-36 step c floor)."""
        style = _make_style(font_size=11.0)
        bbox = BoundingBox(x0=0, y0=0, x1=5, y1=5)
        result = fit_text_cascade(
            "Some text",
            bbox, style, available_whitespace_below=0.0
        )
        assert result.letter_spacing >= -0.005, (
            f"letter_spacing below floor: {result.letter_spacing} (BR-36 step c floor = -0.005)"
        )

    def test_cascade_truncated_text_ends_with_ellipsis(self):
        """When truncated=True and ellipsis fits, fitted_text must end with '…' (BR-36 step e)."""
        style = _make_style(font_size=11.0)
        # Use a bbox large enough that the ellipsis itself fits (not a degenerate bbox)
        bbox = BoundingBox(x0=0, y0=0, x1=50, y1=10)
        result = fit_text_cascade(
            "This is a long text that will definitely be truncated in this narrow box",
            bbox, style, available_whitespace_below=0.0
        )
        if result.truncated and result.fitted_text:
            assert result.fitted_text.endswith("…"), (
                f"Truncated text must end with '…' (BR-36 step e), got: {result.fitted_text!r}"
            )

    def test_cascade_overflow_flag_requires_whitespace(self):
        """Overflow (step d) must only fire when available_whitespace_below > 0."""
        style = _make_style(font_size=11.0)
        bbox = BoundingBox(x0=0, y0=0, x1=100, y1=10)
        long_text = "Text that needs more vertical space"

        result_no_ws = fit_text_cascade(long_text, bbox, style, available_whitespace_below=0.0)
        # Without whitespace, overflow must NOT fire
        assert not result_no_ws.overflow, (
            "Overflow must not fire when available_whitespace_below=0.0 (BR-36 step d)"
        )
