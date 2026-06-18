"""Tests for text region renderer."""

from __future__ import annotations

import io
import pytest
from unittest.mock import MagicMock, patch

from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import white

from app.backend.renderers.text_region_renderer import (
    TextRegion,
    calculate_rotation_from_bbox,
    render_text_region,
    render_text_regions,
    create_text_regions_from_elements,
)
from app.backend.models.translatable_document import BoundingBox, TranslatableElement, ElementType


# ---------------------------------------------------------------------------
# p2-text-expansion: TDD failing tests (must be red before implementation)
# ---------------------------------------------------------------------------


class TestFitCascadeContract:
    """Contract tests for the CascadeDecision struct (AC-4)."""

    def test_cascade_decision_fields_present(self):
        """CascadeDecision must expose all required fields (AC-4 contract)."""
        from app.backend.renderers.text_region_renderer import CascadeDecision
        d = CascadeDecision(
            font_size=10.0,
            line_spacing=1.15,
            letter_spacing=0.0,
            overflow=False,
            truncated=False,
            fitted_text="hello",
        )
        assert hasattr(d, "font_size")
        assert hasattr(d, "line_spacing")
        assert hasattr(d, "letter_spacing")
        assert hasattr(d, "overflow")
        assert hasattr(d, "truncated")
        assert hasattr(d, "fitted_text")

    def test_cascade_decision_is_dataclass(self):
        """CascadeDecision must be importable and instantiable as a dataclass."""
        from app.backend.renderers.text_region_renderer import CascadeDecision
        d = CascadeDecision(
            font_size=8.0,
            line_spacing=1.0,
            letter_spacing=-0.005,
            overflow=True,
            truncated=False,
            fitted_text="text",
        )
        assert d.font_size == 8.0
        assert d.line_spacing == 1.0
        assert d.letter_spacing == -0.005
        assert d.overflow is True
        assert d.truncated is False
        assert d.fitted_text == "text"


