"""Media (STT + translation) API schemas."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class MediaJobCreateResponse(BaseModel):
    job_id: str


class MediaJobStatus(BaseModel):
    job_id: str
    stage: str
    status: str
    error: Optional[str] = None
    created_at: float
    updated_at: float


class TranscriptSegmentOut(BaseModel):
    start: float
    end: float
    text: str
    language: Optional[str] = None
    translated_text: Dict[str, str] = {}


class TranscriptResponse(BaseModel):
    job_id: str
    duration: float
    segments: List[TranscriptSegmentOut] = []
