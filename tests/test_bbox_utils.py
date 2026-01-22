"""Tests for bbox utility functions."""

from __future__ import annotations

import pytest

from app.backend.models.translatable_document import BoundingBox
from app.backend.utils.bbox_utils import (
    bbox_distance,
    calculate_iou,
    is_bbox_inside,
    is_header_footer_region,
    merge_bboxes,
    normalize_bbox,
    sort_bboxes_by_reading_order,
)


class TestNormalizeBbox:
    """Tests for normalize_bbox function."""

    def test_from_pdf_coords(self):
        """Test conversion from PDF coordinates (bottom-left origin)."""
        # PDF coords: (0, 700) is near top of page (page height 792)
        # Internal coords: should become y0 near 0
        bbox = normalize_bbox((72, 700, 540, 750), page_height=792, from_pdf_coords=True)

        # y0 should be 792 - 750 = 42
        # y1 should be 792 - 700 = 92
        assert bbox.y0 == 42
        assert bbox.y1 == 92
        assert bbox.x0 == 72
        assert bbox.x1 == 540

    def test_already_internal_coords(self):
        """Test when coords are already in internal format."""
        bbox = normalize_bbox((72, 42, 540, 92), page_height=792, from_pdf_coords=False)

        assert bbox.x0 == 72
        assert bbox.y0 == 42
        assert bbox.x1 == 540
        assert bbox.y1 == 92

    def test_swapped_coords(self):
        """Test handling of swapped coordinates."""
        # x0 > x1 and y0 > y1 (invalid but should be fixed)
        bbox = normalize_bbox((540, 92, 72, 42), page_height=792, from_pdf_coords=False)

        assert bbox.x0 == 72
        assert bbox.x1 == 540
        assert bbox.y0 == 42
        assert bbox.y1 == 92


class TestCalculateIou:
    """Tests for calculate_iou function."""

    def test_identical_boxes(self):
        """Test IoU of identical boxes."""
        bbox1 = BoundingBox(x0=0, y0=0, x1=100, y1=100)
        bbox2 = BoundingBox(x0=0, y0=0, x1=100, y1=100)

        iou = calculate_iou(bbox1, bbox2)
        assert iou == 1.0

    def test_no_overlap(self):
        """Test IoU of non-overlapping boxes."""
        bbox1 = BoundingBox(x0=0, y0=0, x1=50, y1=50)
        bbox2 = BoundingBox(x0=100, y0=100, x1=150, y1=150)

        iou = calculate_iou(bbox1, bbox2)
        assert iou == 0.0

    def test_partial_overlap(self):
        """Test IoU of partially overlapping boxes."""
        bbox1 = BoundingBox(x0=0, y0=0, x1=100, y1=100)
        bbox2 = BoundingBox(x0=50, y0=50, x1=150, y1=150)

        # Intersection: 50x50 = 2500
        # Union: 100x100 + 100x100 - 2500 = 17500
        # IoU = 2500/17500 = 1/7 ≈ 0.143
        iou = calculate_iou(bbox1, bbox2)
        assert 0.14 < iou < 0.15

    def test_one_inside_other(self):
        """Test IoU when one box is inside the other."""
        bbox1 = BoundingBox(x0=0, y0=0, x1=100, y1=100)
        bbox2 = BoundingBox(x0=25, y0=25, x1=75, y1=75)

        # Intersection = 50x50 = 2500
        # Union = 10000 + 2500 - 2500 = 10000
        # IoU = 2500/10000 = 0.25
        iou = calculate_iou(bbox1, bbox2)
        assert iou == 0.25


class TestIsBboxInside:
    """Tests for is_bbox_inside function."""

    def test_fully_inside(self):
        """Test when inner is fully inside outer."""
        inner = BoundingBox(x0=25, y0=25, x1=75, y1=75)
        outer = BoundingBox(x0=0, y0=0, x1=100, y1=100)

        assert is_bbox_inside(inner, outer) is True

    def test_not_inside(self):
        """Test when inner is not inside outer."""
        inner = BoundingBox(x0=50, y0=50, x1=150, y1=150)
        outer = BoundingBox(x0=0, y0=0, x1=100, y1=100)

        assert is_bbox_inside(inner, outer) is False

    def test_with_tolerance(self):
        """Test with tolerance for small overhang."""
        inner = BoundingBox(x0=-2, y0=-2, x1=102, y1=102)
        outer = BoundingBox(x0=0, y0=0, x1=100, y1=100)

        # Without tolerance: not inside
        assert is_bbox_inside(inner, outer, tolerance=0) is False

        # With tolerance: inside
        assert is_bbox_inside(inner, outer, tolerance=5) is True


