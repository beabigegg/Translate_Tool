"""Translation helper utilities."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import (
    BATCH_SEPARATOR,
    DEFAULT_MAX_BATCH_CHARS,
    MAX_MAX_BATCH_CHARS,
    MIN_MAX_BATCH_CHARS,
)
from app.backend.utils.logging_utils import logger
from app.backend.utils.text_utils import split_sentences


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
        out_lines.append(" ".join(parts))

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
) -> List[Tuple[bool, str]]:
    if not texts:
        return []
    if len(texts) == 1:
        return [translate_block_sentencewise(texts[0], tgt, src_lang, cache, client)]

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
            out_lines.append(" ".join(parts))
        final = "\n".join(out_lines)
        if all_ok:
            cache.put(src_key, tgt, text, final)
        results.append((all_ok, final))
    return results
