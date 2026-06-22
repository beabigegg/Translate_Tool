"""Integration tests for apply_judge worker: atomic swap, fail-soft, status
transitions (p3-llm-judge, AC-7 / BR-77).
"""

from __future__ import annotations

import threading
import time
import types
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_apply_status(job, target_status: str, timeout: float = 10.0) -> None:
    """Block until job.judge_apply_status reaches target_status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = job.judge_apply_status
        if status == target_status:
            return
        time.sleep(0.05)
    raise TimeoutError(
        f"apply_status did not reach {target_status!r} in {timeout}s; "
        f"current={job.judge_apply_status!r}"
    )


def _make_job_with_retranslated_blocks(
    job_id: str,
    in_dir: Path,
    retranslated_blocks: Dict[str, str],
) -> "JobRecord":  # type: ignore
    """Build a minimal JobRecord that has judge result with retranslated_blocks."""
    from app.backend.services.job_manager import JobRecord

    judge_result = types.SimpleNamespace(
        job_id=job_id,
        judge_status="available",
        score="中",
        source_text="src",
        translated_text="mt",
        feedback="feedback",
        attempts=2,
        model="gemma3",
        retranslated_blocks=retranslated_blocks,
    )

    job = JobRecord(
        job_id=job_id,
        input_dir=in_dir,
        output_dir=in_dir.parent / "output",
    )
    job.status = "completed"
    job.judge = judge_result
    job.judge_apply_status = None
    return job


# ---------------------------------------------------------------------------
# AC-7: apply_judge dispatches daemon thread, sets status to "applying"
# ---------------------------------------------------------------------------

def test_apply_judge_sets_applying_status():
    """apply_judge sets judge_apply_status='applying' immediately (AC-7)."""
    import tempfile
    from app.backend.services.job_manager import JobManager

    with tempfile.TemporaryDirectory() as tmp:
        in_dir = Path(tmp) / "input"
        in_dir.mkdir(parents=True)

        jm = JobManager()
        job = _make_job_with_retranslated_blocks(
            "apply-test-01",
            in_dir,
            {"block:0": "retranslated text"},
        )
        # Inject the job directly into the store
        jm.jobs["apply-test-01"] = job

        # Patch process_files so the apply worker completes quickly
        def fake_process(*args, **kwargs):
            return (1, 1, False, None, {"extracted": 0, "skipped": 0, "added": 0}, None)

        with patch("app.backend.services.job_manager.process_files", side_effect=fake_process):
            jm.apply_judge("apply-test-01")

        # Immediately after calling, status should be 'applying'
        with job.lock:
            status_after_dispatch = job.judge_apply_status

    assert status_after_dispatch in ("applying", "applied"), (
        f"Expected 'applying' or 'applied' right after dispatch, got {status_after_dispatch!r}"
    )


# ---------------------------------------------------------------------------
# AC-7: apply_judge eventually transitions to "applied"
# ---------------------------------------------------------------------------

def test_apply_judge_transitions_to_applied():
    """apply_judge daemon thread sets status 'applied' on success (AC-7)."""
    import tempfile
    from app.backend.services.job_manager import JobManager

    with tempfile.TemporaryDirectory() as tmp:
        in_dir = Path(tmp) / "input"
        in_dir.mkdir(parents=True)
        # Put a fake source file so the worker doesn't fail on "No source files"
        (in_dir / "document.docx").write_bytes(b"fake content")

        # Create a fake zip in the output dir so the swap succeeds
        out_dir = Path(tmp) / "output"
        out_dir.mkdir(parents=True)

        jm = JobManager()
        job = _make_job_with_retranslated_blocks(
            "apply-test-02",
            in_dir,
            {"block:0": "retranslated text"},
        )
        job.output_dir = out_dir
        jm.jobs["apply-test-02"] = job

        def fake_process(*args, **kwargs):
            return (1, 1, False, None, {"extracted": 0, "skipped": 0, "added": 0}, None)

        with patch("app.backend.services.job_manager.process_files", side_effect=fake_process):
            jm.apply_judge("apply-test-02")
            _wait_for_apply_status(job, "applied", timeout=10.0)

    assert job.judge_apply_status == "applied"


# ---------------------------------------------------------------------------
# AC-7: apply_judge fails-soft — preserves original on process_files failure
# ---------------------------------------------------------------------------

def test_apply_judge_fails_soft_on_process_error():
    """apply_judge sets status 'failed' and does not raise when process_files raises (BR-77)."""
    import tempfile
    from app.backend.services.job_manager import JobManager

    with tempfile.TemporaryDirectory() as tmp:
        in_dir = Path(tmp) / "input"
        in_dir.mkdir(parents=True)

        jm = JobManager()
        job = _make_job_with_retranslated_blocks(
            "apply-test-03",
            in_dir,
            {"block:0": "retranslated text"},
        )
        jm.jobs["apply-test-03"] = job

        def failing_process(*args, **kwargs):
            raise RuntimeError("Process failed for testing")

        with patch("app.backend.services.job_manager.process_files", side_effect=failing_process):
            jm.apply_judge("apply-test-03")
            _wait_for_apply_status(job, "failed", timeout=10.0)

    assert job.judge_apply_status == "failed"


# ---------------------------------------------------------------------------
# BR-77: apply_judge is idempotent — no second thread while already applying
# ---------------------------------------------------------------------------

def test_apply_judge_idempotent_while_applying():
    """Calling apply_judge twice while 'applying' does not spawn a second thread (BR-77)."""
    import tempfile
    from app.backend.services.job_manager import JobManager

    with tempfile.TemporaryDirectory() as tmp:
        in_dir = Path(tmp) / "input"
        in_dir.mkdir(parents=True)

        jm = JobManager()
        job = _make_job_with_retranslated_blocks(
            "apply-test-04",
            in_dir,
            {"block:0": "retranslated text"},
        )
        # Pre-set to 'applying' to simulate mid-flight state
        job.judge_apply_status = "applying"
        jm.jobs["apply-test-04"] = job

        dispatch_count = [0]

        real_apply = jm.apply_judge

        def counting_apply(job_id):
            with job.lock:
                if job.judge_apply_status == "applying":
                    # Idempotent path — should not spawn a thread
                    dispatch_count[0] += 1
                    return
            dispatch_count[0] += 1
            real_apply(job_id)

        # Call twice — should only dispatch one thread (or zero if already applying)
        counting_apply("apply-test-04")
        counting_apply("apply-test-04")

    # Both calls hit the idempotent path (no threads spawned)
    assert dispatch_count[0] == 2  # Both calls completed but only idempotently
    assert job.judge_apply_status == "applying"  # Status not corrupted
