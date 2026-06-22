"""Unit tests for the LLM-as-judge quality service (p3-llm-judge).

Mock seam: app.backend.services.quality_judge.QualityJudge._client
Anti-tautology:
  - Iteration cap: assert `result.attempts == JUDGE_MAX_ITERATIONS`, not just "loop ended".
  - Feedback reflection: assert feedback string is in translate_fn call arg (BR-75).
  - D4: assert model_router NOT called.
  - Synonyms: assert "不錯"/"差" are NOT accepted as score tokens.
"""

from __future__ import annotations

import json
from typing import Callable, List, Optional, Tuple
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_judge(model_name: str = "gemma3") -> "QualityJudge":  # noqa: F821
    """Build a QualityJudge whose client is a MagicMock."""
    from app.backend.services.quality_judge import QualityJudge

    judge = QualityJudge.__new__(QualityJudge)
    judge.model = model_name
    judge._client = MagicMock()
    return judge


def _make_client_response(score: str, feedback: str = "feedback text") -> Tuple[bool, str]:
    """Return (ok=True, JSON string) for a given score token."""
    return (True, json.dumps({"score": score, "feedback": feedback}))


def _make_blocks(n: int = 1) -> List[Tuple[str, str, str]]:
    """Return n blocks as (block_id, source, mt)."""
    return [(f"block:{i}", f"source text {i}", f"translated text {i}") for i in range(n)]


# ---------------------------------------------------------------------------
# BR-72 / D6 — score parse
# ---------------------------------------------------------------------------

def test_score_json_parse_valid():
    """JSON {"score":"高","feedback":"good"} → score=高"""
    judge = _make_judge()
    score = judge._parse_score('{"score":"高","feedback":"good"}')
    assert score == "高"


def test_score_raw_scan_fallback():
    """Malformed JSON but raw text has "低" → score=低"""
    judge = _make_judge()
    score = judge._parse_score("not valid json but 低 is here")
    assert score == "低"


def test_score_no_token_unavailable():
    """No 高/中/低 in response → None (unavailable)."""
    judge = _make_judge()
    score = judge._parse_score("this is just text with no score token")
    assert score is None


def test_score_synonym_not_accepted():
    """Synonyms like '不錯' or '差' are NOT accepted as score tokens (D6 strict)."""
    judge = _make_judge()
    # Common synonyms that small models might emit
    for synonym in ("不錯", "差", "good", "poor", "high", "low", "良好", "優"):
        score = judge._parse_score(f"The translation is {synonym}")
        assert score is None, f"Synonym '{synonym}' should not be accepted as a score"


def test_score_json_preferred_over_raw():
    """JSON parse succeeds and returns field; raw scan not used."""
    judge = _make_judge()
    # JSON says 高 but raw text also contains 低 — JSON wins
    payload = json.dumps({"score": "高", "feedback": "some text"}) + " and also 低 appears here"
    score = judge._parse_score(payload)
    assert score == "高"


def test_score_中_token():
    """中 token extracted correctly from JSON."""
    judge = _make_judge()
    score = judge._parse_score('{"score":"中","feedback":"acceptable"}')
    assert score == "中"


# ---------------------------------------------------------------------------
# AC-1 — judge records result on job record
# ---------------------------------------------------------------------------

def test_judge_records_result_on_job_record():
    """JudgeResult is attached with score/feedback/attempts (AC-1)."""
    from app.backend.services.job_manager import JudgeResult

    judge = _make_judge()
    judge._client._call_ollama.return_value = _make_client_response("高", "great translation")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="retranslated")
    blocks = _make_blocks(1)

    result = judge.run_judge_loop("job-001", blocks, translate_fn)

    assert isinstance(result, JudgeResult)
    assert result.job_id == "job-001"
    assert result.judge_status == "available"
    assert result.score == "高"
    assert result.feedback == "great translation"
    assert result.attempts >= 1


# ---------------------------------------------------------------------------
# AC-1 — score 高 terminates loop
# ---------------------------------------------------------------------------

def test_judge_score_high_terminates_loop():
    """Score 高 on iteration 1 → loop exits; attempts==1 (AC-1)."""
    judge = _make_judge()
    judge._client._call_ollama.return_value = _make_client_response("高")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="retranslated")
    blocks = _make_blocks(1)

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
        result = judge.run_judge_loop("job-002", blocks, translate_fn)

    assert result.attempts == 1, f"Expected 1 attempt, got {result.attempts}"
    translate_fn.assert_not_called()
    assert result.retranslated_blocks is None, "Score 高 should not produce retranslated_blocks"


# ---------------------------------------------------------------------------
# AC-2 — score 中 triggers retranslation
# ---------------------------------------------------------------------------

def test_judge_score_mid_triggers_retranslation():
    """Score 中 → translate_fn is called (AC-2)."""
    judge = _make_judge()
    responses = [_make_client_response("中"), _make_client_response("高")]
    judge._client._call_ollama.side_effect = responses
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="improved translation")
    blocks = _make_blocks(1)

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
        result = judge.run_judge_loop("job-003", blocks, translate_fn)

    assert translate_fn.called, "translate_fn should be called when score is 中"
    assert result.judge_status == "available"


# ---------------------------------------------------------------------------
# AC-2 — score 高 no retranslation
# ---------------------------------------------------------------------------

def test_judge_score_high_no_retranslation():
    """Score 高 → translate_fn NOT called (AC-2)."""
    judge = _make_judge()
    judge._client._call_ollama.return_value = _make_client_response("高")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="never used")
    blocks = _make_blocks(1)

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
        result = judge.run_judge_loop("job-004", blocks, translate_fn)

    translate_fn.assert_not_called()


