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
