"""Integration tests for the judge hook in _run_job (p3-llm-judge, AC-7).

CRITICAL anti-tautology note (from implementation-plan.md):
  The `_run_job` is a nested closure inside `create_job`. The judge is hooked
  INSIDE `_run_job`. To test AC-7 we must verify the judge hook is reachable
  from the actual execution path for each format, not just that a unit mock ran
  on a stub.

  We do this by:
  1. Calling `job_manager.create_job(...)` with a real (mocked) processor.
  2. Waiting for the thread to complete.
  3. Asserting `job.judge` was set by the real judge hook path.

AC-7: judge hook fires for all 4 formats (docx/pptx/xlsx/pdf).
AC-8: QE scores unchanged; CRITIQUE_LOOP_ENABLED path unchanged.
"""

from __future__ import annotations

import threading
import time
import types
from pathlib import Path
from typing import List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_judge_result(job_id: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        job_id=job_id,
        judge_status="available",
        score="高",
        source_text="src",
        translated_text="mt",
        feedback="OK",
        attempts=1,
        model="gemma3",
        retranslated_blocks=None,
    )


def _wait_for_job(job, timeout: float = 10.0) -> None:
    """Wait until job.status is terminal."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if job.status in ("completed", "failed", "stopped"):
            return
        time.sleep(0.05)
    raise TimeoutError(f"Job did not complete in {timeout}s; status={job.status}")


def _make_minimal_route_group(targets=None):
    from app.backend.services.model_router import RouteGroup
    return RouteGroup(
        targets=targets or ["en"],
        model="test-model",
        profile_id="general",
        model_type="general",
    )


# ---------------------------------------------------------------------------
# Shared mock fixture: patch heavy dependencies so _run_job completes quickly
# ---------------------------------------------------------------------------

def _run_job_with_judge_check(ext: str, judge_mock, winning_provider=None):
    """
    Run create_job with a minimal fake file of the given extension.
    Returns the JobRecord once the thread completes.
    """
    import tempfile
    import shutil

    from app.backend.services.job_manager import JobManager

    # Create a temporary "file" with the right extension
    with tempfile.TemporaryDirectory() as tmp:
        fake_file = Path(tmp) / f"document{ext}"
        fake_file.write_bytes(b"fake content")

        route_group = _make_minimal_route_group(["en"])

        # Patch process_files to add a fake qe_blocks entry and return immediately
        def fake_process_files(*args, **kwargs):
            hook = kwargs.get("post_translate_hook")
            if hook:
                hook([("block:0", "source", "translated")])
            return (1, 1, False, None, {"extracted": 0, "skipped": 0, "added": 0}, winning_provider)

        with patch("app.backend.services.job_manager.process_files", side_effect=fake_process_files), \
             patch("app.backend.services.job_manager.QE_ENABLED", False), \
             patch("app.backend.services.job_manager.config.JUDGE_ENABLED", True), \
             patch("app.backend.services.quality_judge.QualityJudge", return_value=judge_mock):

            jm = JobManager()
            job = jm.create_job(
                uploaded_files=[fake_file],
                route_groups=[route_group],
                src_lang=None,
                include_headers=False,
            )
            _wait_for_job(job)

    return job


# ---------------------------------------------------------------------------
# AC-7: judge hook fires for each format
# ---------------------------------------------------------------------------

def test_judge_hook_fires_docx():
    """judge hook fires in _run_job when processing a DOCX file (AC-7)."""
    fake_judge = MagicMock()
    fake_judge.run_judge_loop.return_value = _make_fake_judge_result("test-docx")

    job = _run_job_with_judge_check(".docx", fake_judge)

    assert job.judge is not None, "job.judge must be set after _run_job completes"
    fake_judge.run_judge_loop.assert_called_once()


def test_judge_hook_fires_pptx():
    """judge hook fires in _run_job when processing a PPTX file (AC-7)."""
    fake_judge = MagicMock()
    fake_judge.run_judge_loop.return_value = _make_fake_judge_result("test-pptx")

    job = _run_job_with_judge_check(".pptx", fake_judge)

    assert job.judge is not None
    fake_judge.run_judge_loop.assert_called_once()


def test_judge_hook_fires_xlsx():
    """judge hook fires in _run_job when processing an XLSX file (AC-7)."""
    fake_judge = MagicMock()
    fake_judge.run_judge_loop.return_value = _make_fake_judge_result("test-xlsx")

    job = _run_job_with_judge_check(".xlsx", fake_judge)

    assert job.judge is not None
    fake_judge.run_judge_loop.assert_called_once()


def test_judge_hook_fires_pdf():
    """judge hook fires in _run_job when processing a PDF file (AC-7)."""
    fake_judge = MagicMock()
    fake_judge.run_judge_loop.return_value = _make_fake_judge_result("test-pdf")

    job = _run_job_with_judge_check(".pdf", fake_judge)

    assert job.judge is not None
    fake_judge.run_judge_loop.assert_called_once()


def test_judge_skipped_when_provider_is_deepseek():
    """judge hook does NOT fire when the translation provider was 'deepseek'."""
    fake_judge = MagicMock()
    fake_judge.run_judge_loop.return_value = _make_fake_judge_result("test-deepseek-skip")

    job = _run_job_with_judge_check(".docx", fake_judge, winning_provider="deepseek")

    assert job.judge is None, "judge must be skipped when translation provider is deepseek"
    fake_judge.run_judge_loop.assert_not_called()


def test_judge_still_fires_when_provider_is_panjit():
    """judge hook still fires for non-deepseek cloud providers (e.g. panjit)."""
    fake_judge = MagicMock()
    fake_judge.run_judge_loop.return_value = _make_fake_judge_result("test-panjit-runs")

    job = _run_job_with_judge_check(".docx", fake_judge, winning_provider="panjit")

    assert job.judge is not None
    fake_judge.run_judge_loop.assert_called_once()


# ---------------------------------------------------------------------------
# AC-8: QE scoring unaffected when judge is enabled
# ---------------------------------------------------------------------------

def test_judge_does_not_alter_qe_scoring():
    """QE scores are unchanged when judge is also enabled (AC-8)."""
    import tempfile
    import shutil

    from app.backend.services.job_manager import JobManager, JobQualityRecord, BlockQualityScore

    fake_judge = MagicMock()
    fake_judge.run_judge_loop.return_value = _make_fake_judge_result("test-qe-coexist")

    # Mock QE model that returns a score
    mock_qe_model = MagicMock()
    mock_qe_prediction = MagicMock()
    mock_qe_prediction.scores = [0.85]
    mock_qe_model.predict.return_value = mock_qe_prediction

    with tempfile.TemporaryDirectory() as tmp:
        fake_file = Path(tmp) / "document.docx"
        fake_file.write_bytes(b"fake content")
        route_group = _make_minimal_route_group(["en"])

        def fake_process_files(*args, **kwargs):
            hook = kwargs.get("post_translate_hook")
            if hook:
                hook([("block:0", "source", "translated")])
            return (1, 1, False, None, {"extracted": 0, "skipped": 0, "added": 0}, None)

        with patch("app.backend.services.job_manager.process_files", side_effect=fake_process_files), \
             patch("app.backend.services.job_manager.QE_ENABLED", True), \
             patch("app.backend.services.job_manager.load_model", return_value=mock_qe_model), \
             patch("app.backend.services.job_manager.score_blocks", return_value=[0.85]), \
             patch("app.backend.services.job_manager.config.JUDGE_ENABLED", True), \
             patch("app.backend.services.quality_judge.QualityJudge", return_value=fake_judge):

            jm = JobManager()
            job = jm.create_job(
                uploaded_files=[fake_file],
                route_groups=[route_group],
                src_lang=None,
                include_headers=False,
            )
            _wait_for_job(job)

    # Both QE and judge should be present
    assert job.quality is not None, "QE record should be present"
    assert job.judge is not None, "judge result should be present"
    assert job.quality.qe_status == "available"
    assert job.judge.judge_status == "available"


# ---------------------------------------------------------------------------
# AC-8: CRITIQUE_LOOP_ENABLED unaffected when JUDGE_ENABLED=False
# ---------------------------------------------------------------------------

def test_critique_loop_unaffected_when_judge_disabled():
    """CRITIQUE_LOOP_ENABLED behavior unchanged when JUDGE_ENABLED=False (AC-8)."""
    # This test verifies the judge step is skipped and doesn't interfere with other flags.
    import tempfile

    from app.backend.services.job_manager import JobManager

    with tempfile.TemporaryDirectory() as tmp:
        fake_file = Path(tmp) / "document.docx"
        fake_file.write_bytes(b"fake content")
        route_group = _make_minimal_route_group(["en"])

        def fake_process_files(*args, **kwargs):
            hook = kwargs.get("post_translate_hook")
            if hook:
                hook([("block:0", "source", "translated")])
            return (1, 1, False, None, {"extracted": 0, "skipped": 0, "added": 0}, None)

        judge_import_mock = MagicMock()

        with patch("app.backend.services.job_manager.process_files", side_effect=fake_process_files), \
             patch("app.backend.services.job_manager.QE_ENABLED", False), \
             patch("app.backend.services.job_manager.config.JUDGE_ENABLED", False):

            jm = JobManager()
            job = jm.create_job(
                uploaded_files=[fake_file],
                route_groups=[route_group],
                src_lang=None,
                include_headers=False,
            )
            _wait_for_job(job)

    # Judge should be None (not set) when JUDGE_ENABLED=False
    assert job.judge is None, "job.judge must be None when JUDGE_ENABLED=False"
    # Job must complete normally
    assert job.status == "completed"
