"""OpenAI-compatible LLM provider client (p1-cloud-providers).

Implements the six-method LLMClient Protocol over HTTP POST /v1/chat/completions
via the ``requests`` library (the project's existing HTTP dependency).

Design decisions:
- Non-streamed completions (streaming=False): translations are typically short,
  a single completion call suffices.
- translate_batch is sequential translate_once calls (no OpenAI batch API).
- unload() is a no-op (True, "no-op") — cloud providers have no unload concept.
- list_models() returns a static list — do not probe a live endpoint.
- Explicit timeouts:
    connect: 120 s — long enough for cold-start but bounded.
    read:    300 s — allows long translations while bounding fallback latency.
- API key is passed as "Authorization: Bearer <key>" header, never in the body.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import urllib3
import requests

logger = logging.getLogger(__name__)

# Connect and read timeouts (seconds).  Explicit values keep fallback latency bounded.
# A hanging provider consumes at most (120 + 300) s = 7 min before the chain advances.
_CONNECT_TIMEOUT_S = 120.0
_READ_TIMEOUT_S = 300.0

# Static model list returned by list_models().  Probing /v1/models is not required
# by the LLMClient Protocol; a static list is sufficient and avoids a live call.
_STATIC_MODEL_LIST: List[str] = [
    "gpt-oss:120b",
    "Qwen3.6-35B-A3B-4bit",
    "deepseek-v4-flash",
]


class OpenAICompatibleClient:
    """LLMClient Protocol implementation for OpenAI-compatible endpoints.

    Talks to any provider that exposes the /v1/chat/completions and /v1/models
    OpenAI-compatible REST API (Panjit, DeepSeek, local vLLM, etc.).

    Args:
        base_url: Provider base URL (e.g. "https://api.panjit.ai").
        api_key: Bearer token / API key for Authorization header.
        model: Default model name to use for completions.
        provider_id: Logical provider ID (used in logs and attribution).
        connect_timeout: HTTP connect timeout in seconds (default 120 s).
        read_timeout: HTTP read timeout in seconds (default 300 s).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        provider_id: str = "openai-compatible",
        connect_timeout: float = _CONNECT_TIMEOUT_S,
        read_timeout: float = _READ_TIMEOUT_S,
        verify_ssl: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider_id = provider_id
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._session.verify = verify_ssl
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # API key is always passed as an explicit per-request header so that test
        # mocks that intercept requests.Session.post can inspect it in kwargs.
        # The header dict is reused on every call (no allocation per request).
        self._auth_headers = {"Authorization": f"Bearer {self.api_key}"}
        self._cache_variant: Optional[str] = None

    @property
    def cache_model_key(self) -> str:
        base = f"{self.provider_id}/{self.model}"
        if self._cache_variant:
            return f"{base}::scenario={self._cache_variant}"
        return base

    @property
    def _timeout(self) -> Tuple[float, float]:
        """Return (connect_timeout, read_timeout) tuple."""
        return (self._connect_timeout, self._read_timeout)

    def _chat_completions_url(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def _embeddings_url(self) -> str:
        return f"{self.base_url}/v1/embeddings"

    def _models_url(self) -> str:
        return f"{self.base_url}/v1/models"

    def _build_messages(self, user_content: str) -> List[dict]:
        return [{"role": "user", "content": user_content}]

    def _post_completion(self, user_content: str) -> Tuple[bool, str]:
        """POST to /v1/chat/completions and return (ok, text)."""
        payload = {
            "model": self.model,
            "messages": self._build_messages(user_content),
            "stream": False,
        }
        try:
            resp = self._session.post(
                self._chat_completions_url(),
                json=payload,
                headers=self._auth_headers,
                timeout=self._timeout,
            )
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "[%s] HTTP request error: %s", self.provider_id, exc
            )
            return False, f"Request error: {exc}"

        if resp.status_code != 200:
            msg = f"HTTP {resp.status_code}: {resp.text[:180]}"
            logger.warning("[%s] Completion error: %s", self.provider_id, msg)
            return False, msg

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return True, content.strip()
        except (KeyError, IndexError, ValueError) as exc:
            msg = f"Response parse error: {exc}"
            logger.warning("[%s] %s", self.provider_id, msg)
            return False, msg

    def embed(self, texts: List[str], model_name: str) -> List[List[float]]:
        """POST to /v1/embeddings and return a list of embedding vectors.

        Args:
            texts: List of strings to embed.
            model_name: Embedding model to use (e.g. config.TERM_EMBEDDING_MODEL).

        Returns:
            List of float vectors, one per input text.  Returns [] on any failure
            (connection error, timeout, HTTP error, or parse failure) so the caller
            can treat embedding unavailability as non-fatal.
        """
        if not texts:
            return []
        payload = {"model": model_name, "input": texts}
        try:
            resp = self._session.post(
                self._embeddings_url(),
                json=payload,
                headers=self._auth_headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            # Parse data[i].embedding for each item, preserving input order.
            items = data["data"]
            return [item["embedding"] for item in items]
        except Exception as exc:
            logger.warning(
                "[%s] embed() failed (non-fatal): %s", self.provider_id, exc
            )
            return []

    @staticmethod
    def _build_table_translate_prompt(serialized_table: str, src_lang: str, tgt_lang: str) -> str:
        """Build a prompt for whole-table translation (table-context-translation, IP-2).

        Instruction placed BEFORE the serialized table (AC-2 / BR-80).
        Wording must be identical to OllamaClient._build_table_translate_prompt.

        Args:
            serialized_table: Markdown pipe-grid from table_serializer.serialize().
            src_lang: Source language code or name.
            tgt_lang: Target language code or name.

        Returns:
            Prompt string ready for translate_once().
        """
        return (
            f"Translate the following table from {src_lang} to {tgt_lang}. "
            f"Keep the exact Markdown pipe-grid structure. "
            f"Translate only the text content, preserving every '|' delimiter, "
            f"row count, and column count. Output the translated grid only.\n\n"
            f"{serialized_table}"
        )

    def translate_once(self, text: str, tgt: str, src_lang: Optional[str]) -> Tuple[bool, str]:
        """Translate a single text segment via /v1/chat/completions.

        Returns:
            (ok, translated_text) where ok=False signals a failure.
        """
        src = src_lang or "auto"
        prompt = (
            f"Translate the following text from {src} to {tgt}. "
            f"Output only the translation, no explanations.\n\n{text}"
        )
        ok, result = self._post_completion(prompt)
        logger.info(
            "[%s] translate_once ok=%s tgt=%s len_in=%d len_out=%d",
            self.provider_id, ok, tgt, len(text), len(result),
        )
        return ok, result

    def translate_batch(
        self, texts: List[str], tgt: str, src_lang: Optional[str]
    ) -> Tuple[bool, List[str]]:
        """Translate a list of text segments sequentially.

        Returns:
            (ok, translated_texts) — ok=False if any segment failed.
        """
        if not texts:
            return True, []

        results: List[str] = []
        all_ok = True
        for text in texts:
            ok, result = self.translate_once(text, tgt, src_lang)
            if not ok:
                all_ok = False
            results.append(result)

        return all_ok, results

    def health(self) -> Tuple[bool, str]:
        """Probe /v1/models to check provider reachability.

        Returns:
            (ok, message) — ok=True means provider is reachable.
        """
        try:
            resp = self._session.get(
                self._models_url(),
                headers=self._auth_headers,
                timeout=self._timeout,
            )
            if resp.status_code == 200:
                return True, f"OK; provider={self.provider_id}"
            return False, f"HTTP {resp.status_code}: {resp.text[:180]}"
        except requests.exceptions.RequestException as exc:
            return False, f"Request error: {exc}"

    def list_models(self) -> List[str]:
        """Return a static list of known model names for this provider type.

        A live /v1/models probe is not required by the Protocol; a static list
        keeps the method free of network calls in test/offline scenarios.

        Returns:
            List of model name strings.
        """
        return list(_STATIC_MODEL_LIST)

    def unload(self) -> Tuple[bool, str]:
        """No-op for cloud providers (no in-memory model to evict).

        Returns:
            (True, "no-op") always.
        """
        return True, "no-op"

    # ------------------------------------------------------------------
    # Orchestrator-compatibility stubs
    # The orchestrator (and the translate_* processors it calls) reference
    # OllamaClient-specific attributes.  These stubs make
    # OpenAICompatibleClient a drop-in replacement for ``client`` in the
    # process_files dispatch without modifying out-of-scope processor files.
    # ------------------------------------------------------------------

    # system_prompt is read at loop start and written per-file by the scenario
    # machinery.  Cloud clients build their own prompt inside translate_once, so
    # these writes are intentionally ignored.
    system_prompt: str = ""
    model_type: str = "general"

    def health_check(self) -> Tuple[bool, str]:
        """Alias for health() — satisfies docx_processor.translate_docx caller."""
        return self.health()

    def _is_translation_dedicated(self) -> bool:
        """Cloud providers are not translation-dedicated Ollama models."""
        return False

    def _is_translategemma_model(self) -> bool:
        """Cloud providers are not a dedicated translation model variant."""
        return False

    def set_runtime_options_override(self, options: Optional[dict]) -> None:
        """No-op — cloud providers do not support Ollama runtime options."""

    def set_cache_variant(self, variant: Optional[str]) -> None:
        """Store scenario variant for cache key differentiation."""
        self._cache_variant = variant
