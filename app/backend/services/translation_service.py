"""Shared translation routines."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

from app.backend.clients.base_llm_client import LLMClient
from app.backend.config import (
    CHUNK_OVERLAP_TOKENS,
    CRITIQUE_LOOP_ENABLED,
    CRITIQUE_MAX_ITERATIONS,
    CRITIQUE_TIMEOUT_SECONDS,
    DEFAULT_MAX_BATCH_CHARS,
    SENTENCE_MODE,
)
from app.backend.services.context_prompts import (
    apply_glossary_substitution,
    compute_glossary_match_rate,
)
from app.backend.services.metrics import (
    record_critique_iteration,
    record_critique_loop_invocation,
    record_translation,
    set_glossary_match_rate,
)
from app.backend.services.translation_cache import get_cache
from app.backend.utils.translation_helpers import translate_blocks_batch

if TYPE_CHECKING:
    from app.backend.models.term import Term
    from app.backend.models.translatable_document import TranslatableDocument, TranslatableElement

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
    client: LLMClient,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
    stop_flag=None,
    log: Callable[[str], None] = lambda s: None,
    terms: "Optional[List[Term]]" = None,
) -> Tuple[Dict[Tuple[str, str], str], int, int, bool]:
    """Translate texts for all targets with character-based batching.

    Args:
        texts: Source text segments to translate.
        targets: Target language codes.
        src_lang: Source language code (or None / "auto").
        client: Primary LLM client.
        max_batch_chars: Character batching budget.
        stop_flag: Optional threading.Event for cancellation.
        log: Progress log callback.
        terms: Optional list of Term objects for glossary enforcement and
               critique loop context (BR-41, BR-44).

    Returns:
        (tmap, done_count, fail_count, stopped)
    """
    tmap: Dict[Tuple[str, str], str] = {}
    cached_keys: set = set()  # (tgt, text) pairs from Phase-1 cache hit
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
            # Check Phase-1 model cache
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
                log(f"[CACHE] {tgt}: all segments from Phase-1 cache")
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
            _batch_t0 = time.monotonic()
            results = translate_blocks_batch(
                texts_to_translate, tgt, src_lang, client,
                max_batch_chars=max_batch_chars,
                progress_log=_on_batch_progress,
                log=log,
                on_segment_done=_on_segment_done,
                stop_flag=stop_flag,
            )
            _batch_elapsed_ms = (time.monotonic() - _batch_t0) * 1000.0
            # Flush remaining cache entries
            if cache is not None and incremental_cache_entries:
                cache.put_batch(incremental_cache_entries)

            # Build map from unique translated texts
            _batch_n = max(len(texts_to_translate), 1)
            _per_item_ms = _batch_elapsed_ms / _batch_n
            for text, (ok, res) in zip(texts_to_translate, results):
                if not ok:
                    res = f"[Translation failed|{tgt}] {text}"
                    fail_cnt += 1
                # Metrics hook (BR-21, BR-22, BR-23): one record per completed call.
                # record_translation(failed=True) already increments provider_failure_count,
                # so no separate record_provider_failure() call is needed here.
                try:
                    record_translation(_per_item_ms, failed=not ok)
                except Exception:
                    pass  # instrumentation must never break translation
                # Convert Simplified to Traditional if needed
                if ok and needs_s2t_conversion:
                    res = _convert_to_traditional(res)
                tmap[(tgt, text)] = res
                done += seen_texts.get(text, 1)  # Count duplicates per segment
            if stop_flag and stop_flag.is_set():
                stopped = True
            if stopped:
                break
        else:
            for text in texts_to_translate:
                if stop_flag and stop_flag.is_set():
                    log(f"[STOP] Translation stopped at {done}/{total} segments")
                    stopped = True
                    break
                _t0 = time.monotonic()
                ok, res = client.translate_once(text, tgt, src_lang)
                _elapsed_ms = (time.monotonic() - _t0) * 1000.0
                # Metrics hook (BR-21, BR-22, BR-23): one record per completed call.
                # record_translation(failed=True) already increments provider_failure_count,
                # so no separate record_provider_failure() call is needed here.
                try:
                    record_translation(_elapsed_ms, failed=not ok)
                except Exception:
                    pass  # instrumentation must never break translation
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

    # ---------------------------------------------------------------------------
    # Critique loop (p2-prompt-fewshot-glossary, BR-44, Table M)
    # Runs per translatable unit (segment), ≥1 iteration, bounded by caps.
    # Degrades to last valid draft on exception/timeout — never fails the job.
    # ---------------------------------------------------------------------------
    _active_terms = terms or []
    if CRITIQUE_LOOP_ENABLED and tmap and not stopped:
        try:
            record_critique_loop_invocation()
        except Exception:
            pass  # metrics must never break translation

        _critique_iter_count = 0
        for _key in list(tmap.keys()):
            _tgt, _src_text = _key
            _current_draft = tmap[_key]
            # Skip failure placeholders
            if _current_draft.startswith("[Translation failed|"):
                continue
            # Run the bounded critique iterations for this segment
            _segment_iters = 0
            for _iter in range(max(1, CRITIQUE_MAX_ITERATIONS)):
                _iter_start = time.monotonic()
                try:
                    _critique_prompt = (
                        f"Review and improve this translation.\n"
                        f"Source: {_src_text}\n"
                        f"Draft: {_current_draft}\n"
                        f"Output ONLY the improved translation:"
                    )
                    _elapsed = time.monotonic() - _iter_start
                    if _elapsed >= CRITIQUE_TIMEOUT_SECONDS:
                        logger.warning(
                            "[CRITIQUE] Timeout budget exhausted before call for segment len=%d",
                            len(_src_text),
                        )
                        break
                    _ok, _revised = client.translate_once(_critique_prompt, _tgt, src_lang)
                    _call_elapsed = time.monotonic() - _iter_start
                    if _call_elapsed >= CRITIQUE_TIMEOUT_SECONDS:
                        logger.warning(
                            "[CRITIQUE] Call exceeded timeout (%.1fs) for segment len=%d; keeping draft",
                            _call_elapsed,
                            len(_src_text),
                        )
                        break
                    if _ok and _revised and not _revised.startswith("[Translation failed|"):
                        _current_draft = _revised
                        _segment_iters += 1
                except Exception as exc:
                    logger.warning(
                        "[CRITIQUE] Exception during critique iteration %d: %s; keeping last draft",
                        _iter + 1,
                        exc,
                    )
                    break
            tmap[_key] = _current_draft
            _critique_iter_count += _segment_iters

        try:
            record_critique_iteration(_critique_iter_count)
        except Exception:
            pass

    # ---------------------------------------------------------------------------
    # Deterministic glossary substitution + match rate (BR-41, IP-5)
    # Applied to final draft after critique loop.
    # ---------------------------------------------------------------------------
    if _active_terms and tmap and not stopped:
        _all_rates: list = []
        for _key in list(tmap.keys()):
            _tgt, _src_text = _key
            _draft = tmap[_key]
            if _draft.startswith("[Translation failed|"):
                continue
            try:
                _draft = apply_glossary_substitution(_draft, _src_text, _active_terms)
                tmap[_key] = _draft
                _rate = compute_glossary_match_rate(_draft, _src_text, _active_terms)
                _all_rates.append(_rate)
            except Exception as exc:
                logger.warning("[GLOSSARY] Substitution error for segment: %s", exc)
        if _all_rates:
            try:
                set_glossary_match_rate(sum(_all_rates) / len(_all_rates))
            except Exception:
                pass
        else:
            try:
                set_glossary_match_rate(1.0)
            except Exception:
                pass

    return tmap, done, fail_cnt, stopped


# ---------------------------------------------------------------------------
# Doc2Doc entry point (p2-long-doc-chunking, BR-47..BR-53, AC-4, AC-6, AC-7)
# ---------------------------------------------------------------------------

def translate_document(
    doc: "TranslatableDocument",
    targets: List[str],
    src_lang: Optional[str],
    client: LLMClient,
    num_ctx: int = 4096,
    overlap_tokens: Optional[int] = None,
    stop_flag=None,
    log: Callable[[str], None] = lambda s: None,
    terms: "Optional[List[Term]]" = None,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
) -> "TranslatableDocument":
    """Translate a complete TranslatableDocument, chunking automatically when needed.

    Implements the Doc2Doc service entry point (data-shape §Doc2Doc contract).
    Splits the document into chunks per BR-47..BR-52, translates each chunk
    independently with one LLM call per chunk (AC-4), then reassembles in order
    (AC-5) with overlap de-duplication (data-shape §Reassembly contract).

    Args:
        doc: Fully parsed TranslatableDocument (translated_content fields may be null).
        targets: Target language codes.
        src_lang: Source language code or None (auto-detect).
        client: Primary LLM client.
        num_ctx: Resolved LLM context window size (token ceiling per chunk, BR-49).
        overlap_tokens: Override for CHUNK_OVERLAP_TOKENS env default (BR-47).
        stop_flag: Optional threading.Event for job cancellation.
        log: Progress log callback.
        terms: Optional list of Term objects for glossary injection.
        max_batch_chars: Character batching budget passed to translate_blocks_batch.

    Returns:
        The same TranslatableDocument instance with translated_content populated
        in-place on every element that has should_translate=True (mutation in place,
        same object reference returned — data-shape Doc2Doc contract).

    Raises:
        Exception: When a chunk translation fails and no retry strategy is configured
                   (job transitions to failed per BR-51, BR-7).
    """
    from app.backend.models.translatable_document import TranslatableDocument as _TD
    from app.backend.services.doc_chunker import (
        ChunkRecord,
        reassemble_document,
        split_document,
    )

    _overlap = overlap_tokens if overlap_tokens is not None else CHUNK_OVERLAP_TOKENS

    # Split document into chunks (BR-47..BR-52)
    chunks = split_document(doc, num_ctx=num_ctx, overlap_tokens=_overlap)

    if not chunks:
        # Empty document: return unchanged (data-shape §Invalid-data-behavior)
        log("[DOC2DOC] Empty document — no chunks; returning unchanged")
        return doc

    log(f"[DOC2DOC] {len(chunks)} chunk(s) for doc with {len(doc.elements)} elements")

    any_chunk_failed = False
    chunk_errors: List[Tuple[int, Exception]] = []

    for chunk in sorted(chunks, key=lambda c: c.chunk_index):
        # Collect texts for this chunk's translatable elements
        chunk_texts = [
            e.content for e in chunk.elements if e.should_translate and e.content.strip()
        ]

        if not chunk_texts:
            # Chunk has no translatable content — mark empty-string translations
            for elem in chunk.elements:
                if elem.should_translate and elem.translated_content is None:
                    elem.translated_content = ""
            log(f"[DOC2DOC] chunk {chunk.chunk_index}: no translatable texts; skipped")
            continue

        log(f"[DOC2DOC] translating chunk {chunk.chunk_index} ({len(chunk_texts)} texts)")

        for tgt in targets:
            if stop_flag and stop_flag.is_set():
                log(f"[DOC2DOC] stop flag set; halting at chunk {chunk.chunk_index} target {tgt}")
                break

            try:
                results = translate_blocks_batch(
                    chunk_texts,
                    tgt,
                    src_lang,
                    client,
                    max_batch_chars=max_batch_chars,
                    log=log,
                    stop_flag=stop_flag,
                )
            except Exception as exc:
                # BR-51: chunk failure surfaced; set BR-25 placeholder on all elements in chunk
                logger.warning(
                    "[DOC2DOC] chunk %d target %s raised exception: %s",
                    chunk.chunk_index,
                    tgt,
                    exc,
                )
                for elem in chunk.elements:
                    if elem.should_translate:
                        placeholder = f"[Translation failed|{tgt}] {elem.content}"
                        elem.translated_content = placeholder
                any_chunk_failed = True
                chunk_errors.append((chunk.chunk_index, exc))
                continue

            # Map results back to elements (same order as chunk_texts)
            text_iter = iter(results)
            for elem in chunk.elements:
                if not elem.should_translate or not elem.content.strip():
                    continue
                try:
                    ok, translated = next(text_iter)
                except StopIteration:
                    # Fewer results than texts — treat as failure for remaining
                    ok, translated = False, ""

                if ok:
                    elem.translated_content = translated
                else:
                    # BR-51, BR-25: set failure placeholder on failed element
                    placeholder = f"[Translation failed|{tgt}] {elem.content}"
                    elem.translated_content = placeholder
                    any_chunk_failed = True
                    logger.warning(
                        "[DOC2DOC] chunk %d element %s failed (target=%s)",
                        chunk.chunk_index,
                        elem.element_id,
                        tgt,
                    )

    # Reassemble in chunk_index order with overlap de-duplication
    # (data-shape §Reassembly contract)
    reassemble_document(doc, chunks)

    log(f"[DOC2DOC] reassembly complete; {len(doc.elements)} elements in output")

    # BR-51, BR-7: if any chunk failed, surface the error so the job transitions to failed
    if any_chunk_failed and chunk_errors:
        first_idx, first_exc = chunk_errors[0]
        raise RuntimeError(
            f"[DOC2DOC] Translation failed on chunk {first_idx}: {first_exc}; "
            f"job transitions to failed (BR-51). "
            f"Failed elements carry BR-25 placeholders."
        ) from first_exc

    return doc


# ---------------------------------------------------------------------------
# Cell-batch seam (p3-table-structure, D6, BR-68..BR-70)
# ---------------------------------------------------------------------------

def translate_table_cells(
    element: "TranslatableElement",
    targets: List[str],
    src_lang: Optional[str],
    client: LLMClient,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
    stop_flag=None,
    log: Callable[[str], None] = lambda s: None,
) -> None:
    """Translate the cells of a structured table element in-place (D6, BR-69, BR-70).

    This is the cell-batch seam for table-typed TranslatableElements that carry
    a recognized TableStructure in metadata["table_structure"].

    Each table's translatable cells (is_numeric=False, content != "") are sent to
    the LLM in exactly ONE batch call per table (BR-69).  Numeric cells get
    translation_status="passthrough" and translated_content=content (BR-68).
    Empty cells get translation_status="skipped" and translated_content="".
    Batch failure applies the BR-25 placeholder to all failed cells.

    After all cells are resolved, sets element.translated_content to the D3
    reconstruction: tab-separated within a row, newline-separated between rows,
    row-major over num_rows × num_cols.  Merged-cell text is emitted at the
    origin (row, col); spanned positions emit empty string.

    Args:
        element: A table-typed TranslatableElement with metadata["table_structure"].
        targets: Target language codes (translation applied for each target in order;
                 last target's cell translations win for cell-level state).
        src_lang: Source language code or None.
        client: LLM client for batch translation.
        max_batch_chars: Character batching budget.
        stop_flag: Optional threading.Event for job cancellation.
        log: Progress log callback.

    Raises:
        KeyError: When metadata["table_structure"] is absent (caller must check).
    """
    from app.backend.models.translatable_document import TableStructure

    ts_dict = element.metadata.get("table_structure")
    if ts_dict is None:
        log(f"[CELL-BATCH] element {element.element_id}: no table_structure in metadata; skipping")
        return

    ts = TableStructure.from_dict(ts_dict)
    if not ts.cells:
        element.translated_content = ""
        return

    for tgt in targets:
        if stop_flag and stop_flag.is_set():
            log(f"[CELL-BATCH] stop flag set; halting at target {tgt}")
            break

        # Partition cells into translatable / numeric / empty
        translatable_cells = []
        translatable_indices = []
        for idx, cell in enumerate(ts.cells):
            if not cell.content:  # empty
                cell.translated_content = ""
                cell.translation_status = "skipped"
            elif cell.is_numeric:  # numeric passthrough (BR-68)
                cell.translated_content = cell.content
                cell.translation_status = "passthrough"
            else:
                translatable_cells.append(cell)
                translatable_indices.append(idx)

        if not translatable_cells:
            # All-numeric or all-empty — no LLM call needed
            log(f"[CELL-BATCH] element {element.element_id}: no translatable cells for {tgt}")
        else:
            # Coalesce into exactly one batch call (BR-69)
            batch_texts = [c.content for c in translatable_cells]
            try:
                results = translate_blocks_batch(
                    batch_texts,
                    tgt,
                    src_lang,
                    client,
                    max_batch_chars=max_batch_chars,
                    stop_flag=stop_flag,
                    log=log,
                )
                for batch_pos, (ok, translated) in enumerate(results):
                    cell = translatable_cells[batch_pos]
                    if ok:
                        cell.translated_content = translated
                        cell.translation_status = "translated"
                    else:
                        # BR-25 placeholder + failed status
                        cell.translated_content = f"[Translation failed|{tgt}] {cell.content}"
                        cell.translation_status = "failed"
            except Exception as exc:
                logger.warning(
                    "[CELL-BATCH] element %s batch failed (target=%s): %s; applying BR-25 placeholders",
                    element.element_id,
                    tgt,
                    exc,
                )
                for cell in translatable_cells:
                    cell.translated_content = f"[Translation failed|{tgt}] {cell.content}"
                    cell.translation_status = "failed"

    # Write updated cells back into metadata (in-place mutation of the dict)
    element.metadata["table_structure"] = ts.to_dict()

    # D3 reconstruction: tab-separated within row, newline-separated between rows (NORMATIVE)
    # Build num_rows × num_cols grid; fill from cells at their (row, col) origin.
    grid: List[List[str]] = [
        ["" for _ in range(ts.num_cols)] for _ in range(ts.num_rows)
    ]
    for cell in ts.cells:
        r, c = cell.row, cell.col
        if 0 <= r < ts.num_rows and 0 <= c < ts.num_cols:
            text = cell.translated_content if cell.translated_content is not None else cell.content
            grid[r][c] = text

    rows_str = ["\t".join(row) for row in grid]
    element.translated_content = "\n".join(rows_str)
