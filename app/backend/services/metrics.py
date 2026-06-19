"""In-process observability counters.

Module-level singleton that tracks five flat counters updated by additive
increment hooks at the translation and font-load call sites.

This module is intentionally side-effect-free on import: no file I/O, no
network access, no logging, no config reads.  Counters initialize to zero at
module load (BR-20).

``reset()`` is a test-only helper; do NOT call it from production code.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Module-level counter state
# ---------------------------------------------------------------------------

_translation_count: int = 0
_translation_latency_mean_ms: float = 0.0
_provider_failure_count: int = 0
_font_cache_hits: int = 0
_font_cache_misses: int = 0

# Critique loop counters (p2-prompt-fewshot-glossary, BR-46)
_critique_loop_invocations: int = 0
_critique_iterations_total: int = 0
_glossary_match_rate: float = 1.0  # last-request scalar (1.0 when no terms present)


# ---------------------------------------------------------------------------
# Increment functions
# ---------------------------------------------------------------------------

def record_translation(latency_ms: float, failed: bool = False) -> None:
    """Record one completed provider translation call.

    Increments ``translation_count`` unconditionally (BR-21).
    Updates the running arithmetic mean for ``translation_latency_mean_ms``
    per the incremental formula in BR-22.
    When ``failed`` is True, also increments ``provider_failure_count`` (BR-23).

    This function is no-op-safe: bad args silently become no-ops.
    """
    global _translation_count, _translation_latency_mean_ms, _provider_failure_count

    try:
        latency_ms = float(latency_ms)
    except (TypeError, ValueError):
        return

    _translation_count += 1
    n = _translation_count
    # Incremental arithmetic mean: new_mean = ((old_mean * (n-1)) + new_latency) / n
    _translation_latency_mean_ms = (
        (_translation_latency_mean_ms * (n - 1) + latency_ms) / n
    )

    if failed:
        _provider_failure_count += 1


def record_provider_failure() -> None:
    """Increment ``provider_failure_count`` by 1 for one failed provider attempt.

    Use this when a provider attempt fails independently of completing a full
    translation call — e.g. each provider in a 3-provider fallback chain.
    """
    global _provider_failure_count
    _provider_failure_count += 1


def record_font_cache_hit() -> None:
    """Increment ``font_cache_hits`` by 1 (BR-24)."""
    global _font_cache_hits
    _font_cache_hits += 1


def record_font_cache_miss() -> None:
    """Increment ``font_cache_misses`` by 1 (BR-24)."""
    global _font_cache_misses
    _font_cache_misses += 1


def record_critique_loop_invocation() -> None:
    """Increment ``critique_loop_invocations`` by 1 (BR-46).

    Call once per translation request that enters the critique loop.
    """
    global _critique_loop_invocations
    _critique_loop_invocations += 1


def record_critique_iteration(n: int = 1) -> None:
    """Add *n* to ``critique_iterations_total`` (BR-46).

    Call with the actual number of iterations completed for one request.
    """
    global _critique_iterations_total
    try:
        _critique_iterations_total += int(n)
    except (TypeError, ValueError):
        pass


def set_glossary_match_rate(rate: float) -> None:
    """Set last-request ``glossary_match_rate`` scalar (BR-46, design Decision 5).

    Value is 0.0–1.0.  Post-substitution it should always be 1.0 when terms
    were present, making it a regression sentinel.  When no terms are present
    the rate is 1.0 (nothing to miss).
    """
    global _glossary_match_rate
    try:
        _glossary_match_rate = float(rate)
    except (TypeError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def get_metrics() -> dict:
    """Return a snapshot dict of all five counters.

    ``translation_latency_mean_ms`` is always a Python ``float`` and is
    ``0.0`` when ``translation_count`` is 0 (BR-22).
    """
    return {
        "translation_count": _translation_count,
        "translation_latency_mean_ms": float(_translation_latency_mean_ms),
        "provider_failure_count": _provider_failure_count,
        "font_cache_hits": _font_cache_hits,
        "font_cache_misses": _font_cache_misses,
        "critique_loop_invocations": _critique_loop_invocations,
        "critique_iterations_total": _critique_iterations_total,
        "glossary_match_rate": float(_glossary_match_rate),
    }


# ---------------------------------------------------------------------------
# Test-only helper
# ---------------------------------------------------------------------------

def reset() -> None:
    """Reset all counters to their initial zero state.

    FOR TESTS ONLY — never call this from production code (routes, services,
    renderers).
    """
    global _translation_count, _translation_latency_mean_ms, _provider_failure_count, _font_cache_hits, _font_cache_misses, _critique_loop_invocations, _critique_iterations_total, _glossary_match_rate  # noqa: E501
    _translation_count = 0
    _translation_latency_mean_ms = 0.0
    _provider_failure_count = 0
    _font_cache_hits = 0
    _font_cache_misses = 0
    _critique_loop_invocations = 0
    _critique_iterations_total = 0
    _glossary_match_rate = 1.0
