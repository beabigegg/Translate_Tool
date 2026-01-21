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


class ModelsResponse(BaseModel):
    models: List[str]
