"""Abstract Protocol for LLM provider clients.

Defines the five-method surface that translation consumers depend on.
Import only stdlib ``typing`` — no import of ``ollama_client`` (avoids cycle).
"""

from __future__ import annotations

import threading
from typing import List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Structural Protocol for LLM translation provider clients.

    Any class that implements these five methods is a structural subtype,
    regardless of inheritance.  ``OllamaClient`` satisfies this Protocol
    via three thin alias methods; future cloud providers (``p1-cloud-providers``)
    implement it directly.
    """

    def translate_once(
        self,
        text: str,
        tgt: str,
        src_lang: Optional[str],
        cancel_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, str]:
        """Translate a single text segment.

        cancel_event (optional): when set, implementations SHOULD abort an
        in-flight call promptly and degrade (best-effort for local clients).
        Back-compatible default None keeps structural-subtype conformance.

        Returns:
            (ok, translated_text) where ok=False signals a failure.
        """
        ...

    def translate_batch(self, texts: List[str], tgt: str, src_lang: Optional[str]) -> Tuple[bool, List[str]]:
        """Translate a list of text segments.

        Returns:
            (ok, translated_texts) where ok=False signals a failure.
        """
        ...

    def health(self) -> Tuple[bool, str]:
        """Check provider health/connectivity.

        Returns:
            (ok, message) where ok=True means the provider is reachable.
        """
        ...

    def list_models(self) -> List[str]:
        """Return list of available model names from the provider.

        Returns:
            List of model name strings.
        """
        ...

    def unload(self) -> Tuple[bool, str]:
        """Best-effort VRAM eviction / model unload.

        Cloud providers may implement this as an immediate no-op returning
        ``(True, "no-op")``.  ``OllamaClient.unload`` delegates to the real
        ``unload_model`` method.

        Returns:
            (ok, message) — best-effort; callers should not treat False as fatal.
        """
        ...