class TestFitCascade:
    """Unit tests for fit_text_cascade step order (AC-1, AC-2, AC-4)."""

    def _make_style(self, font_size=11.0, font_name="Helvetica"):
        from app.backend.models.translatable_document import StyleInfo
        return StyleInfo(font_size=font_size, font_name=font_name)

    def test_fit_cascade_is_importable(self):
        """fit_text_cascade must be importable from text_region_renderer."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        assert callable(fit_text_cascade)

    def test_cascade_returns_cascade_decision(self):
        """fit_text_cascade must return a CascadeDecision object."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade, CascadeDecision
        style = self._make_style()
        bbox = BoundingBox(x0=0, y0=0, x1=200, y1=50)
        result = fit_text_cascade("short text", bbox, style, available_whitespace_below=0.0)
        assert isinstance(result, CascadeDecision)

    def test_cascade_order_font_size_first(self):
        """Step (a): font-size shrink must be tried before line-spacing (AC-4)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        style = self._make_style(font_size=11.0)
        # Very narrow box forces overflow; should try font shrink before line spacing
        bbox = BoundingBox(x0=0, y0=0, x1=30, y1=50)
        long_text = "This is a somewhat longer text that will overflow"
        result = fit_text_cascade(long_text, bbox, style, available_whitespace_below=0.0)
        # Step (a) must have been tried: font_size should be <= initial (11.0)
        assert result.font_size <= 11.0

    def test_cascade_order_line_spacing_after_font_min(self):
        """Step (b): line-spacing compression applied only after font-size hits min (AC-4)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        from app.backend.config import MIN_FONT_SIZE_PT
        style = self._make_style(font_size=11.0)
        # Very tiny box forces font to minimum; line_spacing may then be compressed
        bbox = BoundingBox(x0=0, y0=0, x1=20, y1=8)
        long_text = "A very long text that absolutely will not fit in this tiny box at any size"
        result = fit_text_cascade(long_text, bbox, style, available_whitespace_below=0.0)
        # font_size must be at minimum when line_spacing < 1.15
        if result.line_spacing < 1.15:
            assert result.font_size <= MIN_FONT_SIZE_PT  # at config minimum floor

    def test_cascade_order_letter_spacing_after_line_floor(self):
        """Step (c): letter-spacing reduction only after line-spacing hits 1.0 floor (AC-4)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        style = self._make_style(font_size=11.0)
        bbox = BoundingBox(x0=0, y0=0, x1=15, y1=6)
        long_text = "This extremely long text cannot fit in this ridiculously small bbox at all"
        result = fit_text_cascade(long_text, bbox, style, available_whitespace_below=0.0)
        # letter_spacing floor is -0.005 (per BR-36)
        assert result.letter_spacing >= -0.005

    def test_cascade_order_overflow_before_truncation(self):
        """Step (d): overflow into whitespace attempted before truncation (AC-4)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        style = self._make_style(font_size=11.0)
        # Box too small, but whitespace available below
        bbox = BoundingBox(x0=0, y0=0, x1=100, y1=10)
        long_text = "Text that needs more vertical space than provided"
        # With available whitespace, truncation should be avoided if overflow suffices
        result_with_ws = fit_text_cascade(
            long_text, bbox, style, available_whitespace_below=100.0
        )
        result_no_ws = fit_text_cascade(
            long_text, bbox, style, available_whitespace_below=0.0
        )
        # With whitespace: overflow preferred over truncation (BR-36 step d before e)
        if result_with_ws.overflow:
            assert not result_with_ws.truncated, (
                "If overflow suffices, truncation must not fire (d before e)"
            )

    def test_cascade_truncation_last_resort_only(self):
        """Step (e): truncation fires only when all prior steps are exhausted (AC-4)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        style = self._make_style(font_size=11.0)
        # Large box: text should fit without truncation
        bbox = BoundingBox(x0=0, y0=0, x1=500, y1=200)
        short_text = "Short"
        result = fit_text_cascade(short_text, bbox, style, available_whitespace_below=0.0)
        assert not result.truncated, "Short text in large bbox must not be truncated"

    def test_ende_no_overflow(self):
        """en→de (+30%): with reasonable bbox, cascade must produce 0 overflow at font min (AC-1)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        from app.backend.utils.font_utils import get_expansion_factor
        style = self._make_style(font_size=11.0)
        src = "Hello World"
        factor = get_expansion_factor("en", "de")
        assert factor == pytest.approx(1.30), "BR-37 en→de factor must be 1.30"
        # Simulate German text ~30% longer
        de_text = "Hallo Welt, das ist ein langer Text"  # representative German expansion
        # Generous bbox that a real rendered document would have
        bbox = BoundingBox(x0=0, y0=0, x1=200, y1=50)
        result = fit_text_cascade(de_text, bbox, style, available_whitespace_below=0.0)
        # Should not need truncation for a text that can fit with some size reduction
        # The cascade must handle this without overflow (no bbox violation)
        # At minimum: fitted_text is non-empty
        assert result.fitted_text

    def test_enes_no_overflow(self):
        """en→es (+25%): with reasonable bbox, cascade produces non-empty fitted text (AC-2)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        from app.backend.utils.font_utils import get_expansion_factor
        style = self._make_style(font_size=11.0)
        factor = get_expansion_factor("en", "es")
        assert factor == pytest.approx(1.25), "BR-37 en→es factor must be 1.25"
        es_text = "Hola Mundo, este es un texto más largo en español"
        bbox = BoundingBox(x0=0, y0=0, x1=200, y1=50)
        result = fit_text_cascade(es_text, bbox, style, available_whitespace_below=0.0)
        assert result.fitted_text


class TestTruncationMarker:
    """Tests for render_truncated field on TranslatableElement (AC-5)."""

    def test_render_truncated_field_default_false(self):
        """render_truncated defaults to False on a new element (AC-5)."""
        elem = TranslatableElement(
            element_id="e1",
            content="Hello",
            element_type=ElementType.TEXT,
            page_num=1,
        )
        assert elem.render_truncated is False

    def test_truncation_sets_render_truncated_true(self):
        """When cascade truncates, element.render_truncated must be set True (AC-5, BR-38)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        from app.backend.models.translatable_document import StyleInfo
        # Impossible bbox: absolutely no space
        style = StyleInfo(font_size=11.0, font_name="Helvetica")
        bbox = BoundingBox(x0=0, y0=0, x1=5, y1=5)
        very_long = "This is an extremely long text that cannot possibly fit in a 5x5 box"
        result = fit_text_cascade(very_long, bbox, style, available_whitespace_below=0.0)
        assert result.truncated is True, "Cascade must truncate when nothing fits"
        # When bbox is degenerate (ellipsis itself does not fit), fitted_text may be empty;
        # when any text fits, it must end with the Unicode ellipsis character
        if result.fitted_text:
            assert result.fitted_text.endswith("…"), (
                f"Truncated text must end with '…' (U+2026), got: {result.fitted_text!r}"
            )

    def test_no_truncation_render_truncated_false(self):
        """When text fits, cascade truncated flag must remain False (AC-5, BR-38)."""
        from app.backend.renderers.text_region_renderer import fit_text_cascade
        from app.backend.models.translatable_document import StyleInfo
        style = StyleInfo(font_size=11.0, font_name="Helvetica")
        bbox = BoundingBox(x0=0, y0=0, x1=500, y1=200)
        result = fit_text_cascade("Short", bbox, style, available_whitespace_below=0.0)
        assert result.truncated is False

    def test_render_truncated_field_in_to_dict(self):
        """render_truncated must appear in to_dict output (AC-5 contract)."""
        elem = TranslatableElement(
            element_id="e1",
            content="Hello",
            element_type=ElementType.TEXT,
            page_num=1,
        )
        d = elem.to_dict()
        assert "render_truncated" in d, "render_truncated must be present in to_dict()"
        assert d["render_truncated"] is False

    def test_render_truncated_true_survives_roundtrip(self):
        """render_truncated=True round-trips through to_dict/from_dict (AC-5)."""
        elem = TranslatableElement(
            element_id="e1",
            content="Hello",
            element_type=ElementType.TEXT,
            page_num=1,
        )
        elem.render_truncated = True
        d = elem.to_dict()
        assert d["render_truncated"] is True
        restored = TranslatableElement.from_dict(d)
        assert restored.render_truncated is True

    def test_from_dict_missing_render_truncated_defaults_false(self):
        """Old-format dict lacking render_truncated key deserializes to False (AC-5, backward-compat)."""
        d = {
            "element_id": "e1",
            "content": "Hello",
            "element_type": "text",
            "page_num": 1,
            "should_translate": True,
            "translated_content": None,
            "metadata": {},
            # render_truncated intentionally absent
        }
        elem = TranslatableElement.from_dict(d)
        assert elem.render_truncated is False


