"""Contract tests for GET /jobs/{id}/judge and POST /jobs/{id}/judge/apply (p3-llm-judge).

Mirrors test_quality_evaluation.py pattern (monkeypatch job_manager, TestClient).
"""

from __future__ import annotations

import threading
import types
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_judge_result(
    job_id: str,
    judge_status: str = "available",
    score: Optional[str] = "高",
    feedback: str = "Good translation",
    attempts: int = 1,
    model: str = "gemma3",
    retranslated_blocks=None,
):
    """Build a fake JudgeResult namespace."""
    return types.SimpleNamespace(
        job_id=job_id,
        judge_status=judge_status,
        score=score,
        source_text="Source text",
        translated_text="Translated text",
        feedback=feedback,
        attempts=attempts,
        model=model,
        retranslated_blocks=retranslated_blocks,
    )


def _make_fake_job(
    job_id: str,
    status: str = "completed",
    judge=None,
    judge_apply_status=None,
    input_dir_exists: bool = True,
):
    """Return a minimal object that looks like JobRecord."""
    import tempfile

    _tmp = tempfile.mkdtemp()
    _input = Path(_tmp) / "input"
    _input.mkdir(parents=True, exist_ok=True)
    if not input_dir_exists:
        import shutil
        shutil.rmtree(_tmp, ignore_errors=True)

    job = types.SimpleNamespace(
        job_id=job_id,
        status=status,
        judge=judge,
        judge_apply_status=judge_apply_status,
        input_dir=_input,
        lock=threading.Lock(),
    )
    return job


def _get_client():
    from app.backend.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}/judge — response shape tests
# ---------------------------------------------------------------------------

def test_get_judge_available_response_shape():
    """GET /judge returns all fields when judge_status=available."""
    job_id = "test-judge-avail"
    judge_result = _make_judge_result(job_id, judge_status="available", score="高", attempts=1)
    fake_job = _make_fake_job(job_id, status="completed", judge=judge_result)

    with patch("app.backend.api.routes.job_manager.get_job", return_value=fake_job), \
         patch("app.backend.api.routes.JUDGE_ENABLED", True):
        client = _get_client()
        resp = client.get(f"/api/jobs/{job_id}/judge")

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == job_id
    assert body["judge_status"] == "available"
    assert body["score"] == "高"
    assert body["feedback"] == "Good translation"
    assert body["attempts"] == 1
    assert body["model"] == "gemma3"


def test_get_judge_disabled_response_shape():
    """GET /judge returns judge_status=disabled when JUDGE_ENABLED=False."""
    job_id = "test-judge-disabled"
    fake_job = _make_fake_job(job_id)

    with patch("app.backend.api.routes.job_manager.get_job", return_value=fake_job), \
         patch("app.backend.api.routes.JUDGE_ENABLED", False):
        client = _get_client()
        resp = client.get(f"/api/jobs/{job_id}/judge")

    assert resp.status_code == 200
    body = resp.json()
    assert body["judge_status"] == "disabled"
    assert body["score"] is None


def test_get_judge_unavailable_response_shape():
    """GET /judge returns judge_status=unavailable when judge is None."""
    job_id = "test-judge-unavail"
    fake_job = _make_fake_job(job_id, judge=None)

    with patch("app.backend.api.routes.job_manager.get_job", return_value=fake_job), \
         patch("app.backend.api.routes.JUDGE_ENABLED", True):
        client = _get_client()
        resp = client.get(f"/api/jobs/{job_id}/judge")

    assert resp.status_code == 200
    body = resp.json()
    assert body["judge_status"] == "unavailable"
    assert body["score"] is None


def test_get_judge_unknown_job_returns_404():
    """GET /judge with unknown job_id → 404."""
    with patch("app.backend.api.routes.job_manager.get_job", return_value=None):
        client = _get_client()
        resp = client.get("/api/jobs/nonexistent-job/judge")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/jobs/{id}/judge/apply — precondition + 202 tests
# ---------------------------------------------------------------------------

