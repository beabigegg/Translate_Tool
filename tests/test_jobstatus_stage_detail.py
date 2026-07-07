"""Tests for the JobStatus additive current-segment fields (translation-progress-detail-ui).

Mocks at app.backend.api.routes.job_manager (consumer binding) per test-plan.md,
extending tests/test_jobstatus_download_url.py::_make_job()'s mock shape (AC-1,
AC-2, AC-7, AC-9). Schema-only enum tests construct JobStatus directly.
"""

from __future__ import annotations

import threading
from typing import Optional
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(
    job_id: str = "test-job-abc",
    status: str = "running",
    provider: Optional[str] = None,
    current_segment=None,
) -> MagicMock:
    """Build a minimal MagicMock that looks like a JobRecord (extends
    test_jobstatus_download_url.py::_make_job() with the new current_segment
    bookkeeping fields)."""
    job = MagicMock()
    job.job_id = job_id
    job.status = status
    job.output_zip = None
    job.processed_files = 0
    job.total_files = 1
    job.error = None
    job.current_file = ""
    job.segments_done = 0
    job.segments_total = 0
    job.file_segments_done = 0
    job.file_segments_total = 0
    job.started_at = None
    job.term_summary = None
    job.provider = provider
    job.quality = None
    job.audit = None
    job.judge = None
    job.judge_apply_status = None
    job.status_detail = None
    job.warnings = None
    job.current_segment = current_segment
    job.critique_started_at = None
    job.critique_done = 0
    job.critique_total = 0
    job.judge_started_at = None
    job.judge_units_done = 0
    job.judge_units_total = 0
    job.lock = threading.Lock()
    return job


def _get_test_client():
    from app.backend.main import app
    return TestClient(app)


_NEW_FIELDS = (
    "current_stage",
    "current_segment_source",
    "current_segment_draft",
    "current_segment_qe_score",
    "current_segment_adopted",
    "current_segment_judge_tier",
    "current_segment_judge_attempt",
    "current_segment_judge_substep",
)


# ---------------------------------------------------------------------------
# TestJobStatusAdditiveFields
# ---------------------------------------------------------------------------

class TestJobStatusAdditiveFields:
    def test_new_fields_present_when_populated(self):
        """AC-1: current_stage + core snapshot fields flow through the HTTP payload."""
        from app.backend.services.job_manager import CurrentSegmentSnapshot

        seg = CurrentSegmentSnapshot(
            stage="critique", source="Hello world", draft="Bonjour monde",
            qe_score=0.83, adopted=True,
        )
        job = _make_job(job_id="job-pop", status="running", current_segment=seg)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-pop")

        assert resp.status_code == 200
        data = resp.json()
        assert data["current_stage"] == "critique"
        assert data["current_segment_source"] == "Hello world"
        assert data["current_segment_draft"] == "Bonjour monde"
        assert data["current_segment_qe_score"] == 0.83
        assert data["current_segment_adopted"] is True

    def test_current_stage_enum_values_translate_critique_qe_adopt(self):
        """AC-1: JobStatus accepts each non-judge current_stage enum value."""
        from app.backend.api.schemas import JobStatus

        for stage in ("translate", "critique", "qe", "adopt"):
            job_status = JobStatus(
                job_id="j", status="running", processed_files=0, total_files=1,
                current_stage=stage,
            )
            assert job_status.current_stage == stage

    def test_existing_fields_unchanged_when_new_fields_absent(self):
        """AC-2: pre-existing fields keep working when current_segment is None."""
        job = _make_job(job_id="job-old", status="running", current_segment=None)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-old")

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "job-old"
        assert data["status"] == "running"
        assert data["output_ready"] is False
        for field in _NEW_FIELDS:
            assert data[field] is None, f"{field} should be null, got {data[field]!r}"

    def test_new_fields_null_when_job_just_started(self):
        """AC-7: a freshly-queued job (no current_segment yet) has all new fields null."""
        job = _make_job(job_id="job-fresh", status="queued", current_segment=None)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-fresh")

        assert resp.status_code == 200
        data = resp.json()
        for field in _NEW_FIELDS:
            assert data[field] is None

    def test_new_fields_null_when_critique_and_qe_disabled(self):
        """AC-7: critique+QE disabled → current_segment never populated → fields null."""
        job = _make_job(job_id="job-nocritique", status="running", current_segment=None)

        with patch("app.backend.api.routes.job_manager") as mock_jm, \
             patch("app.backend.api.routes.CRITIQUE_LOOP_ENABLED", False), \
             patch("app.backend.api.routes.QE_ENABLED", False):
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-nocritique")

        assert resp.status_code == 200
        data = resp.json()
        for field in _NEW_FIELDS:
            assert data[field] is None

    def test_current_stage_enum_includes_judge(self):
        """AC-9: JobStatus.current_stage accepts 'judge'."""
        from app.backend.api.schemas import JobStatus

        job_status = JobStatus(
            job_id="j", status="running", processed_files=0, total_files=1,
            current_stage="judge",
        )
        assert job_status.current_stage == "judge"

    def test_judge_fields_shape_when_judge_stage_active(self):
        """AC-9: the 3 judge-only fields carry the exact tier/attempt/substep values."""
        from app.backend.services.job_manager import CurrentSegmentSnapshot

        seg = CurrentSegmentSnapshot(
            stage="judge", source="Src text", draft="Draft text",
            judge_tier="中", judge_attempt=2, judge_substep="retranslating",
        )
        job = _make_job(job_id="job-judge", status="running", current_segment=seg)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-judge")

        assert resp.status_code == 200
        data = resp.json()
        assert data["current_stage"] == "judge"
        assert data["current_segment_judge_tier"] == "中"
        assert data["current_segment_judge_attempt"] == 2
        assert data["current_segment_judge_substep"] == "retranslating"

    def test_judge_fields_null_outside_judge_stage(self):
        """AC-9: a non-judge current_stage leaves the 3 judge-only fields null."""
        from app.backend.services.job_manager import CurrentSegmentSnapshot

        seg = CurrentSegmentSnapshot(stage="critique", source="Src", draft="Draft")
        job = _make_job(job_id="job-crit", status="running", current_segment=seg)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-crit")

        assert resp.status_code == 200
        data = resp.json()
        assert data["current_stage"] == "critique"
        assert data["current_segment_judge_tier"] is None
        assert data["current_segment_judge_attempt"] is None
        assert data["current_segment_judge_substep"] is None
