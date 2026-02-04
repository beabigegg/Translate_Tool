"""Translation helper utilities."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import (
    BATCH_SEPARATOR,
    DEFAULT_MAX_BATCH_CHARS,
    MAX_MAX_BATCH_CHARS,
    MAX_PARAGRAPH_CHARS,
    MIN_MAX_BATCH_CHARS,
    TRANSLATION_GRANULARITY,
    USE_MERGED_CONTEXT,
)
from app.backend.utils.logging_utils import logger
from app.backend.utils.text_utils import is_cjk_language, split_sentences

# Segment marker for merged paragraph translation
SEGMENT_MARKER_PREFIX = "<<<SEG_"
SEGMENT_MARKER_SUFFIX = ">>>"


def _get_sentence_joiner(target_lang: str) -> str:
    """Get the appropriate sentence joiner based on target language.

    CJK languages don't use spaces between sentences.
    """
    return "" if is_cjk_language(target_lang) else " "


def _build_segment_marker(index: int) -> str:
    """Build a segment marker for the given index."""
    return f"{SEGMENT_MARKER_PREFIX}{index}{SEGMENT_MARKER_SUFFIX}"


def _merge_texts_with_markers(texts: List[str], max_chars: int = MAX_PARAGRAPH_CHARS) -> List[Tuple[str, List[int]]]:
    """Merge multiple texts with segment markers, staying under character limit.

    Args:
        texts: List of text segments to merge.
        max_chars: Maximum characters per merged batch.

    Returns:
        List of tuples: (merged_text, list_of_original_indices).
    """
    if not texts:
        return []

    merged_batches: List[Tuple[str, List[int]]] = []
    current_batch: List[str] = []
    current_indices: List[int] = []
    current_length = 0

    for i, text in enumerate(texts):
        if not text or not text.strip():
            continue

        marker = _build_segment_marker(len(current_indices))
        segment = f"{marker}\n{text}"
        segment_length = len(segment) + 1  # +1 for newline separator

        # Check if adding this segment would exceed limit
        if current_batch and (current_length + segment_length > max_chars):
            # Flush current batch
            merged_text = "\n".join(current_batch)
            merged_batches.append((merged_text, current_indices.copy()))
            current_batch = []
            current_indices = []
            current_length = 0
            # Reset marker for new batch
            marker = _build_segment_marker(0)
            segment = f"{marker}\n{text}"
            segment_length = len(segment)

        current_batch.append(segment)
        current_indices.append(i)
        current_length += segment_length

    # Flush remaining
    if current_batch:
        merged_text = "\n".join(current_batch)
        merged_batches.append((merged_text, current_indices))

    return merged_batches


def _parse_merged_response(response: str, expected_count: int) -> List[str]:
    """Parse merged translation response using segment markers.

    Args:
        response: Translation response with segment markers.
        expected_count: Expected number of segments.

    Returns:
        List of translated segments.
    """
    results = [""] * expected_count

    # Pattern to match segment markers and capture content
    pattern = rf'{SEGMENT_MARKER_PREFIX}(\d+){SEGMENT_MARKER_SUFFIX}\s*(.*?)(?={SEGMENT_MARKER_PREFIX}|\Z)'
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        for idx_str, content in matches:
            try:
                idx = int(idx_str)
                if 0 <= idx < expected_count:
                    results[idx] = content.strip()
            except ValueError:
                continue

    # If no markers found, try splitting by double newlines as fallback
    if not any(results):
        parts = [p.strip() for p in response.split("\n\n") if p.strip()]
        if len(parts) == expected_count:
            return parts
        # Single text fallback
        if expected_count == 1:
            return [response.strip()]

    return results


def translate_merged_paragraphs(
    texts: List[str],
    tgt: str,
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    max_chars: int = MAX_PARAGRAPH_CHARS,
) -> List[Tuple[bool, str]]:
    """Translate multiple texts by merging them for better context preservation.

    This function merges multiple paragraphs into batches (staying under max_chars),
    translates them together to preserve context, then splits results back.

    Args:
        texts: List of texts to translate.
        tgt: Target language.
        src_lang: Source language.
        cache: Translation cache.
        client: Ollama client.
        max_chars: Maximum characters per merged batch.

    Returns:
        List of (success, translated_text) tuples.
    """
    if not texts:
        return []

    src_key = (src_lang or "auto").lower()
    results: List[Tuple[bool, str]] = [(False, "")] * len(texts)

    # Check cache for all texts first
    uncached_indices: List[int] = []
    uncached_texts: List[str] = []

    for i, text in enumerate(texts):
        if not text or not text.strip():
            results[i] = (True, "")
            continue

        cached = cache.get(src_key, tgt, text)
        if cached is not None:
            results[i] = (True, cached)
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    if not uncached_texts:
        return results

    # Merge uncached texts into batches
    merged_batches = _merge_texts_with_markers(uncached_texts, max_chars)
    logger.debug(
        "Merged %d texts into %d batches for context-aware translation",
        len(uncached_texts), len(merged_batches)
    )

    # Track which uncached index we're at
    uncached_offset = 0

    # Translate each merged batch
    for merged_text, local_indices in merged_batches:
        batch_size = len(local_indices)

        # Add marker preservation instruction to the text
        instruction = (
            "IMPORTANT: Keep the <<<SEG_N>>> markers in your output.\n"
            "Translate each segment while preserving the markers.\n\n"
        )
        augmented_text = instruction + merged_text

        ok, response = client.translate_once(augmented_text, tgt, src_lang)

        if ok:
            # Parse response to extract individual translations
            translated_parts = _parse_merged_response(response, batch_size)

            for local_idx, translation in enumerate(translated_parts):
                original_idx = uncached_indices[uncached_offset + local_idx]
                original_text = texts[original_idx]

                if translation:
                    results[original_idx] = (True, translation)
                    cache.put(src_key, tgt, original_text, translation)
                else:
                    # Fallback: translate individually
                    fallback_ok, fallback_result = client.translate_once(original_text, tgt, src_lang)
                    if fallback_ok:
                        results[original_idx] = (True, fallback_result)
                        cache.put(src_key, tgt, original_text, fallback_result)
                    else:
                        results[original_idx] = (False, f"[翻譯失敗] {original_text[:30]}...")
        else:
            # Batch failed, fallback to individual translation
            logger.warning("Merged translation failed, falling back to individual")
            for local_idx in range(batch_size):
                original_idx = uncached_indices[uncached_offset + local_idx]
                original_text = texts[original_idx]
                fallback_ok, fallback_result = client.translate_once(original_text, tgt, src_lang)
                if fallback_ok:
                    results[original_idx] = (True, fallback_result)
                    cache.put(src_key, tgt, original_text, fallback_result)
                else:
                    results[original_idx] = (False, f"[翻譯失敗] {original_text[:30]}...")

        uncached_offset += batch_size

    return results


def translate_block_as_paragraph(
    text: str,
    tgt: str,
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
) -> Tuple[bool, str]:
    """Translate entire text block as a single unit, preserving context.

    This is the recommended approach for better translation quality.
    Falls back to chunked translation for very long texts.

    Args:
        text: Text to translate.
        tgt: Target language.
        src_lang: Source language (or None for auto-detect).
        cache: Translation cache.
        client: Ollama client.

    Returns:
        Tuple of (success, translated_text).
    """
    if not text or not text.strip():
        return True, ""

    src_key = (src_lang or "auto").lower()

    # Check cache first
    cached = cache.get(src_key, tgt, text)
    if cached is not None:
        return True, cached

    # If text is within reasonable length, translate as whole
    if len(text) <= MAX_PARAGRAPH_CHARS:
        ok, result = client.translate_once(text, tgt, src_lang)
        if ok:
            cache.put(src_key, tgt, text, result)
        return ok, result

    # For very long texts, split by paragraphs (double newlines) or sentences
    logger.debug(f"Text too long ({len(text)} chars), splitting for translation")

    # Try splitting by double newlines first (paragraph boundaries)
    if "\n\n" in text:
        chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    else:
        # Fall back to splitting by newlines
        chunks = [chunk.strip() for chunk in text.split("\n") if chunk.strip()]

    # If chunks are still too long, use sentence splitting
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= MAX_PARAGRAPH_CHARS:
            final_chunks.append(chunk)
        else:
            # Split by sentences for very long chunks
            sentences = split_sentences(chunk, src_lang) or [chunk]
            final_chunks.extend(sentences)

    # Translate each chunk
    translated_chunks = []
    all_ok = True
    for chunk in final_chunks:
        # Check cache for chunk
        cached_chunk = cache.get(src_key, tgt, chunk)
        if cached_chunk is not None:
            translated_chunks.append(cached_chunk)
            continue

        ok, result = client.translate_once(chunk, tgt, src_lang)
        if ok:
            cache.put(src_key, tgt, chunk, result)
            translated_chunks.append(result)
        else:
            all_ok = False
            translated_chunks.append(f"[翻譯失敗] {chunk[:30]}...")

    # Join with appropriate separator
    joiner = "\n\n" if "\n\n" in text else "\n"
    final_result = joiner.join(translated_chunks)

    # Cache the full result if all chunks succeeded
    if all_ok:
        cache.put(src_key, tgt, text, final_result)

    return all_ok, final_result


def translate_block_sentencewise(
    text: str,
    tgt: str,
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
) -> Tuple[bool, str]:
    if not text or not text.strip():
        return True, ""
    src_key = (src_lang or "auto").lower()
    cached_whole = cache.get(src_key, tgt, text)
    if cached_whole is not None:
        return True, cached_whole

    out_lines: List[str] = []
    all_ok = True

    for raw_line in text.split("\n"):
        if not raw_line.strip():
            out_lines.append("")
            continue
        sentences = split_sentences(raw_line, src_lang) or [raw_line]
        parts = []
        for sentence in sentences:
            cached = cache.get(src_key, tgt, sentence)
            if cached is not None:
                parts.append(cached)
                continue
            ok, ans = client.translate_once(sentence, tgt, src_lang)
            if not ok:
                all_ok = False
                ans = f"[Translation failed|{tgt}] {sentence}"
            else:
                cache.put(src_key, tgt, sentence, ans)
            parts.append(ans)
        joiner = _get_sentence_joiner(tgt)
        out_lines.append(joiner.join(parts))

    final = "\n".join(out_lines)
    if all_ok:
        cache.put(src_key, tgt, text, final)
    return all_ok, final


class BatchTranslator:
    """Batch translation manager that collects segments and translates them in batches.

    Uses character-based batching to optimize for large context windows (~128K tokens).
    """

    def __init__(
        self,
        client: OllamaClient,
        cache: TranslationCache,
        max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
        tgt: str = "",
        src_lang: Optional[str] = None,
    ) -> None:
        self.client = client
        self.cache = cache
        self.max_batch_chars = max(MIN_MAX_BATCH_CHARS, min(max_batch_chars, MAX_MAX_BATCH_CHARS))
        self.tgt = tgt
        self.src_lang = src_lang
        self._pending: List[Tuple[str, int]] = []
        self._pending_chars: int = 0
        self._results: Dict[int, Tuple[bool, str]] = {}
        self._next_index = 0

    def _get_src_key(self) -> str:
        return (self.src_lang or "auto").lower()

    def add(self, text: str) -> int:
        idx = self._next_index
        self._next_index += 1
        if not text or not text.strip():
            self._results[idx] = (True, "")
            return idx
        cached = self.cache.get(self._get_src_key(), self.tgt, text)
        if cached is not None:
            self._results[idx] = (True, cached)
            return idx

        text_chars = len(text)
        # Flush if adding this text would exceed character limit
        if self._pending and (self._pending_chars + text_chars > self.max_batch_chars):
            self.flush()

        self._pending.append((text, idx))
        self._pending_chars += text_chars
        return idx

    def flush(self) -> None:
        if not self._pending:
            return
        texts: List[str] = [text for text, _ in self._pending]
        total_chars = self._pending_chars
        if hasattr(self.client, "translate_batch"):
            ok, results = self.client.translate_batch(texts, self.tgt, self.src_lang)
            if ok and len(results) == len(texts):
                for i, (text, idx) in enumerate(self._pending):
                    self._results[idx] = (True, results[i])
                    self.cache.put(self._get_src_key(), self.tgt, text, results[i])
                logger.debug("Batch translation succeeded: %s segments, %s chars", len(texts), total_chars)
            else:
                logger.warning("Batch translation failed, falling back: %s segments, %s chars", len(texts), total_chars)
                self._fallback_individual()
        else:
            self._fallback_individual()
        self._pending.clear()
        self._pending_chars = 0

    def _fallback_individual(self) -> None:
        for text, idx in self._pending:
            ok, ans = self.client.translate_once(text, self.tgt, self.src_lang)
            if not ok:
                ans = f"[Translation failed|{self.tgt}] {text}"
            else:
                self.cache.put(self._get_src_key(), self.tgt, text, ans)
            self._results[idx] = (ok, ans)

    def get(self, idx: int) -> Tuple[bool, str]:
        if idx not in self._results:
            self.flush()
        return self._results.get(idx, (False, "[Missing translation result]"))

    def translate_all(self, texts: List[str]) -> List[Tuple[bool, str]]:
        indices = [self.add(text) for text in texts]
        self.flush()
        return [self.get(idx) for idx in indices]


def translate_blocks_batch(
    texts: List[str],
    tgt: str,
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
    granularity: Optional[str] = None,
    use_merged_context: Optional[bool] = None,
) -> List[Tuple[bool, str]]:
    """Batch translate multiple text blocks.

    Args:
        texts: List of texts to translate.
        tgt: Target language.
        src_lang: Source language.
        cache: Translation cache.
        client: Ollama client.
        max_batch_chars: Maximum characters per batch.
        granularity: Translation granularity ("sentence" or "paragraph").
                    None uses config default (TRANSLATION_GRANULARITY).
        use_merged_context: If True, merge multiple paragraphs for context-aware
                           translation (within MAX_PARAGRAPH_CHARS limit).

    Returns:
        List of (success, translated_text) tuples.
    """
    if not texts:
        return []

    # Determine granularity and merged context settings
    use_granularity = granularity if granularity is not None else TRANSLATION_GRANULARITY
    enable_merged = use_merged_context if use_merged_context is not None else USE_MERGED_CONTEXT

    # For single text, use appropriate method based on granularity
    if len(texts) == 1:
        if use_granularity == "paragraph":
            return [translate_block_as_paragraph(texts[0], tgt, src_lang, cache, client)]
        else:
            return [translate_block_sentencewise(texts[0], tgt, src_lang, cache, client)]

    # For paragraph granularity with merged context (recommended for quality)
    if use_granularity == "paragraph" and enable_merged:
        logger.debug("Using merged paragraph translation for %d texts", len(texts))
        return translate_merged_paragraphs(texts, tgt, src_lang, cache, client, MAX_PARAGRAPH_CHARS)

    # For paragraph granularity without merged context, translate each block individually
    if use_granularity == "paragraph":
        results = []
        for text in texts:
            ok, result = translate_block_as_paragraph(text, tgt, src_lang, cache, client)
            results.append((ok, result))
        return results

    # Legacy sentence-level batch translation follows

    src_key = (src_lang or "auto").lower()
    results: List[Tuple[bool, str]] = []
    sentences_to_translate: List[Tuple[int, int, int, str]] = []
    text_structures: List[List[List[Optional[str]]]] = []

    for text_idx, text in enumerate(texts):
        if not text or not text.strip():
            text_structures.append([])
            continue
        cached_whole = cache.get(src_key, tgt, text)
        if cached_whole is not None:
            text_structures.append([[cached_whole]])
            continue
        lines_structure: List[List[Optional[str]]] = []
        for raw_line in text.split("\n"):
            if not raw_line.strip():
                lines_structure.append([""])
                continue
            sentences = split_sentences(raw_line, src_lang) or [raw_line]
            sentence_cache: List[Optional[str]] = []
            for s in sentences:
                cached = cache.get(src_key, tgt, s)
                if cached is not None:
                    sentence_cache.append(cached)
                else:
                    sentence_cache.append(None)
                    sentences_to_translate.append((text_idx, len(lines_structure), len(sentence_cache) - 1, s))
            lines_structure.append(sentence_cache)
        text_structures.append(lines_structure)

    if sentences_to_translate:
        batch_translator = BatchTranslator(client, cache, max_batch_chars, tgt, src_lang)
        sentence_texts = [s for _, _, _, s in sentences_to_translate]
        batch_results = batch_translator.translate_all(sentence_texts)
        for i, (text_idx, line_idx, sent_idx, _) in enumerate(sentences_to_translate):
            _, translated = batch_results[i]
            text_structures[text_idx][line_idx][sent_idx] = translated

    for text_idx, text in enumerate(texts):
        if not text or not text.strip():
            results.append((True, ""))
            continue
        struct = text_structures[text_idx]
        if not struct:
            results.append((True, ""))
            continue
        if len(struct) == 1 and len(struct[0]) == 1 and struct[0][0]:
            cached_whole = cache.get(src_key, tgt, text)
            if cached_whole is not None:
                results.append((True, cached_whole))
                continue
        out_lines: List[str] = []
        all_ok = True
        joiner = _get_sentence_joiner(tgt)
        for line_sentences in struct:
            if line_sentences == [""]:
                out_lines.append("")
                continue
            parts = []
            for sent in line_sentences:
                if sent is None:
                    all_ok = False
                    parts.append(f"[Translation failed|{tgt}]")
                elif sent.startswith("[Translation failed"):
                    all_ok = False
                    parts.append(sent)
                else:
                    parts.append(sent)
            out_lines.append(joiner.join(parts))
        final = "\n".join(out_lines)
        if all_ok:
            cache.put(src_key, tgt, text, final)
        results.append((all_ok, final))
    return results
