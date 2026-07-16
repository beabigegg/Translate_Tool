"""Tests for bilingual transcript formatting (transcript_writer.py).

Pure logic module, no external deps — no mocking needed.
"""

from __future__ import annotations

from app.backend.models.media_transcript import TranscriptSegment
from app.backend.services.transcript_writer import write_bilingual_transcript


# ---------------------------------------------------------------------------
# Timestamp formatting
# ---------------------------------------------------------------------------

def test_timestamp_formatted_as_hh_mm_ss():
    segment = TranscriptSegment(start=5.0, end=10.0, text="Hi")
    out = write_bilingual_transcript([segment], [])
    assert "[00:00:05 - 00:00:10]" in out


def test_timestamp_has_no_milliseconds():
    segment = TranscriptSegment(start=5.123, end=10.987, text="Hi")
    out = write_bilingual_transcript([segment], [])
    assert "." not in out.split("\n")[0]
    assert "[00:00:05 - 00:00:10]" in out


def test_timestamp_rolls_over_hours_and_minutes():
    segment = TranscriptSegment(start=3661.0, end=7325.0, text="Hi")
    out = write_bilingual_transcript([segment], [])
    assert "[01:01:01 - 02:02:05]" in out


# ---------------------------------------------------------------------------
# Detected-language line
# ---------------------------------------------------------------------------

def test_detected_language_line_present():
    segment = TranscriptSegment(start=0.0, end=1.0, text="Hi", language="en")
    out = write_bilingual_transcript([segment], [])
    assert "Language: en" in out


def test_missing_language_falls_back_to_unknown():
    segment = TranscriptSegment(start=0.0, end=1.0, text="Hi", language=None)
    out = write_bilingual_transcript([segment], [])
    assert "Language: unknown" in out


# ---------------------------------------------------------------------------
# Source text
# ---------------------------------------------------------------------------

def test_source_text_included():
    segment = TranscriptSegment(start=0.0, end=1.0, text="Hello world", language="en")
    out = write_bilingual_transcript([segment], [])
    assert "Hello world" in out


# ---------------------------------------------------------------------------
# Target-language lines
# ---------------------------------------------------------------------------

def test_one_line_per_target_language():
    segment = TranscriptSegment(
        start=0.0,
        end=1.0,
        text="Hello",
        language="en",
        translated_text={"zh": "你好", "ja": "こんにちは"},
    )
    out = write_bilingual_transcript([segment], ["zh", "ja"])
    assert "zh: 你好" in out
    assert "ja: こんにちは" in out


def test_target_language_line_order_matches_targets_arg():
    segment = TranscriptSegment(
        start=0.0,
        end=1.0,
        text="Hello",
        language="en",
        translated_text={"zh": "你好", "ja": "こんにちは"},
    )
    out = write_bilingual_transcript([segment], ["ja", "zh"])
    ja_idx = out.index("ja: こんにちは")
    zh_idx = out.index("zh: 你好")
    assert ja_idx < zh_idx


def test_missing_translation_renders_untranslated_marker():
    segment = TranscriptSegment(
        start=0.0, end=1.0, text="Hello", language="en", translated_text={}
    )
    out = write_bilingual_transcript([segment], ["fr"])
    assert "fr: (untranslated)" in out


def test_empty_string_translation_renders_untranslated_marker():
    """Falsy-but-present translation (empty string) must still fall back, not print blank."""
    segment = TranscriptSegment(
        start=0.0, end=1.0, text="Hello", language="en", translated_text={"fr": ""}
    )
    out = write_bilingual_transcript([segment], ["fr"])
    assert "fr: (untranslated)" in out


def test_no_target_language_lines_when_targets_empty():
    segment = TranscriptSegment(
        start=0.0, end=1.0, text="Hello", language="en", translated_text={"fr": "Bonjour"}
    )
    out = write_bilingual_transcript([segment], [])
    assert "fr:" not in out


# ---------------------------------------------------------------------------
# Multi-segment output / block separation
# ---------------------------------------------------------------------------

def test_multi_segment_produces_correct_number_of_blocks():
    segments = [
        TranscriptSegment(start=0.0, end=1.0, text="First", language="en"),
        TranscriptSegment(start=1.0, end=2.0, text="Second", language="en"),
        TranscriptSegment(start=2.0, end=3.0, text="Third", language="en"),
    ]
    out = write_bilingual_transcript(segments, [])
    blocks = out.split("\n\n")
    assert len(blocks) == 3
    assert "First" in blocks[0]
    assert "Second" in blocks[1]
    assert "Third" in blocks[2]


def test_multi_segment_blocks_separated_by_blank_line():
    segments = [
        TranscriptSegment(start=0.0, end=1.0, text="First", language="en"),
        TranscriptSegment(start=1.0, end=2.0, text="Second", language="en"),
    ]
    out = write_bilingual_transcript(segments, [])
    assert "\n\n" in out
    # exactly one blank-line separator between exactly two blocks
    assert out.count("\n\n") == 1


def test_multi_segment_each_block_has_own_timestamp_and_language():
    segments = [
        TranscriptSegment(start=0.0, end=1.0, text="First", language="en"),
        TranscriptSegment(start=10.0, end=11.0, text="Second", language="fr"),
    ]
    out = write_bilingual_transcript(segments, [])
    blocks = out.split("\n\n")
    assert "[00:00:00 - 00:00:01]" in blocks[0]
    assert "Language: en" in blocks[0]
    assert "[00:00:10 - 00:00:11]" in blocks[1]
    assert "Language: fr" in blocks[1]


def test_empty_segments_list_produces_empty_string():
    out = write_bilingual_transcript([], [])
    assert out == ""


def test_single_segment_block_line_order():
    segment = TranscriptSegment(
        start=0.0,
        end=1.0,
        text="Hello",
        language="en",
        translated_text={"fr": "Bonjour"},
    )
    out = write_bilingual_transcript([segment], ["fr"])
    lines = out.split("\n")
    assert lines[0] == "[00:00:00 - 00:00:01]"
    assert lines[1] == "Language: en"
    assert lines[2] == "Hello"
    assert lines[3] == "fr: Bonjour"