class TestMergeBboxes:
    """Tests for merge_bboxes function."""

    def test_merge_two_boxes(self):
        """Test merging two bboxes."""
        bboxes = [
            BoundingBox(x0=0, y0=0, x1=50, y1=50),
            BoundingBox(x0=30, y0=30, x1=100, y1=100),
        ]

        merged = merge_bboxes(bboxes)

        assert merged.x0 == 0
        assert merged.y0 == 0
        assert merged.x1 == 100
        assert merged.y1 == 100

    def test_merge_single_box(self):
        """Test merging single bbox."""
        bboxes = [BoundingBox(x0=10, y0=20, x1=30, y1=40)]
        merged = merge_bboxes(bboxes)

        assert merged.x0 == 10
        assert merged.y0 == 20

    def test_empty_list_raises(self):
        """Test that empty list raises ValueError."""
        with pytest.raises(ValueError):
            merge_bboxes([])


class TestBboxDistance:
    """Tests for bbox_distance function."""

    def test_overlapping_boxes(self):
        """Test distance between overlapping boxes."""
        bbox1 = BoundingBox(x0=0, y0=0, x1=100, y1=100)
        bbox2 = BoundingBox(x0=50, y0=50, x1=150, y1=150)

        distance = bbox_distance(bbox1, bbox2)
        assert distance == 0

    def test_horizontal_separation(self):
        """Test distance between horizontally separated boxes."""
        bbox1 = BoundingBox(x0=0, y0=0, x1=50, y1=50)
        bbox2 = BoundingBox(x0=100, y0=0, x1=150, y1=50)

        distance = bbox_distance(bbox1, bbox2)
        assert distance == 50  # 100 - 50

    def test_vertical_separation(self):
        """Test distance between vertically separated boxes."""
        bbox1 = BoundingBox(x0=0, y0=0, x1=50, y1=50)
        bbox2 = BoundingBox(x0=0, y0=100, x1=50, y1=150)

        distance = bbox_distance(bbox1, bbox2)
        assert distance == 50

    def test_diagonal_separation(self):
        """Test distance between diagonally separated boxes."""
        bbox1 = BoundingBox(x0=0, y0=0, x1=50, y1=50)
        bbox2 = BoundingBox(x0=80, y0=90, x1=130, y1=140)

        # dx = 80 - 50 = 30
        # dy = 90 - 50 = 40
        # distance = sqrt(30^2 + 40^2) = 50
        distance = bbox_distance(bbox1, bbox2)
        assert distance == 50


class TestIsHeaderFooterRegion:
    """Tests for is_header_footer_region function."""

    def test_header_region(self):
        """Test detection of header region."""
        bbox = BoundingBox(x0=72, y0=20, x1=540, y1=40)
        is_hf, region = is_header_footer_region(bbox, page_height=792, margin_pt=50)

        assert is_hf is True
        assert region == "header"

    def test_footer_region(self):
        """Test detection of footer region."""
        bbox = BoundingBox(x0=72, y0=760, x1=540, y1=780)
        is_hf, region = is_header_footer_region(bbox, page_height=792, margin_pt=50)

        assert is_hf is True
        assert region == "footer"

    def test_body_region(self):
        """Test detection of body region."""
        bbox = BoundingBox(x0=72, y0=200, x1=540, y1=300)
        is_hf, region = is_header_footer_region(bbox, page_height=792, margin_pt=50)

        assert is_hf is False
        assert region == "body"


class TestSortBboxesByReadingOrder:
    """Tests for sort_bboxes_by_reading_order function."""

    def test_simple_vertical_order(self):
        """Test sorting vertically stacked boxes."""
        bboxes = [
            BoundingBox(x0=72, y0=300, x1=540, y1=320),  # Third
            BoundingBox(x0=72, y0=100, x1=540, y1=120),  # First
            BoundingBox(x0=72, y0=200, x1=540, y1=220),  # Second
        ]

        order = sort_bboxes_by_reading_order(bboxes)

        assert order == [1, 2, 0]  # Indices in reading order

    def test_left_to_right_same_line(self):
        """Test sorting boxes on same line from left to right."""
        bboxes = [
            BoundingBox(x0=300, y0=100, x1=400, y1=120),  # Second (right)
            BoundingBox(x0=72, y0=100, x1=200, y1=120),   # First (left)
        ]

        order = sort_bboxes_by_reading_order(bboxes)

        assert order == [1, 0]

    def test_empty_list(self):
        """Test with empty list."""
        order = sort_bboxes_by_reading_order([])
        assert order == []
