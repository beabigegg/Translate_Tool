"""Tests for post-render layout QA (output-side layout-fidelity confirmation).

Verifies that:
- AC-1: run_layout_qa on an overlay output whose text sits in the source bboxes
        reports biou >= budget and passed=True.
- AC-2: a truncated element makes the QA entry fail (truncated_blocks counted).
- AC-3: residual SOURCE text inside a masked bbox is detected; translated text
        in the same bbox is NOT a false positive.
- AC-4: side_by_side mode reports biou=None and residual_text_blocks=None
        (bbox-identity metrics do not apply), truncation still measured.
- AC-5: fail-soft — unreadable output path returns None, never raises.
- AC-6: _translate_pdf_to_pdf fires layout_qa_callback with the QA result;
        LAYOUT_QA_ENABLED=false (runtime env read) suppresses it.
- AC-7: job_manager._record_layout_qa appends with (file, target_lang) dedup.
- AC-8: JobStatus.layout_qa propagates through GET /api/jobs/{id}.

Anti-tautology guards per CLAUDE.md:
- AC-6 enters via _translate_pdf_to_pdf (the actual QA call site). The lazy
  import inside the function binds at call time, so run_layout_qa is patched
  at its definition module (app.backend.services.layout_qa).
- AC-1/2/3 use real fitz documents — no mocking of the measured surface.
"""

from __future__ import annotations

import threading
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
from app.backend.services.layout_qa import run_layout_qa


def _make_output_pdf(path: str, texts_at: list) -> list:
    """Write a PDF with given (text, x, y) insertions; return block bboxes."""
    import fitz

    pdf = fitz.open()
    page = pdf.new_page(width=612, height=792)
    for text, x, y in texts_at:
        page.insert_text((x, y), text, fontsize=11)
    blocks = [fitz.Rect(b[:4]) for b in page.get_text("blocks")]
    pdf.save(path)
    pdf.close()
    return blocks


def _make_doc(source_path: str, contents_bboxes: list) -> TranslatableDocument:
    elements = [
        TranslatableElement(
            element_id=f"e{i}",
            content=content,
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=r.x0, y0=r.y0, x1=r.x1, y1=r.y1),
            should_translate=True,
            reading_order=i,
        )
        for i, (content, r) in enumerate(contents_bboxes)
    ]
    return TranslatableDocument(
        source_path=source_path,
        source_type="pdf",
        elements=elements,
        pages=[PageInfo(page_num=1, width=612, height=792)],
        metadata=DocumentMetadata(page_count=1, has_text_layer=True),
    )


