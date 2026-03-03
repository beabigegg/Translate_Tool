"""API schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class JobCreateResponse(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    processed_files: int
    total_files: int
    error: Optional[str] = None
    output_ready: bool = False
    current_file: str = ""
    segments_done: int = 0
    segments_total: int = 0
    file_segments_done: int = 0
    file_segments_total: int = 0
    elapsed_seconds: float = 0.0
    overall_progress: float = 0.0
    segments_per_second: float = 0.0
    eta_seconds: Optional[float] = None


class ModelsResponse(BaseModel):
    models: List[str]


class ProfileItem(BaseModel):
    id: str
    name: str
    description: str
