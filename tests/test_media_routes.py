"""Tests for media (STT + translation) FastAPI routes.

Mock boundary: app.backend.api.media_routes.media_job_manager (module-level
singleton) — the real STT/translation pipeline is never invoked. Follows the
job-manager-mocking convention in tests/test_providers_api.py (patch.object
against the module captured at collection time) and the fake-job-with-real-
lock convention in tests/test_quality_evaluation.py.
"""

from __future__ import annotations

import io
import threading
import time
import types
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Capture the module at collection time so patch.object always targets M1
# regardless of sys.modules / parent-package-attribute contamination by other tests.
import app.backend.api.media_routes as _media_routes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(_media_routes.router)
    return TestClient(app)


def _make_fake_job(
    job_id: str = "job-1",
    status: str = "queued",
    stage: str = "queued",
    error=None,
    transcript=None,
    output_txt_path=None,
):
    """SimpleNamespace standing in for MediaJobRecord, with a real Lock so
    `with job.lock:` in the route bodies works without extra mock plumbing."""
    return types.SimpleNamespace(
        job_id=job_id,
        status=status,
        stage=stage,
        error=error,
        transcript=transcript,
        output_txt_path=output_txt_path,
        created_at=time.time(),
        updated_at=time.time(),
        lock=threading.Lock(),
    )


# ===========================================================================
# POST /api/media/jobs
# ===========================================================================

class TestCreateMediaJob:

    def test_happy_path_returns_200_and_job_id(self):
        client = _make_client()
        fake_job = _make_fake_job(job_id="new-job-1")

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.create_job.return_value = fake_job
            resp = client.post(
                "/api/media/jobs",
                data={"targets": "en,fr"},
                files={"file": ("clip.mp3", io.BytesIO(b"fake audio bytes"), "audio/mpeg")},
            )

        assert resp.status_code == 200
        assert resp.json() == {"job_id": "new-job-1"}
        assert mock_jm.create_job.call_count == 1
        _, kwargs = mock_jm.create_job.call_args
        assert kwargs["targets"] == ["en", "fr"]
        assert kwargs["denoise"] is True

    def test_upload_exceeding_max_size_returns_413(self):
        client = _make_client()

        with patch.object(_media_routes, "_MEDIA_MAX_UPLOAD_BYTES", 10), \
             patch.object(_media_routes, "media_job_manager") as mock_jm:
            resp = client.post(
                "/api/media/jobs",
                data={"targets": "en"},
                files={"file": ("clip.mp3", io.BytesIO(b"x" * 100), "audio/mpeg")},
            )

        assert resp.status_code == 413
        mock_jm.create_job.assert_not_called()


# ===========================================================================
# GET /api/media/jobs/{job_id}
# ===========================================================================

class TestMediaJobStatus:

    def test_unknown_job_returns_404(self):
        client = _make_client()

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.get_job.return_value = None
            resp = client.get("/api/media/jobs/does-not-exist")

        assert resp.status_code == 404

    def test_known_job_returns_status_fields(self):
        client = _make_client()
        fake_job = _make_fake_job(job_id="abc", status="running", stage="transcribing")

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.get_job.return_value = fake_job
            resp = client.get("/api/media/jobs/abc")

        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "abc"
        assert body["status"] == "running"
        assert body["stage"] == "transcribing"


# ===========================================================================
# GET /api/media/jobs/{job_id}/transcript
# ===========================================================================

class TestMediaJobTranscript:

    def test_unknown_job_returns_404(self):
        client = _make_client()

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.get_job.return_value = None
            resp = client.get("/api/media/jobs/does-not-exist/transcript")

        assert resp.status_code == 404

    def test_not_yet_completed_returns_409(self):
        client = _make_client()
        fake_job = _make_fake_job(job_id="abc", status="running")

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.get_job.return_value = fake_job
            resp = client.get("/api/media/jobs/abc/transcript")

        assert resp.status_code == 409

    def test_completed_returns_segments(self):
        from app.backend.models.media_transcript import MediaTranscript, TranscriptSegment

        transcript = MediaTranscript(
            duration=12.5,
            segments=[
                TranscriptSegment(
                    start=0.0, end=1.5, text="Hello",
                    language="en", translated_text={"fr": "Bonjour"},
                )
            ],
        )
        fake_job = _make_fake_job(job_id="abc", status="completed", transcript=transcript)
        client = _make_client()

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.get_job.return_value = fake_job
            resp = client.get("/api/media/jobs/abc/transcript")

        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "abc"
        assert body["duration"] == pytest.approx(12.5)
        assert len(body["segments"]) == 1
        seg = body["segments"][0]
        assert seg["text"] == "Hello"
        assert seg["language"] == "en"
        assert seg["translated_text"] == {"fr": "Bonjour"}


# ===========================================================================
# GET /api/media/jobs/{job_id}/download
# ===========================================================================

class TestMediaJobDownload:

    def test_unknown_job_returns_404(self):
        client = _make_client()

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.get_job.return_value = None
            resp = client.get("/api/media/jobs/does-not-exist/download")

        assert resp.status_code == 404

    def test_output_not_ready_returns_404(self):
        fake_job = _make_fake_job(job_id="abc", status="running", output_txt_path=None)
        client = _make_client()

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.get_job.return_value = fake_job
            resp = client.get("/api/media/jobs/abc/download")

        assert resp.status_code == 404

    def test_completed_returns_file_with_correct_content_type_and_filename(self, tmp_path):
        out_path = tmp_path / "clip_bilingual.txt"
        out_path.write_text("hello\nbonjour\n", encoding="utf-8")
        fake_job = _make_fake_job(job_id="abc", status="completed", output_txt_path=out_path)
        client = _make_client()

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.get_job.return_value = fake_job
            resp = client.get("/api/media/jobs/abc/download")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert "clip_bilingual.txt" in resp.headers.get("content-disposition", "")
        assert resp.text == "hello\nbonjour\n"


# ===========================================================================
# POST /api/media/jobs/{job_id}/cancel
# ===========================================================================

class TestMediaJobCancel:

    def test_unknown_job_returns_404(self):
        client = _make_client()

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.cancel_job.return_value = False
            resp = client.post("/api/media/jobs/does-not-exist/cancel")

        assert resp.status_code == 404

    def test_known_job_returns_cancelled_status(self):
        client = _make_client()

        with patch.object(_media_routes, "media_job_manager") as mock_jm:
            mock_jm.cancel_job.return_value = True
            resp = client.post("/api/media/jobs/abc/cancel")

        assert resp.status_code == 200
        assert resp.json() == {"status": "cancelled"}
        mock_jm.cancel_job.assert_called_once_with("abc")
