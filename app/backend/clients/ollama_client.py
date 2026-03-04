"""Ollama API client with connection pooling."""

from __future__ import annotations

import json
import re
import threading
import time
from typing import Callable, ClassVar, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.backend.config import (
    API_ATTEMPTS,
    API_BACKOFF_BASE,
    BATCH_SEPARATOR,
    DEFAULT_MAX_BATCH_CHARS,
    DEFAULT_MODEL,
    HTTP_POOL_CONNECTIONS,
    HTTP_POOL_MAXSIZE,
    LANG_CODE_MAP,
    MODEL_TYPE_OPTIONS,
    ModelType,
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
        model_type: str = ModelType.GENERAL.value,
        system_prompt: Optional[str] = None,
        profile_id: Optional[str] = None,
        num_ctx_override: Optional[int] = None,
        timeout: Optional[TimeoutConfig] = None,
        log: Callable[[str], None] = lambda s: None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.model_type = self._normalize_model_type(model_type).value
        self.system_prompt = (system_prompt or "").strip()
        self.profile_id = (profile_id or "").strip() or None
        self._num_ctx_override = num_ctx_override if (num_ctx_override is not None and num_ctx_override > 0) else None
        self.timeout = timeout or TimeoutConfig()
        self.log = log
        options = self._build_options()
        logger.info(
            "[CONFIG] Ollama options: model_type=%s, options=%s, num_ctx_override=%s, max_batch_chars=%d",
            self.model_type,
            options,
            self._num_ctx_override,
            DEFAULT_MAX_BATCH_CHARS,
        )

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

    @staticmethod
    def _normalize_model_type(model_type: Optional[str]) -> ModelType:
        if not model_type:
            return ModelType.GENERAL
        try:
            return ModelType(model_type.strip().lower())
        except ValueError:
            logger.warning("Unknown model_type=%r, falling back to general", model_type)
            return ModelType.GENERAL

    def _build_options(self) -> Dict[str, object]:
        model_type_enum = self._normalize_model_type(self.model_type)
        options_template = MODEL_TYPE_OPTIONS.get(model_type_enum, MODEL_TYPE_OPTIONS[ModelType.GENERAL])
        options = dict(options_template)
        if self._num_ctx_override is not None:
            options["num_ctx"] = self._num_ctx_override
        return options

    def _is_translation_dedicated(self) -> bool:
        return self.model_type == ModelType.TRANSLATION.value

    @property
    def cache_model_key(self) -> str:
        if self._is_translation_dedicated():
            if self.profile_id:
                return f"{self.model}::{self.profile_id}::{self.model_type}"
            return f"{self.model}::{self.model_type}"
        if self.profile_id:
            return f"{self.model}::{self.profile_id}"
        return self.model

    def _build_payload(self, prompt: str) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "options": self._build_options(),
            "think": False,  # Disable thinking mode — translation needs output only, not reasoning
        }
        if self.system_prompt:
            payload["system"] = self.system_prompt
        return payload

    def _build_no_system_payload(self, prompt: str) -> Dict[str, object]:
        return {"model": self.model, "prompt": prompt, "options": self._build_options(), "think": False}

    def _is_translategemma_model(self) -> bool:
        return "translategemma" in self.model.lower()

    @staticmethod
    def _normalize_source_language(source_language: Optional[str]) -> str:
        if not source_language:
            return "English"
        normalized = source_language.strip()
        if not normalized or normalized.lower() == "auto":
            return "English"
        return normalized

    @staticmethod
    def _is_auto_source(source_language: Optional[str]) -> bool:
        return not source_language or not source_language.strip() or source_language.strip().lower() == "auto"

    def _call_ollama(self, payload: dict, timeout_tuple=None) -> Tuple[bool, str]:
        """Call Ollama /api/generate with streaming.

        stream=True makes read_timeout the max silence between chunks,
        not the max wait for the entire response. As long as Ollama keeps
        producing tokens, it won't timeout.
        """
        session = self._get_session()
        send_payload = {**payload, "stream": True}
        timeout = timeout_tuple or self.timeout.get_timeout_tuple()

        # Log outgoing payload (truncate prompt/system to keep logs readable)
        prompt_preview = str(payload.get("prompt", ""))[:200]
        system_preview = str(payload.get("system", ""))[:200]
        logger.info(
            "[OLLAMA_REQ] model=%s options=%s think=%s\n  system(%d): %s%s\n  prompt(%d): %s%s",
            payload.get("model", "?"),
            payload.get("options", {}),
            payload.get("think", "default"),
            len(str(payload.get("system", ""))), system_preview,
            "..." if len(str(payload.get("system", ""))) > 200 else "",
            len(str(payload.get("prompt", ""))), prompt_preview,
            "..." if len(str(payload.get("prompt", ""))) > 200 else "",
        )

        t0 = time.time()
        resp = session.post(
            self._gen_url("/api/generate"),
            json=send_payload, stream=True, timeout=timeout,
        )

        if resp.status_code != 200:
            error_text = ""
            try:
                error_text = resp.text[:180]
            except Exception:
                pass
            resp.close()
            elapsed = time.time() - t0
            logger.info("[OLLAMA_ERR] HTTP %s after %.1fs: %s", resp.status_code, elapsed, error_text)
            return False, f"HTTP {resp.status_code}: {error_text}"

        try:
            parts: list[str] = []
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = data.get("response", "")
                if token:
                    parts.append(token)
                if data.get("done", False):
                    break
            raw_result = "".join(parts).strip()
            # Strip <think>...</think> blocks from Qwen3.5 thinking mode output
            result = re.sub(r"<think>.*?</think>", "", raw_result, flags=re.DOTALL).strip()
            if raw_result and not result:
                logger.warning("[OLLAMA_RES] Model returned only <think> content (%d chars), no translation", len(raw_result))
            elapsed = time.time() - t0
            result_preview = result[:300]
            logger.info(
                "[OLLAMA_RES] ok, %d chars in %.1fs (%.1f chars/s)\n  response: %s%s",
                len(result), elapsed, len(result) / elapsed if elapsed > 0 else 0,
                result_preview, "..." if len(result) > 300 else "",
            )
            return True, result
        finally:
            resp.close()

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
        src_lang = OllamaClient._normalize_source_language(source_language)
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
        source = OllamaClient._normalize_source_language(source_language)
        return (
            f"Task: Translate ONLY into {target_language} from {source}.\n"
            f"Rules:\n"
            f"1) Output translation text ONLY (no source text, no notes, no questions, no language-detection remarks).\n"
            f"2) Preserve original line breaks.\n"
            f"3) Do NOT wrap in quotes or code blocks.\n\n"
            f"{text}"
        )

    @staticmethod
    def _involves_chinese(target_language: str, source_language: Optional[str] = None) -> bool:
        """Check if Chinese is involved as source or target (for HY-MT template selection)."""
        cn_keywords = ("chinese", "zh-tw", "zh-cn", "zh")
        if any(kw in target_language.lower() for kw in cn_keywords):
            return True
        if source_language and any(kw in source_language.lower() for kw in cn_keywords):
            return True
        return False

    @staticmethod
    def _build_translation_dedicated_prompt(
        text: str, target_language: str, source_language: Optional[str] = None,
    ) -> str:
        if OllamaClient._involves_chinese(target_language, source_language):
            return f"将以下文本翻译为{target_language}，注意只需要输出翻译后的结果，不要额外解释：\n\n{text}"
        return f"Translate the following segment into {target_language}, without additional explanation.\n\n{text}"

    @staticmethod
    def _build_user_prompt(text: str, target_language: str, source_language: Optional[str]) -> str:
        if OllamaClient._is_auto_source(source_language):
            direction = f"Translate to {target_language}:"
        else:
            direction = f"Translate from {source_language} to {target_language}:"
        return f"{direction}\n\n{text}"

    @staticmethod
    def _build_batch_user_prompt(texts: List[str], target_language: str, source_language: Optional[str]) -> str:
        segments = [f"<<<SEG_{i}>>>\n{text}" for i, text in enumerate(texts)]
        combined_text = "\n".join(segments)
        if OllamaClient._is_auto_source(source_language):
            direction = f"Translate to {target_language}:"
        else:
            direction = f"Translate from {source_language} to {target_language}:"
        return (
            f"{direction}\n"
            "Translate each segment and keep every <<<SEG_N>>> marker exactly as-is.\n"
            "Output only translated text in the same marker order.\n\n"
            f"{combined_text}\n\n"
            "Output format:\n"
            "<<<SEG_0>>>\n[translation]\n"
            "<<<SEG_1>>>\n[translation]\n..."
        )

    def _build_single_translate_payload(self, text: str, tgt: str, src_lang: Optional[str]) -> Dict[str, object]:
        if self._is_translation_dedicated():
            prompt = self._build_translation_dedicated_prompt(text, tgt, src_lang)
            return self._build_no_system_payload(prompt)
        if self._is_translategemma_model():
            prompt = self._build_translategemma_prompt(text, tgt, src_lang)
            return self._build_no_system_payload(prompt)
        if self.system_prompt:
            prompt = self._build_user_prompt(text, tgt, src_lang)
            return self._build_payload(prompt)
        prompt = self._build_generic_prompt(text, tgt, src_lang)
        return self._build_payload(prompt)

    def _build_batch_translate_payload(self, texts: List[str], tgt: str, src_lang: Optional[str]) -> Dict[str, object]:
        if self._is_translation_dedicated():
            prompt = self._build_translation_dedicated_prompt("\n\n".join(texts), tgt, src_lang)
            return self._build_no_system_payload(prompt)
        if self._is_translategemma_model():
            prompt = self._build_batch_translategemma_prompt(texts, tgt, src_lang)
            return self._build_no_system_payload(prompt)
        if self.system_prompt:
            prompt = self._build_batch_user_prompt(texts, tgt, src_lang)
            return self._build_payload(prompt)

        segments = [f"<<<SEG_{i}>>>\n{text}" for i, text in enumerate(texts)]
        combined_text = "\n".join(segments)
        source = self._normalize_source_language(src_lang)
        prompt = (
            f"Translate the following text from {source} to {tgt}.\n\n"
            "Rules:\n"
            "1) Output translation text ONLY (no source text, no notes, no questions).\n"
            "2) Preserve original line breaks within each segment.\n"
            "3) Do NOT wrap in quotes or code blocks.\n"
            "4) IMPORTANT: Keep the <<<SEG_N>>> markers in your output.\n\n"
            f"{combined_text}\n\n"
            "Output format (keep all markers):\n"
            "<<<SEG_0>>>\n[translation]\n<<<SEG_1>>>\n[translation]..."
        )
        return self._build_payload(prompt)

    def translate_once(self, text: str, tgt: str, src_lang: Optional[str]) -> Tuple[bool, str]:
        payload = self._build_single_translate_payload(text, tgt, src_lang)
        last = None
        for attempt in range(1, API_ATTEMPTS + 1):
            try:
                ok, result = self._call_ollama(payload)
                if ok:
                    return True, result
                last = result
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
            payload = self._build_single_translate_payload(chunk, tgt, src_lang)

            try:
                ok, result = self._call_ollama(payload)
                if ok:
                    translated_chunks.append(result)
                else:
                    return False, f"[Chunk translation failed] {result}"
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
        payload = self._build_single_translate_payload(text, tgt, src_lang)
        extended_timeout = (self.timeout.connect_timeout, self.timeout.read_timeout * 1.5)

        # Extended retry with longer waits
        wait_times = [5, 10, 20]  # seconds
        for wait_time in wait_times:
            logger.debug(f"Extended retry: waiting {wait_time}s before attempt")
            time.sleep(wait_time)

            try:
                ok, result = self._call_ollama(payload, timeout_tuple=extended_timeout)
                if ok:
                    return True, result
            except requests.exceptions.RequestException:
                continue

        return False, "[Extended retry failed after multiple attempts]"

    @staticmethod
    def _build_batch_translategemma_prompt(texts: List[str], target_language: str, source_language: Optional[str]) -> str:
        """Build batch translation prompt with numbered segment markers for better parsing."""
        tgt_name, tgt_code = LANG_CODE_MAP.get(target_language, (target_language, target_language.lower()[:2]))
        src_lang = OllamaClient._normalize_source_language(source_language)
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
        if self._is_translation_dedicated():
            results: List[str] = []
            all_ok = True
            for text in texts:
                ok, result = self.translate_once(text, tgt, src_lang)
                if not ok:
                    all_ok = False
                results.append(result)
            return all_ok, results

        payload = self._build_batch_translate_payload(texts, tgt, src_lang)
        last = None
        for attempt in range(1, API_ATTEMPTS + 1):
            try:
                ok, result = self._call_ollama(payload)
                if ok:
                    results = self._parse_batch_response(result, len(texts))
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
                    last = result
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
            num_gpu = self._build_options().get("num_gpu")
            payload = {"model": self.model, "prompt": "", "keep_alive": 0, "options": {"num_gpu": num_gpu}}
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
