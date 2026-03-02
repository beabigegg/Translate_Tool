"""Post-translation verification and gap-filling.

Scans translation results for known failure patterns, retries failed
segments individually, and updates results in-place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from app.backend.config import VERIFY_MAX_RETRIES
from app.backend.services.translation_service import (
    _convert_to_traditional,
    _is_traditional_chinese_target,
)

# Regex matching all known error prefixes produced by the translation pipeline.
_FAILURE_PATTERNS = re.compile(
    r"^\["
    r"(?:"
    r"Translation failed\|"
    r"|翻譯失敗\]"
    r"|No translation\|"
    r"|Translation missing"
    r"|Extended retry failed"
    r"|Chunked translation failed"
    r"|Chunk translation failed\]"
    r"|Missing translation result\]"
    r")"
)


def is_failed_translation(text: str) -> bool:
    """Return True if *text* matches a known translation-failure pattern."""
    return bool(_FAILURE_PATTERNS.search(text))


@dataclass
class VerificationResult:
    """Summary of a verification pass."""

    gaps_found: int
    gaps_filled: int
    gaps_remaining: int


def verify_and_fill_tmap(
    tmap: Dict[Tuple[str, str], str],
    client: object,
    src_lang: Optional[str],
    *,
    stop_flag: object = None,
    log: Callable[[str], None] = lambda s: None,
    max_retries: int = VERIFY_MAX_RETRIES,
) -> VerificationResult:
    """Scan *tmap* for failed translations and retry them in-place.

    Used by docx / xlsx / pptx processors whose translation map has the
    shape ``{(target_lang, source_text): translated_text}``.
    """
    # Collect failed entries: list of (tgt, src_text) keys
    failed: List[Tuple[str, str]] = [
        key for key, val in tmap.items() if is_failed_translation(val)
    ]
    if not failed:
        return VerificationResult(0, 0, 0)

    log(f"[VERIFY] Found {len(failed)} failed translation(s), retrying …")
    filled = 0

    for tgt, src_text in failed:
        if stop_flag and stop_flag.is_set():
            log("[VERIFY] Stopped by user")
            break

        needs_s2t = _is_traditional_chinese_target(tgt)

        for attempt in range(1, max_retries + 1):
            ok, result = client.translate_once(src_text, tgt, src_lang)
            if ok and not is_failed_translation(result):
                if needs_s2t:
                    result = _convert_to_traditional(result)
                tmap[(tgt, src_text)] = result
                filled += 1
                break

    remaining = len(failed) - filled
    log(f"[VERIFY] Done — filled {filled}, remaining {remaining}")
    return VerificationResult(len(failed), filled, remaining)


def verify_and_fill_dict(
    translations: Dict[str, str],
    tgt: str,
    client: object,
    src_lang: Optional[str],
    *,
    stop_flag: object = None,
    log: Callable[[str], None] = lambda s: None,
    max_retries: int = VERIFY_MAX_RETRIES,
) -> VerificationResult:
    """Scan a ``{source_text: translated_text}`` dict and retry failures.

    Used by PDF processors where translations are stored per-language in a
    flat dict rather than the ``(tgt, src)`` keyed tmap.
    """
    failed: List[str] = [
        src for src, val in translations.items() if is_failed_translation(val)
    ]
    if not failed:
        return VerificationResult(0, 0, 0)

    log(f"[VERIFY] Found {len(failed)} failed translation(s) for {tgt}, retrying …")
    filled = 0
    needs_s2t = _is_traditional_chinese_target(tgt)

    for src_text in failed:
        if stop_flag and stop_flag.is_set():
            log("[VERIFY] Stopped by user")
            break

        for attempt in range(1, max_retries + 1):
            ok, result = client.translate_once(src_text, tgt, src_lang)
            if ok and not is_failed_translation(result):
                if needs_s2t:
                    result = _convert_to_traditional(result)
                translations[src_text] = result
                filled += 1
                break

    remaining = len(failed) - filled
    log(f"[VERIFY] Done — filled {filled}, remaining {remaining}")
    return VerificationResult(len(failed), filled, remaining)
