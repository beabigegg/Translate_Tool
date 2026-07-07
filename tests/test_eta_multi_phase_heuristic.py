"""Unit tests for the multi-phase ETA heuristic (BR-105, eta-multi-phase-pipeline).

Pure unit tests against app.backend.api.routes._compute_multi_phase_eta — a
standalone, testable helper (kept the route handler itself thin), covering the
translate / critique+QE / judge terms described in design.md's ETA prose.

Renamed (per implementation-plan.md IP-17) from the plan's original
tests/test_eta_two_phase_heuristic.py — this file never existed on this branch
(the sibling change that would have created it had not landed), so this is a
straight new-file creation under the final name, not a literal git rename.
"""

from __future__ import annotations

from app.backend.api.routes import _compute_multi_phase_eta


def _eta(**overrides):
    """Build a call to _compute_multi_phase_eta with sane defaults, override as needed."""
    kwargs = dict(
        now=1_000.0,
        elapsed=100.0,
        segments_done=50,
        segments_total=100,
        critique_enabled=True,
        qe_enabled=True,
        critique_started_at=None,
        critique_done=0,
        critique_total=0,
        critique_max_iterations=3,
        judge_enabled=False,
        winning_provider=None,
        judge_started_at=None,
        judge_units_done=0,
        judge_units_total=0,
        judge_max_iterations=3,
    )
    kwargs.update(overrides)
    return _compute_multi_phase_eta(**kwargs)


# ---------------------------------------------------------------------------
# AC-5: translate phase rate feeds the pre-observed critique estimate
# ---------------------------------------------------------------------------

def test_translate_phase_only_rate_before_critique_starts():
    """Before critique starts, its coarse pre-estimate is DERIVED from the
    translate-phase rate (the only rate observable so far) — not some
    unrelated constant."""
    per_segment_time = 100.0 / 50  # elapsed / segments_done == 2.0s/segment
    result = _eta(critique_started_at=None, critique_done=0, critique_max_iterations=3)

    remaining_translate = 100 - 50
    translate_rate = 50 / 100.0
    term1 = remaining_translate / translate_rate
    expected_term2 = 100 * per_segment_time * 3  # segments_total * per_segment_time * factor
    assert abs(result - (term1 + expected_term2)) < 1e-6


# ---------------------------------------------------------------------------
# AC-5: coarse critique pre-estimate uses CRITIQUE_MAX_ITERATIONS as a factor
# ---------------------------------------------------------------------------

def test_critique_phase_estimated_via_max_iterations_factor_before_observed():
    per_segment_time = 100.0 / 50
    result_factor_3 = _eta(critique_max_iterations=3)
    result_factor_1 = _eta(critique_max_iterations=1)

    # A larger max-iterations factor must yield a strictly larger phase-2 term
    # (all else equal) — proves the factor is actually load-bearing, not a
    # constant that happens to be present.
    assert result_factor_3 > result_factor_1
    expected_delta = 100 * per_segment_time * (3 - 1)
    assert abs((result_factor_3 - result_factor_1) - expected_delta) < 1e-6


# ---------------------------------------------------------------------------
# AC-5: blended two-phase estimate once critique's OWN rate is observed
# ---------------------------------------------------------------------------

def test_blended_two_phase_estimate_once_critique_rate_observed():
    """Once critique_started_at/critique_done are populated, phase-2 uses ITS
    OWN observed rate instead of the pre-observed coarse estimate."""
    result = _eta(
        segments_done=100, segments_total=100,  # translation phase fully done
        critique_started_at=990.0, critique_done=5, critique_total=20,
        now=1_000.0,  # critique_elapsed = 10s -> rate = 0.5/s
    )
    term1 = 0.0  # no remaining translate segments
    critique_rate = 5 / 10.0
    remaining_critique = 20 - 5
    term2 = remaining_critique / critique_rate
    assert abs(result - (term1 + term2)) < 1e-6


# ---------------------------------------------------------------------------
# AC-5: phase-2 omitted entirely when both critique and QE are disabled
# ---------------------------------------------------------------------------

def test_eta_omits_critique_phase_when_critique_and_qe_disabled():
    result = _eta(critique_enabled=False, qe_enabled=False, judge_enabled=False)
    remaining_translate = 100 - 50
    translate_rate = 50 / 100.0
    term1 = remaining_translate / translate_rate
    assert abs(result - term1) < 1e-6


# ---------------------------------------------------------------------------
# AC-9: judge phase pre-estimate uses JUDGE_MAX_ITERATIONS as a factor
# ---------------------------------------------------------------------------

def test_judge_phase_estimated_via_max_iterations_factor_before_observed():
    per_segment_time = 100.0 / 50
    result = _eta(
        critique_enabled=False, qe_enabled=False,
        judge_enabled=True, winning_provider="panjit",
        judge_started_at=None, judge_units_done=0, judge_max_iterations=3,
    )
    term1 = (100 - 50) / (50 / 100.0)
    expected_term3 = 100 * 3 * per_segment_time
    assert abs(result - (term1 + expected_term3)) < 1e-6


# ---------------------------------------------------------------------------
# AC-9: blended judge estimate once its own rate is observed
# ---------------------------------------------------------------------------

def test_judge_phase_blended_estimate_once_observed_rate_available():
    result = _eta(
        segments_done=100, segments_total=100,
        critique_enabled=False, qe_enabled=False,
        judge_enabled=True, winning_provider="panjit",
        judge_started_at=990.0, judge_units_done=4, judge_units_total=12,
        now=1_000.0,  # judge_elapsed = 10s -> rate = 0.4/s
    )
    judge_rate = 4 / 10.0
    remaining_judge = 12 - 4
    term3 = remaining_judge / judge_rate
    assert abs(result - term3) < 1e-6


# ---------------------------------------------------------------------------
# AC-9: judge phase omitted when JUDGE_ENABLED=false
# ---------------------------------------------------------------------------

def test_eta_omits_judge_phase_when_judge_disabled():
    result = _eta(
        critique_enabled=False, qe_enabled=False,
        judge_enabled=False, winning_provider="panjit",
        judge_started_at=990.0, judge_units_done=4, judge_units_total=12, now=1_000.0,
    )
    term1 = (100 - 50) / (50 / 100.0)
    assert abs(result - term1) < 1e-6


# ---------------------------------------------------------------------------
# AC-9: judge phase omitted when winning provider is deepseek (BR-97)
# ---------------------------------------------------------------------------

def test_eta_omits_judge_phase_when_winning_provider_is_deepseek():
    result_deepseek = _eta(
        critique_enabled=False, qe_enabled=False,
        judge_enabled=True, winning_provider="DeepSeek",  # case-insensitive per BR-97
        judge_started_at=990.0, judge_units_done=4, judge_units_total=12, now=1_000.0,
    )
    result_panjit = _eta(
        critique_enabled=False, qe_enabled=False,
        judge_enabled=True, winning_provider="panjit",
        judge_started_at=990.0, judge_units_done=4, judge_units_total=12, now=1_000.0,
    )
    term1 = (100 - 50) / (50 / 100.0)
    assert abs(result_deepseek - term1) < 1e-6, "deepseek must omit the judge term entirely"
    assert result_panjit > result_deepseek, "a non-deepseek provider must still add a judge term"
