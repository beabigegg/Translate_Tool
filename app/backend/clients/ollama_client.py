"""Ollama API client with connection pooling."""

from __future__ import annotations

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
        if source_language and source_language.lower() not in ("auto", "auto-detect", "auto detect"):
            src_name, src_code = LANG_CODE_MAP.get(source_language, (source_language, source_language.lower()[:2]))
        else:
            src_name, src_code = "Auto-detect", "auto"
        return (
            f"You are a professional {src_name} ({src_code}) to {tgt_name} ({tgt_code}) translator. "
            f"Your goal is to accurately convey the meaning and nuances of the original {src_name} text "
            f"while adhering to {tgt_name} grammar, vocabulary, and cultural sensitivities. "
            f"Produce only the {tgt_name} translation, without any additional explanations or commentary. "
            f"Please translate the following {src_name} text into {tgt_name}:\n\n{text}"
        )

    @staticmethod
    def _build_generic_prompt(text: str, target_language: str, source_language: Optional[str]) -> str:
        source = source_language if (source_language and source_language.lower() not in ("auto", "auto-detect", "auto detect")) else "Auto"
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
        return False, str(last)

    @staticmethod
    def _build_batch_translategemma_prompt(texts: List[str], target_language: str, source_language: Optional[str]) -> str:
        tgt_name, tgt_code = LANG_CODE_MAP.get(target_language, (target_language, target_language.lower()[:2]))
        if source_language and source_language.lower() not in ("auto", "auto-detect", "auto detect"):
            src_name, src_code = LANG_CODE_MAP.get(source_language, (source_language, source_language.lower()[:2]))
        else:
            src_name, src_code = "Auto-detect", "auto"
        combined_text = BATCH_SEPARATOR.join(texts)
        separator = BATCH_SEPARATOR.strip()
        return (
            f"You are a professional {src_name} ({src_code}) to {tgt_name} ({tgt_code}) translator. "
            f"Your goal is to accurately convey the meaning and nuances of the original {src_name} text "
            f"while adhering to {tgt_name} grammar, vocabulary, and cultural sensitivities. "
            f"IMPORTANT: The following text contains multiple segments separated by '{separator}'. "
            f"Translate each segment separately and output them in the same order, separated by the same separator '{separator}'. "
            f"Do NOT add any explanations, numbering, or commentary. Just output the translations separated by the separator.\n\n"
            f"{combined_text}"
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
            combined_text = BATCH_SEPARATOR.join(texts)
            prompt = (
                f"Translate the following text from {src_lang or 'auto-detect'} to {tgt}.\n\n"
                f"Rules:\n"
                f"1) Output translation text ONLY (no source text, no notes, no questions, no language-detection remarks).\n"
                f"2) Preserve original line breaks within each segment.\n"
                f"3) Do NOT wrap in quotes or code blocks.\n"
                f"4) IMPORTANT: The text contains multiple segments separated by '{BATCH_SEPARATOR.strip()}'. "
                f"Translate each segment separately and output them in the same order, separated by the same separator.\n\n"
                f"{combined_text}"
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
        separator = BATCH_SEPARATOR.strip()
        parts = response.split(separator)
        results = [p.strip() for p in parts if p.strip()]
        if len(results) == expected_count:
            return results
        alternative_separators = ["---SEGMENT_SEPARATOR---", "---", "\n\n---\n\n", "\n---\n"]
        for alt_sep in alternative_separators:
            if alt_sep in response:
                parts = response.split(alt_sep)
                results = [p.strip() for p in parts if p.strip()]
                if len(results) == expected_count:
                    return results
        return results

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
