"""Tests for media_translation.py's translate_texts() wiring.

Mock seam: app.backend.services.media_translation.translate_texts.
Anti-tautology: assert the exact texts/targets/src_lang passed through, and
that the returned map is written back onto the correct segment/target pair
(not just "some" segment got "some" translation).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.backend.models.media_transcript import MediaTranscript, TranscriptSegment
from app.backend.services import media_translation


def test_translate_transcript_calls_translate_texts_with_auto_src_lang():
    segments = [
        TranscriptSegment(start=0.0, end=1.0, text="hello", language="en"),
        TranscriptSegment(start=1.0, end=2.0, text="你好", language="zh"),
    ]
    transcript = MediaTranscript(segments=segments, duration=2.0)
    fake_client = MagicMock()

    with patch.object(media_translation, "translate_texts") as mock_translate:
        mock_translate.return_value = (
            {("fr", "hello"): "bonjour", ("fr", "你好"): "salut"},
            2, 0, False,
        )
        media_translation.translate_transcript(transcript, ["fr"], fake_client)

    mock_translate.assert_called_once()
    args, kwargs = mock_translate.call_args
    assert args[0] == ["hello", "你好"]
    assert args[1] == ["fr"]
    assert args[2] is None, (
        "src_lang must be None (auto) — independent of each segment's "
        "STT-detected `language` field, which is informational only"
    )
    assert args[3] is fake_client
    assert kwargs.get("use_json_body") is False, (
        "media transcripts must skip the JSON-envelope/echoed-source-retry "
        "path — a same-language segment producing translation == source is "
        "an expected valid outcome here, not a failure to recover from"
    )
    assert kwargs.get("critique_enabled") is False, (
        "media transcripts must skip the critique/revision loop — exactly "
        "one translation call per segment"
    )


def test_translate_transcript_writes_translation_back_onto_matching_segment_only():
    segments = [
        TranscriptSegment(start=0.0, end=1.0, text="hello", language="en"),
        TranscriptSegment(start=1.0, end=2.0, text="world", language="en"),
    ]
    transcript = MediaTranscript(segments=segments, duration=2.0)

    with patch.object(media_translation, "translate_texts") as mock_translate:
        mock_translate.return_value = (
            {
                ("fr", "hello"): "bonjour",
                ("fr", "world"): "monde",
                ("de", "hello"): "hallo",
                ("de", "world"): "welt",
            },
            4, 0, False,
        )
        media_translation.translate_transcript(transcript, ["fr", "de"], MagicMock())

    assert segments[0].translated_text == {"fr": "bonjour", "de": "hallo"}
    assert segments[1].translated_text == {"fr": "monde", "de": "welt"}


def test_translate_transcript_skips_translate_texts_call_when_no_segments():
    transcript = MediaTranscript(segments=[], duration=0.0)

    with patch.object(media_translation, "translate_texts") as mock_translate:
        media_translation.translate_transcript(transcript, ["fr"], MagicMock())

    mock_translate.assert_not_called()


def test_translate_transcript_leaves_translated_text_empty_for_missing_map_entry():
    """A segment whose text never made it into translate_texts' returned map
    (e.g. it failed translation) must not raise and must not fabricate an
    entry — translated_text stays empty for that target."""
    segments = [TranscriptSegment(start=0.0, end=1.0, text="hello", language="en")]
    transcript = MediaTranscript(segments=segments, duration=1.0)

    with patch.object(media_translation, "translate_texts") as mock_translate:
        mock_translate.return_value = ({}, 0, 1, False)
        media_translation.translate_transcript(transcript, ["fr"], MagicMock())

    assert segments[0].translated_text == {}
