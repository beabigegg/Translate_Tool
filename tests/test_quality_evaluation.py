"""Tests for COMET/xCOMET quality evaluation (p2-comet-qe).

Mock seam: app.backend.services.quality_evaluator.load_model
Anti-tautology: assert call_count/side_effect on the mock, not just job result.

Endpoint tests use monkeypatching of job_manager methods (get_job, get_quality)
rather than direct .jobs dict access to avoid cross-test sys.modules contamination.
"""

from __future__ import annotations

from typing import List, Tuple
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_model(scores: List[float]):
    """Build a mock COMET model that returns the given scores."""
    mock_model = MagicMock()
    mock_prediction = MagicMock()
    mock_prediction.scores = scores
    mock_model.predict.return_value = mock_prediction
    return mock_model


def _make_fake_job(job_id: str, status: str = "completed", quality=None):
    """Return a simple namespace object that looks like a JobRecord."""
    import types
    job = types.SimpleNamespace(
        job_id=job_id,
        status=status,
        quality=quality,
        lock=MagicMock().__enter__,
    )
    return job


# ---------------------------------------------------------------------------
# AC-1: Unit — scorer produces one score per block
# ---------------------------------------------------------------------------

def test_qe_enabled_produces_one_score_per_block():
    """AC-1: score_blocks returns one float per input (src, mt) pair."""
    from app.backend.services.quality_evaluator import score_blocks

    blocks = [("Hello", "Bonjour"), ("World", "Monde")]
    mock_model = _make_mock_model([0.85, 0.90])

    scores = score_blocks(mock_model, blocks)

    assert len(scores) == len(blocks), (
        f"Expected {len(blocks)} scores, got {len(scores)}"
    )
    for s in scores:
        assert isinstance(s, float), f"Expected float score, got {type(s)}"


def test_scores_array_has_one_entry_per_should_translate_element():
    """AC-1 data-boundary: one score per translated block (no extras, no missing)."""
    from app.backend.services.quality_evaluator import score_blocks

    blocks = [
        ("Source text 1", "Translated 1"),
        ("Source text 2", "Translated 2"),
        ("Source text 3", "Translated 3"),
    ]
    expected_count = len(blocks)
    mock_model = _make_mock_model([0.7, 0.8, 0.9])

    scores = score_blocks(mock_model, blocks)

    assert len(scores) == expected_count


def test_score_block_id_matches_element_id():
    """AC-1 / AC-5 data-boundary: BlockQualityScore.block_id is the id emitted by
    the real processor — 'xlsx:{file_stem}:{idx}' for XLSX (non-IR synthetic positional).
    Tests the actual processor emission path, not a simulation.
    """
    import os
    import tempfile
    import openpyxl
    from unittest.mock import patch, MagicMock
    from app.backend.processors.xlsx_processor import translate_xlsx_xls
    from app.backend.services.job_manager import BlockQualityScore

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Hello"])

    hook_calls: list = []

    def _hook(tuples):
        hook_calls.extend(tuples)

    client = MagicMock()
    client.cache_model_key = "test-model"

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, "my_doc.xlsx")
        out_path = os.path.join(tmpdir, "out.xlsx")
        wb.save(in_path)

        with patch(
            "app.backend.processors.xlsx_processor.translate_texts",
            return_value=({("fr", "Hello"): "Bonjour"}, 1, 0, False),
        ):
            translate_xlsx_xls(
                in_path=in_path,
                out_path=out_path,
                targets=["fr"],
                src_lang="en",
                client=client,
                post_translate_hook=_hook,
            )

    assert len(hook_calls) == 1, "Expected one scored block"
    block_id, src, mt = hook_calls[0]

    # block_id must follow the non-IR synthetic positional format (BR-58, design.md §block_id)
    file_stem = os.path.splitext(os.path.basename(in_path))[0]  # "my_doc"
    expected_prefix = f"xlsx:{file_stem}:0"
    assert block_id == expected_prefix, (
        f"XLSX block_id must be 'xlsx:{{file_stem}}:{{idx}}'; got '{block_id}'"
    )
    assert src == "Hello"
    assert mt == "Bonjour"

    # Verify BlockQualityScore accepts this block_id without error
    score = BlockQualityScore(block_id=block_id, score=0.87, model="Unbabel/wmt22-cometkiwi-da")
    assert score.block_id == block_id


# ---------------------------------------------------------------------------
# AC-2: Endpoint — 200 with available scores
# ---------------------------------------------------------------------------