class TestRunLayoutQA:
    def _overlay_fixture(self, tmp_path, source_content="Hello world source"):
        """Output PDF with translated text; doc element bbox == rendered block bbox."""
        out_path = str(tmp_path / "out.pdf")
        blocks = _make_output_pdf(out_path, [("translated text here", 72, 100)])
        assert len(blocks) == 1
        doc = _make_doc(str(tmp_path / "in.pdf"), [(source_content, blocks[0])])
        return doc, out_path

    def test_overlay_clean_render_passes(self, tmp_path):
        """AC-1: aligned bboxes, no truncation, no residual → passed=True."""
        doc, out_path = self._overlay_fixture(tmp_path)
        qa = run_layout_qa(doc, out_path, "English", "overlay", draw_mask=True)

        assert qa is not None
        assert qa["file"] == "out.pdf"
        assert qa["target_lang"] == "English"
        assert qa["biou"] is not None and qa["biou"] >= qa["biou_budget"], (
            f"aligned bboxes must satisfy the BIoU budget, got {qa['biou']}"
        )
        assert qa["residual_text_blocks"] == 0, (
            "translated text in the bbox must NOT count as residual source text"
        )
        assert qa["truncated_blocks"] == 0
        assert qa["passed"] is True

    def test_truncated_element_fails_qa(self, tmp_path):
        """AC-2: render_truncated element → counted and passed=False."""
        doc, out_path = self._overlay_fixture(tmp_path)
        doc.elements[0].render_truncated = True

        qa = run_layout_qa(doc, out_path, "English", "overlay", draw_mask=True)

        assert qa is not None
        assert qa["truncated_blocks"] == 1
        assert qa["total_blocks"] == 1
        assert qa["truncation_ratio"] == 1.0
        assert qa["passed"] is False

    def test_residual_source_text_detected(self, tmp_path):
        """AC-3: SOURCE text still readable in its masked bbox → residual flagged."""
        out_path = str(tmp_path / "out.pdf")
        # Simulate a redaction failure: the output still contains the source text.
        blocks = _make_output_pdf(out_path, [("Hello world source", 72, 100)])
        doc = _make_doc(str(tmp_path / "in.pdf"), [("Hello world source", blocks[0])])

        qa = run_layout_qa(doc, out_path, "English", "overlay", draw_mask=True)

        assert qa is not None
        assert qa["residual_text_blocks"] == 1, (
            "source text surviving inside its whiteover bbox must be flagged"
        )
        assert qa["passed"] is False

    def test_no_mask_skips_residual_check(self, tmp_path):
        """AC-3: without masking the source text intentionally remains → None."""
        doc, out_path = self._overlay_fixture(tmp_path)
        qa = run_layout_qa(doc, out_path, "English", "overlay", draw_mask=False)
        assert qa is not None
        assert qa["residual_text_blocks"] is None

    def test_side_by_side_reports_truncation_only(self, tmp_path):
        """AC-4: recomposed pages → bbox-identity metrics are None."""
        doc, out_path = self._overlay_fixture(tmp_path)
        qa = run_layout_qa(doc, out_path, "English", "side_by_side", draw_mask=True)

        assert qa is not None
        assert qa["biou"] is None
        assert qa["residual_text_blocks"] is None
        assert qa["truncated_blocks"] == 0
        assert qa["passed"] is True

    def test_fail_soft_on_unreadable_output(self, tmp_path):
        """AC-5: missing output file → None, no exception."""
        doc = _make_doc(
            str(tmp_path / "in.pdf"),
            [("Hello", BoundingBox(x0=72, y0=72, x1=300, y1=90))],
        )
        qa = run_layout_qa(
            doc, str(tmp_path / "missing.pdf"), "English", "overlay", draw_mask=True
        )
        assert qa is None


class TestLayoutQAWiring:
    """AC-6: _translate_pdf_to_pdf computes QA and fires layout_qa_callback."""

    def _run(self, tmp_path, monkeypatch=None, enabled=True):
        import app.backend.processors.pdf_processor as _mod

        in_dir = tmp_path / "input"
        in_dir.mkdir(exist_ok=True)
        in_path = str(in_dir / "sample.pdf")
        Path(in_path).write_bytes(b"")
        out_path = str(tmp_path / "output.pdf")

        fake_doc = _make_doc(
            in_path, [("Hello World", BoundingBox(x0=72, y0=72, x1=300, y1=90))]
        )
        fake_parser = MagicMock()
        fake_parser.parse.return_value = fake_doc

        if monkeypatch is not None:
            monkeypatch.setenv(
                "LAYOUT_QA_ENABLED", "true" if enabled else "false"
            )

        sentinel = {
            "file": "output.pdf",
            "target_lang": "English",
            "layout_mode": "overlay",
            "biou": 0.95,
            "biou_budget": 0.8,
            "residual_text_blocks": 0,
            "truncated_blocks": 0,
            "total_blocks": 1,
            "truncation_ratio": 0.0,
            "passed": True,
        }
        received = []
        with patch(
            "app.backend.parsers.pdf_parser.PyMuPDFParser",
            return_value=fake_parser,
        ):
            with patch.object(
                _mod, "translate_blocks_batch", return_value=[(True, "translated")]
            ):
                with patch.object(_mod, "_dispatch_render"):
                    # Lazy import in _translate_pdf_to_pdf → patch the
                    # definition module (binds at call time).
                    with patch(
                        "app.backend.services.layout_qa.run_layout_qa",
                        return_value=sentinel,
                    ) as mock_qa:
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
                            layout_qa_callback=received.append,
                        )
        return received, sentinel, mock_qa

    def test_callback_receives_qa_result(self, tmp_path, monkeypatch):
        received, sentinel, mock_qa = self._run(tmp_path, monkeypatch, enabled=True)
        assert mock_qa.called, "run_layout_qa was never invoked after render"
        assert received == [sentinel]

    def test_disabled_flag_suppresses_qa(self, tmp_path, monkeypatch):
        received, _, mock_qa = self._run(tmp_path, monkeypatch, enabled=False)
        assert not mock_qa.called, "LAYOUT_QA_ENABLED=false must skip the QA pass"
        assert received == []


