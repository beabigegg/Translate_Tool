"""Ollama API client with connection pooling."""

from __future__ import annotations

import re
import threading
import time
from typing import Callable, ClassVar, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.backend.config import (
    API_ATTEMPTS,
    API_BACKOFF_BASE,
    BATCH_SEPARATOR,
    DEFAULT_MODEL,
    HTTP_POOL_CONNECTIONS,
    HTTP_POOL_MAXSIZE,
    LANG_CODE_MAP,
    OLLAMA_BASE_URL,
    TimeoutConfig,
)
from app.backend.utils.logging_utils import logger


class OllamaClient:
    """Ollama API client for local translation services with connection pooling."""

    _session: ClassVar[Optional[requests.Session]] = None
    _session_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: Optional[TimeoutConfig] = None,
        log: Callable[[str], None] = lambda s: None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout or TimeoutConfig()
        self.log = log

    @classmethod
    def _get_session(cls) -> requests.Session:
        """Get or create shared session with connection pooling."""
        if cls._session is None:
            with cls._session_lock:
                if cls._session is None:
                    session = requests.Session()
                    retry_strategy = Retry(
                        total=3,
                        backoff_factor=0.5,
                        status_forcelist=[500, 502, 503, 504],
                    )
                    adapter = HTTPAdapter(
                        pool_connections=HTTP_POOL_CONNECTIONS,
                        pool_maxsize=HTTP_POOL_MAXSIZE,
                        max_retries=retry_strategy,
                    )
                    session.mount("http://", adapter)
                    session.mount("https://", adapter)
                    cls._session = session
                    logger.debug(
                        "Created HTTP session with pool_connections=%d, pool_maxsize=%d",
                        HTTP_POOL_CONNECTIONS,
                        HTTP_POOL_MAXSIZE,
                    )
        return cls._session

    @classmethod
    def close_session(cls) -> None:
        """Close the shared session and release connections."""
        with cls._session_lock:
            if cls._session is not None:
                cls._session.close()
                cls._session = None
                logger.debug("Closed HTTP session")

    def _gen_url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def health_check(self) -> Tuple[bool, str]:
        try:
            session = self._get_session()
            resp = session.get(self._gen_url("/api/tags"), timeout=self.timeout.get_timeout_tuple())
            if resp.status_code == 200:
                names = [m.get("name", "") for m in (resp.json().get("models") or []) if isinstance(m, dict)]
                preview = ", ".join(names[:6]) + ("..." if len(names) > 6 else "")
                return True, f"OK; models={preview}"
            return False, f"HTTP {resp.status_code}: {resp.text[:180]}"
        except requests.exceptions.RequestException as exc:
            return False, f"Request error: {exc}"

    @staticmethod
    def _build_translategemma_prompt(text: str, target_language: str, source_language: Optional[str]) -> str:
        tgt_name, tgt_code = LANG_CODE_MAP.get(target_language, (target_language, target_language.lower()[:2]))
        # Source language is required - default to English if not provided
        src_lang = source_language if source_language else "English"
        src_name, src_code = LANG_CODE_MAP.get(src_lang, (src_lang, src_lang.lower()[:2]))
        return (
            f"You are a professional {src_name} ({src_code}) to {tgt_name} ({tgt_code}) translator. "
            f"Your goal is to accurately convey the meaning and nuances of the original {src_name} text "
            f"while adhering to {tgt_name} grammar, vocabulary, and cultural sensitivities. "
            f"Produce only the {tgt_name} translation, without any additional explanations or commentary. "
            f"Please translate the following {src_name} text into {tgt_name}:\n\n{text}"
        )

    @staticmethod
    def _build_generic_prompt(text: str, target_language: str, source_language: Optional[str]) -> str:
        # Source language is required - default to English if not provided
        source = source_language if source_language else "English"
        return (
            f"Task: Translate ONLY into {target_language} from {source}.\n"
            f"Rules:\n"
            f"1) Output translation text ONLY (no source text, no notes, no questions, no language-detection remarks).\n"
            f"2) Preserve original line breaks.\n"
            f"3) Do NOT wrap in quotes or code blocks.\n\n"
            f"{text}"
        )

    def translate_once(self, text: str, tgt: str, src_lang: Optional[str]) -> Tuple[bool, str]:
        if "translategemma" in self.model.lower():
            prompt = self._build_translategemma_prompt(text, tgt, src_lang)
        else:
            prompt = self._build_generic_prompt(text, tgt, src_lang)

        payload = {"model": self.model, "prompt": prompt, "stream": False}
        session = self._get_session()
        last = None
        for attempt in range(1, API_ATTEMPTS + 1):
            try:
                resp = session.post(self._gen_url("/api/generate"), json=payload, timeout=self.timeout.get_timeout_tuple())
                if resp.status_code == 200:
                    data = resp.json()
                    ans = data.get("response", "")
                    return True, ans.strip()
                last = f"HTTP {resp.status_code}: {resp.text[:180]}"
            except requests.exceptions.RequestException as exc:
                last = f"Request error: {exc}"
            time.sleep(API_BACKOFF_BASE * attempt)

        # Smart retry: detect error type and apply appropriate strategy
        return self._smart_retry(text, tgt, src_lang, str(last))

    def _smart_retry(self, text: str, tgt: str, src_lang: Optional[str], error_msg: str) -> Tuple[bool, str]:
        """Apply smart retry strategies based on error type.

        Strategies:
        1. Text too long -> Split into chunks and translate separately
        2. Timeout/busy -> Wait longer and retry
        3. Other errors -> Return failure

        Args:
            text: Original text to translate.
            tgt: Target language.
            src_lang: Source language.
            error_msg: Error message from initial attempts.

        Returns:
            Tuple of (success, result_or_error).
        """
        error_lower = error_msg.lower()

        # Strategy 1: Text too long (context length, memory issues)
        if any(kw in error_lower for kw in ["context", "length", "memory", "too long", "exceeded"]):
            logger.info(f"Text too long ({len(text)} chars), attempting chunked translation")
            return self._translate_chunked(text, tgt, src_lang)

        # Strategy 2: Temporary issues (timeout, busy, connection)
        if any(kw in error_lower for kw in ["timeout", "busy", "connection", "reset", "refused"]):
            logger.info("Temporary error detected, attempting extended retry")
            return self._translate_with_extended_retry(text, tgt, src_lang)

        # Strategy 3: No applicable strategy, return original error
        return False, error_msg

    def _translate_chunked(self, text: str, tgt: str, src_lang: Optional[str], max_chunk_chars: int = 1500) -> Tuple[bool, str]:
        """Translate long text by splitting into smaller chunks.

        Args:
            text: Long text to translate.
            tgt: Target language.
            src_lang: Source language.
            max_chunk_chars: Maximum characters per chunk.

        Returns:
            Tuple of (success, translated_text).
        """
        # Try splitting by paragraphs first
        if "\n\n" in text:
            chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
            joiner = "\n\n"
        elif "\n" in text:
            chunks = [chunk.strip() for chunk in text.split("\n") if chunk.strip()]
            joiner = "\n"
        else:
            # Split by sentences (rough approximation)
            sentences = re.split(r'(?<=[.!?。！？])\s+', text)
            chunks = [s.strip() for s in sentences if s.strip()]
            joiner = " "

        # Further split chunks that are still too long
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= max_chunk_chars:
                final_chunks.append(chunk)
            else:
                # Force split by character limit
                for i in range(0, len(chunk), max_chunk_chars):
                    final_chunks.append(chunk[i:i + max_chunk_chars])

        if not final_chunks:
            return False, "[Chunked translation failed: no valid chunks]"

        # Translate each chunk
        translated_chunks = []
        for chunk in final_chunks:
            if "translategemma" in self.model.lower():
                prompt = self._build_translategemma_prompt(chunk, tgt, src_lang)
            else:
                prompt = self._build_generic_prompt(chunk, tgt, src_lang)

            payload = {"model": self.model, "prompt": prompt, "stream": False}
            session = self._get_session()

            try:
                resp = session.post(
                    self._gen_url("/api/generate"),
                    json=payload,
                    timeout=self.timeout.get_timeout_tuple()
                )
                if resp.status_code == 200:
                    data = resp.json()
                    translated_chunks.append(data.get("response", "").strip())
                else:
                    return False, f"[Chunk translation failed] HTTP {resp.status_code}"
            except requests.exceptions.RequestException as exc:
                return False, f"[Chunk translation failed] {exc}"

        return True, joiner.join(translated_chunks)

    def _translate_with_extended_retry(self, text: str, tgt: str, src_lang: Optional[str]) -> Tuple[bool, str]:
        """Retry translation with extended wait times for temporary issues.

        Args:
            text: Text to translate.
            tgt: Target language.
            src_lang: Source language.

        Returns:
            Tuple of (success, result_or_error).
        """
        if "translategemma" in self.model.lower():
            prompt = self._build_translategemma_prompt(text, tgt, src_lang)
        else:
            prompt = self._build_generic_prompt(text, tgt, src_lang)

        payload = {"model": self.model, "prompt": prompt, "stream": False}
        session = self._get_session()

        # Extended retry with longer waits
        wait_times = [5, 10, 20]  # seconds
        for wait_time in wait_times:
            logger.debug(f"Extended retry: waiting {wait_time}s before attempt")
            time.sleep(wait_time)

            try:
                resp = session.post(
                    self._gen_url("/api/generate"),
                    json=payload,
                    timeout=(self.timeout.connect_timeout, self.timeout.read_timeout * 1.5)
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return True, data.get("response", "").strip()
            except requests.exceptions.RequestException:
                continue

        return False, "[Extended retry failed after multiple attempts]"

    @staticmethod
    def _build_batch_translategemma_prompt(texts: List[str], target_language: str, source_language: Optional[str]) -> str:
        """Build batch translation prompt with numbered segment markers for better parsing."""
        tgt_name, tgt_code = LANG_CODE_MAP.get(target_language, (target_language, target_language.lower()[:2]))
        # Source language is required - default to English if not provided
        src_lang = source_language if source_language else "English"
        src_name, src_code = LANG_CODE_MAP.get(src_lang, (src_lang, src_lang.lower()[:2]))

        # Build segments with numbered markers
        segments = []
        for i, text in enumerate(texts):
            segments.append(f"<<<SEG_{i}>>>\n{text}")
        combined_text = "\n".join(segments)

        return (
            f"You are a professional {src_name} ({src_code}) to {tgt_name} ({tgt_code}) translator. "
            f"Your goal is to accurately convey the meaning and nuances of the original {src_name} text "
            f"while adhering to {tgt_name} grammar, vocabulary, and cultural sensitivities.\n\n"
            f"IMPORTANT: Translate each numbered segment below. Keep the <<<SEG_N>>> markers in your output.\n\n"
            f"{combined_text}\n\n"
            f"Output format (keep all markers):\n"
            f"<<<SEG_0>>>\n[translation of segment 0]\n"
            f"<<<SEG_1>>>\n[translation of segment 1]\n..."
        )

    def translate_batch(self, texts: List[str], tgt: str, src_lang: Optional[str]) -> Tuple[bool, List[str]]:
        if not texts:
            return True, []
        if len(texts) == 1:
            ok, result = self.translate_once(texts[0], tgt, src_lang)
            return ok, [result]

        if "translategemma" in self.model.lower():
            prompt = self._build_batch_translategemma_prompt(texts, tgt, src_lang)
        else:
            # Build segments with numbered markers for reliable parsing
            segments = []
            for i, text in enumerate(texts):
                segments.append(f"<<<SEG_{i}>>>\n{text}")
            combined_text = "\n".join(segments)

            # Source language is required - default to English if not provided
            source = src_lang if src_lang else "English"
            prompt = (
                f"Translate the following text from {source} to {tgt}.\n\n"
                f"Rules:\n"
                f"1) Output translation text ONLY (no source text, no notes, no questions).\n"
                f"2) Preserve original line breaks within each segment.\n"
                f"3) Do NOT wrap in quotes or code blocks.\n"
                f"4) IMPORTANT: Keep the <<<SEG_N>>> markers in your output.\n\n"
                f"{combined_text}\n\n"
                f"Output format (keep all markers):\n"
                f"<<<SEG_0>>>\n[translation]\n<<<SEG_1>>>\n[translation]..."
            )

        payload = {"model": self.model, "prompt": prompt, "stream": False}
        session = self._get_session()
        last = None
        for attempt in range(1, API_ATTEMPTS + 1):
            try:
                resp = session.post(self._gen_url("/api/generate"), json=payload, timeout=self.timeout.get_timeout_tuple())
                if resp.status_code == 200:
                    data = resp.json()
                    ans = data.get("response", "").strip()
                    results = self._parse_batch_response(ans, len(texts))
                    if len(results) == len(texts):
                        return True, results
                    logger.warning(
                        "Batch response parse mismatch: expected %s segments, got %s. Attempt %s/%s.",
                        len(texts),
                        len(results),
                        attempt,
                        API_ATTEMPTS,
                    )
                    last = f"Batch parse failed: expected {len(texts)} segments, got {len(results)}"
                else:
                    last = f"HTTP {resp.status_code}: {resp.text[:180]}"
            except requests.exceptions.RequestException as exc:
                last = f"Request error: {exc}"
            time.sleep(API_BACKOFF_BASE * attempt)
        return False, [str(last)] * len(texts)

    def _parse_batch_response(self, response: str, expected_count: int) -> List[str]:
        """Parse batch response using numbered segment markers.

        Tries multiple parsing strategies:
        1. Numbered markers (<<<SEG_N>>>)
        2. Legacy separator
        3. Alternative separators
        """
        # Strategy 1: Try numbered segment markers (most reliable)
        results = [""] * expected_count
        pattern = r'<<<SEG_(\d+)>>>\s*(.*?)(?=<<<SEG_|\Z)'
        matches = re.findall(pattern, response, re.DOTALL)

        if matches:
            parsed_count = 0
            for idx_str, content in matches:
                try:
                    idx = int(idx_str)
                    if 0 <= idx < expected_count:
                        results[idx] = content.strip()
                        parsed_count += 1
                except ValueError:
                    continue

            # If we got all segments, return
            if parsed_count == expected_count and all(r for r in results):
                return results

            # If we got most segments, fill in missing ones and return
            if parsed_count >= expected_count * 0.8:
                logger.debug(f"Parsed {parsed_count}/{expected_count} segments with numbered markers")
                return results

        # Strategy 2: Try legacy separator
        separator = BATCH_SEPARATOR.strip()
        parts = response.split(separator)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) == expected_count:
            return parts

        # Strategy 3: Try alternative separators
        alternative_separators = [
            "---SEGMENT_SEPARATOR---",
            "\n---\n",
            "\n\n---\n\n",
            "---",
        ]
        for alt_sep in alternative_separators:
            if alt_sep in response:
                parts = response.split(alt_sep)
                parts = [p.strip() for p in parts if p.strip()]
                if len(parts) == expected_count:
                    return parts

        # Strategy 4: If numbered markers got partial results, use them
        if matches and any(r for r in results):
            logger.debug(f"Using partial numbered marker results: {sum(1 for r in results if r)}/{expected_count}")
            return results

        # Return whatever we got from legacy parsing
        return parts if parts else results

    def unload_model(self) -> Tuple[bool, str]:
        try:
            session = self._get_session()
            payload = {"model": self.model, "prompt": "", "keep_alive": 0}
            resp = session.post(
                self._gen_url("/api/generate"),
                json=payload,
                timeout=(self.timeout.connect_timeout, 30),
            )
            if resp.status_code == 200:
                logger.info("Model %s unloaded successfully", self.model)
                return True, f"Model {self.model} unloaded successfully"
            msg = f"HTTP {resp.status_code}: {resp.text[:180]}"
            logger.warning("Failed to unload model: %s", msg)
            return False, msg
        except requests.exceptions.RequestException as exc:
            msg = f"Request error while unloading model: {exc}"
            logger.warning(msg)
            return False, msg


def list_ollama_models(base_url: str = OLLAMA_BASE_URL, timeout: Optional[TimeoutConfig] = None) -> List[str]:
    timeout = timeout or TimeoutConfig()
    try:
        session = OllamaClient._get_session()
        resp = session.get(base_url.rstrip("/") + "/api/tags", timeout=timeout.get_timeout_tuple())
        if resp.status_code == 200:
            return [m.get("name", "") for m in (resp.json().get("models") or []) if isinstance(m, dict)]
    except requests.exceptions.RequestException as exc:
        logger.debug("Failed to list Ollama models from %s: %s", base_url, exc)
    return [DEFAULT_MODEL]
