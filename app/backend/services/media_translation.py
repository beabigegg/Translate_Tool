"""Wires MediaTranscript segments through the existing translate_texts() batch pipeline."""

from __future__ import annotations

import threading
from typing import Any, Callable, List, Optional

from app.backend.clients.base_llm_client import LLMClient
from app.backend.models.media_transcript import MediaTranscript
from app.backend.services.translation_service import translate_texts


def translate_transcript(
    transcript: MediaTranscript,
    targets: List[str],
    client: LLMClient,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
    status_callback: Optional[Callable[[Optional[str], Optional[Any]], None]] = None,
) -> None:
    """Translate every segment's text into all targets, mutating segments in place.

    src_lang=None (per-text auto-detection by the LLM) — independent of each
    segment's STT-detected `language` field, which is informational only
    (per-utterance detection at the STT layer, purely for UI display/debugging).

    use_json_body=False, critique_enabled=False: a multi-language meeting
    transcript legitimately has segments already in the target language, so a
    translation reply that equals the source text is an expected, valid
    outcome here — not a failure signal. The default document-pipeline path
    (BR-111/BR-112's JSON-envelope call + echoed-source retry, plus the
    critique/revision loop) treats that equality as "translation failed" and
    burns 1-2 extra LLM round trips per segment recovering from it. Media
    transcripts skip straight to one plain-text translate_once call per
    segment instead.
    """
    texts = [seg.text for seg in transcript.segments]
    if not texts:
        return

    tmap, _done, _fail, _stopped = translate_texts(
        texts,
        targets,
        None,
        client,
        stop_flag=stop_flag,
        log=log,
        status_callback=status_callback,
        use_json_body=False,
        critique_enabled=False,
    )

    for seg in transcript.segments:
        for tgt in targets:
            translated = tmap.get((tgt, seg.text))
            if translated is not None:
                seg.translated_text[tgt] = translated