class TestRecordLayoutQA:
    """AC-7: job_manager._record_layout_qa append + dedup semantics."""

    def _job(self, tmp_path=None):
        from pathlib import Path as _P
        from app.backend.services.job_manager import JobRecord

        base = _P("/tmp") if tmp_path is None else tmp_path
        return JobRecord(
            job_id="j1",
            status="running",
            total_files=1,
            input_dir=base / "in",
            output_dir=base / "out",
        )

    def test_appends_and_initialises(self):
        from app.backend.services.job_manager import _record_layout_qa

        job = self._job()
        assert job.layout_qa is None
        entry = {"file": "a.pdf", "target_lang": "English", "passed": True}
        _record_layout_qa(job, entry)
        assert job.layout_qa == [entry]

    def test_dedup_on_file_and_lang(self):
        from app.backend.services.job_manager import _record_layout_qa

        job = self._job()
        _record_layout_qa(job, {"file": "a.pdf", "target_lang": "English", "passed": True})
        _record_layout_qa(job, {"file": "a.pdf", "target_lang": "English", "passed": False})
        _record_layout_qa(job, {"file": "a.pdf", "target_lang": "Japanese", "passed": True})
        assert len(job.layout_qa) == 2
        assert job.layout_qa[0]["passed"] is True  # first entry wins


class TestLayoutQAApiPropagation:
    """AC-8: layout_qa propagates through GET /api/jobs/{id} (same consumer-
    binding mock pattern as TestWarningsApiPropagation)."""

    def _make_job(self, layout_qa=None):
        job = MagicMock()
        job.job_id = "job-layout-qa"
        job.status = "completed"
        job.output_zip = None
        job.processed_files = 1
        job.total_files = 1
        job.error = None
        job.current_file = ""
        job.segments_done = 0
        job.segments_total = 0
        job.file_segments_done = 0
        job.file_segments_total = 0
        job.started_at = None
        job.term_summary = None
        job.provider = None
        job.quality = None
        job.audit = None
        job.judge = None
        job.judge_apply_status = None
        job.status_detail = None
        job.warnings = None
        job.layout_qa = layout_qa
        job.lock = threading.Lock()
        return job

    def test_layout_qa_in_api_response(self):
        from fastapi.testclient import TestClient
        from app.backend.main import app

        entry = {
            "file": "out.pdf",
            "target_lang": "English",
            "layout_mode": "overlay",
            "biou": 0.93,
            "biou_budget": 0.8,
            "residual_text_blocks": 0,
            "truncated_blocks": 0,
            "total_blocks": 12,
            "truncation_ratio": 0.0,
            "passed": True,
        }
        job = self._make_job(layout_qa=[entry])

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            resp = TestClient(app).get("/api/jobs/job-layout-qa")

        assert resp.status_code == 200
        data = resp.json()
        assert data["layout_qa"] == [entry]

    def test_null_layout_qa_in_api_response(self):
        from fastapi.testclient import TestClient
        from app.backend.main import app

        job = self._make_job(layout_qa=None)
        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            resp = TestClient(app).get("/api/jobs/job-layout-qa")

        assert resp.status_code == 200
        assert resp.json()["layout_qa"] is None
