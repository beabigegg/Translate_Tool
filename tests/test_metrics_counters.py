"""Unit tests for app.backend.services.metrics counter module.

All tests reset singleton state via the exposed reset() helper so counter state
does not bleed between cases.
"""

from __future__ import annotations

import pytest

import app.backend.services.metrics as metrics_mod


@pytest.fixture(autouse=True)
def reset_counters():
    """Reset all counters before each test."""
    metrics_mod.reset()
    yield
    metrics_mod.reset()


# ---------------------------------------------------------------------------
# AC-6 — Initialization
# ---------------------------------------------------------------------------

def test_all_counters_initialize_to_zero():
    data = metrics_mod.get_metrics()
    assert data["translation_count"] == 0
    assert data["translation_latency_mean_ms"] == 0.0
    assert data["provider_failure_count"] == 0
    assert data["font_cache_hits"] == 0
    assert data["font_cache_misses"] == 0


def test_latency_mean_is_float_zero_when_count_zero():
    data = metrics_mod.get_metrics()
    value = data["translation_latency_mean_ms"]
    assert value == 0.0
    assert isinstance(value, float)


def test_counters_no_external_io():
    """Smoke test: importing and calling counter functions must not raise or perform IO."""
    # If this passes at all, the module is importable without side effects.
    metrics_mod.reset()
    metrics_mod.record_translation(100.0)
    metrics_mod.record_provider_failure()
    metrics_mod.record_font_cache_hit()
    metrics_mod.record_font_cache_miss()
    data = metrics_mod.get_metrics()
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# AC-3 — Translation count and latency mean
# ---------------------------------------------------------------------------

def test_translation_count_increments_on_success():
    metrics_mod.record_translation(50.0, failed=False)
    assert metrics_mod.get_metrics()["translation_count"] == 1


def test_translation_count_increments_on_failure_too():
    # BR-21: count increments on both success and failure
    metrics_mod.record_translation(50.0, failed=True)
    assert metrics_mod.get_metrics()["translation_count"] == 1


def test_latency_mean_updated_after_calls():
    metrics_mod.record_translation(100.0)
    metrics_mod.record_translation(200.0)
    data = metrics_mod.get_metrics()
    assert data["translation_count"] == 2
    assert data["translation_latency_mean_ms"] == 150.0


def test_latency_mean_incremental_formula():
    # n=1: mean = 100.0
    metrics_mod.record_translation(100.0)
    assert metrics_mod.get_metrics()["translation_latency_mean_ms"] == pytest.approx(100.0)
    # n=2: new_mean = ((100.0 * 1) + 300.0) / 2 = 200.0
    metrics_mod.record_translation(300.0)
    assert metrics_mod.get_metrics()["translation_latency_mean_ms"] == pytest.approx(200.0)
    # n=3: new_mean = ((200.0 * 2) + 100.0) / 3 = 166.666...
    metrics_mod.record_translation(100.0)
    assert metrics_mod.get_metrics()["translation_latency_mean_ms"] == pytest.approx(500.0 / 3)


# ---------------------------------------------------------------------------
# AC-4 — Provider failure count
# ---------------------------------------------------------------------------

def test_provider_failure_count_increments_on_failure():
    metrics_mod.record_translation(50.0, failed=True)
    assert metrics_mod.get_metrics()["provider_failure_count"] == 1


def test_provider_failure_count_unchanged_on_success():
    metrics_mod.record_translation(50.0, failed=False)
    assert metrics_mod.get_metrics()["provider_failure_count"] == 0


def test_provider_failure_count_increments_per_attempt_in_chain():
    # Table E: 3-provider chain, all fail → +3
    metrics_mod.record_provider_failure()
    metrics_mod.record_provider_failure()
    metrics_mod.record_provider_failure()
    assert metrics_mod.get_metrics()["provider_failure_count"] == 3


# ---------------------------------------------------------------------------
# AC-5 — Font cache hit/miss
# ---------------------------------------------------------------------------

def test_font_cache_hit_increments_hits():
    metrics_mod.record_font_cache_hit()
    data = metrics_mod.get_metrics()
    assert data["font_cache_hits"] == 1
    assert data["font_cache_misses"] == 0


def test_font_cache_miss_increments_misses():
    metrics_mod.record_font_cache_miss()
    data = metrics_mod.get_metrics()
    assert data["font_cache_misses"] == 1
    assert data["font_cache_hits"] == 0


def test_font_cache_exactly_one_counter_per_access():
    # BR-24: exactly one counter per access
    metrics_mod.record_font_cache_hit()
    metrics_mod.record_font_cache_miss()
    metrics_mod.record_font_cache_hit()
    data = metrics_mod.get_metrics()
    assert data["font_cache_hits"] == 2
    assert data["font_cache_misses"] == 1
    assert data["font_cache_hits"] + data["font_cache_misses"] == 3


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def test_reset_restores_initial_state():
    metrics_mod.record_translation(100.0, failed=True)
    metrics_mod.record_provider_failure()
    metrics_mod.record_font_cache_hit()
    metrics_mod.record_font_cache_miss()

    metrics_mod.reset()

    data = metrics_mod.get_metrics()
    assert data["translation_count"] == 0
    assert data["translation_latency_mean_ms"] == 0.0
    assert data["provider_failure_count"] == 0
    assert data["font_cache_hits"] == 0
    assert data["font_cache_misses"] == 0


# ---------------------------------------------------------------------------
# AC-8 / BR-46 — New critique loop counters
# ---------------------------------------------------------------------------

def test_critique_loop_invocations_initializes_to_zero():
    data = metrics_mod.get_metrics()
    assert data["critique_loop_invocations"] == 0


def test_critique_iterations_total_initializes_to_zero():
    data = metrics_mod.get_metrics()
    assert data["critique_iterations_total"] == 0


def test_glossary_match_rate_initializes_to_one():
    data = metrics_mod.get_metrics()
    # 1.0 when no terms present (nothing to miss)
    assert data["glossary_match_rate"] == pytest.approx(1.0)


def test_critique_loop_invocations_increments():
    metrics_mod.record_critique_loop_invocation()
    metrics_mod.record_critique_loop_invocation()
    data = metrics_mod.get_metrics()
    assert data["critique_loop_invocations"] == 2


def test_critique_iterations_total_accumulates():
    metrics_mod.record_critique_iteration(3)
    metrics_mod.record_critique_iteration(2)
    data = metrics_mod.get_metrics()
    assert data["critique_iterations_total"] == 5


def test_glossary_match_rate_set_scalar():
    metrics_mod.set_glossary_match_rate(0.5)
    data = metrics_mod.get_metrics()
    assert data["glossary_match_rate"] == pytest.approx(0.5)


def test_critique_counters_reset_via_reset():
    metrics_mod.record_critique_loop_invocation()
    metrics_mod.record_critique_iteration(4)
    metrics_mod.set_glossary_match_rate(0.25)

    metrics_mod.reset()

    data = metrics_mod.get_metrics()
    assert data["critique_loop_invocations"] == 0
    assert data["critique_iterations_total"] == 0
    assert data["glossary_match_rate"] == pytest.approx(1.0)  # reset to sentinel 1.0
