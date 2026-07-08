"""Tests for pdf-renderer-fallback-warn change.

Verifies that:
- AC-1: fitz-fallback path emits FITZ_FALLBACK_WARNING via warnings_callback
- AC-2: PDF→DOCX routing path emits DOCX_ROUTING_WARNING via warnings_callback
- AC-3: no warning emitted when fitz succeeds
- AC-4: JobStatus.warnings field is Optional[List[str]], rejects bare str
- AC-5: JobStatus schema has a 'warnings' field
- AC-6: fitz-fallback test patches consumer binding (pdf_processor._run_fitz_render)
        and enters via _dispatch_render — not translate_pdf or the renderer module

Anti-tautology guards per CLAUDE.md and test-plan.md:
- Fitz-fallback tests call _dispatch_render directly (not translate_pdf).
- Patch target is app.backend.processors.pdf_processor._run_fitz_render (consumer binding),
  not app.backend.renderers.fitz_renderer.PDFGenerator.
- API propagation tests mock app.backend.api.routes.job_manager (consumer binding,
  same pattern as test_jobstatus_download_url.py).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(
    job_id: str = "test-job-warn",
    status: str = "completed",
    warnings=None,
) -> MagicMock:
    """Build a minimal MagicMock that looks like a JobRecord for API-layer tests."""
    job = MagicMock()
    job.job_id = job_id
    job.status = status
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
    job.warnings = warnings
    # translation-progress-detail-ui: explicit defaults so a bare MagicMock
    # attribute access doesn't return an auto-mock (fails JobStatus validation).
    job.current_segment = None
    job.critique_started_at = None
    job.critique_done = 0
    job.critique_total = 0
    job.judge_started_at = None
    job.judge_units_done = 0
    job.judge_units_total = 0
    job.lock = threading.Lock()
    return job


def _get_test_client() -> TestClient:
    from app.backend.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# TestFitzFallbackWarning (AC-1, AC-6)
# ---------------------------------------------------------------------------

class TestFitzFallbackWarning:
    """AC-1: fitz-fallback path emits FITZ_FALLBACK_WARNING; AC-6: anti-tautology guard."""

    def test_fitz_exception_emits_exact_fallback_warning(self):
        """AC-1: when _run_fitz_render raises, _dispatch_render emits FITZ_FALLBACK_WARNING
        via warnings_callback.

        Entry point: _dispatch_render (not translate_pdf — avoids wrong-entry-point tautology).
        Patch target: app.backend.processors.pdf_processor._run_fitz_render (consumer binding).
        """
        import app.backend.processors.pdf_processor as _mod

        captured = []

        with patch(
            "app.backend.processors.pdf_processor._run_fitz_render",
            side_effect=RuntimeError("fitz failure injected by test"),
        ):
            with patch("app.backend.processors.pdf_processor._run_reportlab_render"):
                _mod._dispatch_render(
                    doc=None,
                    translations={},
                    output_path="/tmp/fitz_warn_test.pdf",
                    target_lang="en",
                    mode=None,
                    draw_mask=False,
                    doc_id="test.pdf",
                    warnings_callback=captured.append,
                )

        assert len(captured) == 1, f"expected exactly 1 warning, got {captured!r}"
        assert captured[0] == _mod.FITZ_FALLBACK_WARNING, (
            f"warning string mismatch:\n  got:      {captured[0]!r}\n"
            f"  expected: {_mod.FITZ_FALLBACK_WARNING!r}"
        )

    def test_fitz_mock_targets_consumer_call_site_not_renderer_module(self):
        """AC-6: seam is on pdf_processor._run_fitz_render (consumer binding);
        entry is _dispatch_render directly (not translate_pdf or the renderer module).

        Uses patch.object on the consumer module to demonstrate that:
        - Patching at the consumer binding intercepts _dispatch_render's call.
        - A patch only at app.backend.renderers.fitz_renderer.PDFGenerator would NOT
          intercept this seam (that would be a call-wiring tautology per CLAUDE.md).
        """
        import app.backend.processors.pdf_processor as _mod

        captured = []

        # patch.object targets the consumer-module binding, not the renderer module.
        with patch.object(_mod, "_run_fitz_render", side_effect=RuntimeError("injected")):
            with patch.object(_mod, "_run_reportlab_render"):
                # Enter via _dispatch_render directly — not translate_pdf.
                _mod._dispatch_render(
                    doc=None,
                    translations={},
                    output_path="/tmp/antitautology.pdf",
                    target_lang="en",
                    mode=None,
                    draw_mask=False,
                    doc_id="anti-tautology.pdf",
                    warnings_callback=captured.append,
                )

        assert captured == [_mod.FITZ_FALLBACK_WARNING], (
            "Consumer-binding patch via _dispatch_render did not capture the warning; "
            "seam may be missing or wired to the wrong location."
        )

    def test_fitz_crash_fallback_still_wraps_long_text(self):
        """AC-2 (resilience, BR-34): when the fitz path raises, the REAL
        ReportLab fallback that _dispatch_render invokes must still WRAP
        long translated text within its bbox — not just log a warning while
        silently overflowing/truncating (BR-40 shared cascade)."""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        import os
        import tempfile

        from app.backend.models.translatable_document import (
            BoundingBox,
            DocumentMetadata,
            ElementType,
            PageInfo,
            TranslatableDocument,
            TranslatableElement,
        )
        from app.backend.renderers.base import RenderMode
        import app.backend.processors.pdf_processor as _mod

        long_translation = (
            "This is a considerably long piece of translated text that must "
            "wrap across multiple lines instead of overflowing horizontally "
            "past its narrow allotted column width no matter what."
        )
        elem = TranslatableElement(
            element_id="e1",
            content="Short",
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=300, x1=220, y1=400),
            should_translate=True,
            translated_content=long_translation,
        )
        doc = TranslatableDocument(
            source_path="/test/sample.pdf",
            source_type="pdf",
            elements=[elem],
            pages=[PageInfo(page_num=1, width=612, height=792)],
            metadata=DocumentMetadata(page_count=1, has_text_layer=True),
        )

        fd, out_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        captured = []
        try:
            with patch(
                "app.backend.processors.pdf_processor._run_fitz_render",
                side_effect=RuntimeError("forced fitz crash"),
            ):
                _mod._dispatch_render(
                    doc=doc,
                    translations={},
                    output_path=out_path,
                    target_lang="en",
                    mode=RenderMode.OVERLAY,
                    draw_mask=True,
                    doc_id="crash-wrap-test.pdf",
                    warnings_callback=captured.append,
                )

            assert captured == [_mod.FITZ_FALLBACK_WARNING]

            result_doc = fitz.open(out_path)
            page_dict = result_doc[0].get_text("dict")
            line_ys = {
                round(line["bbox"][1], 1)
                for block in page_dict.get("blocks", [])
                for line in block.get("lines", [])
            }
            result_doc.close()

            assert len(line_ys) > 1, (
                "the ReportLab fallback must wrap the long translation across "
                f"multiple lines, got {len(line_ys)} distinct line(s)"
            )
        finally:
            if os.path.exists(out_path):
                os.unlink(out_path)


# ---------------------------------------------------------------------------
# TestDocxRoutingWarning (AC-2)
# ---------------------------------------------------------------------------

class TestDocxRoutingWarning:
    """AC-2: PDF→bilingual-DOCX routing path emits DOCX_ROUTING_WARNING."""

    def test_docx_routing_emits_exact_layout_skip_warning(self, tmp_path):
        """AC-2: output_format='docx' + is_win32com_available=False → DOCX_ROUTING_WARNING.

        Forces the DOCX routing arm (not the pdf-output arm).  COM is absent (False)
        so the warning emit point is reached before parser dispatch.
        Parser dispatch is short-circuited with a no-op _translate_pdf_with_pypdf2.
        """
        import app.backend.processors.pdf_processor as _mod

        captured = []

        fake_in = str(tmp_path / "sample.pdf")
        Path(fake_in).write_bytes(b"")  # stub so path manipulation succeeds

        with patch(
            "app.backend.processors.pdf_processor.is_win32com_available",
            return_value=False,
        ):
            with patch(
                "app.backend.processors.pdf_processor._get_pymupdf_parser",
                return_value=None,
            ):
                with patch(
                    "app.backend.processors.pdf_processor._translate_pdf_with_pypdf2",
                    return_value=False,
                ):
                    _mod.translate_pdf(
                        in_path=fake_in,
                        out_path=str(tmp_path / "out.docx"),
                        targets=["English"],
                        src_lang=None,
                        client=MagicMock(),
                        output_format="docx",
                        layout_mode="inline",
                        warnings_callback=captured.append,
                    )

        assert captured == [_mod.DOCX_ROUTING_WARNING], (
            f"Expected [DOCX_ROUTING_WARNING], got {captured!r}"
        )


# ---------------------------------------------------------------------------
# TestNoDegradationNoWarning (AC-3)
# ---------------------------------------------------------------------------

class TestNoDegradationNoWarning:
    """AC-3: no warning emitted when fitz render succeeds."""

    def test_no_warning_when_fitz_succeeds(self):
        """AC-3: _run_fitz_render completes normally → warnings_callback never invoked."""
        import app.backend.processors.pdf_processor as _mod

        captured = []

        # _run_fitz_render is patched to succeed (no side_effect = returns None).
        with patch("app.backend.processors.pdf_processor._run_fitz_render"):
            _mod._dispatch_render(
                doc=None,
                translations={},
                output_path="/tmp/success.pdf",
                target_lang="en",
                mode=None,
                draw_mask=False,
                doc_id="clean.pdf",
                warnings_callback=captured.append,
            )

        assert captured == [], (
            f"Expected no warnings on fitz success, got {captured!r}"
        )


# ---------------------------------------------------------------------------
# TestWarningsSchema (AC-4, AC-5)
# ---------------------------------------------------------------------------

class TestWarningsSchema:
    """AC-4: warnings field type enforcement; AC-5: field presence in JobStatus."""

    def test_warnings_field_is_list_or_none_not_bare_string(self):
        """AC-4: warnings=None and warnings=['x'] accepted; warnings='x' rejected by pydantic."""
        from app.backend.api.schemas import JobStatus
        import pydantic

        # None is valid (no degradation)
        s = JobStatus(
            job_id="j-none",
            status="completed",
            processed_files=1,
            total_files=1,
            output_ready=True,
            warnings=None,
        )
        assert s.warnings is None

        # List[str] is valid
        s2 = JobStatus(
            job_id="j-list",
            status="completed",
            processed_files=1,
            total_files=1,
            output_ready=True,
            warnings=["a warning message"],
        )
        assert s2.warnings == ["a warning message"]

        # Bare str must be rejected — data-shape-contract requires list or null
        with pytest.raises(pydantic.ValidationError):
            JobStatus(
                job_id="j-bad",
                status="completed",
                processed_files=1,
                total_files=1,
                output_ready=True,
                warnings="bare_string_not_list",
            )

    def test_jobstatus_schema_has_warnings_field(self):
        """AC-5: JobStatus model must have a 'warnings' field."""
        from app.backend.api.schemas import JobStatus

        # Compatible with both pydantic v1 (__fields__) and v2 (model_fields)
        if hasattr(JobStatus, "model_fields"):
            field_names = set(JobStatus.model_fields.keys())
        else:
            field_names = set(JobStatus.__fields__.keys())

        assert "warnings" in field_names, (
            f"'warnings' field missing from JobStatus; found: {sorted(field_names)}"
        )


# ---------------------------------------------------------------------------
# TestWarningsApiPropagation (AC-1 contract, AC-2 contract, AC-3 contract)
# ---------------------------------------------------------------------------

class TestWarningsApiPropagation:
    """API-level: warnings field propagates through GET /api/jobs/{id} response.

    Mocks app.backend.api.routes.job_manager (consumer binding — same pattern
    as test_jobstatus_download_url.py) so the route serializes job.warnings.
    """

    def test_fitz_fallback_warning_in_api_response(self):
        """AC-1 contract: job.warnings=[FITZ_FALLBACK_WARNING] → JSON warnings list present."""
        from app.backend.processors.pdf_processor import FITZ_FALLBACK_WARNING

        job = _make_job(job_id="job-fitz-warn", warnings=[FITZ_FALLBACK_WARNING])

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-fitz-warn")

        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data
        assert data["warnings"] == [FITZ_FALLBACK_WARNING]

    def test_docx_routing_warning_in_api_response(self):
        """AC-2 contract: job.warnings=[DOCX_ROUTING_WARNING] → JSON warnings list present."""
        from app.backend.processors.pdf_processor import DOCX_ROUTING_WARNING

        job = _make_job(job_id="job-docx-warn", warnings=[DOCX_ROUTING_WARNING])

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-docx-warn")

        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data
        assert data["warnings"] == [DOCX_ROUTING_WARNING]

    def test_no_warnings_is_null_or_empty_in_api_response(self):
        """AC-3 contract: job.warnings=None → JSON warnings is null (no degradation)."""
        job = _make_job(job_id="job-no-warn", warnings=None)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-no-warn")

        assert resp.status_code == 200
        data = resp.json()
        warnings_val = data.get("warnings")
        assert warnings_val is None or warnings_val == [], (
            f"Expected null/empty warnings when no degradation, got {warnings_val!r}"
        )


# ---------------------------------------------------------------------------
# TestTruncationDisclosureWarning (AC-11, BR-104)
# ---------------------------------------------------------------------------

class TestTruncationDisclosureWarning:
    """AC-11/BR-104: post-render sweep emits exactly one aggregated
    job.warnings entry per file when any element has render_truncated=True.

    Entry point: _dispatch_render directly (not translate_pdf), matching the
    file's established anti-tautology convention.
    """

    @staticmethod
    def _make_doc(pages_with_truncation):
        from app.backend.models.translatable_document import (
            BoundingBox,
            DocumentMetadata,
            ElementType,
            PageInfo,
            TranslatableDocument,
            TranslatableElement,
        )

        elements = []
        seen_pages = []
        for i, (page_num, truncated) in enumerate(pages_with_truncation):
            elem = TranslatableElement(
                element_id=f"e{i}",
                content="text",
                element_type=ElementType.TEXT,
                page_num=page_num,
                bbox=BoundingBox(x0=0, y0=0, x1=100, y1=20),
            )
            elem.render_truncated = truncated
            elements.append(elem)
            if page_num not in seen_pages:
                seen_pages.append(page_num)
        pages = [PageInfo(page_num=p, width=612, height=792) for p in seen_pages]
        return TranslatableDocument(
            source_path="/fake.pdf",
            source_type="pdf",
            elements=elements,
            pages=pages,
            metadata=DocumentMetadata(page_count=len(pages), has_text_layer=True),
        )

    def test_one_aggregated_warning_per_file_regardless_of_truncated_count(self):
        """Case 1: 3 truncated elements across 2 pages -> exactly ONE aggregated entry."""
        import app.backend.processors.pdf_processor as _mod

        doc = self._make_doc([(1, True), (1, True), (2, True)])
        captured = []

        with patch.object(_mod, "_run_fitz_render"):
            _mod._dispatch_render(
                doc=doc,
                translations={},
                output_path="/tmp/trunc_disclosure_test.pdf",
                target_lang="en",
                mode=None,
                draw_mask=False,
                doc_id="trunc-multi.pdf",
                warnings_callback=captured.append,
            )

        assert len(captured) == 1, f"expected exactly 1 aggregated warning, got {captured!r}"
        assert "trunc-multi.pdf" in captured[0]
        assert "1" in captured[0] and "2" in captured[0], (
            f"aggregated warning must name the affected page(s), got {captured[0]!r}"
        )

    def test_no_warning_entry_when_no_truncation(self):
        """Case 2: no element truncated -> disclosure sweep emits nothing."""
        import app.backend.processors.pdf_processor as _mod

        doc = self._make_doc([(1, False), (2, False)])
        captured = []

        with patch.object(_mod, "_run_fitz_render"):
            _mod._dispatch_render(
                doc=doc,
                translations={},
                output_path="/tmp/no_trunc_disclosure_test.pdf",
                target_lang="en",
                mode=None,
                draw_mask=False,
                doc_id="clean-multi.pdf",
                warnings_callback=captured.append,
            )

        assert captured == [], f"expected no warnings when nothing was truncated, got {captured!r}"

    def test_warning_fires_identically_fitz_or_reportlab_truncation_source(self):
        """Case 3 (CONTINGENT on IP-1/IP-12 element-ref threading): the sweep
        reads the IR render_truncated marker post-render — it must fire the
        same way regardless of WHICH backend (fitz primary or the ReportLab
        fallback) set that marker.
        """
        import app.backend.processors.pdf_processor as _mod

        # render_truncated already set on the IR (simulates the fitz path
        # having marked it during a real _run_fitz_render call).
        doc_fitz_source = self._make_doc([(1, True)])
        captured_fitz = []
        with patch.object(_mod, "_run_fitz_render"):
            _mod._dispatch_render(
                doc=doc_fitz_source,
                translations={},
                output_path="/tmp/fitz_source.pdf",
                target_lang="en",
                mode=None,
                draw_mask=False,
                doc_id="fitz-source.pdf",
                warnings_callback=captured_fitz.append,
            )

        # render_truncated already set on the IR (simulates the ReportLab
        # fallback path having marked it via the IP-1 element-ref thread),
        # AND the fitz primary path fails so the fallback branch also fires.
        doc_reportlab_source = self._make_doc([(1, True)])
        captured_reportlab = []
        with patch.object(_mod, "_run_fitz_render", side_effect=RuntimeError("forced fallback")), \
             patch.object(_mod, "_run_reportlab_render"):
            _mod._dispatch_render(
                doc=doc_reportlab_source,
                translations={},
                output_path="/tmp/reportlab_source.pdf",
                target_lang="en",
                mode=None,
                draw_mask=False,
                doc_id="reportlab-source.pdf",
                warnings_callback=captured_reportlab.append,
            )

        assert len(captured_fitz) == 1, f"fitz-source truncation must emit 1 entry, got {captured_fitz!r}"
        truncation_entries_reportlab = [
            w for w in captured_reportlab if w != _mod.FITZ_FALLBACK_WARNING
        ]
        assert len(truncation_entries_reportlab) == 1, (
            "truncation disclosure must fire identically on the ReportLab-fallback "
            f"source, got {captured_reportlab!r}"
        )


# ---------------------------------------------------------------------------
# TestLayoutQaDisabled / TestLayoutQaWarning (BR-106, layout-qa-safety-net)
# ---------------------------------------------------------------------------

class TestLayoutQaDisabled:
    """AC-1: with LAYOUT_QA_ENABLED=false (default), run_layout_qa is never
    invoked and no new job.warnings entry is emitted.

    Entry point: _dispatch_render directly (not translate_pdf), matching this
    file's established anti-tautology convention. Patches the consumer binding
    (pdf_processor.run_layout_qa) and asserts NOT-CALLED -- not merely that
    captured warnings are empty -- per the flag-off anti-tautology guard.
    """

    def test_flag_off_run_layout_qa_not_invoked_no_warning(self):
        import app.backend.processors.pdf_processor as _mod

        doc = TestTruncationDisclosureWarning._make_doc([(1, False)])
        captured = []

        with patch.object(_mod, "_run_fitz_render"):
            with patch.object(_mod, "run_layout_qa") as mock_run_layout_qa:
                _mod._dispatch_render(
                    doc=doc,
                    translations={},
                    output_path="/tmp/layout_qa_disabled_test.pdf",
                    target_lang="en",
                    mode=None,
                    draw_mask=False,
                    doc_id="qa-disabled.pdf",
                    warnings_callback=captured.append,
                )

        mock_run_layout_qa.assert_not_called()
        assert captured == [], f"expected no warnings with the flag off, got {captured!r}"


class TestLayoutQaWarning:
    """AC-2/AC-3/AC-4: with LAYOUT_QA_ENABLED=true, the real _dispatch_render
    seam fires run_layout_qa exactly once per warranted file via
    warnings_callback -> _record_job_warning; fail-soft on exception.
    """

    def test_biou_regression_warning_fires_through_real_seam(self, tmp_path):
        """AC-2: real seam -- _dispatch_render invokes the REAL run_layout_qa
        (not a mock wrapper), which re-opens a real rendered PDF and detects a
        BIoU regression, emitting exactly one job.warnings entry."""
        import fitz

        import app.backend.processors.pdf_processor as _mod

        doc = TestTruncationDisclosureWarning._make_doc([(1, False)])
        # doc's element bbox is fixed at (0, 0, 100, 20) (see _make_doc); render
        # real text far away from it so the mean BIoU regresses below budget.
        out_path = str(tmp_path / "real_seam_regress.pdf")
        pdf = fitz.open()
        page = pdf.new_page(width=612, height=792)
        page.insert_textbox(fitz.Rect(400, 600, 560, 650), "Unrelated rendered text", fontsize=11)
        pdf.save(out_path)
        pdf.close()

        captured = []
        with patch.object(_mod, "LAYOUT_QA_ENABLED", True):
            with patch.object(_mod, "_run_fitz_render"):
                _mod._dispatch_render(
                    doc=doc,
                    translations={},
                    output_path=out_path,
                    target_lang="en",
                    mode=None,
                    draw_mask=False,
                    doc_id="real-seam-regress.pdf",
                    warnings_callback=captured.append,
                )

        assert len(captured) == 1, f"expected exactly 1 aggregated warning, got {captured!r}"
        assert "real-seam-regress.pdf" in captured[0]
        assert "1" in captured[0]

    def test_layout_qa_exception_never_fails_job_or_fabricates_warning(self, tmp_path):
        """AC-4: forcing an internal layout-QA metric to raise must never
        propagate out of _dispatch_render (job never fails) and must never
        fabricate a warning."""
        import fitz

        import app.backend.processors.pdf_processor as _mod

        doc = TestTruncationDisclosureWarning._make_doc([(1, False)])
        out_path = str(tmp_path / "real_seam_exception.pdf")
        pdf = fitz.open()
        page = pdf.new_page(width=612, height=792)
        page.insert_textbox(fitz.Rect(0, 0, 100, 20), "some text", fontsize=8)
        pdf.save(out_path)
        pdf.close()

        captured = []
        with patch.object(_mod, "LAYOUT_QA_ENABLED", True):
            with patch.object(_mod, "_run_fitz_render"):
                with patch(
                    "app.backend.services.layout_qa.compute_biou",
                    side_effect=RuntimeError("forced layout-qa metric failure"),
                ):
                    # Must not raise -- this call succeeding IS the assertion
                    # that the job would not fail.
                    _mod._dispatch_render(
                        doc=doc,
                        translations={},
                        output_path=out_path,
                        target_lang="en",
                        mode=None,
                        draw_mask=False,
                        doc_id="qa-exception.pdf",
                        warnings_callback=captured.append,
                    )

        assert captured == [], (
            f"a caught layout-QA exception must not fabricate a warning, got {captured!r}"
        )
