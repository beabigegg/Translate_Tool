"""Tests for download_url derivation in the job_status endpoint (download-url-in-jobstatus).

Mocks at app.backend.api.routes.job_manager (consumer binding) per test-plan.md.
"""

from __future__ import annotations

import threading
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(
    job_id: str = "test-job-abc",
    status: str = "completed",
    output_zip: Optional[Path] = None,
    total_files: int = 1,
    processed_files: int = 1,
    provider: Optional[str] = None,
) -> MagicMock:
    """Build a minimal MagicMock that looks like a JobRecord."""
    job = MagicMock()
    job.job_id = job_id
    job.status = status
    job.output_zip = output_zip
    job.processed_files = processed_files
    job.total_files = total_files
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
    # translation-progress-detail-ui: explicit defaults so a bare MagicMock
    # attribute access doesn't return an auto-mock (which would fail JobStatus
    # pydantic validation for these Optional[str]/int fields).
    job.current_segment = None
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


# ---------------------------------------------------------------------------
# TestDownloadUrlDerivation
# ---------------------------------------------------------------------------

class TestDownloadUrlDerivation:
    """Parametrized and individual unit tests for the download_url derivation rule."""

    def test_completed_with_existing_zip(self, tmp_path):
        """status=completed + output_zip path exists → download_url set (AC-2)."""
        zip_path = tmp_path / "output.zip"
        zip_path.write_bytes(b"PK")  # create the file so .exists() returns True

        job = _make_job(job_id="job-xyz", status="completed", output_zip=zip_path)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-xyz")

        assert resp.status_code == 200
        data = resp.json()
        assert data["download_url"] == "/api/jobs/job-xyz/download"

    def test_completed_no_zip_returns_none(self):
        """status=completed + output_zip is None → download_url is None (AC-3)."""
        job = _make_job(job_id="job-no-zip", status="completed", output_zip=None)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-no-zip")

        assert resp.status_code == 200
        data = resp.json()
        assert data["download_url"] is None

    def test_completed_zip_path_missing_on_disk(self, tmp_path):
        """status=completed + output_zip path set but file absent → download_url is None (AC-3)."""
        zip_path = tmp_path / "nonexistent.zip"
        # Do NOT create the file — .exists() will return False

        job = _make_job(job_id="job-missing", status="completed", output_zip=zip_path)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-missing")

        assert resp.status_code == 200
        data = resp.json()
        assert data["download_url"] is None

    def test_running_status_returns_none(self, tmp_path):
        """status=running, output_zip exists → download_url is None (AC-3)."""
        zip_path = tmp_path / "output.zip"
        zip_path.write_bytes(b"PK")

        job = _make_job(job_id="job-running", status="running", output_zip=zip_path,
                        processed_files=0)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-running")

        assert resp.status_code == 200
        data = resp.json()
        assert data["download_url"] is None

    def test_failed_status_returns_none(self, tmp_path):
        """status=failed, output_zip exists → download_url is None (AC-3)."""
        zip_path = tmp_path / "output.zip"
        zip_path.write_bytes(b"PK")

        job = _make_job(job_id="job-failed", status="failed", output_zip=zip_path,
                        processed_files=0)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-failed")

        assert resp.status_code == 200
        data = resp.json()
        assert data["download_url"] is None

    def test_stopped_status_returns_none(self, tmp_path):
        """status=stopped, output_zip exists → download_url is None (AC-3)."""
        zip_path = tmp_path / "output.zip"
        zip_path.write_bytes(b"PK")

        job = _make_job(job_id="job-stopped", status="stopped", output_zip=zip_path,
                        processed_files=0)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/job-stopped")

        assert resp.status_code == 200
        data = resp.json()
        assert data["download_url"] is None

    @pytest.mark.parametrize("status,zip_exists,expected_url", [
        ("queued",    False, None),
        ("queued",    True,  None),
        ("running",   False, None),
        ("running",   True,  None),
        ("stopped",   True,  None),
        ("failed",    True,  None),
        ("completed", False, None),
        ("completed", True,  "/api/jobs/param-job/download"),
    ])
    def test_derivation_parametrized(self, tmp_path, status, zip_exists, expected_url):
        """Parametrized sweep over all status × zip-state combinations (AC-2/AC-3)."""
        if zip_exists:
            zip_path = tmp_path / f"output_{status}.zip"
            zip_path.write_bytes(b"PK")
        else:
            zip_path = None

        job = _make_job(job_id="param-job", status=status, output_zip=zip_path,
                        processed_files=0)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/param-job")

        assert resp.status_code == 200
        data = resp.json()
        assert data["download_url"] == expected_url, (
            f"status={status!r}, zip_exists={zip_exists}: "
            f"expected {expected_url!r}, got {data['download_url']!r}"
        )


# ---------------------------------------------------------------------------
# TestJobStatusEndpoint
# ---------------------------------------------------------------------------

class TestJobStatusEndpoint:
    """Integration-style tests: GET /api/jobs/{id} payload carries correct download_url (AC-4)."""

    def test_get_job_status_completed_has_download_url(self, tmp_path):
        """Completed job with existing zip: JSON response includes correct download_url (AC-4)."""
        zip_path = tmp_path / "result.zip"
        zip_path.write_bytes(b"PK")

        job = _make_job(job_id="complete-job-1", status="completed", output_zip=zip_path)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/complete-job-1")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["job_id"] == "complete-job-1"
        assert payload["status"] == "completed"
        assert payload["output_ready"] is True
        assert payload["download_url"] == "/api/jobs/complete-job-1/download"

    def test_get_job_status_running_download_url_null(self, tmp_path):
        """Running job: JSON response has download_url == null (AC-4)."""
        job = _make_job(job_id="running-job-1", status="running", output_zip=None,
                        processed_files=0)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/running-job-1")

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["download_url"] is None


# ---------------------------------------------------------------------------
# TestDownloadEndpointUnchanged
# ---------------------------------------------------------------------------

class TestDownloadEndpointUnchanged:
    """Confirms AC-7: the download endpoint routes.py:339-350 is untouched and reachable."""

    def test_download_endpoint_still_returns_zip(self, tmp_path):
        """GET /api/jobs/{id}/download returns a response (not 500), confirming route is intact."""
        zip_path = tmp_path / "out.zip"
        zip_path.write_bytes(b"PK\x03\x04")

        job = _make_job(job_id="dl-job-1", status="completed", output_zip=zip_path)

        with patch("app.backend.api.routes.job_manager") as mock_jm:
            mock_jm.get_job.return_value = job
            client = _get_test_client()
            resp = client.get("/api/jobs/dl-job-1/download")

        # The download endpoint should return 200 (FileResponse) or 404 if not ready,
        # but must NOT return 500 (which would indicate the route is broken).
        assert resp.status_code != 500, (
            f"Download endpoint returned 500, indicating route may be broken: {resp.text}"
        )
        # Should be 200 (file served) since job has a real zip file on disk
        assert resp.status_code == 200
