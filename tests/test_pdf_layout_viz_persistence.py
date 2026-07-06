"""Regression test: layout_viz.json must be persisted for the PDF-to-PDF
output path (output_format=pdf, layout_mode=overlay/side_by_side), not just
the PDF-to-DOCX path.

Bug: _translate_pdf_to_pdf parsed the document (populating doc.layout_viz)
but never wrote layout_viz.json, so GET /api/jobs/{id} always reported
layout_viz_available=False for PDF output jobs and the frontend's layout
viewer button never appeared, even though layout detection ran successfully.

Fix: extracted the persistence logic into a shared _save_layout_viz() helper
called by both _translate_pdf_with_pymupdf and _translate_pdf_to_pdf.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.backend.models.translatable_document import (
    BoundingBox,
    DocumentMetadata,
    ElementType,
    PageInfo,
    TranslatableDocument,
    TranslatableElement,
)


def _make_doc_with_layout_viz(source_path: str) -> TranslatableDocument:
    elements = [
        TranslatableElement(
            element_id="e1",
            content="Hello World",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=72, x1=300, y1=90),
            should_translate=True,
            reading_order=0,
        ),
    ]
    return TranslatableDocument(
        source_path=source_path,
        source_type="pdf",
        elements=elements,
        pages=[PageInfo(page_num=1, width=612, height=792)],
        metadata=DocumentMetadata(page_count=1, has_text_layer=True),
        layout_viz=[
            {
                "detector": "heuristic",
                "boxes": [{"type": "text", "bbox": [0.1, 0.1, 0.5, 0.2], "score": 1.0, "preview": "Hello"}],
                "page_num": 1,
                "width": 612.0,
                "height": 792.0,
            }
        ],
    )


class TestSaveLayoutVizHelper:
    """AC: _save_layout_viz writes layout_viz.json under the job directory."""

    def test_writes_layout_viz_json(self, tmp_path):
        import app.backend.processors.pdf_processor as _mod

        in_path = str(tmp_path / "input" / "sample.pdf")
        out_path = str(tmp_path / "output" / "sample_translated.pdf")
        doc = _make_doc_with_layout_viz(in_path)

        _mod._save_layout_viz(doc, in_path, out_path)

        viz_path = tmp_path / "layout_viz.json"
        assert viz_path.exists(), "layout_viz.json was not written"
        data = json.loads(viz_path.read_text(encoding="utf-8"))
        assert "sample.pdf" in data["files"]
        assert data["files"]["sample.pdf"]["total_pages"] == 1

    def test_noop_when_layout_viz_empty(self, tmp_path):
        import app.backend.processors.pdf_processor as _mod

        in_path = str(tmp_path / "input" / "sample.pdf")
        out_path = str(tmp_path / "output" / "sample_translated.pdf")
        doc = _make_doc_with_layout_viz(in_path)
        doc.layout_viz = []

        _mod._save_layout_viz(doc, in_path, out_path)

        assert not (tmp_path / "layout_viz.json").exists()


class TestPdfToPdfPersistsLayoutViz:
    """Regression: the PDF-to-PDF overlay path must persist layout_viz.json.

    Entry point: _translate_pdf_to_pdf directly (the actual code path used
    when output_format=pdf, layout_mode=overlay) — not translate_pdf or
    _translate_pdf_with_pymupdf, which would miss this exact regression.
    """

    def test_translate_pdf_to_pdf_writes_layout_viz_json(self, tmp_path):
        import app.backend.processors.pdf_processor as _mod

        in_dir = tmp_path / "input"
        out_dir = tmp_path / "output"
        in_dir.mkdir()
        out_dir.mkdir()
        in_path = str(in_dir / "sample.pdf")
        Path(in_path).write_bytes(b"")  # stub; parser is mocked below
        out_path = str(out_dir / "sample_translated.pdf")

        fake_doc = _make_doc_with_layout_viz(in_path)
        fake_parser = MagicMock()
        fake_parser.parse.return_value = fake_doc

        with patch(
            "app.backend.parsers.pdf_parser.PyMuPDFParser",
            return_value=fake_parser,
        ):
            with patch.object(
                _mod,
                "translate_blocks_batch",
                return_value=[(True, "Translated Hello")],
            ):
                with patch.object(_mod, "_dispatch_render"):
                    _mod._translate_pdf_to_pdf(
                        in_path=in_path,
                        out_path=out_path,
                        targets=["English"],
                        src_lang=None,
                        client=MagicMock(),
                        stop_flag=None,
                        log=lambda s: None,
                        skip_header_footer=False,
                        layout_mode="overlay",
                    )

        viz_path = tmp_path / "layout_viz.json"
        assert viz_path.exists(), (
            "layout_viz.json was not written by _translate_pdf_to_pdf — "
            "the layout viewer button will never appear for PDF output jobs"
        )
        data = json.loads(viz_path.read_text(encoding="utf-8"))
        assert "sample.pdf" in data["files"]
