"""API schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OutputMode(str, Enum):
    APPEND = "append"
    REPLACE = "replace"
    BILINGUAL = "bilingual"
    ADJACENT = "adjacent"
    ANNOTATION = "annotation"


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
    provider: Optional[str] = None  # p1-cloud-providers: winning provider ID (AC-6)
    quality_score_avg: Optional[float] = None   # average COMET score when QE is enabled
    audit_hit_rate: Optional[float] = None       # terminology hit rate when audit ran
    judge_score: Optional[str] = None           # p3-llm-judge: latest judge score tier (高/中/低)
    judge_apply_status: Optional[str] = None    # p3-llm-judge: applying|applied|failed|null
    download_url: Optional[str] = None           # populated when job is completed and output zip exists
    layout_viz_available: bool = False           # True once layout_viz.json exists (PDF jobs only)
    status_detail: Optional[str] = None         # human-readable current stage during "running"
    warnings: Optional[List[str]] = None        # pdf-renderer-fallback-warn: render-quality degradation warnings
    # translation-progress-detail-ui (BR-105): single overwritten current-segment
    # snapshot — 5 core fields + 3 judge-phase fields, all optional/nullable (AC-1,
    # AC-2, AC-7, AC-9). current_stage enum: translate | critique | qe | adopt | judge.
    current_stage: Optional[str] = None
    current_segment_source: Optional[str] = None
    current_segment_draft: Optional[str] = None
    current_segment_qe_score: Optional[float] = None
    current_segment_adopted: Optional[bool] = None
    current_segment_judge_tier: Optional[str] = None      # 高 | 中 | 低; null unless current_stage == judge
    current_segment_judge_attempt: Optional[int] = None
    current_segment_judge_substep: Optional[str] = None   # scoring | retranslating


class TermImportResult(BaseModel):
    inserted: int
    skipped: int
    overwritten: int


class TermStatsResponse(BaseModel):
    total: int
    unverified: int = 0
    by_target_lang: Dict[str, int]
    by_domain: Dict[str, int]
    needs_review: int = 0
    approved: int = 0
    rejected: int = 0
    by_status: Dict[str, int] = {}


class TermItem(BaseModel):
    source_text: str
    target_text: str
    source_lang: str
    target_lang: str
    domain: str
    context_snippet: str
    confidence: float
    usage_count: int
    status: str


class TermApproveRequest(BaseModel):
    source_text: str
    target_lang: str
    domain: str


class TermRejectRequest(BaseModel):
    source_text: str
    target_lang: str
    domain: str


class TermFlagNeedsReviewRequest(BaseModel):
    source_text: str
    target_lang: str
    domain: str


class TermEditRequest(BaseModel):
    source_text: str
    target_lang: str
    domain: str
    target_text: str
    confidence: Optional[float] = None


class WikidataSearchRequest(BaseModel):
    term: str
    source_lang: str = "Chinese"
    target_langs: List[str] = ["English"]
    domain: str = "general"


class WikidataCandidate(BaseModel):
    entity_id: str
    source_label: str
    description: str
    labels: Dict[str, str]


class WikidataSearchResponse(BaseModel):
    term: str
    candidates: List[WikidataCandidate]


class WikidataImportRequest(BaseModel):
    source_text: str
    target_text: str
    source_lang: str
    target_lang: str
    domain: str = "general"
    entity_id: str = ""


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
    provider: Optional[str] = None  # p1-cloud-providers: resolved provider ID (AC-7)


class RouteInfoResponse(BaseModel):
    routes: List[RouteInfoEntry]


class MetricsResponse(BaseModel):
    translation_count: int
    translation_latency_mean_ms: float
    provider_failure_count: int
    font_cache_hits: int
    font_cache_misses: int


class BlockQualityScore(BaseModel):
    """Per-block quality score returned by the QE endpoint (p2-comet-qe)."""
    block_id: str
    score: float
    model: str


class JobQualityResponse(BaseModel):
    """Response body for GET /jobs/{job_id}/quality (p2-comet-qe)."""
    job_id: str
    status: str  # available | pending | disabled | unavailable
    scores: List[BlockQualityScore] = []


class JobAuditResponse(BaseModel):
    """Response body for GET /jobs/{job_id}/audit (p2-term-audit)."""
    job_id: str
    status: str  # available | disabled
    hit_rate: float = 0.0
    unapplied_terms: List[str] = []
    rejected_injections: List[str] = []
    total_approved: int = 0
    matched_approved: int = 0


class JobJudgeResponse(BaseModel):
    """Response body for GET /jobs/{job_id}/judge (p3-llm-judge)."""
    job_id: str
    judge_status: str  # available | disabled | unavailable
    score: Optional[str] = None          # 高 | 中 | 低; null unless judge_status=available
    source_text: Optional[str] = None    # representative joined source text
    translated_text: Optional[str] = None  # display-only joined final translation
    feedback: Optional[str] = None       # judge natural-language feedback
    attempts: Optional[int] = None       # iterations performed; null unless judge_status=available
    model: Optional[str] = None          # JUDGE_MODEL name; null unless judge_status=available


class JobJudgeApplyResponse(BaseModel):
    """Response body for POST /jobs/{job_id}/judge/apply (p3-llm-judge, 202)."""
    status: str  # always 'applying' on HTTP 202


# ---------------------------------------------------------------------------
# Provider API schemas (settings-page-cloud-redesign, BR-63/BR-64/BR-65)
# ---------------------------------------------------------------------------

class ProviderHealthItem(BaseModel):
    """Single element in GET /providers/health response (BR-63)."""
    provider: str
    status: str  # "online" | "offline" | "not_configured"
    latency_ms: Optional[float] = None


class ProviderModelEntry(BaseModel):
    """Single element in GET /providers/models response (BR-63)."""
    provider: str
    translate_model: Optional[str] = None
    long_doc_model: Optional[str] = None


class TestTranslationRequest(BaseModel):
    """Request body for POST /providers/test-translation (BR-64, BR-65)."""
    text: str = Field(..., min_length=1)
    src_lang: str
    targets: List[str] = Field(..., min_length=1)
    profile: Optional[str] = None
    models: Optional[List[str]] = None
    deepseek_api_key: Optional[str] = None


class TestTranslationResult(BaseModel):
    """Single element in POST /providers/test-translation response (BR-64).

    comet_score is Optional — serialise with exclude_none=True so the field is
    entirely absent (not null) when QE_ENABLED=False (BR-64 / AC-6 / AC-8).
    """
    model_id: str
    provider: str
    duration_ms: float
    translation: Optional[str] = None
    comet_score: Optional[float] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Layout visualization schemas (layout-viz change)
# ---------------------------------------------------------------------------

class LayoutBoxSchema(BaseModel):
    type: str
    bbox: List[float]
    score: float
    preview: str = ""


class LayoutPageSchema(BaseModel):
    page_num: int
    width: float
    height: float
    detector: str
    boxes: List[LayoutBoxSchema] = []


class LayoutFileVizResponse(BaseModel):
    file_name: str
    total_pages: int
    pages: List[LayoutPageSchema] = []


class LayoutVizResponse(BaseModel):
    job_id: str
    files: List[LayoutFileVizResponse] = []
