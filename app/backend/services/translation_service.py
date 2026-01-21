"""Shared translation routines."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import DEFAULT_MAX_BATCH_CHARS, SENTENCE_MODE
from app.backend.utils.translation_helpers import translate_block_sentencewise, translate_blocks_batch


def translate_texts(
    texts: List[str],
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
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

    for tgt in targets:
        if stop_flag and stop_flag.is_set():
            log(f"[STOP] Translation stopped at {done}/{total} segments")
            stopped = True
            break

        if SENTENCE_MODE:
            # Use character-based batching - translate_blocks_batch handles batching internally
            results = translate_blocks_batch(texts, tgt, src_lang, cache, client, max_batch_chars=max_batch_chars)
            for text, (ok, res) in zip(texts, results):
                done += 1
                if not ok:
                    fail_cnt += 1
                tmap[(tgt, text)] = res
                if done % 10 == 0 or done == total:
                    log(f"[TR] {done}/{total} {tgt} len={len(text)}")
        else:
            for text in texts:
                if stop_flag and stop_flag.is_set():
                    log(f"[STOP] Translation stopped at {done}/{total} segments")
                    stopped = True
                    break
                ok, res = client.translate_once(text, tgt, src_lang)
                if not ok:
                    res = f"[Translation failed|{tgt}] {text}"
                    fail_cnt += 1
                done += 1
                tmap[(tgt, text)] = res
                if done % 10 == 0 or done == total:
                    log(f"[TR] {done}/{total} {tgt} len={len(text)}")
            if stopped:
                break

    return tmap, done, fail_cnt, stopped
