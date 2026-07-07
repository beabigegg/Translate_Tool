"""Tests for the QE-gated critique adoption logic (quality-metrics-gating AC-7, AC-8).

Tests the _critique_gate_adopt and _heuristic_should_adopt helpers in translation_service.py.

Anti-tautology guards (CLAUDE.md):
- _critique_gate_adopt uses LAZY imports (inside the function body):
    from app.backend.services.quality_evaluator import load_model, score_blocks
  So we MUST patch at the DEFINITION module (`quality_evaluator`), NOT the consumer module.
  Use patch.object(qe_mod, "load_model") and patch.object(qe_mod, "score_blocks")
  where qe_mod is captured at collection time (immune to sys.modules contamination).
- Assert ADOPTED TEXT IDENTITY, not just that translation ran.
- For ImportError tests, verify no exception escapes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Capture the definition module at collection time (immune to reload contamination).
import app.backend.services.quality_evaluator as _qe_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_helpers():
    """Import the private helpers under test."""
    from app.backend.services.translation_service import (
        _critique_gate_adopt,
        _heuristic_should_adopt,
    )
    return _critique_gate_adopt, _heuristic_should_adopt


# ---------------------------------------------------------------------------
# AC-7: Critique gate adoption rules
# ---------------------------------------------------------------------------

def test_gate_adopts_revised_when_revised_score_strictly_higher():
    """AC-7: score_blocks returns [0.7, 0.9] → revised is adopted (0.9 > 0.7)."""
    _critique_gate_adopt, _ = _get_helpers()

    src = "Hello world"
    draft = "Bonjour monde"
    revised = "Bonjour le monde"

    with patch.object(_qe_mod, "load_model", return_value=MagicMock()), \
         patch.object(_qe_mod, "score_blocks", return_value=[0.7, 0.9]):
        result = _critique_gate_adopt(src, draft, revised)

    assert result == revised, (
        f"Expected revised to be adopted when revised_score(0.9) > draft_score(0.7); "
        f"got {result!r}"
    )


def test_gate_keeps_original_when_revised_score_lower():
    """AC-7: score_blocks returns [0.9, 0.7] → original draft is kept (0.7 < 0.9)."""
    _critique_gate_adopt, _ = _get_helpers()

    src = "Hello world"
    draft = "Bonjour le monde"
    revised = "Hé monde"

    with patch.object(_qe_mod, "load_model", return_value=MagicMock()), \
         patch.object(_qe_mod, "score_blocks", return_value=[0.9, 0.7]):
        result = _critique_gate_adopt(src, draft, revised)

    assert result == draft, (
        f"Expected draft to be kept when revised_score(0.7) < draft_score(0.9); "
        f"got {result!r}"
    )


def test_gate_keeps_original_on_exact_tie():
    """AC-7: score_blocks returns [0.8, 0.8] → tie keeps original draft (no-op)."""
    _critique_gate_adopt, _ = _get_helpers()

    src = "Hello world"
    draft = "Bonjour le monde"
    revised = "Bonjour monde"

    with patch.object(_qe_mod, "load_model", return_value=MagicMock()), \
         patch.object(_qe_mod, "score_blocks", return_value=[0.8, 0.8]):
        result = _critique_gate_adopt(src, draft, revised)

    assert result == draft, (
        f"Expected draft on exact tie (0.8 == 0.8); got {result!r}"
    )


def test_gate_keeps_draft_when_score_blocks_returns_empty():
    """AC-7 resilience: score_blocks returns [] (internal failure) → keep draft."""
    _critique_gate_adopt, _ = _get_helpers()

    src = "Hello"
    draft = "Hallo"
    revised = "Hei"

    with patch.object(_qe_mod, "load_model", return_value=MagicMock()), \
         patch.object(_qe_mod, "score_blocks", return_value=[]):
        result = _critique_gate_adopt(src, draft, revised)

    assert result == draft, (
        f"Expected draft when score_blocks returns empty; got {result!r}"
    )


# ---------------------------------------------------------------------------
# AC-8: ImportError / QE unavailable → heuristic fallback
# ---------------------------------------------------------------------------

def test_comet_import_error_falls_back_to_heuristic():
    """AC-8: ImportError when loading COMET → heuristic fires → no exception raised."""
    _critique_gate_adopt, _ = _get_helpers()

    src = "Hello"
    draft = "Hallo"
    revised = "Hei"  # passes length ratio check

    # Simulate COMET not installed: load_model raises ImportError.
    # Patch at definition module — the lazy import in _critique_gate_adopt resolves here.
    with patch.object(_qe_mod, "load_model", side_effect=ImportError("No module named 'comet'")):
        # Should NOT raise; heuristic should fire
        result = _critique_gate_adopt(src, draft, revised)

    # Heuristic: "Hei" vs "Hallo" → ratio≈0.6 ≥ 0.3 → accepted
    assert result in (draft, revised), (
        f"Expected either draft or revised; got {result!r}"
    )
    # No exception was raised — test passes if we got here


def test_pipeline_completes_with_no_exception_when_qe_unavailable():
    """AC-8: QE model load exception → heuristic fallback → pipeline always completes."""
    _critique_gate_adopt, _ = _get_helpers()

    src = "Test source"
    draft = "Test draft translation"
    revised = "Test revised translation"

    with patch.object(_qe_mod, "load_model", side_effect=RuntimeError("OOM: COMET model too large")):
        result = _critique_gate_adopt(src, draft, revised)

    # Just verify no exception escapes
    assert isinstance(result, str), f"Expected str result; got {type(result)}"


def test_heuristic_penalises_empty_output_and_failure_markers():
    """AC-8 heuristic rule: empty/failure-placeholder revised → draft kept."""
    _, _heuristic_should_adopt = _get_helpers()

    draft = "Bonjour le monde"

    # Empty revised → reject
    assert not _heuristic_should_adopt(draft, ""), "Empty revised must be rejected"

    # Failure placeholder → reject
    assert not _heuristic_should_adopt(
        draft, "[Translation failed|fr] Hello world"
    ), "Failure placeholder must be rejected"


def test_heuristic_rejects_extreme_length_ratios():
    """AC-8 heuristic rule: length ratio outside [0.3, 3.0] → reject revised."""
    _, _heuristic_should_adopt = _get_helpers()

    draft = "A" * 100

    # Far too short (ratio < 0.3)
    too_short = "A" * 10
    assert not _heuristic_should_adopt(draft, too_short), (
        "Revised that is 10% of draft length must be rejected (ratio=0.1 < 0.3)"
    )

    # Far too long (ratio > 3.0)
    too_long = "A" * 400
    assert not _heuristic_should_adopt(draft, too_long), (
        "Revised that is 400% of draft length must be rejected (ratio=4.0 > 3.0)"
    )


def test_heuristic_accepts_normal_revised_text():
    """AC-8 heuristic rule: normal revised text (sane length ratio) → accepted."""
    _, _heuristic_should_adopt = _get_helpers()

    draft = "Hello world, this is a test."
    revised = "Hello world, this is a revised test."  # ratio ≈ 1.2

    assert _heuristic_should_adopt(draft, revised), (
        f"Normal revised text should be accepted by heuristic"
    )


# ---------------------------------------------------------------------------
# batch-critique-qe-scoring AC-3: batched round scores map to the correct
# segment by index (highest-risk detail — an off-by-one silently swaps which
# segment's revised score is compared against which draft score).
# ---------------------------------------------------------------------------

def _get_batched_helper():
    from app.backend.services.translation_service import _batched_critique_adopt
    return _batched_critique_adopt


def test_batched_round_scores_map_to_correct_segment_index():
    """AC-3: a single score_blocks() call scoring 3 segments' pairs must map
    each segment's own (draft, revised) scores back by index — not shifted by
    one — and apply strict-greater-than / tie-keeps-draft per segment.

    blocks layout built by _batched_critique_adopt is
    [seg0_draft, seg0_revised, seg1_draft, seg1_revised, seg2_draft, seg2_revised]
    Scores are scripted so each segment has a DIFFERENT, unambiguous outcome:
      segment 0: revised(0.9) > draft(0.2)  -> adopt revised
      segment 1: revised(0.5) == draft(0.5) -> tie keeps draft
      segment 2: revised(0.1) < draft(0.8)  -> keep draft
    An off-by-one pairing would produce a different combination than this
    exact expected list.
    """
    _batched_critique_adopt = _get_batched_helper()

    pairs = [
        ("Src A", "Draft A", "Revised A"),
        ("Src B", "Draft B", "Revised B"),
        ("Src C", "Draft C", "Revised C"),
    ]
    # Flat scores in blocks order: [d0, r0, d1, r1, d2, r2]
    scripted_scores = [0.2, 0.9, 0.5, 0.5, 0.8, 0.1]

    with patch.object(_qe_mod, "load_model", return_value=MagicMock()), \
         patch.object(_qe_mod, "score_blocks", return_value=scripted_scores) as mock_sb:
        result = _batched_critique_adopt(pairs)

    # Exactly one score_blocks() call for the whole batch, not one per segment.
    assert mock_sb.call_count == 1

    # Verify the flat blocks list passed to score_blocks matches the expected
    # per-segment (src, draft)/(src, revised) pairing and order.
    call_blocks = mock_sb.call_args[0][1]
    assert call_blocks == [
        ("Src A", "Draft A"), ("Src A", "Revised A"),
        ("Src B", "Draft B"), ("Src B", "Revised B"),
        ("Src C", "Draft C"), ("Src C", "Revised C"),
    ], f"Unexpected blocks pairing/order: {call_blocks!r}"

    assert result == ["Revised A", "Draft B", "Draft C"], (
        f"Expected per-segment adoption [revised, draft(tie), draft] by exact "
        f"index mapping; got {result!r}"
    )


def test_batched_adopt_empty_scores_keeps_all_drafts():
    """AC-3/AC-1 resilience: score_blocks() returning [] (total failure) must
    degrade every pending segment in the round to 'keep draft' — never crash,
    never partially adopt."""
    _batched_critique_adopt = _get_batched_helper()

    pairs = [
        ("Src A", "Draft A", "Revised A"),
        ("Src B", "Draft B", "Revised B"),
    ]

    with patch.object(_qe_mod, "load_model", return_value=MagicMock()), \
         patch.object(_qe_mod, "score_blocks", return_value=[]):
        result = _batched_critique_adopt(pairs)

    assert result == ["Draft A", "Draft B"], (
        f"Expected all drafts kept when score_blocks returns []; got {result!r}"
    )


def test_batched_adopt_qe_unavailable_falls_back_to_heuristic_per_segment():
    """AC-8: QE model load failure in the batched path must still fall back to
    the deterministic length-ratio/fluency heuristic per segment, exactly as
    _critique_gate_adopt's except-path does today."""
    _batched_critique_adopt = _get_batched_helper()

    pairs = [
        ("Src A", "Hallo", "Hei"),  # passes heuristic (ratio ok)
        ("Src B", "A" * 100, "A" * 400),  # fails heuristic (ratio > 3.0)
    ]

    with patch.object(_qe_mod, "load_model", side_effect=ImportError("no comet")):
        result = _batched_critique_adopt(pairs)

    assert result[0] == "Hei", "Segment A should adopt revised via heuristic pass"
    assert result[1] == "A" * 100, "Segment B should keep draft via heuristic reject"


def test_batched_adopt_empty_pairs_returns_empty_list_without_calling_score_blocks():
    """No pending segments this round → no score_blocks() call at all."""
    _batched_critique_adopt = _get_batched_helper()

    with patch.object(_qe_mod, "load_model") as mock_load, \
         patch.object(_qe_mod, "score_blocks") as mock_sb:
        result = _batched_critique_adopt([])

    assert result == []
    mock_load.assert_not_called()
    mock_sb.assert_not_called()
