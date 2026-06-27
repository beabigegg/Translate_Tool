"""Tests for the layout-fidelity metrics harness (21 nodes).

Change: layout-fidelity-metrics
Test plan: specs/changes/layout-fidelity-metrics/test-plan.md
"""
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    fitz = None  # type: ignore[assignment]
    HAS_FITZ = False

from tests.metrics.biou import BIOU_REGRESSION_BUDGET, compute_biou
from tests.metrics.residual_text import check_residual_text
from tests.metrics.truncation_rate import compute_truncation_rate

# ---------------------------------------------------------------------------
# Repo root — never a hardcoded absolute path (promoted learning)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bb(x0, y0, x1, y1):
    """Create a duck-typed bbox namespace with x0/y0/x1/y1."""
    return SimpleNamespace(x0=x0, y0=y0, x1=x1, y1=y1)


class _Elem:
    """Minimal stub for a TranslatableElement-like object."""

    def __init__(self, render_truncated, bbox=None, overflow_area=None):
        self.render_truncated = render_truncated
        self.bbox = bbox
        self.metadata = {"overflow_area": overflow_area} if overflow_area is not None else {}


class StubPage:
    """Fake fitz.Page for residual-text tests — no real PDF I/O."""

    def __init__(self, text_by_clip=None):
        # text_by_clip: dict mapping clip-tuple -> list of block tuples
        self._text_by_clip = text_by_clip or {}

    def get_text(self, mode, clip=None):
        return self._text_by_clip.get(clip, [])


# ---------------------------------------------------------------------------
# TestBIoU
# ---------------------------------------------------------------------------

class TestBIoU:

    def test_identical_bboxes_return_1(self):
        """Identical source and rendered boxes must yield BIoU == 1.0."""
        src = [_bb(0, 0, 100, 50), _bb(200, 100, 400, 200)]
        rnd = [_bb(0, 0, 100, 50), _bb(200, 100, 400, 200)]
        result = compute_biou(src, rnd)
        assert result == pytest.approx(1.0)

    def test_disjoint_bboxes_return_0(self):
        """Completely non-overlapping boxes must yield BIoU == 0.0."""
        src = [_bb(0, 0, 10, 10)]
        rnd = [_bb(100, 100, 200, 200)]
        result = compute_biou(src, rnd)
        assert result == pytest.approx(0.0)

    def test_partial_overlap_value_and_matched_pair(self):
        """Partial-overlap test with selection assertion (AC-6 anti-tautology).

        source[0] overlaps rendered[0]; source[1] overlaps rendered[1].
        Assert:
          1. argmax IoU(source[0], rendered[i]) == 0  (selection identity)
          2. mean BIoU matches hand-computed value
        """
        # source[0]: (0,0,100,100) ; source[1]: (200,0,300,100)
        source_bboxes = [_bb(0, 0, 100, 100), _bb(200, 0, 300, 100)]
        # rendered[0]: (10,10,110,110) — overlaps source[0]
        # rendered[1]: (210,10,310,110) — overlaps source[1]
        rendered_bboxes = [_bb(10, 10, 110, 110), _bb(210, 10, 310, 110)]

        # Verify selection: source[0] best matches rendered[0]
        from tests.metrics.biou import _iou
        iou_scores_for_src0 = [_iou(source_bboxes[0], rendered_bboxes[i]) for i in range(len(rendered_bboxes))]
        best_rendered_idx_for_src0 = iou_scores_for_src0.index(max(iou_scores_for_src0))
        assert best_rendered_idx_for_src0 == 0, (
            f"source[0] should best match rendered[0], but matched rendered[{best_rendered_idx_for_src0}]"
        )

        # Hand-computed IoU for source[0] vs rendered[0]:
        #   intersection: max(0, min(100,110)-max(0,10)) * max(0, min(100,110)-max(0,10))
        #               = (100-10) * (100-10) = 90 * 90 = 8100
        #   areaA = 100*100 = 10000; areaB = 100*100 = 10000
        #   union = 10000 + 10000 - 8100 = 11900
        #   IoU = 8100/11900 ≈ 0.68067
        expected_iou_pair = 8100 / 11900
        # By symmetry, source[1] vs rendered[1] gives the same IoU
        expected_mean = expected_iou_pair  # mean of two equal values

        result = compute_biou(source_bboxes, rendered_bboxes)
        assert result == pytest.approx(expected_mean, rel=1e-4)

    def test_return_type_is_float_in_unit_interval(self):
        """Return value must be a float in [0, 1]."""
        src = [_bb(0, 0, 50, 50)]
        rnd = [_bb(25, 25, 75, 75)]
        result = compute_biou(src, rnd)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# TestBIoUDegenerate
