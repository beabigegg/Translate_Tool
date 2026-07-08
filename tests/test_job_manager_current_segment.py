"""Integration tests for JobRecord.current_segment (translation-progress-detail-ui).

Anti-tautology pattern mirrors tests/test_orchestrator_judge.py: `_run_job` is a
nested closure inside `JobManager.create_job`; the widened status_callback and the
judge snapshot_cb/`_translate_fn` closures live INSIDE it, so these tests run the
REAL `create_job(...)` path with `process_files`/`QualityJudge` faked at the
boundary, then assert on the resulting JobRecord — never a stand-in for the wiring
itself (AC-6, AC-8, AC-9).
"""

from __future__ import annotations

import tempfile
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers (mirrors test_orchestrator_judge.py's harness)
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


def _run_job_with_process_files_side_effect(fake_process_files):
    """Run create_job with process_files faked; QE/judge disabled (critique-loop
    snapshot tests don't need them)."""
    from app.backend.services.job_manager import JobManager

    with tempfile.TemporaryDirectory() as tmp:
        fake_file = Path(tmp) / "document.docx"
        fake_file.write_bytes(b"fake content")
        route_group = _make_minimal_route_group(["en"])

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

    return job


def _run_job_with_judge_check(judge_mock, winning_provider=None):
    from app.backend.services.job_manager import JobManager

    with tempfile.TemporaryDirectory() as tmp:
        fake_file = Path(tmp) / "document.docx"
        fake_file.write_bytes(b"fake content")
        route_group = _make_minimal_route_group(["en"])

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
# AC-6: reference-assignment overhead (never a list/history)
# ---------------------------------------------------------------------------

def test_snapshot_capture_is_reference_assignment_negligible_overhead():
    """AC-6: job.current_segment is a single overwritten object, never a growing list."""
    from app.backend.services.job_manager import CurrentSegmentSnapshot

    def fake_process_files(*args, **kwargs):
        cb = kwargs.get("status_callback")
        hook = kwargs.get("post_translate_hook")
        if hook:
            hook([("block:0", "source", "translated")])
        if cb:
            for i in range(5):
                cb(f"msg {i}", CurrentSegmentSnapshot(stage="critique", source=f"s{i}", draft=f"d{i}"))
        return (1, 1, False, None, {"extracted": 0, "skipped": 0, "added": 0}, None)

    job = _run_job_with_process_files_side_effect(fake_process_files)

    assert not isinstance(job.current_segment, list), (
        "current_segment must never be a rolling history / list (AC-6, AC-8)"
    )
    assert job.current_segment is not None
    assert job.current_segment.source == "s4", "only the LAST write should survive"


# ---------------------------------------------------------------------------
# AC-8: overwritten, not appended, across successive calls
# ---------------------------------------------------------------------------

def test_current_segment_snapshot_overwritten_not_appended_across_calls():
    """AC-8: 3 successive widened-callback calls leave only the LAST snapshot."""
    from app.backend.services.job_manager import CurrentSegmentSnapshot

    def fake_process_files(*args, **kwargs):
        cb = kwargs.get("status_callback")
        hook = kwargs.get("post_translate_hook")
        if hook:
            hook([("block:0", "source", "translated")])
        if cb:
            cb("m1", CurrentSegmentSnapshot(stage="translate", source="A"))
            cb("m2", CurrentSegmentSnapshot(stage="critique", source="B"))
            cb("m3", CurrentSegmentSnapshot(stage="adopt", source="C"))
        return (1, 1, False, None, {"extracted": 0, "skipped": 0, "added": 0}, None)

    job = _run_job_with_process_files_side_effect(fake_process_files)

    assert job.current_segment.stage == "adopt"
    assert job.current_segment.source == "C"


# ---------------------------------------------------------------------------
# AC-1, AC-5 (pdf-stage-detail-snapshot): PDF path parity, end-to-end
# ---------------------------------------------------------------------------

def test_pdf_job_populates_current_segment_stage_translate_end_to_end():
    """AC-1, AC-5: real create_job() -> process_files() -> translate_pdf() runs
    for real (unlike the process_files-faking harness above); only
    translate_blocks_batch (the LLM call boundary) is mocked. Proves the
    orchestrator's .pdf branch and translate_pdf actually thread status_callback
    all the way through to job.current_segment, matching the Office parity
    already proven by test_snapshot_capture_is_reference_assignment_negligible_overhead
    et al. above.

    model_type="translation" bypasses the (network-calling) context-detection
    step; enable_term_extraction=False and QE_ENABLED/JUDGE_ENABLED disabled
    keep the run scoped to the translate stage under test (out of scope per
    test-plan.md).
    """
    from app.backend.services.job_manager import JobManager
    from app.backend.services.model_router import RouteGroup

    fixture_pdf = Path(__file__).parent / "fixtures" / "test.pdf"

    def fake_translate_blocks_batch(texts, tgt, src_lang, client, log=None, on_segment_done=None, **kwargs):
        results = []
        for text in texts:
            translated = f"[{tgt}] {text}"
            if on_segment_done is not None:
                on_segment_done(text, translated)
            results.append((True, translated))
        return results

    with tempfile.TemporaryDirectory() as tmp:
        fake_file = Path(tmp) / "sample.pdf"
        fake_file.write_bytes(fixture_pdf.read_bytes())
        route_group = RouteGroup(
            targets=["English"], model="test-model", profile_id="general", model_type="translation",
        )

        with patch("app.backend.processors.pdf_processor.translate_blocks_batch", side_effect=fake_translate_blocks_batch), \
             patch("app.backend.services.job_manager.QE_ENABLED", False), \
             patch("app.backend.services.job_manager.config.JUDGE_ENABLED", False):

            jm = JobManager()
            job = jm.create_job(
                uploaded_files=[fake_file],
                route_groups=[route_group],
                src_lang=None,
                include_headers=False,
                enable_term_extraction=False,
            )
            _wait_for_job(job)

    assert job.status == "completed", f"job did not complete: status={job.status} error={job.error}"
    assert job.current_segment is not None, "current_segment stayed null for the PDF job (the bug)"
    assert job.current_segment.stage == "translate"
    assert job.current_segment.source, "current_segment_source stayed empty/null"
    assert job.current_segment.draft, "current_segment_draft stayed empty/null"


# ---------------------------------------------------------------------------
# AC-9: judge snapshot written at BOTH the scoring and retranslating sub-steps
# ---------------------------------------------------------------------------

def test_judge_snapshot_written_onto_jobrecord_at_scoring_and_retranslating_substeps():
    """AC-9 wiring: job_manager's REAL snapshot_cb (scoring) and _translate_fn
    (retranslating) closures both write CurrentSegmentSnapshot onto JobRecord.

    A subclass spy on CurrentSegmentSnapshot observes BOTH writes in order without
    racing the background worker thread (a naive read of job.current_segment after
    the run only sees the LAST write, per the single-overwrite design)."""
    from app.backend.services.job_manager import CurrentSegmentSnapshot as _RealSnapshot

    captured = []

    class _SpySnapshot(_RealSnapshot):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            captured.append(self)

    fake_judge = MagicMock()
    fake_judge.translation_client.translate_once.return_value = (True, "re-mt")

    def run_loop(_jid, blocks, translate_fn, cancel_event=None, snapshot_cb=None):
        assert snapshot_cb is not None, "job_manager must pass a snapshot_cb into run_judge_loop"
        snapshot_cb("block:0", None, 1, "scoring")
        translate_fn("source", "needs improvement")
        return _make_fake_judge_result(_jid)

    fake_judge.run_judge_loop.side_effect = run_loop

    with patch("app.backend.services.job_manager.CurrentSegmentSnapshot", _SpySnapshot):
        job = _run_job_with_judge_check(fake_judge, winning_provider="panjit")

    assert job.judge is not None
    assert len(captured) == 2, f"expected exactly 2 snapshot writes, got {len(captured)}"

    scoring_seg, retranslate_seg = captured
    assert scoring_seg.stage == "judge"
    assert scoring_seg.judge_substep == "scoring"
    assert scoring_seg.judge_attempt == 1
    assert scoring_seg.source == "source"  # resolved from qe_blocks [("block:0", "source", "translated")]

    assert retranslate_seg.stage == "judge"
    assert retranslate_seg.judge_substep == "retranslating"
    assert retranslate_seg.judge_attempt == 1  # first retranslate call (_judge_retranslate_count)
    assert retranslate_seg.source == "source"
    assert retranslate_seg.draft == "translated"  # resolved via the src->mt lookup