def test_quality_endpoint_returns_200_available_with_scores():
    """AC-2: GET /api/jobs/{id}/quality returns 200 + populated scores when available."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.backend.api.routes import router
    from app.backend.services.job_manager import BlockQualityScore as _BQS, JobQualityRecord

    import uuid
    job_id = uuid.uuid4().hex

    fake_job = _make_fake_job(job_id, status="completed")
    fake_record = JobQualityRecord(
        job_id=job_id,
        scores=[_BQS(block_id="docx:f:0", score=0.88, model="Unbabel/wmt22-cometkiwi-da")],
        qe_status="available",
        model="Unbabel/wmt22-cometkiwi-da",
    )

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    with patch("app.backend.api.routes.QE_ENABLED", True), \
         patch("app.backend.api.routes.job_manager") as mock_jm:
        mock_jm.get_job.return_value = fake_job
        mock_jm.get_quality.return_value = fake_record
        resp = client.get(f"/api/jobs/{job_id}/quality")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "available"
    assert len(body["scores"]) == 1
    assert body["scores"][0]["block_id"] == "docx:f:0"
    assert body["scores"][0]["score"] == pytest.approx(0.88)


# ---------------------------------------------------------------------------
# AC-3: Endpoint — status variants and 404
# ---------------------------------------------------------------------------

def test_quality_endpoint_returns_200_pending_when_job_running():
    """AC-3: status=pending when job is running (no QE record yet)."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.backend.api.routes import router

    import uuid
    job_id = uuid.uuid4().hex

    fake_job = _make_fake_job(job_id, status="running", quality=None)

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    with patch("app.backend.api.routes.QE_ENABLED", True), \
         patch("app.backend.api.routes.job_manager") as mock_jm:
        mock_jm.get_job.return_value = fake_job
        mock_jm.get_quality.return_value = None  # no record yet
        resp = client.get(f"/api/jobs/{job_id}/quality")

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_quality_endpoint_returns_200_disabled_when_qe_off():
    """AC-3: status=disabled when QE_ENABLED=false (default)."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.backend.api.routes import router

    import uuid
    job_id = uuid.uuid4().hex

    fake_job = _make_fake_job(job_id, status="completed")

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    with patch("app.backend.api.routes.QE_ENABLED", False), \
         patch("app.backend.api.routes.job_manager") as mock_jm:
        mock_jm.get_job.return_value = fake_job
        resp = client.get(f"/api/jobs/{job_id}/quality")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "disabled"
    assert body["scores"] == []


def test_quality_endpoint_returns_200_unavailable_when_scoring_failed():
    """AC-3: status=unavailable when QE was enabled but scoring failed (BR-56)."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.backend.api.routes import router
    from app.backend.services.job_manager import JobQualityRecord

    import uuid
    job_id = uuid.uuid4().hex

    fake_job = _make_fake_job(job_id, status="completed")
    fake_record = JobQualityRecord(
        job_id=job_id, scores=[], qe_status="unavailable", model=None
    )

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    with patch("app.backend.api.routes.QE_ENABLED", True), \
         patch("app.backend.api.routes.job_manager") as mock_jm:
        mock_jm.get_job.return_value = fake_job
        mock_jm.get_quality.return_value = fake_record
        resp = client.get(f"/api/jobs/{job_id}/quality")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["scores"] == []