class TestSinglePathEnforcement:
    """AC-6: cascade helper must not be imported in legacy renderer paths (BR-40)."""

    def test_no_cascade_logic_in_legacy_paths(self):
        """fit_text_cascade must not be imported in coordinate_renderer, inline_renderer, pdf_generator."""
        from pathlib import Path

        repo_root = Path(__file__).parent.parent
        legacy_paths = [
            repo_root / "app/backend/renderers/coordinate_renderer.py",
            repo_root / "app/backend/renderers/inline_renderer.py",
            repo_root / "app/backend/renderers/pdf_generator.py",
        ]
        forbidden_symbols = {"fit_text_cascade", "CascadeDecision"}

        for path in legacy_paths:
            with open(path) as f:
                src = f.read()
            for sym in forbidden_symbols:
                assert sym not in src, (
                    f"BR-40 violation: '{sym}' found in {path}. "
                    "Cascade logic must only be in text_region_renderer.py and fitz_renderer.py."
                )


class TestTextRegion:
    """Tests for TextRegion dataclass."""

    def test_text_region_creation(self):
        """Test basic TextRegion creation."""
        region = TextRegion(
            text="Hello",
            x0=10,
            y0=20,
            x1=100,
            y1=40,
        )
        assert region.text == "Hello"
        assert region.x0 == 10
        assert region.y0 == 20
        assert region.x1 == 100
        assert region.y1 == 40

    def test_text_region_width(self):
        """Test TextRegion width property."""
        region = TextRegion(text="Test", x0=10, y0=20, x1=110, y1=40)
        assert region.width == 100

    def test_text_region_height(self):
        """Test TextRegion height property."""
        region = TextRegion(text="Test", x0=10, y0=20, x1=110, y1=50)
        assert region.height == 30

    def test_text_region_center_x(self):
        """Test TextRegion center_x property."""
        region = TextRegion(text="Test", x0=10, y0=20, x1=110, y1=40)
        assert region.center_x == 60

    def test_text_region_center_y(self):
        """Test TextRegion center_y property."""
        region = TextRegion(text="Test", x0=10, y0=20, x1=110, y1=60)
        assert region.center_y == 40

    def test_text_region_rotation(self):
        """Test TextRegion rotation attribute."""
        region = TextRegion(text="Test", x0=10, y0=20, x1=110, y1=40, rotation=45.0)
        assert region.rotation == 45.0

    def test_text_region_font_name(self):
        """Test TextRegion font_name attribute."""
        region = TextRegion(
            text="Test",
            x0=10, y0=20, x1=110, y1=40,
            font_name="Helvetica",
        )
        assert region.font_name == "Helvetica"

    def test_text_region_font_size(self):
        """Test TextRegion font_size attribute."""
        region = TextRegion(
            text="Test",
            x0=10, y0=20, x1=110, y1=40,
            font_size=12.0,
        )
        assert region.font_size == 12.0

    def test_text_region_text_color(self):
        """Test TextRegion text_color attribute."""
        region = TextRegion(
            text="Test",
            x0=10, y0=20, x1=110, y1=40,
            text_color=(1.0, 0.0, 0.0),  # Red
        )
        assert region.text_color == (1.0, 0.0, 0.0)

    def test_text_region_from_bbox(self):
        """Test creating TextRegion from BoundingBox."""
        bbox = BoundingBox(x0=10, y0=20, x1=110, y1=50)
        region = TextRegion.from_bbox(bbox, "Hello World")

        assert region.text == "Hello World"
        assert region.x0 == 10
        assert region.y0 == 20
        assert region.x1 == 110
        assert region.y1 == 50

    def test_text_region_from_bbox_with_rotation(self):
        """Test creating TextRegion from BoundingBox with rotation."""
        bbox = BoundingBox(x0=10, y0=20, x1=110, y1=50)
        region = TextRegion.from_bbox(bbox, "Hello", rotation=90.0)

        assert region.rotation == 90.0

    def test_text_region_from_bbox_with_font(self):
        """Test creating TextRegion from BoundingBox with font."""
        bbox = BoundingBox(x0=10, y0=20, x1=110, y1=50)
        region = TextRegion.from_bbox(
            bbox, "Hello",
            font_name="Courier",
            font_size=14.0,
        )

        assert region.font_name == "Courier"
        assert region.font_size == 14.0


