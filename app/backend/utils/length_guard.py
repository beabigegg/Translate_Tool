"""Composition-aware truncation length guard (truncation-length-guard, BR-117, ADR-0020).

Pure module: no I/O, no LLM dependency. Flags a DOCX table-cell translation
as suspiciously short when `translated_len < k * E`, where
`E = a*cjk + b*latin_alpha` is an expected-length model derived from a
per-target coefficient table. Fails safe (never flags) on any uncalibrated
target, a short source, or `E == 0` — see ADR-0020 reversal-guarded
invariant 1.
"""

from __future__ import annotations

from app.backend import config
from app.backend.utils.text_utils import count_composition, normalize_text


def expected_length(source: str, target: str, coeffs: dict) -> float:
    """Return the expected-length model `E = a*cjk + b*latin_alpha` for
    `source` under `target`'s coefficients. `0.0` if `target` (normalized,
    stripped+lowercased) has no entry in `coeffs`.

    Args:
        source: Source text (already whitespace-normalized by the caller).
        target: Target language string (normalized case-insensitively here).
        coeffs: Coefficient table `{normalized_target: (a_cjk, b_latin)}`.

    Returns:
        The expected-length value `E`, or `0.0` when the target is unlisted.
    """
    key = (target or "").strip().lower()
    if key not in coeffs:
        return 0.0
    a, b = coeffs[key]
    cjk, latin = count_composition(source)
    return a * cjk + b * latin


def is_suspiciously_short(source: str, translation: str, target: str) -> bool:
    """Return True when `translation` is suspiciously short relative to
    `source`'s composition-aware expected length for `target`.

    Fails safe (returns False) — no exceptions — when ANY of:
      1. `target` (normalized) has no entry in the coefficient table.
      2. The normalized source is shorter than `TRUNCATION_GUARD_MIN_SOURCE_CHARS`.
      3. The expected length `E == 0` (no CJK/latin-alpha counted, e.g. an
         all-numeric source — BR-68 backstop).

    Otherwise flags when `len(translation) < TRUNCATION_GUARD_K * E`.
    """
    key = (target or "").strip().lower()
    if key not in config.TRUNCATION_GUARD_COEFFICIENTS:
        return False  # fail-safe 1: uncalibrated target

    norm_source = normalize_text(source)
    if len(norm_source) < config.TRUNCATION_GUARD_MIN_SOURCE_CHARS:
        return False  # fail-safe 2: source too short to trust the model

    e = expected_length(norm_source, target, config.TRUNCATION_GUARD_COEFFICIENTS)
    if e == 0:
        return False  # fail-safe 3: no CJK/latin-alpha (e.g. numeric, BR-68)

    return len(translation or "") < config.TRUNCATION_GUARD_K * e
