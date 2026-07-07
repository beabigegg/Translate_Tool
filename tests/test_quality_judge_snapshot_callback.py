"""Unit tests for QualityJudge.run_judge_loop's additive snapshot_cb param
(translation-progress-detail-ui, IP-12).

Mirrors tests/test_quality_judge.py's `_make_judge()`/`_make_blocks()` helpers and
its convention of overriding `judge.evaluate` directly with a fake function.

Anti-tautology: the fail-soft test uses a callback that ACTUALLY raises and
asserts a valid JudgeResult is still returned (not merely that no exception
propagated to the caller).
"""

from __future__ import annotations

from typing import List, Tuple
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helpers (mirrors tests/test_quality_judge.py)
# ---------------------------------------------------------------------------

def _make_judge(model_name: str = "gemma3") -> "QualityJudge":  # noqa: F821
    from app.backend.services.quality_judge import QualityJudge

    judge = QualityJudge.__new__(QualityJudge)
    judge.model = model_name
    judge._provider = "ollama"
    return judge


def _make_blocks(n: int = 1) -> List[Tuple[str, str, str]]:
    return [(f"block:{i}", f"source text {i}", f"translated text {i}") for i in range(n)]


# ---------------------------------------------------------------------------
# None = complete no-op
# ---------------------------------------------------------------------------

def test_callback_none_is_complete_noop():
    """Default snapshot_cb=None must not change judge behavior at all."""
    judge = _make_judge()
    judge.evaluate = lambda *a, **k: {"judge_status": "available", "score": "高", "feedback": "ok"}

    result = judge.run_judge_loop("job-noop", _make_blocks(1), lambda s, f: "x", snapshot_cb=None)

    assert result.judge_status == "available"
    assert result.score == "高"


# ---------------------------------------------------------------------------
# Invocation shape: scoring + retranslating sub-steps with attempt index
# ---------------------------------------------------------------------------

def test_callback_invoked_at_scoring_and_retranslating_substeps_with_attempt_index():
    """snapshot_cb fires once per block at 'scoring', and once per block at
    'retranslating' when the score is 中/低 and another iteration remains."""
    calls = []

    def snapshot_cb(block_id, tier, attempt, substep):
        calls.append((block_id, tier, attempt, substep))

    judge = _make_judge()
    judge.evaluate = lambda *a, **k: {"judge_status": "available", "score": "中", "feedback": "needs work"}

    with patch("app.backend.config.JUDGE_MAX_ITERATIONS", 2):
        result = judge.run_judge_loop(
            "job-shape", _make_blocks(2), lambda s, f: "retranslated",
            snapshot_cb=snapshot_cb,
        )

    assert result.judge_status == "available"

    scoring_calls = [c for c in calls if c[3] == "scoring"]
    retranslate_calls = [c for c in calls if c[3] == "retranslating"]

    # 2 blocks scored on iteration 1 (attempt=1); score 中 keeps looping (not last
    # iteration) so both blocks are also retranslated at attempt=1.
    assert ("block:0", None, 1, "scoring") in scoring_calls
    assert ("block:1", None, 1, "scoring") in scoring_calls
    assert ("block:0", "中", 1, "retranslating") in retranslate_calls
    assert ("block:1", "中", 1, "retranslating") in retranslate_calls

    # Iteration 2 (the last iteration, max_iterations=2) scores again but does
    # NOT retranslate (BR-73/BR-75 — no iterations left).
    assert ("block:0", "中", 2, "scoring") in scoring_calls
    assert not any(c[3] == "retranslating" and c[2] == 2 for c in calls), (
        "the last iteration must not retranslate"
    )


# ---------------------------------------------------------------------------
# Fail-soft: a raising callback must not break the judge loop
# ---------------------------------------------------------------------------

def test_callback_that_raises_does_not_break_judge_loop():
    """A snapshot_cb that ACTUALLY raises on every call must not abort the judge
    loop — the loop still returns a well-defined, valid JudgeResult (AC-9)."""

    def raising_cb(block_id, tier, attempt, substep):
        raise RuntimeError("boom — a broken snapshot hook must never break judging")

    judge = _make_judge()
    judge.evaluate = lambda *a, **k: {"judge_status": "available", "score": "高", "feedback": "great"}

    result = judge.run_judge_loop(
        "job-failsoft", _make_blocks(1), lambda s, f: "x", snapshot_cb=raising_cb,
    )

    assert result.judge_status == "available", (
        "a raising snapshot_cb must not degrade the loop to 'unavailable'/'stopped'"
    )
    assert result.score == "高"
    assert result.attempts == 1
