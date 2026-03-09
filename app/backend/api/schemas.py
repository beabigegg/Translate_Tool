"""API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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
    term_summary: Optional[Dict[str, Any]] = None


class TermImportResult(BaseModel):
    inserted: int
    skipped: int
    overwritten: int


class TermStatsResponse(BaseModel):
    total: int
    by_target_lang: Dict[str, int]
    by_domain: Dict[str, int]


class ModelsResponse(BaseModel):
    models: List[str]


class ProfileItem(BaseModel):
    id: str
    name: str
    description: str
    model_type: str


class ModelConfigItem(BaseModel):
    model_type: str
    model_size_gb: float
    kv_per_1k_ctx_gb: float
    default_num_ctx: int
    min_num_ctx: int
    max_num_ctx: int


class RouteInfoEntry(BaseModel):
    target: str
    model: str
    profile_id: str
    model_type: str
    is_primary: bool


class RouteInfoResponse(BaseModel):
    routes: List[RouteInfoEntry]
