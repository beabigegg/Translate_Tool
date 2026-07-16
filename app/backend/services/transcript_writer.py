"""Bilingual transcript formatting (no SRT/VTT — plain-text, human-readable)."""

from __future__ import annotations

from typing import List

from app.backend.models.media_transcript import TranscriptSegment


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def write_bilingual_transcript(segments: List[TranscriptSegment], targets: List[str]) -> str:
    blocks = []
    for segment in segments:
        lines = [
            f"[{_format_timestamp(segment.start)} - {_format_timestamp(segment.end)}]",
            f"Language: {segment.language or 'unknown'}",
            segment.text,
        ]
        for target in targets:
            translation = segment.translated_text.get(target) or "(untranslated)"
            lines.append(f"{target}: {translation}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
