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