def test_post_apply_202_when_preconditions_pass():
    """POST /judge/apply returns 202 when all preconditions pass."""
    job_id = "test-apply-ok"
    judge_result = _make_judge_result(
        job_id,
        judge_status="available",
        score="中",
        retranslated_blocks={"block:0": "re-translated text"},
    )
    fake_job = _make_fake_job(
        job_id,
        status="completed",
        judge=judge_result,
        judge_apply_status=None,
        input_dir_exists=True,
    )

    with patch("app.backend.api.routes.job_manager.get_job", return_value=fake_job), \
         patch("app.backend.api.routes.job_manager.apply_judge") as mock_apply, \
         patch("app.backend.api.routes.JUDGE_ENABLED", True):
        client = _get_client()
        resp = client.post(f"/api/jobs/{job_id}/judge/apply")

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "applying"
    mock_apply.assert_called_once_with(job_id)


def test_post_apply_409_job_not_completed():
    """POST /judge/apply → 409 when job status ≠ completed (BR-76)."""
    job_id = "test-apply-not-completed"
    judge_result = _make_judge_result(
        job_id,
        judge_status="available",
        score="中",
        retranslated_blocks={"block:0": "re-translated"},
    )
    fake_job = _make_fake_job(
        job_id,
        status="running",  # Not completed
        judge=judge_result,
        judge_apply_status=None,
    )

    with patch("app.backend.api.routes.job_manager.get_job", return_value=fake_job), \
         patch("app.backend.api.routes.JUDGE_ENABLED", True):
        client = _get_client()
        resp = client.post(f"/api/jobs/{job_id}/judge/apply")

    assert resp.status_code == 409


def test_post_apply_409_judge_not_available():
    """POST /judge/apply → 409 when judge_status ≠ available (BR-76)."""
    job_id = "test-apply-unavail"
    judge_result = _make_judge_result(
        job_id,
        judge_status="unavailable",
        score=None,
    )
    fake_job = _make_fake_job(
        job_id,
        status="completed",
        judge=judge_result,
    )

    with patch("app.backend.api.routes.job_manager.get_job", return_value=fake_job), \
         patch("app.backend.api.routes.JUDGE_ENABLED", True):
        client = _get_client()
        resp = client.post(f"/api/jobs/{job_id}/judge/apply")

    assert resp.status_code == 409


def test_post_apply_409_retranslated_blocks_empty():
    """POST /judge/apply → 409 when retranslated_blocks is empty/None (BR-76)."""
    job_id = "test-apply-empty-blocks"
    # Score 高 → no retranslated_blocks
    judge_result = _make_judge_result(
        job_id,
        judge_status="available",
        score="高",
        retranslated_blocks=None,  # Empty because score was 高
    )
    fake_job = _make_fake_job(
        job_id,
        status="completed",
        judge=judge_result,
    )

    with patch("app.backend.api.routes.job_manager.get_job", return_value=fake_job), \
         patch("app.backend.api.routes.JUDGE_ENABLED", True):
        client = _get_client()
        resp = client.post(f"/api/jobs/{job_id}/judge/apply")

    assert resp.status_code == 409


def test_post_apply_409_source_evicted():
    """POST /judge/apply → 409 when source input_dir is gone (evicted) (BR-76)."""
    job_id = "test-apply-evicted"
    judge_result = _make_judge_result(
        job_id,
        judge_status="available",
        score="低",
        retranslated_blocks={"block:0": "re-translated"},
    )
    fake_job = _make_fake_job(
        job_id,
        status="completed",
        judge=judge_result,
        input_dir_exists=False,  # Evicted
    )

    with patch("app.backend.api.routes.job_manager.get_job", return_value=fake_job), \
         patch("app.backend.api.routes.JUDGE_ENABLED", True):
        client = _get_client()
        resp = client.post(f"/api/jobs/{job_id}/judge/apply")

    assert resp.status_code == 409


def test_post_apply_idempotent_while_applying():
    """POST /judge/apply returns 202 without spawning duplicate worker when already applying (BR-77)."""
    job_id = "test-apply-idempotent"
    judge_result = _make_judge_result(
        job_id,
        judge_status="available",
        score="低",
        retranslated_blocks={"block:0": "re-translated"},
    )
    fake_job = _make_fake_job(
        job_id,
        status="completed",
        judge=judge_result,
        judge_apply_status="applying",  # Already in progress
    )

    with patch("app.backend.api.routes.job_manager.get_job", return_value=fake_job), \
         patch("app.backend.api.routes.job_manager.apply_judge") as mock_apply, \
         patch("app.backend.api.routes.JUDGE_ENABLED", True):
        client = _get_client()
        resp = client.post(f"/api/jobs/{job_id}/judge/apply")

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "applying"
    # No second worker should be dispatched
    mock_apply.assert_not_called()
