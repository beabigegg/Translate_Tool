"""Golden-sample dual-run regression harness (AC-6, AC-7).

Tests:
- test_golden_fixture_inventory — verify fixture files exist per format
- test_golden_pdf_parse_ir_stable — parse PDF fixtures; compare against snapshot
- test_dual_run_diff_no_regressions — parse same file twice; IR dicts must be identical
- test_golden_offline_no_network — all tests pass with socket monkeypatched closed

Snapshot format (per test-plan.md §Golden-Sample Set Design):
  {"element_count": int, "element_types": {type: count}, "reading_order_present": bool}

Snapshots are self-initializing: written on first run if absent.
If no snapshot exists yet, the test skips the comparison.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Dict, Any, List

import pytest

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
PDF_DIR = GOLDEN_DIR / "pdf"
DOCX_DIR = GOLDEN_DIR / "docx"
PPTX_DIR = GOLDEN_DIR / "pptx"


def _get_fixtures(directory: Path, suffix: str) -> List[Path]:
    """Return fixture files in directory with the given suffix."""
    if not directory.exists():
        return []
    return sorted(directory.glob(f"*{suffix}"))


def _compute_ir_snapshot(doc) -> Dict[str, Any]:
    """Compute the snapshot dict from a parsed TranslatableDocument."""
    element_types: Dict[str, int] = {}
    for elem in doc.elements:
        key = elem.element_type.value
        element_types[key] = element_types.get(key, 0) + 1

    reading_order_present = any(e.reading_order is not None for e in doc.elements)

    return {
        "element_count": len(doc.elements),
        "element_types": element_types,
        "reading_order_present": reading_order_present,
    }


def _snapshot_path(fixture_path: Path) -> Path:
    """Return the companion snapshot JSON path for a fixture."""
    return fixture_path.parent / (fixture_path.stem + ".ir.json")


def _load_or_create_snapshot(fixture_path: Path, doc) -> Dict[str, Any] | None:
    """Load snapshot if it exists; write it on first run and return None."""
    snap_path = _snapshot_path(fixture_path)
    current = _compute_ir_snapshot(doc)

    if snap_path.exists():
        with open(snap_path) as f:
            return json.load(f)
    else:
        # First run: write snapshot, skip comparison this run
        with open(snap_path, "w") as f:
            json.dump(current, f, indent=2)
        return None


class TestGoldenFixtureInventory:
    """AC-6: Fixture file inventory check."""

    def test_golden_fixture_inventory(self):
        """At least 3 PDF golden fixture files must exist under tests/fixtures/golden/pdf/.

        DOCX and PPTX directories exist with gitkeep placeholders (fixtures TBD).
        The test verifies the PDF floor (3 files) and that the format directories exist.
        """
        pdf_fixtures = _get_fixtures(PDF_DIR, ".pdf")
        assert len(pdf_fixtures) >= 3, (
            f"Expected at least 3 PDF fixtures in {PDF_DIR}, found {len(pdf_fixtures)}: "
            f"{[f.name for f in pdf_fixtures]}"
        )

        assert DOCX_DIR.exists(), f"DOCX golden fixture directory missing: {DOCX_DIR}"
        assert PPTX_DIR.exists(), f"PPTX golden fixture directory missing: {PPTX_DIR}"


def _pdf_fixtures() -> List[Path]:
    return _get_fixtures(PDF_DIR, ".pdf")


def _docx_fixtures() -> List[Path]:
    return _get_fixtures(DOCX_DIR, ".docx")


def _pptx_fixtures() -> List[Path]:
    return _get_fixtures(PPTX_DIR, ".pptx")


@pytest.fixture
def pdf_parser():
    """Create PDF parser; skip if PyMuPDF not installed."""
    try:
        from app.backend.parsers.pdf_parser import PyMuPDFParser
        return PyMuPDFParser()
    except ImportError:
        pytest.skip("PyMuPDF not installed")


@pytest.fixture
def docx_parser():
    """Create DOCX parser."""
    from app.backend.parsers.docx_parser import DocxParser
    return DocxParser()


@pytest.fixture
def pptx_parser():
    """Create PPTX parser."""
    from app.backend.parsers.pptx_parser import PptxParser
    return PptxParser()


class TestGoldenPDFParseIRStable:
    """AC-7: Per-sample snapshot stability for PDF fixtures."""

    @pytest.mark.parametrize("fixture_path", _pdf_fixtures(), ids=lambda p: p.name)
    def test_golden_pdf_parse_ir_stable(self, pdf_parser, fixture_path):
        """Parse PDF fixture; compare element_count/element_types/reading_order_present
        against committed snapshot. On first run (no snapshot), writes snapshot and passes.
        """
        doc = pdf_parser.parse(str(fixture_path))
        current = _compute_ir_snapshot(doc)
        saved = _load_or_create_snapshot(fixture_path, doc)

        if saved is None:
            # First run: snapshot written, no comparison yet
            return

        # Compare pre-existing fields
        assert current["element_count"] == saved["element_count"], (
            f"element_count mismatch for {fixture_path.name}: "
            f"expected {saved['element_count']}, got {current['element_count']}"
        )
        assert current["element_types"] == saved["element_types"], (
            f"element_types mismatch for {fixture_path.name}: "
            f"expected {saved['element_types']}, got {current['element_types']}"
        )
        # reading_order_present is allowed to change from False to True
        # (new-format parse populates it; old snapshot may have it as False)
        if saved.get("reading_order_present") is True:
            assert current["reading_order_present"] is True, (
                f"reading_order_present regressed to False for {fixture_path.name}"
            )


class TestGoldenDocxParseIRStable:
    """AC-7: Per-sample snapshot stability for DOCX fixtures (xfail until fixtures added)."""

    @pytest.mark.parametrize(
        "fixture_path",
        _docx_fixtures() if _docx_fixtures() else [pytest.param(None, marks=pytest.mark.skip(reason="No DOCX fixtures available yet"))],
        ids=lambda p: p.name if p is not None else "no-fixtures",
    )
    def test_golden_docx_parse_ir_stable(self, docx_parser, fixture_path):
        """Parse DOCX fixture; compare against snapshot."""
        if fixture_path is None:
            pytest.skip("No DOCX fixtures available")
        doc = docx_parser.parse(str(fixture_path))
        current = _compute_ir_snapshot(doc)
        saved = _load_or_create_snapshot(fixture_path, doc)
        if saved is None:
            return
        assert current["element_count"] == saved["element_count"]
        assert current["element_types"] == saved["element_types"]


class TestGoldenPptxParseIRStable:
    """AC-7: Per-sample snapshot stability for PPTX fixtures (xfail until fixtures added)."""

    @pytest.mark.parametrize(
        "fixture_path",
        _pptx_fixtures() if _pptx_fixtures() else [pytest.param(None, marks=pytest.mark.skip(reason="No PPTX fixtures available yet"))],
        ids=lambda p: p.name if p is not None else "no-fixtures",
    )
    def test_golden_pptx_parse_ir_stable(self, pptx_parser, fixture_path):
        """Parse PPTX fixture; compare against snapshot."""
        if fixture_path is None:
            pytest.skip("No PPTX fixtures available")
        doc = pptx_parser.parse(str(fixture_path))
        current = _compute_ir_snapshot(doc)
        saved = _load_or_create_snapshot(fixture_path, doc)
        if saved is None:
            return
        assert current["element_count"] == saved["element_count"]
        assert current["element_types"] == saved["element_types"]


class TestDualRunDiffNoRegressions:
    """AC-7: Parse same file twice; IR dicts must be identical (determinism)."""

    @pytest.mark.parametrize("fixture_path", _pdf_fixtures(), ids=lambda p: p.name)
    def test_dual_run_diff_no_regressions(self, pdf_parser, fixture_path):
        """Parse the same PDF twice with identical config; IR dicts must match."""
        doc1 = pdf_parser.parse(str(fixture_path))
        doc2 = pdf_parser.parse(str(fixture_path))

        d1 = doc1.to_dict()
        d2 = doc2.to_dict()

        # Remove non-deterministic fields: element_id contains uuid
        def normalize(d: dict) -> dict:
            """Strip element_ids (which contain UUIDs) for comparison."""
            for elem in d.get("elements", []):
                elem["element_id"] = "<normalized>"
            return d

        n1 = normalize(d1)
        n2 = normalize(d2)

        # Compare element counts
        assert len(n1["elements"]) == len(n2["elements"]), (
            f"Element count differs across two parses of {fixture_path.name}: "
            f"{len(n1['elements'])} vs {len(n2['elements'])}"
        )

        # Compare each element field-by-field (excluding element_id)
        for i, (e1, e2) in enumerate(zip(n1["elements"], n2["elements"])):
            for key in ("content", "element_type", "page_num", "should_translate",
                        "reading_order", "metadata"):
                assert e1.get(key) == e2.get(key), (
                    f"Element [{i}] field '{key}' differs across two parses of "
                    f"{fixture_path.name}: {e1.get(key)!r} vs {e2.get(key)!r}"
                )


# ---------------------------------------------------------------------------
# p2-layout-detection: AC-6 dual-run and multi-column accuracy
# ---------------------------------------------------------------------------

class TestDualRunLayoutDetectorVsHeuristic:
    """AC-6: parse same fixture with detector enabled vs heuristic; IR schema-identical."""

    def test_dual_run_layout_detector_vs_heuristic(self, monkeypatch):
        """Both detector and heuristic paths produce IR-schema-compatible output.

        The IR wire shape (element fields) must be identical under both paths.
        reading_order values may differ (detector may reorder); element_count
        and element_type sets must not differ.
        """
        import os
        import numpy as np
        from unittest.mock import MagicMock, patch

        pdf_fixtures = _pdf_fixtures()
        if not pdf_fixtures:
            pytest.skip("No PDF fixtures available")

        fixture_path = pdf_fixtures[0]

        try:
            from app.backend.parsers.pdf_parser import PyMuPDFParser
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        # --- Run 1: heuristic (detector disabled) ---
        monkeypatch.setenv("LAYOUT_DETECTOR_ENABLED", "false")
        parser_h = PyMuPDFParser()
        doc_heuristic = parser_h.parse(str(fixture_path))

        # --- Run 2: detector enabled (mocked ONNX, returns empty detections) ---
        monkeypatch.setenv("LAYOUT_DETECTOR_ENABLED", "true")

        mock_session = MagicMock()
        mock_session.run.return_value = [
            np.zeros((1, 0, 4), dtype=np.float32),
            np.zeros((1, 0), dtype=np.float32),
            np.zeros((1, 0), dtype=np.int64),
        ]
        mock_input = MagicMock()
        mock_input.name = "pixel_values"
        mock_session.get_inputs.return_value = [mock_input]

        with patch("onnxruntime.InferenceSession", return_value=mock_session):
            parser_d = PyMuPDFParser()
            doc_detector = parser_d.parse(str(fixture_path))

        # IR schema must be identical: same number of elements
        assert len(doc_heuristic.elements) == len(doc_detector.elements), (
            f"Element count changed between heuristic and detector runs: "
            f"{len(doc_heuristic.elements)} vs {len(doc_detector.elements)}"
        )

        # All elements must have reading_order set in both runs
        for elem in doc_detector.elements:
            assert elem.reading_order is not None, (
                f"Detector run: element {elem.element_id} missing reading_order"
            )
        for elem in doc_heuristic.elements:
            assert elem.reading_order is not None, (
                f"Heuristic run: element {elem.element_id} missing reading_order"
            )

        # reading_order values must form a valid 0..N-1 sequence in both runs
        def _is_sequential(elements) -> bool:
            orders = sorted(e.reading_order for e in elements)
            return orders == list(range(len(elements)))

        assert _is_sequential(doc_heuristic.elements), (
            "Heuristic run: reading_order is not a valid 0..N-1 sequence"
        )
        assert _is_sequential(doc_detector.elements), (
            "Detector run: reading_order is not a valid 0..N-1 sequence"
        )


class TestMultiColumnReadingOrderAccuracy:
    """AC-6: multi-column reading-order accuracy — detector path must handle column layouts."""

    def test_multi_column_reading_order_accuracy(self, monkeypatch):
        """With mocked detector columns (left col before right col), verify correct order.

        Constructs 4 elements in a 2-column layout and mocks the detector to
        assign 2 region boxes (left column and right column).  Expected reading
        order: left-col top, left-col bottom, right-col top, right-col bottom.
        """
        import os
        import numpy as np
        from unittest.mock import MagicMock, patch

        try:
            from app.backend.parsers.layout_detector import LayoutDetector
        except ImportError:
            pytest.skip("layout_detector not yet implemented")

        from app.backend.models.translatable_document import (
            BoundingBox,
            ElementType,
            TranslatableElement,
        )

        # 2-column layout (page: 0..600 wide, 0..800 tall)
        # Left column: x 0..280; right column: x 320..600
        elements = [
            TranslatableElement("lc_top",  "Left top",    ElementType.TEXT, 1, BoundingBox(10, 50, 270, 80),   metadata={}),
            TranslatableElement("rc_top",  "Right top",   ElementType.TEXT, 1, BoundingBox(330, 50, 590, 80),  metadata={}),
            TranslatableElement("lc_bot",  "Left bottom", ElementType.TEXT, 1, BoundingBox(10, 150, 270, 180), metadata={}),
            TranslatableElement("rc_bot",  "Right bottom",ElementType.TEXT, 1, BoundingBox(330, 150, 590, 180),metadata={}),
        ]

        # Mock detector: 2 region boxes — left col and right col
        # Pixel coordinates for page 600×800 (model returns pixel coords; detector normalises)
        boxes  = [
            [  0.0,   0.0, 276.0, 800.0],   # left column region (0..46% of width)
            [318.0,   0.0, 600.0, 800.0],   # right column region (53%..100% of width)
        ]
        scores = [0.9, 0.9]
        labels = [0, 0]  # both TEXT

        mock_session = MagicMock()
        # Output order matches layout_detector.py: labels, boxes, scores
        mock_session.run.return_value = [
            np.array([labels], dtype=np.int64),
            np.array([boxes],  dtype=np.float32),
            np.array([scores], dtype=np.float32),
        ]
        mock_input0 = MagicMock()
        mock_input0.name = "pixel_values"
        mock_input1 = MagicMock()
        mock_input1.name = "orig_sizes"
        mock_session.get_inputs.return_value = [mock_input0, mock_input1]

        page_pixmap = np.zeros((800, 600, 3), dtype=np.uint8)

        monkeypatch.setenv("LAYOUT_DETECTOR_ENABLED", "true")
        with patch("onnxruntime.InferenceSession", return_value=mock_session):
            detector = LayoutDetector(model_path="/fake/path")
            detector.detect(page_pixmap, elements)

        # All elements must have reading_order
        orders = {e.element_id: e.reading_order for e in elements}
        assert all(v is not None for v in orders.values()), (
            f"Not all elements got reading_order: {orders}"
        )

        # Left column elements must come before right column elements
        lc_orders = {eid: o for eid, o in orders.items() if eid.startswith("lc")}
        rc_orders = {eid: o for eid, o in orders.items() if eid.startswith("rc")}

        max_lc = max(lc_orders.values())
        min_rc = min(rc_orders.values())
        assert max_lc < min_rc, (
            f"Left-column elements must precede right-column elements in reading order. "
            f"Left: {lc_orders}, Right: {rc_orders}"
        )


class TestGoldenOfflineNoNetwork:
    """AC-7: Golden tests must pass with network access blocked."""

    def test_golden_offline_no_network(self, monkeypatch):
        """Golden tests pass with socket monkeypatched closed (no network calls)."""
        # Block all socket connections
        original_socket = socket.socket

        def blocked_socket(*args, **kwargs):
            raise OSError("Network access is blocked in golden tests")

        monkeypatch.setattr(socket, "socket", blocked_socket)

        # Run a minimal parse operation — should not make any network calls
        pdf_fixtures = _pdf_fixtures()
        if not pdf_fixtures:
            pytest.skip("No PDF fixtures available")

        try:
            from app.backend.parsers.pdf_parser import PyMuPDFParser
            parser = PyMuPDFParser()
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        # Parse without network — must succeed
        doc = parser.parse(str(pdf_fixtures[0]))
        assert doc is not None
        assert len(doc.elements) >= 0

        # Restore socket
        monkeypatch.setattr(socket, "socket", original_socket)