# ---------------------------------------------------------------------------

class TestBIoUDegenerate:

    def test_empty_source_list(self):
        """Empty source list returns 0.0 without raising."""
        result = compute_biou([], [_bb(0, 0, 10, 10)])
        assert result == pytest.approx(0.0)

    def test_empty_rendered_list(self):
        """Empty rendered list returns 0.0 without raising."""
        result = compute_biou([_bb(0, 0, 10, 10)], [])
        assert result == pytest.approx(0.0)

    def test_zero_area_source_box(self):
        """Zero-area source box (collapsed point) returns 0.0 without raising."""
        # x0==x1 → area == 0; IoU must be 0.0 (not division by zero)
        result = compute_biou([_bb(50, 50, 50, 50)], [_bb(0, 0, 100, 100)])
        assert isinstance(result, float)
        assert result == pytest.approx(0.0)

    def test_zero_area_rendered_box(self):
        """Zero-area rendered box returns 0.0 without raising."""
        result = compute_biou([_bb(0, 0, 100, 100)], [_bb(50, 50, 50, 50)])
        assert isinstance(result, float)
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestResidualText
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
class TestResidualText:

    def test_clean_page_returns_empty_list(self):
        """Page with no text in any whiteover region returns []."""
        page = StubPage()  # all clips return empty list
        bboxes = [_bb(0, 0, 100, 100), _bb(200, 200, 300, 300)]
        result = check_residual_text(page, bboxes)
        assert result == []

    def test_leaking_text_flagged_with_region_record(self):
        """A bbox region that contains text blocks must appear in the output."""
        clip = (10.0, 20.0, 110.0, 120.0)
        # A fitz block tuple has at least 5 elements; index 4 is the text string
        blocks = [(10, 20, 110, 120, "Leaked text\n", 0, 0)]
        page = StubPage(text_by_clip={clip: blocks})
        bbox = _bb(10.0, 20.0, 110.0, 120.0)
        result = check_residual_text(page, [bbox])
        assert len(result) == 1

    def test_record_contains_bbox_and_text_fields(self):
        """Each record must have 'bbox', 'text', and 'blocks' keys."""
        clip = (0.0, 0.0, 50.0, 50.0)
        blocks = [(0, 0, 50, 50, "Some text\n", 0, 0)]
        page = StubPage(text_by_clip={clip: blocks})
        bbox = _bb(0.0, 0.0, 50.0, 50.0)
        result = check_residual_text(page, [bbox])
        assert len(result) == 1
        record = result[0]
        assert "bbox" in record
        assert "text" in record
        assert "blocks" in record
        assert record["bbox"] is bbox
        assert "Some text" in record["text"]


# ---------------------------------------------------------------------------
# TestTruncationRate
# ---------------------------------------------------------------------------

