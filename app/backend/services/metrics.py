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
    }


# ---------------------------------------------------------------------------
# Test-only helper
# ---------------------------------------------------------------------------

def reset() -> None:
    """Reset all counters to their initial zero state.

    FOR TESTS ONLY — never call this from production code (routes, services,
    renderers).
    """
    global _translation_count, _translation_latency_mean_ms, _provider_failure_count, _font_cache_hits, _font_cache_misses  # noqa: E501
    _translation_count = 0
    _translation_latency_mean_ms = 0.0
    _provider_failure_count = 0
    _font_cache_hits = 0
    _font_cache_misses = 0
