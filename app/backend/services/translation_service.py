"""Shared translation routines."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Tuple

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import DEFAULT_MAX_BATCH_CHARS, SENTENCE_MODE
from app.backend.services.translation_cache import get_cache
from app.backend.utils.translation_helpers import translate_blocks_batch

logger = logging.getLogger(__name__)

# Lazy-loaded OpenCC converter for Simplified to Traditional Chinese
_opencc_s2t = None


def _ensure_opencc_s2t():
    """Lazily initialize OpenCC converter."""
    global _opencc_s2t
    if _opencc_s2t is None:
        try:
            from opencc import OpenCC
            _opencc_s2t = OpenCC('s2t')
            logger.debug("OpenCC s2t converter initialized")
        except ImportError:
            logger.warning("OpenCC not installed, Traditional Chinese conversion disabled")
            _opencc_s2t = False  # Mark as unavailable
    return _opencc_s2t if _opencc_s2t else None


def _convert_to_traditional(text: str) -> str:
    """Convert Simplified Chinese to Traditional Chinese using OpenCC.

    Args:
        text: Text that may contain Simplified Chinese characters.

    Returns:
        Text converted to Traditional Chinese, or original if conversion unavailable.
    """
    converter = _ensure_opencc_s2t()
    if converter:
        return converter.convert(text)
    return text


def _is_traditional_chinese_target(tgt: str) -> bool:
    """Check if target language is Traditional Chinese."""
    tgt_lower = tgt.lower()
    return 'traditional' in tgt_lower or tgt_lower in ('zh-tw', 'zh-hk', 'zh-hant')


def translate_texts(
    texts: List[str],
    targets: List[str],
    src_lang: Optional[str],
    client: OllamaClient,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
    stop_flag=None,
    log: Callable[[str], None] = lambda s: None,
) -> Tuple[Dict[Tuple[str, str], str], int, int, bool]:
    """Translate texts for all targets with character-based batching.

    Returns:
        (tmap, done_count, fail_count, stopped)
    """
    tmap: Dict[Tuple[str, str], str] = {}
    total = len(texts) * len(targets)
    done = 0
    fail_cnt = 0
    stopped = False
    cache = get_cache()
    cache_hits = 0

    for tgt in targets:
        if stop_flag and stop_flag.is_set():
            log(f"[STOP] Translation stopped at {done}/{total} segments")
            stopped = True
            break

        # Check if we need OpenCC conversion for Traditional Chinese
        needs_s2t_conversion = _is_traditional_chinese_target(tgt)

        # --- Cache lookup ---
        if cache is not None:
            cached = cache.get_batch(texts, tgt, src_lang or "auto", client.model)
            for src_text, cached_trans in cached.items():
                trans = _convert_to_traditional(cached_trans) if needs_s2t_conversion else cached_trans
                tmap[(tgt, src_text)] = trans
                done += 1
                cache_hits += 1
            texts_to_translate = [t for t in texts if t not in cached]
            if not texts_to_translate:
                log(f"[CACHE] {tgt}: all {len(cached)} from cache")
                continue
            log(f"[CACHE] {tgt}: {len(cached)} hits, {len(texts_to_translate)} to translate")
        else:
            texts_to_translate = texts

        if SENTENCE_MODE:
            # Progress callback: emit [TR] logs during batch processing
            batch_base = done

            def _on_batch_progress(batch_done: int) -> None:
                current = batch_base + batch_done
                if batch_done % 10 == 0 or current == total:
                    log(f"[TR] {current}/{total} {tgt} len=~")

            # Use character-based batching - translate_blocks_batch handles batching internally
            results = translate_blocks_batch(
                texts_to_translate, tgt, src_lang, client,
                max_batch_chars=max_batch_chars,
                progress_log=_on_batch_progress,
            )
            cache_entries: List[Tuple[str, str, str, str, str]] = []
            for text, (ok, res) in zip(texts_to_translate, results):
                done += 1
                if not ok:
                    fail_cnt += 1
                else:
                    # Store raw (pre-OpenCC) result in cache
                    cache_entries.append((text, tgt, src_lang or "auto", client.model, res))
                # Convert Simplified to Traditional if needed
                if ok and needs_s2t_conversion:
                    res = _convert_to_traditional(res)
                tmap[(tgt, text)] = res
                if done % 10 == 0 or done == total:
                    log(f"[TR] {done}/{total} {tgt} len={len(text)}")
            if cache is not None and cache_entries:
                cache.put_batch(cache_entries)
        else:
            for text in texts_to_translate:
                if stop_flag and stop_flag.is_set():
                    log(f"[STOP] Translation stopped at {done}/{total} segments")
                    stopped = True
                    break
                ok, res = client.translate_once(text, tgt, src_lang)
                if not ok:
                    res = f"[Translation failed|{tgt}] {text}"
                    fail_cnt += 1
                else:
                    if cache is not None:
                        cache.put(text, tgt, src_lang or "auto", client.model, res)
                # Convert Simplified to Traditional if needed
                if ok and needs_s2t_conversion:
                    res = _convert_to_traditional(res)
                done += 1
                tmap[(tgt, text)] = res
                if done % 10 == 0 or done == total:
                    log(f"[TR] {done}/{total} {tgt} len={len(text)}")
            if stopped:
                break

    if cache_hits > 0:
        log(f"[CACHE] total: {cache_hits} hits, {done - cache_hits} translated")

    return tmap, done, fail_cnt, stopped