class TestTruncationRate:

    def test_all_truncated_ratio_is_1(self):
        """All elements truncated → ratio == 1.0."""
        elements = [
            _Elem(render_truncated=True, overflow_area=10.0),
            _Elem(render_truncated=True, overflow_area=5.0),
        ]
        result = compute_truncation_rate(elements)
        assert result["count"] == 2
        assert result["total"] == 2
        assert result["ratio"] == pytest.approx(1.0)
        assert result["overflow_area_sum"] == pytest.approx(15.0)

    def test_none_truncated_ratio_is_0(self):
        """No truncated elements → ratio == 0.0 and overflow_area_sum == 0.0."""
        elements = [_Elem(render_truncated=False), _Elem(render_truncated=False)]
        result = compute_truncation_rate(elements)
        assert result["count"] == 0
        assert result["total"] == 2
        assert result["ratio"] == pytest.approx(0.0)
        assert result["overflow_area_sum"] == pytest.approx(0.0)

    def test_partial_truncated_ratio_and_overflow_area(self):
        """Partial truncation: ratio and overflow_area_sum match hand-computed values."""
        elements = [
            _Elem(render_truncated=True, overflow_area=12.0),
            _Elem(render_truncated=False),
            _Elem(render_truncated=True, overflow_area=8.0),
            _Elem(render_truncated=False),
        ]
        result = compute_truncation_rate(elements)
        assert result["count"] == 2
        assert result["total"] == 4
        assert result["ratio"] == pytest.approx(0.5)
        assert result["overflow_area_sum"] == pytest.approx(20.0)

    def test_elements_with_none_bbox_excluded_from_overflow(self):
        """Truncated element with bbox=None counts in ratio but adds 0 to overflow_area_sum."""
        elements = [
            _Elem(render_truncated=True, bbox=None),  # no overflow_area key
            _Elem(render_truncated=False),
        ]
        result = compute_truncation_rate(elements)
        assert result["count"] == 1
        assert result["total"] == 2
        assert result["ratio"] == pytest.approx(0.5)
        # bbox=None and no overflow_area key → contributes 0.0, must not raise
        assert result["overflow_area_sum"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestGoldenFixture
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
class TestGoldenFixture:

    _fixture_path = REPO_ROOT / "tests" / "fixtures" / "golden" / "simple_test.pdf"

    def test_fixture_file_exists_and_is_valid_pdf(self):
        """simple_test.pdf must exist and be openable by fitz."""
        assert self._fixture_path.exists(), f"Fixture not found: {self._fixture_path}"
        doc = fitz.open(str(self._fixture_path))
        assert doc.is_pdf
        doc.close()

    def test_fixture_is_exactly_one_page(self):
        """simple_test.pdf must contain exactly one page."""
        doc = fitz.open(str(self._fixture_path))
        page_count = doc.page_count
        doc.close()
        assert page_count == 1


# ---------------------------------------------------------------------------
# TestModuleImports
# ---------------------------------------------------------------------------

class TestModuleImports:

    def test_biou_importable_from_tests_metrics(self):
        """compute_biou and BIOU_REGRESSION_BUDGET are importable from tests.metrics.biou."""
        from tests.metrics.biou import compute_biou as _cb, BIOU_REGRESSION_BUDGET as _budget
        assert callable(_cb)
        assert isinstance(_budget, float)

    def test_residual_text_importable_from_tests_metrics(self):
        """check_residual_text is importable from tests.metrics.residual_text."""
        from tests.metrics.residual_text import check_residual_text as _crt
        assert callable(_crt)

    def test_truncation_rate_importable_from_tests_metrics(self):
        """compute_truncation_rate is importable from tests.metrics.truncation_rate."""
        from tests.metrics.truncation_rate import compute_truncation_rate as _ctr
        assert callable(_ctr)

    def test_no_app_backend_files_modified(self):
        """No file under app/backend/ or app/frontend/ should appear in this PR's diff.

        Uses git diff against origin/main (the merge base) so the check is
        meaningful in CI, where git diff HEAD only shows uncommitted changes
        (always empty on a CI checkout).
        """
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if result.returncode != 0:
            # origin/main not available (e.g. local dev without fetch); skip.
            pytest.skip("origin/main not reachable — skipping PR-scope check")
        changed_files = result.stdout.splitlines()
        backend_or_frontend = [
            f for f in changed_files
            if f.startswith("app/backend/") or f.startswith("app/frontend/")
        ]
        assert backend_or_frontend == [], (
            f"app/backend/ or app/frontend/ files were modified: {backend_or_frontend}"
        )