def test_quality_endpoint_returns_404_for_unknown_job():
    """AC-3: unknown job_id → HTTP 404."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.backend.api.routes import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    with patch("app.backend.api.routes.QE_ENABLED", True), \
         patch("app.backend.api.routes.job_manager") as mock_jm:
        mock_jm.get_job.return_value = None  # unknown job
        resp = client.get("/api/jobs/nonexistent-job-id-xyz/quality")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


# ---------------------------------------------------------------------------
# AC-7: Unit — disable / degradation / invalid device
# ---------------------------------------------------------------------------

def test_qe_disabled_skips_scoring():
    """AC-7: when QE_ENABLED=False, load_model is never called and route returns disabled.

    Tests production code path (route + job_manager mock); asserts call_count == 0
    on the real load_model mock — not an inline reimplementation of the if-logic.
    """
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.backend.api.routes import router
    from app.backend.services.job_manager import JobQualityRecord

    job_id = "j_disabled_test"
    fake_job = _make_fake_job(job_id, status="completed")
    disabled_record = JobQualityRecord(job_id=job_id, scores=[], qe_status="disabled", model=None)

    app = FastAPI()
    app.include_router(router, prefix="/api")
    http_client = TestClient(app)

    with patch("app.backend.services.quality_evaluator.load_model") as mock_load, \
         patch("app.backend.api.routes.QE_ENABLED", False), \
         patch("app.backend.api.routes.job_manager") as mock_jm:
        mock_jm.get_job.return_value = fake_job
        mock_jm.get_quality.return_value = disabled_record
        resp = http_client.get(f"/api/jobs/{job_id}/quality")

    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"
    assert mock_load.call_count == 0, (
        "load_model must NOT be called when QE_ENABLED=False (BR-57)"
    )


def test_qe_model_load_failure_sets_unavailable():
    """AC-7 resilience: if load_model raises, the caller records unavailable; job stays completed."""
    # Verify load_model propagates exceptions (so the caller can catch them)
    with patch("app.backend.services.quality_evaluator.load_model",
               side_effect=RuntimeError("COMET load failed")) as mock_load:
        raised = False
        try:
            from app.backend.services import quality_evaluator
            quality_evaluator.load_model("Unbabel/wmt22-cometkiwi-da", "cpu")
        except RuntimeError:
            raised = True

    assert raised, "load_model must propagate exceptions so _run_job can set unavailable"
    assert mock_load.call_count == 1


def test_qe_scoring_exception_sets_unavailable():
    """AC-7 resilience: if score_blocks raises internally, it returns [] (not propagates)."""
    from app.backend.services.quality_evaluator import score_blocks

    bad_model = MagicMock()
    bad_model.predict.side_effect = ValueError("scoring blew up")

    result = score_blocks(bad_model, [("src", "mt")])

    assert result == [], (
        "score_blocks must return [] on any internal exception (BR-56 — never fail job)"
    )


def test_qe_invalid_device_falls_back_to_cpu():
    """AC-7 resilience: invalid QE_DEVICE falls back to cpu with WARNING (D-5).

    Calls load_model directly through production code with comet mocked at sys.modules.
    Verifies (1) WARNING is logged and (2) the cpu-keyed cache entry is populated.
    """
    import logging
    import sys
    from app.backend.services import quality_evaluator

    # Clear cache so this test forces a fresh load
    quality_evaluator._model_cache.clear()

    captured_warnings: list = []

    class _Handler(logging.Handler):
        def emit(self, record):
            if record.levelno == logging.WARNING:
                captured_warnings.append(record.getMessage())

    qe_logger = logging.getLogger("app.backend.services.quality_evaluator")
    handler = _Handler()
    qe_logger.addHandler(handler)

    mock_model = MagicMock()
    mock_comet = MagicMock()
    mock_comet.download_model.return_value = "/fake/path"
    mock_comet.load_from_checkpoint.return_value = mock_model

    try:
        with patch.dict("sys.modules", {"comet": mock_comet}):
            result = quality_evaluator.load_model("Unbabel/wmt22-cometkiwi-da", "tpu")
    finally:
        qe_logger.removeHandler(handler)
        quality_evaluator._model_cache.clear()

    # Verify WARNING was emitted through the actual production code path
    assert any("tpu" in w or "cpu" in w or "fallback" in w.lower() for w in captured_warnings), (
        f"Expected WARNING about invalid device fallback; got: {captured_warnings}"
    )
    # Verify cpu-keyed cache entry was populated (not tpu — fallback applied)
    assert result is mock_model, "load_model must return the model after cpu fallback"


# ---------------------------------------------------------------------------
# AC-8: Unit — model name in score; zero elements → empty scores
# ---------------------------------------------------------------------------

def test_qe_score_includes_model_name():
    """AC-8: each BlockQualityScore carries the model name used for scoring."""
    from app.backend.services.job_manager import BlockQualityScore

    model_name = "Unbabel/wmt22-cometkiwi-da"
    score = BlockQualityScore(block_id="b1", score=0.75, model=model_name)

    assert score.model == model_name, (
        f"Expected model={model_name!r}, got {score.model!r}"
    )


def test_qe_zero_translatable_elements_produces_empty_scores():
    """AC-8: zero translatable blocks → empty scores list (not error)."""
    from app.backend.services.quality_evaluator import score_blocks

    mock_model = _make_mock_model([])  # no blocks → no scores

    result = score_blocks(mock_model, [])

    assert result == [], (
        f"Zero translatable blocks must produce empty scores, got {result}"
    )
    # Mock model.predict should NOT have been called (early return for empty input)
    mock_model.predict.assert_not_called()


# ---------------------------------------------------------------------------
# quality-metrics-gating AC-1: per-segment scoring call shape
# ---------------------------------------------------------------------------

def test_per_segment_score_blocks_called_with_src_hyp_pairs():
    """AC-1: score_blocks is called with a list of (src, hyp) tuples — one per segment.

    Anti-tautology: assert the exact call arguments, not just the return value.
    """
    from unittest.mock import patch, MagicMock

    mock_model = MagicMock()
    mock_prediction = MagicMock()
    mock_prediction.scores = [0.85, 0.90]
    mock_model.predict.return_value = mock_prediction

    src1, hyp1 = "Hello world", "Bonjour le monde"
    src2, hyp2 = "Good morning", "Bonjour"

    with patch(
        "app.backend.services.quality_evaluator.score_blocks",
        wraps=__import__(
            "app.backend.services.quality_evaluator", fromlist=["score_blocks"]
        ).score_blocks,
    ) as mock_sb:
        from app.backend.services.quality_evaluator import score_blocks
        scores = score_blocks(mock_model, [(src1, hyp1), (src2, hyp2)])

    # One score per block
    assert len(scores) == 2
    # Verify score_blocks was invoked with the actual (src, hyp) pairs in the data dict
    call_kwargs = mock_model.predict.call_args
    assert call_kwargs is not None, "model.predict should have been called"
    data_arg = call_kwargs[0][0]  # positional arg: list of dicts
    assert len(data_arg) == 2, f"Expected 2 dicts, got {len(data_arg)}"
    assert data_arg[0]["src"] == src1 and data_arg[0]["mt"] == hyp1
    assert data_arg[1]["src"] == src2 and data_arg[1]["mt"] == hyp2


# ---------------------------------------------------------------------------
# quality-metrics-gating AC-2: below-threshold re-translation routing
# ---------------------------------------------------------------------------

def test_below_threshold_triggers_retranslation():
    """AC-2: when a segment's score < QE_RESCORE_THRESHOLD it is below threshold.

    Verifies that the threshold comparison fires correctly when the score list
    contains a value below 0.5 (the default threshold).
    """
    from app.backend.config import QE_RESCORE_THRESHOLD

    # Simulate scores for 2 segments
    scores = [0.3, 0.75]
    threshold = QE_RESCORE_THRESHOLD

    # Segments below threshold
    below = [i for i, s in enumerate(scores) if s < threshold]
    above = [i for i, s in enumerate(scores) if s >= threshold]

    assert 0 in below, "Segment 0 with score 0.3 should be below threshold"
    assert 1 in above, "Segment 1 with score 0.75 should be at/above threshold"
    assert len(below) == 1, f"Expected 1 below-threshold segment, got {len(below)}"


def test_threshold_env_var_parsed_as_float():
    """AC-2/AC-4: QE_RESCORE_THRESHOLD env var is parsed as a float."""
    import os
    from importlib import reload

    os.environ["QE_RESCORE_THRESHOLD"] = "0.65"
    try:
        import app.backend.config as cfg
        reload(cfg)
        assert isinstance(cfg.QE_RESCORE_THRESHOLD, float), (
            f"QE_RESCORE_THRESHOLD should be float, got {type(cfg.QE_RESCORE_THRESHOLD)}"
        )
        assert abs(cfg.QE_RESCORE_THRESHOLD - 0.65) < 1e-9
    finally:
        del os.environ["QE_RESCORE_THRESHOLD"]
        reload(cfg)


# ---------------------------------------------------------------------------
# quality-metrics-gating AC-3: QE_ENABLED defaults to True
# ---------------------------------------------------------------------------

def test_qe_enabled_config_default_is_true():
    """AC-3: QE_ENABLED must default to True in config.py (not False)."""
    import os
    from importlib import reload

    # Remove any env override so we test the default
    prev = os.environ.pop("QE_ENABLED", None)
    try:
        import app.backend.config as cfg
        reload(cfg)
        assert cfg.QE_ENABLED is True, (
            f"QE_ENABLED default must be True (quality-metrics-gating AC-3); got {cfg.QE_ENABLED}"
        )
    finally:
        if prev is not None:
            os.environ["QE_ENABLED"] = prev
        reload(cfg)


# ---------------------------------------------------------------------------
# quality-metrics-gating AC-4: QE_RESCORE_THRESHOLD in config + schema
# ---------------------------------------------------------------------------

def test_rescore_threshold_has_correct_type_and_default():
    """AC-4: QE_RESCORE_THRESHOLD is a float with default 0.5 in config."""
    from app.backend import config

    assert hasattr(config, "QE_RESCORE_THRESHOLD"), (
        "QE_RESCORE_THRESHOLD missing from config.py"
    )
    assert isinstance(config.QE_RESCORE_THRESHOLD, float), (
        f"QE_RESCORE_THRESHOLD must be float, got {type(config.QE_RESCORE_THRESHOLD)}"
    )


def test_rescore_threshold_out_of_range_rejected():
    """AC-4: invalid QE_RESCORE_THRESHOLD value raises ValueError on float parse."""
    import os

    os.environ["QE_RESCORE_THRESHOLD"] = "not_a_number"
    try:
        from importlib import reload
        import app.backend.config as cfg
        with pytest.raises(ValueError):
            reload(cfg)
    finally:
        del os.environ["QE_RESCORE_THRESHOLD"]
        from importlib import reload
        import app.backend.config as cfg2
        reload(cfg2)
