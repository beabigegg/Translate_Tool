"""Tests for the layout-qa-safety-net change (BR-106).

Change: layout-qa-safety-net
Test plan: specs/changes/layout-qa-safety-net/test-plan.md

Covers (AC-2..AC-9, unit/data-boundary/resilience/contract families):
- AC-2: BIoU-below-budget path emits exactly one aggregated warning.
- AC-3: residual-source-text path emits a warning; both signals combine into
  ONE entry when both fire; correctly-translated boxes are NOT flagged.
- AC-4: fail-soft (forced exceptions caught, no raise, no fabricated warning)
  and data-boundary (degenerate inputs never raise).
- AC-5: metric-core shim identity (tests.metrics.* is the SAME object as the
  runtime module -- catches duplication/orphan per CLAUDE.md learning).
- AC-7: BR-106 documented in business-rules.md.
- AC-8: office processors never import run_layout_qa (PDF-only).
- AC-9: BIOU_REGRESSION_BUDGET is a named constant actually consumed by
  run_layout_qa (not an inline literal).

Real fitz-rendered PDFs are used for the signal-composition tests (not mocks)
so the disambiguation logic is genuinely exercised end-to-end; mocking is
reserved for exception-injection (fail-soft) tests, where forcing a raise is
the explicit point of the test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")

from app.backend.models.translatable_document import (
    BoundingBox,
    DocumentMetadata,
    ElementType,
    PageInfo,
    TranslatableDocument,
    TranslatableElement,
)
from app.backend.services import layout_qa

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(elements, pages=None):
    """Build a minimal TranslatableDocument from a list of elements."""
    if pages is None:
        seen = sorted({e.page_num for e in elements}) or [1]
        pages = [PageInfo(page_num=p, width=612, height=792) for p in seen]
    return TranslatableDocument(
        source_path="/fake.pdf",
        source_type="pdf",
        elements=elements,
        pages=pages,
        metadata=DocumentMetadata(page_count=len(pages), has_text_layer=True),
    )


def _make_pdf_with_textboxes(path: str, entries, page_size=(612, 792)):
    """Write a real 1-page PDF with each (rect, text) inserted via insert_textbox.

    Returns the list of ACTUAL rendered block bboxes (x0, y0, x1, y1), aligned
    to `entries` order via substring match on the rendered text content -- the
    real glyph-extent bbox is tighter than the insertion rect, so tests that
    need an exact-overlap bbox must use the returned coordinates, not the
    insertion rect.
    """
    doc = fitz.open()
    page = doc.new_page(width=page_size[0], height=page_size[1])
    for rect, text in entries:
        page.insert_textbox(fitz.Rect(*rect), text, fontsize=11)
    doc.save(path)
    doc.close()

    check_doc = fitz.open(path)
    blocks = check_doc[0].get_text("blocks")
    check_doc.close()

    result = []
    for _rect, text in entries:
        needle = text.strip().split("\n")[0][:15]
        match = next((b for b in blocks if needle in b[4]), None)
        assert match is not None, f"could not locate rendered block for text {text!r}"
        result.append((match[0], match[1], match[2], match[3]))
    return result


def _blank_pdf(path: str, page_size=(612, 792)) -> None:
    doc = fitz.open()
    doc.new_page(width=page_size[0], height=page_size[1])
    doc.save(path)
    doc.close()


# ---------------------------------------------------------------------------
# AC-2: BIoU regression
# ---------------------------------------------------------------------------

class TestBiouRegressionSignal:

    def test_biou_regression_below_budget_emits_one_aggregated_warning(self, tmp_path):
        out_path = str(tmp_path / "regress.pdf")
        rendered_text = "Bonjour completement different"
        _make_pdf_with_textboxes(out_path, [((400, 600, 560, 650), rendered_text)])

        elem = TranslatableElement(
            element_id="e1",
            content="Hello world original",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=72, x1=260, y1=110),
            translated_content=rendered_text,
        )
        doc = _make_doc([elem])

        captured = []
        result = layout_qa.run_layout_qa(doc, out_path, "regress.pdf", captured.append)

        assert result is not None
        assert result.biou_regressed is True
        assert result.warned is True
        assert len(captured) == 1, f"expected exactly 1 aggregated warning, got {captured!r}"
        assert "regress.pdf" in captured[0]
        assert "1" in captured[0], "warning must name the affected page"
        assert "residual" not in captured[0].lower(), (
            "only the BIoU signal fired; the residual signal must not appear"
        )

    def test_biou_regression_budget_is_named_constant_and_consumed_by_run_layout_qa(
        self, tmp_path, monkeypatch
    ):
        """AC-9: BIOU_REGRESSION_BUDGET must be a real module-level constant that
        run_layout_qa reads dynamically -- not a hardcoded 0.8 literal."""
        assert isinstance(layout_qa.BIOU_REGRESSION_BUDGET, float)

        out_path = str(tmp_path / "budget.pdf")
        _make_pdf_with_textboxes(
            out_path, [((400, 600, 560, 650), "Completely unrelated rendered text")]
        )
        elem = TranslatableElement(
            element_id="e1",
            content="source text nowhere near rendered spot",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=72, x1=260, y1=110),
        )
        doc = _make_doc([elem])

        captured_default = []
        result_default = layout_qa.run_layout_qa(
            doc, out_path, "budget-default.pdf", captured_default.append
        )
        assert result_default.biou_regressed is True
        assert len(captured_default) == 1

        monkeypatch.setattr(layout_qa, "BIOU_REGRESSION_BUDGET", -1.0)
        captured_patched = []
        result_patched = layout_qa.run_layout_qa(
            doc, out_path, "budget-patched.pdf", captured_patched.append
        )
        assert result_patched.biou_regressed is False, (
            "run_layout_qa must consume the module-level BIOU_REGRESSION_BUDGET "
            "constant dynamically, not a hardcoded 0.8 literal"
        )
        assert captured_patched == []


# ---------------------------------------------------------------------------
# AC-3: residual source text + aggregation
# ---------------------------------------------------------------------------

class TestResidualSignal:

    def test_residual_source_text_emits_warning(self, tmp_path):
        out_path = str(tmp_path / "leftover.pdf")
        leftover_source = "UNTRANSLATED SOURCE MARKER"
        [rendered_bbox] = _make_pdf_with_textboxes(
            out_path, [((72, 700, 320, 730), leftover_source)]
        )

        elem = TranslatableElement(
            element_id="e1",
            content=leftover_source,
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(
                x0=rendered_bbox[0], y0=rendered_bbox[1],
                x1=rendered_bbox[2], y1=rendered_bbox[3],
            ),
            translated_content=None,
        )
        doc = _make_doc([elem])

        captured = []
        result = layout_qa.run_layout_qa(doc, out_path, "leftover.pdf", captured.append)

        assert result is not None
        assert result.residual_pages == [1]
        assert result.biou_regressed is False, "exact-bbox match must not regress BIoU"
        assert result.warned is True
        assert len(captured) == 1, f"expected exactly 1 aggregated warning, got {captured!r}"
        assert "leftover.pdf" in captured[0]
        assert "1" in captured[0]
        assert "residual" in captured[0].lower()
        assert "biou" not in captured[0].lower() and "fidelity" not in captured[0].lower(), (
            "only the residual signal fired; the BIoU signal must not appear"
        )

    def test_correctly_translated_box_not_flagged_as_residual(self, tmp_path):
        """Disambiguation guard: a box whose rendered text is the TRANSLATED
        string (source string absent) must NOT be flagged as residual."""
        out_path = str(tmp_path / "translated.pdf")
        translated_text = "Ceci est correctement traduit"
        [rendered_bbox] = _make_pdf_with_textboxes(out_path, [((72, 700, 340, 730), translated_text)])

        elem = TranslatableElement(
            element_id="e1",
            content="This was correctly translated",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(
                x0=rendered_bbox[0], y0=rendered_bbox[1],
                x1=rendered_bbox[2], y1=rendered_bbox[3],
            ),
            translated_content=translated_text,
        )
        doc = _make_doc([elem])

        captured = []
        result = layout_qa.run_layout_qa(doc, out_path, "translated.pdf", captured.append)

        assert result is not None
        assert result.residual_pages == []
        assert result.warned is False
        assert captured == []

    def test_biou_and_residual_both_present_aggregate_into_single_entry(self, tmp_path):
        out_path = str(tmp_path / "both.pdf")
        leftover_source = "SECOND MARKER LEFT UNTRANSLATED"
        far_away_translation = "Something translated far away and unrelated"
        entries = [
            ((400, 400, 560, 450), far_away_translation),
            ((72, 700, 340, 730), leftover_source),
        ]
        far_bbox, leftover_bbox = _make_pdf_with_textboxes(out_path, entries)

        elem_biou = TranslatableElement(
            element_id="e1",
            content="Original source text unrelated to far away render",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=72, x1=260, y1=110),
            translated_content=far_away_translation,
        )
        elem_residual = TranslatableElement(
            element_id="e2",
            content=leftover_source,
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(
                x0=leftover_bbox[0], y0=leftover_bbox[1],
                x1=leftover_bbox[2], y1=leftover_bbox[3],
            ),
            translated_content=None,
        )
        doc = _make_doc([elem_biou, elem_residual])

        captured = []
        result = layout_qa.run_layout_qa(doc, out_path, "both.pdf", captured.append)

        assert result is not None
        assert result.biou_regressed is True
        assert result.residual_pages == [1]
        assert result.warned is True
        assert len(captured) == 1, (
            f"both signals must aggregate into exactly ONE entry, got {captured!r}"
        )
        assert "both.pdf" in captured[0]
        assert "1" in captured[0]
        assert "residual" in captured[0].lower()
        assert "biou" in captured[0].lower() or "fidelity" in captured[0].lower()


# ---------------------------------------------------------------------------
# AC-4: fail-soft (resilience)
# ---------------------------------------------------------------------------

class TestFailSoft:

    def test_metric_exception_is_caught_returns_none_no_warning(self, tmp_path, monkeypatch):
        out_path = str(tmp_path / "boom.pdf")
        _make_pdf_with_textboxes(out_path, [((72, 72, 300, 100), "Hello world")])

        elem = TranslatableElement(
            element_id="e1",
            content="Hello world",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=72, x1=300, y1=100),
        )
        doc = _make_doc([elem])

        def _boom(*_a, **_kw):
            raise RuntimeError("forced metric failure")

        monkeypatch.setattr(layout_qa, "compute_biou", _boom)

        captured = []
        logged = []
        result = layout_qa.run_layout_qa(
            doc, out_path, "boom.pdf", captured.append, log=logged.append
        )

        assert result is None
        assert captured == []
        assert logged, "the forced failure must be logged"

    def test_corrupt_output_pdf_reopen_is_fail_soft(self, tmp_path):
        corrupt_path = str(tmp_path / "corrupt.pdf")
        Path(corrupt_path).write_bytes(b"not a real pdf, deliberately corrupt")

        elem = TranslatableElement(
            element_id="e1",
            content="x",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=0, y0=0, x1=10, y1=10),
        )
        doc = _make_doc([elem])

        captured = []
        result = layout_qa.run_layout_qa(doc, corrupt_path, "corrupt.pdf", captured.append)

        assert result is None
        assert captured == []

    def test_missing_output_file_is_fail_soft(self, tmp_path):
        missing_path = str(tmp_path / "does_not_exist.pdf")
        elem = TranslatableElement(
            element_id="e1",
            content="x",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=0, y0=0, x1=10, y1=10),
        )
        doc = _make_doc([elem])

        captured = []
        result = layout_qa.run_layout_qa(doc, missing_path, "missing.pdf", captured.append)

        assert result is None
        assert captured == []

    def test_no_doc_or_no_callback_is_a_no_op(self, tmp_path):
        assert layout_qa.run_layout_qa(None, "/whatever.pdf", "d.pdf", lambda s: None) is None

        elem = TranslatableElement(
            element_id="e1", content="x", element_type=ElementType.TEXT,
            page_num=1, bbox=BoundingBox(x0=0, y0=0, x1=10, y1=10),
        )
        doc = _make_doc([elem])
        assert layout_qa.run_layout_qa(doc, "/whatever.pdf", "d.pdf", None) is None


# ---------------------------------------------------------------------------
# AC-4: data-boundary
# ---------------------------------------------------------------------------

class TestDataBoundary:

    def test_empty_source_bboxes_no_raise(self, tmp_path):
        out_path = str(tmp_path / "out.pdf")
        _make_pdf_with_textboxes(out_path, [((72, 72, 300, 100), "Some rendered text")])

        elem = TranslatableElement(
            element_id="e1", content="x", element_type=ElementType.TEXT,
            page_num=1, bbox=None,
        )
        doc = _make_doc([elem])

        captured = []
        result = layout_qa.run_layout_qa(doc, out_path, "empty-src.pdf", captured.append)

        assert result is not None
        assert result.warned is False
        assert captured == []

    def test_empty_rendered_bboxes_no_raise(self, tmp_path):
        out_path = str(tmp_path / "out.pdf")
        _blank_pdf(out_path)

        elem = TranslatableElement(
            element_id="e1", content="Hello", element_type=ElementType.TEXT,
            page_num=1, bbox=BoundingBox(x0=72, y0=72, x1=300, y1=100),
        )
        doc = _make_doc([elem])

        captured = []
        result = layout_qa.run_layout_qa(doc, out_path, "empty-rendered.pdf", captured.append)

        assert result is not None  # no raise is the point of this test

    def test_mismatched_box_counts_no_raise(self, tmp_path):
        out_path = str(tmp_path / "out.pdf")
        _make_pdf_with_textboxes(
            out_path,
            [((72, 72, 150, 110), "A"), ((200, 72, 280, 110), "B"), ((72, 200, 150, 240), "C")],
        )
        elems = [
            TranslatableElement(
                element_id=f"e{i}", content=c, element_type=ElementType.TEXT,
                page_num=1, bbox=BoundingBox(x0=0, y0=0, x1=50, y1=20),
            )
            for i, c in enumerate(["m1", "m2"])
        ]
        doc = _make_doc(elems)

        captured = []
        result = layout_qa.run_layout_qa(doc, out_path, "mismatch.pdf", captured.append)

        assert result is not None

    def test_no_text_page_no_raise(self, tmp_path):
        out_path = str(tmp_path / "out.pdf")
        _blank_pdf(out_path)

        doc = _make_doc([], pages=[PageInfo(page_num=1, width=612, height=792)])

        captured = []
        result = layout_qa.run_layout_qa(doc, out_path, "blank.pdf", captured.append)

        assert result is not None
        assert result.warned is False
        assert captured == []

    def test_page_over_max_boxes_per_page_short_circuits_without_raising(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(layout_qa, "LAYOUT_QA_MAX_BOXES_PER_PAGE", 2)

        out_path = str(tmp_path / "out.pdf")
        _make_pdf_with_textboxes(out_path, [((72, 72, 150, 110), "A"), ((72, 150, 150, 190), "B")])

        elems = [
            TranslatableElement(
                element_id=f"e{i}", content=f"text{i}", element_type=ElementType.TEXT,
                page_num=1,
                bbox=BoundingBox(x0=i * 10, y0=i * 10, x1=i * 10 + 20, y1=i * 10 + 20),
            )
            for i in range(5)  # 5 > cap of 2
        ]
        doc = _make_doc(elems)

        captured = []
        logged = []
        result = layout_qa.run_layout_qa(
            doc, out_path, "overcap.pdf", captured.append, log=logged.append
        )

        assert result is not None, "over-cap page must be skipped, not raised"
        assert result.warned is False
        assert captured == []
        assert any("exceed" in msg.lower() or "skip" in msg.lower() for msg in logged), (
            f"the over-cap page must be logged, got {logged!r}"
        )


# ---------------------------------------------------------------------------
# AC-5: metric-core shim identity (anti-orphan guard)
# ---------------------------------------------------------------------------

class TestMetricCoreIdentity:

    def test_biou_shim_same_object_as_runtime(self):
        import tests.metrics.biou as shim

        assert shim.compute_biou is layout_qa.compute_biou

    def test_residual_text_shim_same_object_as_runtime(self):
        import tests.metrics.residual_text as shim

        assert shim.check_residual_text is layout_qa.check_residual_text

    def test_truncation_rate_shim_same_object_as_runtime(self):
        import tests.metrics.truncation_rate as shim

        assert shim.compute_truncation_rate is layout_qa.compute_truncation_rate

    def test_iou_and_budget_importable_from_shim(self):
        from tests.metrics.biou import BIOU_REGRESSION_BUDGET, _iou

        assert callable(_iou)
        assert _iou is layout_qa._iou
        assert isinstance(BIOU_REGRESSION_BUDGET, float)
        assert BIOU_REGRESSION_BUDGET == layout_qa.BIOU_REGRESSION_BUDGET


# ---------------------------------------------------------------------------
# AC-7: BR-106 presence
# ---------------------------------------------------------------------------

def test_br_106_documented_in_business_rules():
    path = REPO_ROOT / "contracts" / "business" / "business-rules.md"
    text = path.read_text(encoding="utf-8")
    assert "BR-106" in text
    assert "layout-qa-safety-net-disclosure" in text


# ---------------------------------------------------------------------------
# AC-8: PDF-only (office processors never import run_layout_qa)
# ---------------------------------------------------------------------------

def test_office_processors_do_not_import_run_layout_qa():
    office_files = [
        REPO_ROOT / "app" / "backend" / "processors" / "docx_processor.py",
        REPO_ROOT / "app" / "backend" / "processors" / "pptx_processor.py",
        REPO_ROOT / "app" / "backend" / "processors" / "xlsx_processor.py",
    ]
    for f in office_files:
        text = f.read_text(encoding="utf-8")
        assert "run_layout_qa" not in text, f"{f} must not import run_layout_qa (PDF-only, AC-8)"
        assert "layout_qa" not in text, f"{f} must not reference the layout_qa module (AC-8)"
