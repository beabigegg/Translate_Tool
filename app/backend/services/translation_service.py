"""Shared translation routines."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Tuple

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import CROSS_MODEL_REFINEMENT_ENABLED, DEFAULT_MAX_BATCH_CHARS, REFINEMENT_MIN_CHARS, SENTENCE_MODE
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
    refine_client: Optional[OllamaClient] = None,
) -> Tuple[Dict[Tuple[str, str], str], int, int, bool]:
    """Translate texts for all targets with character-based batching.

    Returns:
        (tmap, done_count, fail_count, stopped)
    """
    tmap: Dict[Tuple[str, str], str] = {}
    cached_keys: set = set()  # (tgt, text) pairs from Phase-1 cache hit
    refine_cached_keys: set = set()  # (tgt, text) pairs with final refined result in cache — skip both phases
    total = len(texts) * len(targets)
    done = 0
    fail_cnt = 0
    stopped = False
    cache = get_cache()
    cache_hits = 0

    # Emit initial progress so frontend knows total segment count immediately
    log(f"[TR] 0/{total} - len=0")

    for tgt in targets:
        if stop_flag and stop_flag.is_set():
            log(f"[STOP] Translation stopped at {done}/{total} segments")
            stopped = True
            break

        # Check if we need OpenCC conversion for Traditional Chinese
        needs_s2t_conversion = _is_traditional_chinese_target(tgt)

        # --- Deduplicate + cache lookup ---
        # Count how many times each text appears (for correct progress counting)
        seen_texts: Dict[str, int] = {}
        for t in texts:
            seen_texts[t] = seen_texts.get(t, 0) + 1
        unique_input = list(seen_texts.keys())

        if cache is not None:
            # Check refiner cache first (final output) — skip both Phase 1 and Phase 2
            if refine_client is not None:
                refiner_cached = cache.get_batch(unique_input, tgt, src_lang or "auto", refine_client.cache_model_key)
                for src_text, cached_refined in refiner_cached.items():
                    trans = _convert_to_traditional(cached_refined) if needs_s2t_conversion else cached_refined
                    tmap[(tgt, src_text)] = trans
                    refine_cached_keys.add((tgt, src_text))
                    count = seen_texts[src_text]
                    done += count
                    cache_hits += count
                unique_input = [t for t in unique_input if (tgt, t) not in refine_cached_keys]

            # Check Phase-1 model cache for remaining texts
            cached = cache.get_batch(unique_input, tgt, src_lang or "auto", client.cache_model_key)
            for src_text, cached_trans in cached.items():
                trans = _convert_to_traditional(cached_trans) if needs_s2t_conversion else cached_trans
                tmap[(tgt, src_text)] = trans
                cached_keys.add((tgt, src_text))
                count = seen_texts[src_text]
                done += count
                cache_hits += count
            texts_to_translate = [t for t in unique_input if t not in cached]
            if not texts_to_translate and not any((tgt, t) in cached_keys for t in unique_input):
                log(f"[CACHE] {tgt}: all {len(texts)} from cache")
                continue
            if not texts_to_translate:
                log(f"[CACHE] {tgt}: all untranslated segments from Phase-1 cache, Phase 2 pending")
                continue
            uncached_segs = sum(seen_texts[t] for t in texts_to_translate)
            log(f"[CACHE] {tgt}: {cache_hits} hits, {uncached_segs} to translate ({len(texts_to_translate)} unique)")
        else:
            texts_to_translate = unique_input

        dedup_saved = sum(seen_texts[t] - 1 for t in texts_to_translate)
        if dedup_saved > 0:
            log(f"[DEDUP] {tgt}: {dedup_saved} duplicate segments skipped ({len(texts_to_translate)} unique)")

        if SENTENCE_MODE:
            # Progress callback: emit [TR] logs during batch processing
            batch_base = done

            def _on_batch_progress(batch_done: int) -> None:
                current = batch_base + batch_done
                if batch_done % 10 == 0 or current == total:
                    log(f"[TR] {current}/{total} {tgt} len=~")

            # Incremental cache write: each segment is cached as soon as it's translated
            incremental_cache_entries: List[Tuple[str, str, str, str, str]] = []

            def _on_segment_done(src_text: str, translated: str) -> None:
                """Cache each segment immediately so interrupted jobs still benefit."""
                incremental_cache_entries.append(
                    (src_text, tgt, src_lang or "auto", client.cache_model_key, translated)
                )
                # Flush to DB every 10 segments to balance I/O and safety
                if cache is not None and len(incremental_cache_entries) >= 10:
                    cache.put_batch(incremental_cache_entries[:])
                    incremental_cache_entries.clear()

            # Use character-based batching - translate_blocks_batch handles batching internally
            results = translate_blocks_batch(
                texts_to_translate, tgt, src_lang, client,
                max_batch_chars=max_batch_chars,
                progress_log=_on_batch_progress,
                log=log,
                on_segment_done=_on_segment_done,
            )
            # Flush remaining cache entries
            if cache is not None and incremental_cache_entries:
                cache.put_batch(incremental_cache_entries)

            # Build map from unique translated texts
            for text, (ok, res) in zip(texts_to_translate, results):
                if not ok:
                    fail_cnt += 1
                # Convert Simplified to Traditional if needed
                if ok and needs_s2t_conversion:
                    res = _convert_to_traditional(res)
                tmap[(tgt, text)] = res

            # Count all segments (unique + duplicates) as done
            done += len(texts_to_translate) + dedup_saved
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
                        cache.put(text, tgt, src_lang or "auto", client.cache_model_key, res)
                # Convert Simplified to Traditional if needed
                if ok and needs_s2t_conversion:
                    res = _convert_to_traditional(res)
                done += seen_texts.get(text, 1)  # Count duplicates
                tmap[(tgt, text)] = res
                if done % 10 == 0 or done == total:
                    log(f"[TR] {done}/{total} {tgt} len={len(text)}")
            if stopped:
                break

    if cache_hits > 0:
        log(f"[CACHE] total: {cache_hits} hits, {done - cache_hits} translated")

    # Phase 2: Cross-model refinement (HY-MT → Qwen polish pass)
    if refine_client is not None and CROSS_MODEL_REFINEMENT_ENABLED and not stopped:
        # Evict primary model from VRAM before loading refiner
        client.unload_model()

        # Deferred context detection: run now that primary VRAM is free.
        # Orchestrator sets _deferred_context_sample on refine_client when the
        # primary is a dedicated translation model (e.g. HY-MT).
        _ctx_sample = getattr(refine_client, "_deferred_context_sample", None)
        if _ctx_sample:
            _ctx_profile = getattr(refine_client, "_deferred_context_profile", "general")
            _ctx_target = getattr(refine_client, "_deferred_context_target", targets[0] if targets else "")
            _detect_prompt = (
                "以下是一份文件的開頭內容，請用一句話描述這份文件的類型、所屬領域和主題。"
                "只輸出描述，不要解釋。\n\n" + _ctx_sample
            )
            _payload = refine_client._build_no_system_payload(_detect_prompt)
            try:
                _ok, _ctx = refine_client._call_ollama(_payload)
                if _ok and _ctx.strip():
                    _ctx = _ctx.strip()[:200]
                    log(f"[REFINE] Context detected: {_ctx}")
                    from app.backend.clients.ollama_client import OllamaClient as _OC
                    _base = _OC._build_refine_system_prompt(_ctx_target, _ctx_profile)
                    refine_client.system_prompt = f"{_base}\n\nDocument context: {_ctx}"
            except Exception:
                pass
            refine_client._deferred_context_sample = None

        refine_total = sum(
            1 for tgt in targets
            for text in texts
            if (tgt, text) in tmap
            and (tgt, text) not in refine_cached_keys
            and len(text) >= REFINEMENT_MIN_CHARS
        )
        refine_done = 0
        refine_cache_entries: List[Tuple[str, str, str, str, str]] = []
        log(f"[REFINE] Phase 2: refining {refine_total} segments with {refine_client.model}")
        for tgt in targets:
            for text in texts:
                if (tgt, text) not in tmap:
                    continue
                if (tgt, text) in refine_cached_keys:
                    continue
                if len(text) < REFINEMENT_MIN_CHARS:
                    continue
                draft = tmap[(tgt, text)]
                ok, refined = refine_client.refine_translation(text, draft, tgt, src_lang)
                if ok:
                    tmap[(tgt, text)] = refined
                    # Cache the final refined result for future runs
                    refine_cache_entries.append(
                        (text, tgt, src_lang or "auto", refine_client.cache_model_key, refined)
                    )
                    if cache is not None and len(refine_cache_entries) >= 10:
                        cache.put_batch(refine_cache_entries[:])
                        refine_cache_entries.clear()
                refine_done += 1
                if refine_done % 10 == 0 or refine_done == refine_total:
                    log(f"[REFINE] {refine_done}/{refine_total}")
        if cache is not None and refine_cache_entries:
            cache.put_batch(refine_cache_entries)

    return tmap, done, fail_cnt, stopped
