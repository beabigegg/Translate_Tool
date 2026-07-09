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
import threading
import time
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
        system_prompt: Optional caller-supplied base system prompt (BR-110),
            normalized identically to OllamaClient (`.strip()`, `""` when
            omitted/falsy). Delivered to the model as system-channel content
            on every translate_once() call (BR-109); never read by
            complete().
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
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        from app.backend.config import OPENAI_COMPLETION_MAX_TOKENS

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider_id = provider_id
        self.system_prompt = (system_prompt or "").strip()
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._max_tokens = max_tokens if max_tokens is not None else OPENAI_COMPLETION_MAX_TOKENS
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

    def _build_messages(self, user_content: str, system_context: Optional[str] = None) -> List[dict]:
        messages: List[dict] = []
        if system_context:
            messages.append({"role": "system", "content": system_context})
        messages.append({"role": "user", "content": user_content})
        return messages

    def _run_bounded_post(self, fn, cancel_event=None):
        """Run a blocking cloud call on a daemon worker, bounded by a wall-clock
        total-duration ceiling and an optional cancel_event.

        The ceiling (`OPENAI_TOTAL_TIMEOUT_SECONDS`) is ADDITIVE on top of the
        per-chunk `(connect, read)` tuple: it bounds TOTAL call duration so a
        provider that dribbles keep-alive bytes (each gap < read timeout) can no
        longer hang the caller indefinitely (BR-100). If the ceiling expires OR
        `cancel_event` is set before the worker returns, the session is closed
        (best-effort, to hasten aborting the in-flight read) and a
        `requests.Timeout` is raised so the caller's existing
        `except RequestException` path degrades cleanly (BR-74/BR-99). The
        abandoned daemon worker lingering until its own read timeout is acceptable
        (ADR-0011) — the point is that the CALLER is unblocked promptly.
        """
        from app.backend.config import OPENAI_TOTAL_TIMEOUT_SECONDS

        outcome: dict = {}

        def _worker():
            try:
                outcome["resp"] = fn()
            except BaseException as exc:  # noqa: BLE001 — re-raised in caller thread
                outcome["exc"] = exc

        worker = threading.Thread(
            target=_worker, name=f"{self.provider_id}-post", daemon=True
        )
        worker.start()

        deadline = time.monotonic() + max(0.0, float(OPENAI_TOTAL_TIMEOUT_SECONDS))
        while True:
            worker.join(0.25)
            if not worker.is_alive():
                break
            cancelled = cancel_event is not None and cancel_event.is_set()
            expired = time.monotonic() >= deadline
            if cancelled or expired:
                reason = (
                    "cancelled by stop_flag"
                    if cancelled
                    else f"total-duration ceiling {OPENAI_TOTAL_TIMEOUT_SECONDS}s exceeded"
                )
                try:
                    self._session.close()
                except Exception:  # noqa: BLE001 — best-effort abort
                    pass
                logger.warning("[%s] cloud completion aborted: %s", self.provider_id, reason)
                raise requests.exceptions.Timeout(reason)

        if "exc" in outcome:
            raise outcome["exc"]
        return outcome["resp"]

    def _post_completion(
        self, user_content: str, cancel_event=None, system_context: Optional[str] = None
    ) -> Tuple[bool, str]:
        """POST to /v1/chat/completions and return (ok, text).

        cancel_event (optional threading.Event): when set, an in-flight call is
        aborted promptly and degraded (BR-99). Every call is additionally bounded
        by the `OPENAI_TOTAL_TIMEOUT_SECONDS` wall-clock ceiling (BR-100).

        system_context (optional, BR-78): forwarded to `_build_messages` as a
        leading `role:"system"` message; never merged into `user_content`.
        """
        payload = {
            "model": self.model,
            "messages": self._build_messages(user_content, system_context),
            "stream": False,
            "max_tokens": self._max_tokens,
        }

        def _do_post():
            return self._session.post(
                self._chat_completions_url(),
                json=payload,
                headers=self._auth_headers,
                timeout=self._timeout,
            )

        try:
            resp = self._run_bounded_post(_do_post, cancel_event)
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
            choice = data["choices"][0]
            content = choice["message"]["content"].strip()
            if not content:
                # Reasoning models (e.g. gpt-oss) can exhaust max_tokens entirely
                # on hidden reasoning_content before emitting the final content
                # field, returning finish_reason="length" with empty content.
                # Treat this as a failure rather than a valid empty response so
                # callers don't silently score/parse an empty string.
                finish_reason = choice.get("finish_reason")
                msg = f"Empty content (finish_reason={finish_reason!r}); likely truncated before final answer"
                logger.warning("[%s] %s", self.provider_id, msg)
                return False, msg
            return True, content
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

    def translate_once(
        self,
        text: str,
        tgt: str,
        src_lang: Optional[str],
        cancel_event=None,
        system_context: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Translate a single text segment via /v1/chat/completions.

        cancel_event (optional threading.Event): forwarded to the bounded post so
        an in-flight re-translation can be cancelled/ceiling-bounded (BR-99/BR-100).

        system_context (optional, BR-78): delivered as a leading system message,
        never concatenated into `text`/the user "Translate the following text..."
        payload — keeps reference context out of the translatable body.

        BR-109 / ADR-0016: this client's `self.system_prompt` (the scenario
        style plus the "Document context: <summary>" preamble assigned by the
        orchestrator) is merged ahead of the per-segment `system_context` into
        ONE leading system message — preamble first, then BR-78 neighbor
        context — so both reach the model via the system channel and neither
        is ever concatenated into the translatable user payload.

        Returns:
            (ok, translated_text) where ok=False signals a failure.
        """
        src = src_lang or "auto"
        prompt = (
            f"Translate the following text from {src} to {tgt}. "
            f"Output only the translation, no explanations.\n\n{text}"
        )
        parts = [p for p in ((self.system_prompt or "").strip(), (system_context or "").strip()) if p]
        merged_system_context = "\n\n".join(parts) or None
        ok, result = self._post_completion(prompt, cancel_event=cancel_event, system_context=merged_system_context)
        logger.info(
            "[%s] translate_once ok=%s tgt=%s len_in=%d len_out=%d",
            self.provider_id, ok, tgt, len(text), len(result),
        )
        return ok, result

    def complete(self, prompt: str) -> Tuple[bool, str]:
        """Raw single-turn completion, no translate framing, no system prompt.

        Shared seam (BR-109) used by the document-context summary
        (`orchestrator._detect_document_context`) on both OllamaClient and
        OpenAICompatibleClient. Delivers `prompt` as the sole user message
        (no "Translate the following..." wrapping) so the model summarizes
        the document instead of translating the instruction. Wraps
        `_post_completion`, which is already `requests.RequestException`-safe
        and bounded by `OPENAI_TOTAL_TIMEOUT_SECONDS` (BR-100).
        """
        return self._post_completion(prompt)

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

    def list_live_models(self) -> List[str]:
        """Fetch the live model list from /v1/models, excluding embedding and reranker models.

        Returns:
            List of translatable model ID strings; empty list on any error.
        """
        try:
            resp = self._session.get(
                self._models_url(),
                headers=self._auth_headers,
                timeout=(10.0, 30.0),
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            result = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                info = m.get("info") or {}
                task = info.get("task", "")
                if task in ("embedding", "reranker"):
                    continue
                mid_lower = mid.lower()
                if "embedding" in mid_lower or "reranker" in mid_lower:
                    continue
                result.append(mid)
            return result
        except Exception as exc:
            logger.debug("[%s] list_live_models failed: %s", self.provider_id, exc)
            return []

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
    # machinery (scenario style + the "Document context: <summary>" preamble).
    # BR-109 / ADR-0016: translate_once() merges this value ahead of the
    # per-segment BR-78 system_context into ONE leading system message on
    # every cloud call — it is delivered to the model, not discarded.
    # complete() (the document-context summary seam) deliberately does NOT
    # read this attribute: the summary call must carry no system prompt.
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
