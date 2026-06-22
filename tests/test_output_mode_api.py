"""Contract tests for output_mode Form field on POST /api/jobs.

AC-5: POST /api/jobs accepts "append" and "replace"; rejects invalid values with HTTP 422;
      defaults to "append" when omitted.

Pattern: mock at job_manager boundary only so that FastAPI/Pydantic Form validation
runs for real (no shortcut around the route handler).
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Capture the routes module object at collection time (before any test modifies
# sys.modules).  patch.object(_routes, ...) always targets M1 regardless of
# sys.modules contamination by other test modules (e.g. test_model_config_api).
import app.backend.api.routes as _routes


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Return a TestClient for the FastAPI app with job_manager mocked."""
    from app.backend.main import app

    with TestClient(app) as c:
        yield c


def _upload_files():
    """Return multipart files payload for POST /api/jobs."""
    return [("files", ("test.docx", io.BytesIO(b"PK\x03\x04"), "application/octet-stream"))]


def _base_data(**extra):
    """Return base form data with optional overrides."""
    data = {
        "targets": "Vietnamese",
        "src_lang": "auto",
        "include_headers": "false",
        "profile": "general",
        "mode": "translation",
        "enable_term_extraction": "false",
    }
    data.update(extra)
    return data


# ---------------------------------------------------------------------------
# Helper: patch job_manager.create_job so no real translation runs
# ---------------------------------------------------------------------------

def _fake_create_job(*args, **kwargs):
    return SimpleNamespace(job_id="test-job-id")


# ---------------------------------------------------------------------------
# AC-5 tests
# ---------------------------------------------------------------------------

def test_post_jobs_accepts_output_mode_append(client):
    """POST /api/jobs with output_mode=append must return 200 with a job_id."""
    with patch.object(_routes, "job_manager") as mock_jm:
        mock_jm.create_job.side_effect = _fake_create_job
        resp = client.post(
            "/api/jobs",
            files=_upload_files(),
            data={**_base_data(), "output_mode": "append"},
        )
    assert resp.status_code == 200, resp.text
    assert "job_id" in resp.json()


def test_post_jobs_accepts_output_mode_replace(client):
    """POST /api/jobs with output_mode=replace must return 200 with a job_id."""
    with patch.object(_routes, "job_manager") as mock_jm:
        mock_jm.create_job.side_effect = _fake_create_job
        resp = client.post(
            "/api/jobs",
            files=_upload_files(),
            data={**_base_data(), "output_mode": "replace"},
        )
    assert resp.status_code == 200, resp.text
    assert "job_id" in resp.json()


def test_post_jobs_rejects_invalid_output_mode_422(client):
    """POST /api/jobs with an invalid output_mode value must return HTTP 422."""
    with patch.object(_routes, "job_manager") as mock_jm:
        mock_jm.create_job.side_effect = _fake_create_job
        resp = client.post(
            "/api/jobs",
            files=_upload_files(),
            data={**_base_data(), "output_mode": "overwrite"},
        )
    assert resp.status_code == 422, resp.text


def test_post_jobs_output_mode_defaults_to_append(client):
    """POST /api/jobs without output_mode must succeed (default is append)."""
    captured: dict = {}

    def _capture_create_job(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(job_id="test-job-id")

    with patch.object(_routes, "job_manager") as mock_jm:
        mock_jm.create_job.side_effect = _capture_create_job
        resp = client.post(
            "/api/jobs",
            files=_upload_files(),
            data=_base_data(),
        )
    assert resp.status_code == 200, resp.text
    # output_mode forwarded to job_manager must be "append" (the default)
    assert captured.get("output_mode") == "append", f"Unexpected output_mode: {captured}"
