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


# ---------------------------------------------------------------------------
# AC-1 (office-output-mode): bilingual is now a valid enum value
# ---------------------------------------------------------------------------

def test_output_mode_enum_accepts_bilingual():
    """OutputMode enum must include BILINGUAL = 'bilingual'."""
    from app.backend.api.schemas import OutputMode

    assert hasattr(OutputMode, "BILINGUAL"), "OutputMode.BILINGUAL not found"
    assert OutputMode.BILINGUAL == "bilingual", f"Unexpected value: {OutputMode.BILINGUAL!r}"
    # Existing values still present
    assert OutputMode.APPEND == "append"
    assert OutputMode.REPLACE == "replace"


def test_post_jobs_accepts_output_mode_bilingual(client):
    """POST /api/jobs with output_mode=bilingual must return 200 (not 422)."""
    with patch.object(_routes, "job_manager") as mock_jm:
        mock_jm.create_job.side_effect = _fake_create_job
        resp = client.post(
            "/api/jobs",
            files=_upload_files(),
            data={**_base_data(), "output_mode": "bilingual"},
        )
    assert resp.status_code == 200, (
        f"Expected 200 but got {resp.status_code}; body: {resp.text}"
    )
    assert "job_id" in resp.json()


def test_openapi_bilingual_in_output_mode_enum():
    """contracts/api/openapi.yml must list all five output_mode values including bilingual,
    adjacent, and annotation."""
    import json
    from pathlib import Path

    repo_root = Path(__file__).parent.parent
    openapi_path = repo_root / "contracts" / "api" / "openapi.yml"

    assert openapi_path.exists(), f"openapi.yml not found at {openapi_path}"

    content = openapi_path.read_text()
    # The openapi.yml is JSON emitted by cdd-kit
    data = json.loads(content)

    # Find the output_mode property in the JobCreateRequest schema
    schemas = data.get("components", {}).get("schemas", {})
    job_req = schemas.get("JobCreateRequest", {})
    props = job_req.get("properties", {})
    om_prop = props.get("output_mode", {})
    enum_vals = om_prop.get("enum", [])

    for expected in ("append", "replace", "bilingual", "adjacent", "annotation"):
        assert expected in enum_vals, (
            f"'{expected}' not in output_mode enum in openapi.yml. Found: {enum_vals}"
        )


def test_post_jobs_accepts_output_mode_adjacent(client):
    """POST /api/jobs with output_mode=adjacent must return 200 (not 422)."""
    with patch.object(_routes, "job_manager") as mock_jm:
        mock_jm.create_job.side_effect = _fake_create_job
        resp = client.post(
            "/api/jobs",
            files=_upload_files(),
            data={**_base_data(), "output_mode": "adjacent"},
        )
    assert resp.status_code == 200, (
        f"Expected 200 but got {resp.status_code}; body: {resp.text}"
    )


def test_post_jobs_accepts_output_mode_annotation(client):
    """POST /api/jobs with output_mode=annotation must return 200 (not 422)."""
    with patch.object(_routes, "job_manager") as mock_jm:
        mock_jm.create_job.side_effect = _fake_create_job
        resp = client.post(
            "/api/jobs",
            files=_upload_files(),
            data={**_base_data(), "output_mode": "annotation"},
        )
    assert resp.status_code == 200, (
        f"Expected 200 but got {resp.status_code}; body: {resp.text}"
    )


def test_output_mode_enum_has_all_five_values():
    """OutputMode enum must have all five valid values."""
    from app.backend.api.schemas import OutputMode

    expected = {"append", "replace", "bilingual", "adjacent", "annotation"}
    actual = {m.value for m in OutputMode}
    assert expected == actual, f"OutputMode values mismatch: expected {expected}, got {actual}"
