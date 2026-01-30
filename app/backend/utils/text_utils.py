"""Text processing helpers."""

from __future__ import annotations

import re
from typing import Any, List, Optional

from app.backend.utils.logging_utils import logger

try:
    import blingfire
    HAS_BLINGFIRE = True
except ImportError:
    HAS_BLINGFIRE = False

try:
    import pysbd
    HAS_PYSBD = True
except ImportError:
    HAS_PYSBD = False


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def has_cjk(text: str) -> bool:
    """Check if text contains CJK characters."""
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def is_cjk_language(lang: Optional[str]) -> bool:
    """Check if language code indicates CJK (Chinese/Japanese/Korean).

    Args:
        lang: Language code or name (e.g., "zh-TW", "Japanese", "ko").

    Returns:
        True if language is CJK, False otherwise.
    """
    if not lang:
        return False
    lang_lower = lang.lower()
    cjk_indicators = {
        "zh", "zh-cn", "zh-tw", "chinese", "traditional chinese", "simplified chinese",
        "ja", "japanese",
        "ko", "korean",
    }
    return any(indicator in lang_lower for indicator in cjk_indicators)


def should_translate(text: Any, source_lang: str) -> bool:
    """Determine if text should be translated.

    Args:
        text: The text to check.
        source_lang: Source language hint (e.g., "en", "auto", "fr").

    Returns:
        True if text should be translated, False otherwise.

    Note:
        - Empty or whitespace-only text: skip
        - Pure digits or numbers with punctuation (e.g., "5.", "1.4", "-10"): skip
        - Pure punctuation/symbols: skip
        - Very short text with insufficient meaningful content: skip
        - All other text: translate (regardless of source language setting)

    The source_lang parameter is kept for API compatibility but no longer
    affects the decision. If a user explicitly selects a source language
    (including English), they intend to translate that text.
    """
    if not text:
        return False
    text_str = str(text).strip()
    if not text_str:
        return False

    # Extract alphanumeric characters only
    filtered = "".join(ch for ch in text_str if ch.isalnum())
    if not filtered:
        return False  # Pure punctuation/symbols

    # Pure digits don't need translation
    if filtered.isdigit():
        return False

    # Check if text is a number with punctuation (e.g., "5.", "1.4", "-10", "3,900")
    # Pattern: optional minus, digits, optional decimal/comma with more digits
    number_pattern = re.compile(r'^[-+]?\d+([.,]\d+)*[.]?$')
    if number_pattern.match(text_str):
        return False

    # Extract only letters (alphabetic characters)
    letters_only = "".join(ch for ch in text_str if ch.isalpha())

    # Skip if no letters at all
    if not letters_only:
        return False

    # Skip very short text that likely lacks meaningful context
    # At least 3 letters required for translation
    if len(letters_only) < 3:
        return False

    # All other text should be translated
    # The source_lang parameter is intentionally not used for filtering.
    # If a user explicitly selects any source language (including English),
    # they want that text translated.
    return True


def _is_cjk_lang(lang: Optional[str]) -> bool:
    """Check if language code indicates CJK (Chinese/Japanese/Korean)."""
    if not lang:
        return False
    lang_lower = lang.lower()
    cjk_codes = {"zh", "zh-cn", "zh-tw", "ja", "ko", "chinese", "japanese", "korean"}
    return any(lang_lower.startswith(code) or code in lang_lower for code in cjk_codes)


def _get_pysbd_lang(lang_hint: Optional[str]) -> str:
    """Map language hint to pysbd supported language code."""
    if not lang_hint:
        return "en"
    lang_lower = lang_hint.lower()

    # pysbd supports: en, es, fr, de, it, nl, pl, da, ru, ja, zh, etc.
    pysbd_lang_map = {
        "en": "en", "english": "en",
        "es": "es", "spanish": "es",
        "fr": "fr", "french": "fr",
        "de": "de", "german": "de",
        "it": "it", "italian": "it",
        "nl": "nl", "dutch": "nl",
        "pl": "pl", "polish": "pl",
        "da": "da", "danish": "da",
        "ru": "ru", "russian": "ru",
        "ja": "ja", "japanese": "ja",
        "zh": "zh", "zh-cn": "zh", "zh-tw": "zh", "chinese": "zh",
    }

    for key, value in pysbd_lang_map.items():
        if lang_lower.startswith(key) or key in lang_lower:
            return value
    return "en"  # Default fallback


def split_sentences(line: str, lang_hint: Optional[str]) -> List[str]:
    """Split text into sentences based on language hint.

    Args:
        line: Text to split into sentences.
        lang_hint: Language hint for sentence segmentation.

    Returns:
        List of sentences.
    """
    line = line or ""
    if not line.strip():
        return []

    # For CJK languages, use punctuation-based splitting directly
    # as it's more reliable than blingfire/pysbd for CJK
    if _is_cjk_lang(lang_hint):
        return _split_cjk_sentences(line)

    # Try blingfire first (fast, but only good for English-like languages)
    if HAS_BLINGFIRE and not _is_cjk_lang(lang_hint):
        try:
            sentence_text = blingfire.text_to_sentences(line)
            sentences = [t.strip() for t in sentence_text.split("\n") if t.strip()]
            if sentences:
                return sentences
        except (ValueError, RuntimeError) as exc:
            logger.debug("blingfire split failed: %s", exc)

    # Try pysbd with appropriate language
    if HAS_PYSBD:
        try:
            pysbd_lang = _get_pysbd_lang(lang_hint)
            seg = pysbd.Segmenter(language=pysbd_lang, clean=False)
            sentences = [t.strip() for t in seg.segment(line) if t.strip()]
            if sentences:
                return sentences
        except (ValueError, RuntimeError) as exc:
            logger.debug("pysbd split failed for lang=%s: %s", lang_hint, exc)

    # Fallback: punctuation-based splitting
    return _split_by_punctuation(line)


def _split_cjk_sentences(line: str) -> List[str]:
    """Split CJK text by sentence-ending punctuation."""
    out, buf = [], ""
    # CJK sentence-ending punctuation
    cjk_ends = set("\u3002\uFF01\uFF1F")  # 。！？
    western_ends = set(".!?")

    for ch in line:
        buf += ch
        if ch in cjk_ends or ch in western_ends:
            if buf.strip():
                out.append(buf.strip())
            buf = ""

    if buf.strip():
        out.append(buf.strip())
    return out if out else [line.strip()] if line.strip() else []


def _split_by_punctuation(line: str) -> List[str]:
    """Fallback punctuation-based sentence splitting."""
    out, buf = [], ""
    for ch in line:
        buf += ch
        if ch in "\u3002\uFF01\uFF1F" or ch in ".!?":
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out if out else [line.strip()] if line.strip() else []
