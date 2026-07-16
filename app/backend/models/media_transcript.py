"""Media transcript data models (STT + translation pipeline)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    language: Optional[str] = None  # detected FOR THIS SEGMENT, not the whole file
    translated_text: Dict[str, str] = field(default_factory=dict)  # target lang code -> translation
    speaker: Optional[str] = None


@dataclass
class MediaTranscript:
    segments: List[TranscriptSegment]
    duration: float