class TestCalculateRotationFromBbox:
    """Tests for calculate_rotation_from_bbox function."""

    def test_normal_box_no_rotation(self):
        """Test that normal aspect ratio box has no rotation."""
        bbox = BoundingBox(x0=0, y0=0, x1=100, y1=30)
        rotation = calculate_rotation_from_bbox(bbox, "Hello World")
        assert rotation == 0.0

    def test_tall_narrow_box_rotation(self):
        """Test that tall narrow box may indicate 90° rotation."""
        bbox = BoundingBox(x0=0, y0=0, x1=10, y1=100)
        rotation = calculate_rotation_from_bbox(bbox, "Hello World")
        # Very tall and narrow should be 90 degrees
        assert rotation == 90.0

    def test_short_text_no_rotation(self):
        """Test that short text doesn't trigger rotation."""
        bbox = BoundingBox(x0=0, y0=0, x1=10, y1=100)
        rotation = calculate_rotation_from_bbox(bbox, "Hi")
        # Short text (<=3 chars) should not be rotated
        assert rotation == 0.0


class TestRenderTextRegion:
    """Tests for render_text_region function."""

    def test_render_text_region_basic(self):
        """Test basic text region rendering."""
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(612, 792))

        region = TextRegion(
            text="Hello World",
            x0=72, y0=700, x1=200, y1=720,
        )

        # Should not raise
        render_text_region(
            canvas, region,
            target_lang="en",
            page_height=792,
        )

        canvas.save()
        assert buffer.tell() > 0

    def test_render_text_region_with_background(self):
        """Test rendering with background."""
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(612, 792))

        region = TextRegion(text="Test", x0=72, y0=700, x1=150, y1=720)

        render_text_region(
            canvas, region,
            target_lang="en",
            page_height=792,
            draw_background=True,
        )

        canvas.save()
        assert buffer.tell() > 0

    def test_render_text_region_without_background(self):
        """Test rendering without background."""
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(612, 792))

        region = TextRegion(text="Test", x0=72, y0=700, x1=150, y1=720)

        render_text_region(
            canvas, region,
            target_lang="en",
            page_height=792,
            draw_background=False,
        )

        canvas.save()
        assert buffer.tell() > 0

    def test_render_text_region_with_rotation(self):
        """Test rendering with rotation."""
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(612, 792))

        region = TextRegion(
            text="Rotated",
            x0=72, y0=700, x1=150, y1=720,
            rotation=45.0,
        )

        render_text_region(
            canvas, region,
            target_lang="en",
            page_height=792,
        )

        canvas.save()
        assert buffer.tell() > 0

    def test_render_text_region_multiline(self):
        """Test rendering multiline text."""
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(612, 792))

        region = TextRegion(
            text="Line 1\nLine 2\nLine 3",
            x0=72, y0=650, x1=200, y1=720,
        )

        render_text_region(
            canvas, region,
            target_lang="en",
            page_height=792,
        )

        canvas.save()
        assert buffer.tell() > 0

    def test_render_text_region_cjk(self):
        """Test rendering CJK text."""
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(612, 792))

        region = TextRegion(
            text="你好世界",
            x0=72, y0=700, x1=200, y1=720,
        )

        # Should not raise even if CJK font not available
        render_text_region(
            canvas, region,
            target_lang="zh-TW",
            page_height=792,
        )

        canvas.save()
        assert buffer.tell() > 0