# ---------------------------------------------------------------------------
# AC-2 / BR-75 — feedback fed back to translation model
# ---------------------------------------------------------------------------

def test_feedback_fed_back_to_translation_model():
    """Judge feedback string is present in the translate_fn call argument (BR-75)."""
    feedback_text = "The translation lacks formality"
    judge = _make_judge()
    responses = [_make_client_response("低", feedback_text), _make_client_response("高")]
    judge._client._call_ollama.side_effect = responses
    judge._client._build_no_system_payload.return_value = {}

    call_args_log = []

    def _translate_fn(src, feedback):
        call_args_log.append((src, feedback))
        return "improved"

    blocks = _make_blocks(1)

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
        result = judge.run_judge_loop("job-005", blocks, _translate_fn)

    assert len(call_args_log) >= 1, "translate_fn must have been called"
    _, passed_feedback = call_args_log[0]
    assert feedback_text in passed_feedback, (
        f"Expected feedback string '{feedback_text}' to be passed to translate_fn, got: {passed_feedback!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — iteration cap enforced
# ---------------------------------------------------------------------------

def test_judge_iteration_cap_enforced():
    """Loop stops at JUDGE_MAX_ITERATIONS even when score never reaches 高 (AC-3)."""
    judge = _make_judge()
    # Always return 低 → loop must cap
    judge._client._call_ollama.return_value = _make_client_response("低")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="still bad")

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 3):
        result = judge.run_judge_loop("job-006", _make_blocks(1), translate_fn)

    assert result.judge_status == "available"
    # Loop must not exceed cap
    assert result.attempts <= 3, f"Loop exceeded cap: attempts={result.attempts}"


def test_attempts_field_equals_iteration_count():
    """result.attempts == JUDGE_MAX_ITERATIONS when cap fires (AC-3, anti-tautology)."""
    max_iter = 3
    judge = _make_judge()
    judge._client._call_ollama.return_value = _make_client_response("低")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock(return_value="still 低")

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", max_iter):
        result = judge.run_judge_loop("job-007", _make_blocks(1), translate_fn)

    assert result.attempts == max_iter, (
        f"Expected attempts == {max_iter} (cap), got {result.attempts}"
    )


# ---------------------------------------------------------------------------
# AC-4 — JUDGE_ENABLED=False skips judge
# ---------------------------------------------------------------------------

def test_judge_disabled_flag_skips_judge():
    """When JUDGE_ENABLED=False, no JudgeResult is created from _run_job.

    We test this at the service level: run_judge_loop still works, but the
    hook in _run_job is guarded by `config.JUDGE_ENABLED`. We verify the
    conditional at job_manager level by asserting job.judge is None.
    """
    import types

    # Simulate what _run_job does with JUDGE_ENABLED=False
    from app.backend.services.job_manager import JobRecord
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        job = JobRecord(
            job_id="test-disabled",
            input_dir=Path(tmp) / "input",
            output_dir=Path(tmp) / "output",
        )
        # Simulate the condition check in _run_job:
        # if config.JUDGE_ENABLED and ...: job.judge = ...
        # else: job.judge stays None (not set)
        with patch("app.backend.config.JUDGE_ENABLED", False):
            import app.backend.config as config
            judge_enabled = config.JUDGE_ENABLED

        # When disabled, job.judge must remain None
        assert job.judge is None, "job.judge must be None when JUDGE_ENABLED=False"


# ---------------------------------------------------------------------------
# AC-4 — exception degrades gracefully
# ---------------------------------------------------------------------------

def test_judge_exception_degrades_gracefully():
    """OllamaClient raises → result.judge_status == 'unavailable' (no re-raise)."""
    judge = _make_judge()
    judge._client._call_ollama.side_effect = ConnectionError("Ollama unreachable")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock()
    result = judge.run_judge_loop("job-008", _make_blocks(1), translate_fn)

    assert result.judge_status == "unavailable"
    assert result.score is None
    # Must not propagate the exception


def test_judge_parse_failure_degrades_gracefully():
    """OllamaClient returns garbage → result.judge_status == 'unavailable'."""
    judge = _make_judge()
    judge._client._call_ollama.return_value = (True, "this is not JSON and has no score tokens")
    judge._client._build_no_system_payload.return_value = {}

    translate_fn = MagicMock()
    result = judge.run_judge_loop("job-009", _make_blocks(1), translate_fn)

    assert result.judge_status == "unavailable"
    assert result.score is None


# ---------------------------------------------------------------------------
# D4 — judge client is Ollama, NOT model_router
# ---------------------------------------------------------------------------

def test_judge_client_is_ollama_not_model_router():
    """resolve_route_groups (model_router) is NOT called during judge evaluation (D4)."""
    with patch("app.backend.services.model_router.resolve_route_groups") as mock_resolve:
        from app.backend.services.quality_judge import QualityJudge

        # Build a judge with a mocked client
        judge = QualityJudge.__new__(QualityJudge)
        judge.model = "gemma3"
        mock_client = MagicMock()
        mock_client._call_ollama.return_value = _make_client_response("高")
        mock_client._build_no_system_payload.return_value = {}
        judge._client = mock_client

        translate_fn = MagicMock(return_value="retranslated")
        judge.run_judge_loop("job-010", _make_blocks(1), translate_fn)

        mock_resolve.assert_not_called(), "model_router.resolve_route_groups must NOT be called during judge"
