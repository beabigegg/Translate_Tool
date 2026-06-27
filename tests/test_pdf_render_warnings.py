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