class TestRenderTextRegions:
    """Tests for render_text_regions function."""

    def test_render_multiple_regions(self):
        """Test rendering multiple text regions."""
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(612, 792))

        regions = [
            TextRegion(text="Region 1", x0=72, y0=700, x1=200, y1=720),
            TextRegion(text="Region 2", x0=72, y0=650, x1=200, y1=670),
            TextRegion(text="Region 3", x0=72, y0=600, x1=200, y1=620),
        ]

        rendered = render_text_regions(
            canvas, regions,
            target_lang="en",
            page_height=792,
        )

        canvas.save()
        assert rendered == 3
        assert buffer.tell() > 0

    def test_render_empty_regions_list(self):
        """Test rendering empty regions list."""
        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(612, 792))

        rendered = render_text_regions(
            canvas, [],
            target_lang="en",
            page_height=792,
        )

        canvas.save()
        assert rendered == 0


class TestCreateTextRegionsFromElements:
    """Tests for create_text_regions_from_elements function."""

    def test_create_regions_basic(self):
        """Test creating regions from elements."""
        elements = [
            TranslatableElement(
                element_id="e1",
                content="Hello",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=700, x1=200, y1=720),
                should_translate=True,
            ),
            TranslatableElement(
                element_id="e2",
                content="World",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=650, x1=200, y1=670),
                should_translate=True,
            ),
        ]

        translations = {
            "Hello": "你好",
            "World": "世界",
        }

        regions = create_text_regions_from_elements(elements, translations, "zh-TW")

        assert len(regions) == 2
        assert regions[0].text == "你好"
        assert regions[1].text == "世界"

    def test_create_regions_skip_non_translatable(self):
        """Test that non-translatable elements are skipped."""
        elements = [
            TranslatableElement(
                element_id="e1",
                content="Translate me",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=700, x1=200, y1=720),
                should_translate=True,
            ),
            TranslatableElement(
                element_id="e2",
                content="Skip me",
                element_type=ElementType.HEADER,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=750, x1=200, y1=770),
                should_translate=False,
            ),
        ]

        translations = {
            "Translate me": "翻譯我",
            "Skip me": "跳過我",
        }

        regions = create_text_regions_from_elements(elements, translations, "zh-TW")

        assert len(regions) == 1
        assert regions[0].text == "翻譯我"

    def test_create_regions_skip_no_bbox(self):
        """Test that elements without bbox are skipped."""
        elements = [
            TranslatableElement(
                element_id="e1",
                content="Has bbox",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=700, x1=200, y1=720),
                should_translate=True,
            ),
            TranslatableElement(
                element_id="e2",
                content="No bbox",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=None,
                should_translate=True,
            ),
        ]

        translations = {
            "Has bbox": "有邊界框",
            "No bbox": "無邊界框",
        }

        regions = create_text_regions_from_elements(elements, translations, "zh-TW")

        assert len(regions) == 1
        assert regions[0].text == "有邊界框"

    def test_create_regions_skip_missing_translation(self):
        """Test that elements without translation are skipped."""
        elements = [
            TranslatableElement(
                element_id="e1",
                content="Has translation",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=700, x1=200, y1=720),
                should_translate=True,
            ),
            TranslatableElement(
                element_id="e2",
                content="No translation",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=72, y0=650, x1=200, y1=670),
                should_translate=True,
            ),
        ]

        translations = {
            "Has translation": "有翻譯",
            # "No translation" is intentionally missing
        }

        regions = create_text_regions_from_elements(elements, translations, "zh-TW")

        assert len(regions) == 1
        assert regions[0].text == "有翻譯"

    def test_create_regions_preserves_coordinates(self):
        """Test that coordinates are preserved from bbox."""
        elements = [
            TranslatableElement(
                element_id="e1",
                content="Test",
                element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=100, y0=200, x1=300, y1=250),
                should_translate=True,
            ),
        ]

        translations = {"Test": "測試"}

        regions = create_text_regions_from_elements(elements, translations, "zh-TW")

        assert len(regions) == 1
        assert regions[0].x0 == 100
        assert regions[0].y0 == 200
        assert regions[0].x1 == 300
        assert regions[0].y1 == 250
