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
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def should_translate(text: Any, source_lang: str) -> bool:
    if not text:
        return False
    if not str(text).strip():
        return False
    source = (source_lang or "").strip().lower()
    filtered = "".join(ch for ch in str(text) if str(ch).isalnum())
    if not filtered:
        return False
    if source.startswith("en"):
        return True
    if source.startswith("auto") or source == "":
        return True
    ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if all((c in ascii_letters) for c in filtered):
        return False
    if filtered.isdigit():
        return False
    return True


def split_sentences(line: str, lang_hint: Optional[str]) -> List[str]:
    line = line or ""
    if not line.strip():
        return []
    if HAS_BLINGFIRE:
        try:
            sentence_text = blingfire.text_to_sentences(line)
            sentences = [t.strip() for t in sentence_text.split("\n") if t.strip()]
            if sentences:
                return sentences
        except (ValueError, RuntimeError) as exc:
            logger.debug("blingfire split failed: %s", exc)
    if HAS_PYSBD:
        try:
            seg = pysbd.Segmenter(language="en", clean=False)
            sentences = [t.strip() for t in seg.segment(line) if t.strip()]
            if sentences:
                return sentences
        except (ValueError, RuntimeError) as exc:
            logger.debug("pysbd split failed: %s", exc)
    out, buf = [], ""
    for ch in line:
        buf += ch
        if ch in "\u3002\uFF01\uFF1F" or ch in ".!?":
            out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out
