"""FastAPI routes."""

from __future__ import annotations

import asyncio
import io
import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.backend.api.schemas import (
    BlockQualityScore,
    JobAuditResponse,
    JobCreateResponse,
    JobJudgeApplyResponse,
    JobJudgeResponse,
    JobQualityResponse,
    JobStatus,
    LayoutFileVizResponse,
    LayoutVizResponse,
    MetricsResponse,
    ModelConfigItem,
    ModelsResponse,
    OutputMode,
    ProfileItem,
    ProviderHealthItem,
    ProviderModelEntry,
    RouteInfoEntry,
    RouteInfoResponse,
    TermApproveRequest,
    TermEditRequest,
    TermFlagNeedsReviewRequest,
    TermImportResult,
    TermItem,
    TermRejectRequest,
    TermStatsResponse,
    TestTranslationRequest,
    TestTranslationResult,
    WikidataCandidate,
    WikidataImportRequest,
    WikidataSearchRequest,
    WikidataSearchResponse,
)
from app.backend.services.metrics import get_metrics as _get_metrics_snapshot
from app.backend.clients.ollama_client import list_ollama_models
from app.backend.clients.openai_compatible_client import OpenAICompatibleClient
from app.backend.config import (
    JUDGE_ENABLED,
    ModelType,
    QE_DEVICE,
    QE_ENABLED,
    QE_MODEL_NAME,
    VRAM_METADATA,
    load_providers_config,
)
from app.backend.services.model_router import RouteGroup, get_route_info, resolve_route_groups

# Load provider config once at module initialisation.  Returns None when
# providers.yml is absent/malformed — callers fall back to Ollama table.
_providers_config = load_providers_config()
from app.backend.translation_profiles import get_profile, list_profiles
from app.backend.services.job_manager import JobManager, JOBS_DIR
from app.backend.services.translation_cache import get_cache
from app.backend.services.term_db import TermDB, _VALID_STATUSES

_term_db = TermDB()

router = APIRouter()
job_manager = JobManager()


def _sanitize_filename(name: str) -> str:
    return Path(name).name or "upload"


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics_endpoint() -> MetricsResponse:
    """Return current observability counter snapshot (BR-20..BR-24)."""
    return MetricsResponse(**_get_metrics_snapshot())


@router.get("/models", response_model=ModelsResponse)
def models() -> ModelsResponse:
    return ModelsResponse(models=list_ollama_models())


@router.get("/profiles", response_model=List[ProfileItem])
def profiles() -> List[ProfileItem]:
    return [
        ProfileItem(
            id=profile.id,
            name=profile.name,
            description=profile.description,
            model_type=profile.model_type,
        )
        for profile in list_profiles()
    ]


@router.get("/model-config", response_model=List[ModelConfigItem])
def model_config() -> List[ModelConfigItem]:
    items: List[ModelConfigItem] = []
    for model_type in ModelType:
        metadata = VRAM_METADATA.get(model_type)
        if not metadata:
            continue
        items.append(
            ModelConfigItem(
                model_type=model_type.value,
                model_size_gb=float(metadata["model_size_gb"]),
                kv_per_1k_ctx_gb=float(metadata["kv_per_1k_ctx_gb"]),
                default_num_ctx=int(metadata["default_num_ctx"]),
                min_num_ctx=int(metadata["min_num_ctx"]),
                max_num_ctx=int(metadata["max_num_ctx"]),
            )
        )
    return items


@router.get("/route-info", response_model=RouteInfoResponse)
def route_info(targets: str = "") -> RouteInfoResponse:
    """Return auto-routing model info for each requested target language."""
    target_list = [t.strip() for t in targets.split(",") if t.strip()]
    entries = [
        RouteInfoEntry(**entry)
        for entry in get_route_info(target_list, provider_config=_providers_config)
    ]
    return RouteInfoResponse(routes=entries)


@router.post("/jobs", response_model=JobCreateResponse)
async def create_job(
    files: List[UploadFile] = File(...),
    targets: str = Form(...),
    src_lang: Optional[str] = Form(None),
    include_headers: bool = Form(False),
    profile: Optional[str] = Form(None),
    num_ctx: Optional[int] = Form(None),
    pdf_output_format: str = Form("docx"),  # "docx" or "pdf"
    pdf_layout_mode: str = Form("overlay"),  # "overlay" or "side_by_side"
    mode: str = Form("translation"),  # "translation" or "extraction_only"
    enable_term_extraction: bool = Form(True),
    output_mode: OutputMode = Form(OutputMode.APPEND),
) -> JobCreateResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    target_list = [t.strip() for t in targets.split(",") if t.strip()]
    if not target_list:
        raise HTTPException(status_code=400, detail="No target languages provided")

    # Auto-routing: group targets by benchmark-optimal model, or use manual override
    route_groups_result = resolve_route_groups(
        target_list, profile_override=profile, provider_config=_providers_config
    )
    if route_groups_result is None:
        # Manual profile override: profile selects system-prompt; model/provider still come
        # from cloud routing when providers.yml is configured (p1-cloud-providers).
        explicit_profile = get_profile(profile)
        cloud_groups = resolve_route_groups(
            target_list, profile_override=None, provider_config=_providers_config
        ) if _providers_config else None
        if cloud_groups:
            # Use cloud provider + model, but apply the selected profile's system prompt.
            route_groups = [
                RouteGroup(
                    targets=g.targets,
                    model=g.model,
                    profile_id=explicit_profile.id,
                    model_type=g.model_type,
                    provider=g.provider,
                )
                for g in cloud_groups
            ]
        else:
            # No cloud config — fall back to profile's Ollama model (legacy path).
            route_groups = [RouteGroup(
                targets=target_list,
                model=explicit_profile.model,
                profile_id=explicit_profile.id,
                model_type=explicit_profile.model_type,
            )]
        ref_model_type = route_groups[0].model_type
    else:
        route_groups = route_groups_result
        ref_model_type = route_groups[0].model_type if route_groups else ModelType.GENERAL.value

    try:
        resolved_model_type = ModelType((ref_model_type or ModelType.GENERAL.value).lower())
    except ValueError:
        resolved_model_type = ModelType.GENERAL

    metadata = VRAM_METADATA.get(resolved_model_type, VRAM_METADATA[ModelType.GENERAL])
    min_num_ctx = int(metadata["min_num_ctx"])
    max_num_ctx = int(metadata["max_num_ctx"])
    if num_ctx is not None:
        if num_ctx <= 0:
            raise HTTPException(status_code=422, detail="num_ctx must be a positive integer")
        if not min_num_ctx <= num_ctx <= max_num_ctx:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"num_ctx must be between {min_num_ctx} and {max_num_ctx} "
                    f"for model_type={resolved_model_type.value}"
                ),
            )

    temp_dir = Path(tempfile.mkdtemp(prefix="translate_upload_"))
    stored_files: List[Path] = []
    try:
        for upload in files:
            dest = temp_dir / _sanitize_filename(upload.filename or "upload")
            with dest.open("wb") as f:
                shutil.copyfileobj(upload.file, f)
            stored_files.append(dest)
            await upload.close()

        job = job_manager.create_job(
            stored_files,
            route_groups=route_groups,
            src_lang=src_lang,
            include_headers=include_headers,
            num_ctx=num_ctx,
            pdf_output_format=pdf_output_format,
            pdf_layout_mode=pdf_layout_mode,
            mode=mode,
            enable_term_extraction=enable_term_extraction,
            output_mode=output_mode.value,
        )
        return JobCreateResponse(job_id=job.job_id)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Read all fields within lock to ensure consistency
    with job.lock:
        output_zip = job.output_zip
        status = job.status
        processed = job.processed_files
        total = job.total_files
        error = job.error
        current_file = job.current_file
        segments_done = job.segments_done
        segments_total = job.segments_total
        file_seg_done = job.file_segments_done
        file_seg_total = job.file_segments_total
        started_at = job.started_at
        term_summary = job.term_summary
        job_provider = getattr(job, "provider", None)  # p1-cloud-providers (AC-6)
        job_quality = getattr(job, "quality", None)
        job_audit = getattr(job, "audit", None)
        job_judge = getattr(job, "judge", None)
        job_judge_apply_status = getattr(job, "judge_apply_status", None)

    output_ready = output_zip is not None and output_zip.exists()

    # Compute derived progress values
    now = time.time()
    elapsed = (now - started_at) if started_at else 0.0

    if status in ("completed", "stopped", "failed"):
        overall_progress = 1.0 if status == "completed" else 0.0
        if total > 0:
            overall_progress = processed / total if status != "completed" else 1.0
    elif total > 0:
        file_frac = (file_seg_done / file_seg_total) if file_seg_total > 0 else 0.0
        overall_progress = (processed + file_frac) / total
    else:
        overall_progress = 0.0

    speed = (segments_done / elapsed) if elapsed > 1.0 else 0.0
    eta = None
    if overall_progress > 0.01 and status == "running":
        eta = elapsed * (1.0 - overall_progress) / overall_progress

    # Compute quality_score_avg from QE scores
    quality_score_avg: Optional[float] = None
    if job_quality and job_quality.scores:
        scores_list = [s.score for s in job_quality.scores]
        if scores_list:
            quality_score_avg = sum(scores_list) / len(scores_list)

    # Compute audit_hit_rate from terminology audit result
    audit_hit_rate: Optional[float] = None
    if job_audit is not None:
        audit_hit_rate = job_audit.terminology_hit_rate

    # Derive download_url: only when completed and zip file is present on disk
    download_url: Optional[str] = (
        f"/api/jobs/{job_id}/download"
        if (status == "completed" and output_ready)
        else None
    )

    # layout_viz.json is written during PDF parsing (before translation begins),
    # so it can become available while the job is still running.
    layout_viz_available = (JOBS_DIR / job_id / "layout_viz.json").exists()

    return JobStatus(
        job_id=job.job_id,
        status=status,
        processed_files=processed,
        total_files=total,
        error=error,
        output_ready=output_ready,
        current_file=current_file,
        segments_done=segments_done,
        segments_total=segments_total,
        file_segments_done=file_seg_done,
        file_segments_total=file_seg_total,
        elapsed_seconds=round(elapsed, 1),
        overall_progress=round(overall_progress, 4),
        segments_per_second=round(speed, 2),
        eta_seconds=round(eta, 1) if eta is not None else None,
        term_summary=term_summary,
        provider=job_provider,  # p1-cloud-providers (AC-6)
        quality_score_avg=quality_score_avg,
        audit_hit_rate=audit_hit_rate,
        judge_score=job_judge.score if job_judge else None,
        judge_apply_status=job_judge_apply_status,
        download_url=download_url,
        layout_viz_available=layout_viz_available,
        status_detail=getattr(job, "status_detail", None),
    )


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    if not job_manager.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "cancelled"}


@router.get("/jobs/{job_id}/quality", response_model=JobQualityResponse)
def job_quality(job_id: str) -> JobQualityResponse:
    """Return quality evaluation scores for a completed job (p2-comet-qe).

    Status semantics (HTTP 200 in all non-404 cases):
    - disabled: QE_ENABLED=false (default).
    - pending: job not yet completed or QE record not yet attached.
    - unavailable: QE was enabled but scoring failed.
    - available: scores are populated.
    Unknown job → HTTP 404.
    """
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not QE_ENABLED:
        return JobQualityResponse(job_id=job_id, status="disabled", scores=[])
    record = job_manager.get_quality(job_id)
    if record is None or record.qe_status == "pending":
        return JobQualityResponse(job_id=job_id, status="pending", scores=[])
    return JobQualityResponse(
        job_id=job_id,
        status=record.qe_status,
        scores=[
            BlockQualityScore(block_id=s.block_id, score=s.score, model=s.model)
            for s in (record.scores or [])
        ],
    )


@router.get("/jobs/{job_id}/audit", response_model=JobAuditResponse)
def job_audit(job_id: str) -> JobAuditResponse:
    """Return terminology audit result for a completed job (p2-term-audit)."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.audit is None:
        return JobAuditResponse(job_id=job_id, status="disabled")
    return JobAuditResponse(
        job_id=job_id,
        status="available",
        hit_rate=job.audit.terminology_hit_rate,
        unapplied_terms=job.audit.unapplied_terms,
        rejected_injections=job.audit.rejected_injections,
        total_approved=job.audit.total_approved,
        matched_approved=job.audit.matched_approved,
    )


@router.get("/jobs/{job_id}/judge", response_model=JobJudgeResponse)
def get_job_judge(job_id: str) -> JobJudgeResponse:
    """Return LLM judge evaluation results for a completed job (p3-llm-judge).

    Status semantics (HTTP 200 in all non-404 cases):
    - disabled: JUDGE_ENABLED=false (default).
    - unavailable: Gemma was unreachable or any exception occurred.
    - available: score/feedback/attempts are populated.
    Unknown job → HTTP 404.
    """
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not JUDGE_ENABLED:
        return JobJudgeResponse(job_id=job_id, judge_status="disabled")
    judge = getattr(job, "judge", None)
    if judge is None:
        return JobJudgeResponse(job_id=job_id, judge_status="unavailable")
    return JobJudgeResponse(
        job_id=job_id,
        judge_status=judge.judge_status,
        score=judge.score,
        source_text=judge.source_text,
        translated_text=judge.translated_text,
        feedback=judge.feedback,
        attempts=judge.attempts if judge.judge_status == "available" else None,
        model=judge.model,
    )


@router.post("/jobs/{job_id}/judge/apply", status_code=202)
def post_job_judge_apply(job_id: str) -> JobJudgeApplyResponse:
    """Trigger async re-render of the job's output using the judge's per-block map.

    Preconditions (else HTTP 409, per BR-76):
    1. job.status == "completed"
    2. JUDGE_ENABLED is True
    3. judge_status == "available"
    4. retranslated_blocks is non-empty
    5. input_dir exists on disk

    Returns HTTP 202 {"status": "applying"} when dispatched.
    If already applying (BR-77), returns 202 without spawning a second worker.
    """
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    with job.lock:
        status = job.status
        judge = getattr(job, "judge", None)
        apply_status = getattr(job, "judge_apply_status", None)
        input_dir = job.input_dir

    # BR-77: idempotent while applying
    if apply_status == "applying":
        return JobJudgeApplyResponse(status="applying")

    # BR-76: precondition checks → HTTP 409
    if status != "completed":
        raise HTTPException(status_code=409, detail="Job is not completed")
    if not JUDGE_ENABLED:
        raise HTTPException(status_code=409, detail="JUDGE_ENABLED is false")
    if judge is None or judge.judge_status != "available":
        raise HTTPException(status_code=409, detail="Judge result not available")
    if not judge.retranslated_blocks:
        raise HTTPException(status_code=409, detail="No retranslated blocks to apply")
    if not input_dir.exists():
        raise HTTPException(status_code=409, detail="Source input directory no longer on disk (evicted)")

    # Dispatch the apply worker (sets judge_apply_status="applying" under lock)
    job_manager.apply_judge(job_id)
    return JobJudgeApplyResponse(status="applying")


@router.get("/jobs/{job_id}/layout", response_model=LayoutVizResponse)
def job_layout(job_id: str) -> LayoutVizResponse:
    """Return layout detection visualization data for a PDF job.

    Supports multi-file jobs: each PDF's viz is stored under its filename key.
    Returns 404 when job not found or layout data has not yet been written (non-PDF
    jobs or jobs where parsing has not started).
    """
    import json

    if job_id not in job_manager.jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    viz_path = JOBS_DIR / job_id / "layout_viz.json"
    if not viz_path.exists():
        raise HTTPException(status_code=404, detail="Layout data not available for this job")

    try:
        data = json.loads(viz_path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read layout data")

    # Support both new multi-file format {"files": {...}} and legacy single-file format
    if "files" in data:
        files_raw = data["files"]
    else:
        # Legacy: {"file_name": ..., "pages": [...]}
        files_raw = {data.get("file_name", "unknown.pdf"): data}

    files = [
        LayoutFileVizResponse(
            file_name=f.get("file_name", name),
            total_pages=f.get("total_pages", len(f.get("pages", []))),
            pages=f.get("pages", []),
        )
        for name, f in files_raw.items()
    ]
    return LayoutVizResponse(job_id=job_id, files=files)


@router.get("/jobs/{job_id}/layout/page/{file_stem}/{page_num}")
def job_layout_page(job_id: str, file_stem: str, page_num: int):
    """Serve a rendered JPEG thumbnail for the layout viz page overlay.

    file_stem: filename without extension (e.g. "document" for "document.pdf").
    page_num: 1-based page number.
    """
    if job_id not in job_manager.jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    img_path = JOBS_DIR / job_id / "layout_pages" / file_stem / f"page_{page_num}.jpg"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Page image not available")
    return FileResponse(str(img_path), media_type="image/jpeg")


@router.get("/jobs/{job_id}/download")
def download(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    with job.lock:
        output_zip = job.output_zip

    if not output_zip or not output_zip.exists():
        raise HTTPException(status_code=404, detail="Output not ready")
    return FileResponse(output_zip, filename=f"{job_id}.zip")



@router.get("/stats")
def get_stats() -> dict:
    """Get system statistics for monitoring."""
    return {
        "jobs": job_manager.get_stats(),
    }


@router.get("/cache/stats")
def cache_stats() -> dict:
    """Return translation cache statistics."""
    cache = get_cache()
    if cache is None:
        return {"enabled": False, "entries": 0, "db_size_bytes": 0, "db_path": None}
    info = cache.stats()
    return {"enabled": True, **info}


@router.delete("/cache")
def clear_cache(model: Optional[str] = None) -> dict:
    """Clear translation cache. Optionally filter by model."""
    cache = get_cache()
    if cache is None:
        return {"enabled": False, "cleared": 0}
    cleared = cache.clear(model=model)
    return {"enabled": True, "cleared": cleared}


# ---------------------------------------------------------------------------
# Term DB API
# ---------------------------------------------------------------------------

@router.get("/terms/stats", response_model=TermStatsResponse)
def terms_stats() -> TermStatsResponse:
    """Return term database statistics."""
    stats = _term_db.get_stats()
    by_status = stats.get("by_status", {})
    return TermStatsResponse(
        total=stats["total"],
        unverified=stats.get("unverified", 0),
        by_target_lang=stats.get("by_target_lang", {}),
        by_domain=stats.get("by_domain", {}),
        needs_review=by_status.get("needs_review", 0),
        approved=by_status.get("approved", 0),
        rejected=by_status.get("rejected", 0),
        by_status=by_status,
    )


@router.get("/terms/export")
def terms_export(format: str = "json", status: Optional[str] = None):
    """Download term database. format: json|csv|xlsx. status: approved|unverified|all (default all)."""
    fmt = format.lower()
    if fmt not in ("json", "csv", "xlsx"):
        raise HTTPException(status_code=400, detail="format must be json, csv, or xlsx")
    status_filter = status if status in _VALID_STATUSES else None

    import tempfile as _tempfile

    with _tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    suffix_str = f"_{status_filter}" if status_filter else ""
    try:
        if fmt == "json":
            _term_db.export_json(tmp_path, status_filter=status_filter)
            media_type = "application/json"
        elif fmt == "csv":
            _term_db.export_csv(tmp_path, status_filter=status_filter)
            media_type = "text/csv"
        else:
            _term_db.export_xlsx(tmp_path, status_filter=status_filter)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        return FileResponse(
            tmp_path,
            media_type=media_type,
            filename=f"term_db{suffix_str}.{fmt}",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/terms/import", response_model=TermImportResult)
async def terms_import(
    file: UploadFile = File(...),
    strategy: str = "skip",
) -> TermImportResult:
    """Import terms from a JSON or CSV file.
    strategy: skip | overwrite | merge | force
    - overwrite/merge protect already-approved records
    - force overwrites everything including approved (intentional correction)
    """
    if strategy not in ("skip", "overwrite", "merge", "force"):
        raise HTTPException(status_code=400, detail="strategy must be skip, overwrite, merge, or force")

    suffix = Path(file.filename or "import.json").suffix.lower()
    if suffix not in (".json", ".csv"):
        raise HTTPException(status_code=400, detail="Only .json and .csv files are supported")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)
    await file.close()

    try:
        counts = _term_db.import_file(tmp_path, strategy=strategy)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    return TermImportResult(
        inserted=counts.get("inserted", 0),
        skipped=counts.get("skipped", 0),
        overwritten=counts.get("overwritten", 0),
    )


@router.get("/terms/unverified", response_model=List[TermItem])
def terms_unverified(
    target_lang: Optional[str] = None,
    domain: Optional[str] = None,
) -> List[TermItem]:
    """List unverified terms pending human review."""
    terms = _term_db.get_unverified(target_lang=target_lang, domain=domain)
    return [
        TermItem(
            source_text=t.source_text,
            target_text=t.target_text,
            source_lang=t.source_lang,
            target_lang=t.target_lang,
            domain=t.domain,
            context_snippet=t.context_snippet,
            confidence=t.confidence,
            usage_count=t.usage_count,
            status=t.status,
        )
        for t in terms
    ]


@router.post("/terms/approve")
def terms_approve(body: TermApproveRequest):
    """Mark a term as approved for prompt injection."""
    found = _term_db.approve(body.source_text, body.target_lang, body.domain)
    if not found:
        raise HTTPException(status_code=404, detail="Term not found")
    return {"ok": True}


@router.post("/terms/reject")
def terms_reject(req: TermRejectRequest):
    """Transition a term to rejected status."""
    ok = _term_db.reject(req.source_text, req.target_lang, req.domain)
    if not ok:
        raise HTTPException(status_code=404, detail="Term not found")
    return {"status": "rejected"}


@router.post("/terms/flag-needs-review")
def terms_flag_needs_review(req: TermFlagNeedsReviewRequest):
    """Transition a term to needs_review status."""
    ok = _term_db.flag_needs_review(req.source_text, req.target_lang, req.domain)
    if not ok:
        raise HTTPException(status_code=404, detail="Term not found")
    return {"status": "needs_review"}


@router.get("/terms/approved", response_model=List[TermItem])
def terms_approved(
    target_lang: Optional[str] = None,
    domain: Optional[str] = None,
) -> List[TermItem]:
    """List approved terms, optionally filtered."""
    terms = _term_db.get_approved(target_lang=target_lang, domain=domain)
    return [
        TermItem(
            source_text=t.source_text,
            target_text=t.target_text,
            source_lang=t.source_lang,
            target_lang=t.target_lang,
            domain=t.domain,
            context_snippet=t.context_snippet,
            confidence=t.confidence,
            usage_count=t.usage_count,
            status=t.status,
        )
        for t in terms
    ]


@router.patch("/terms/edit")
def terms_edit(body: TermEditRequest):
    """Edit the target_text (and optionally confidence) of any term. Sets status='approved'."""
    found = _term_db.edit_term(
        body.source_text,
        body.target_lang,
        body.domain,
        target_text=body.target_text,
        confidence=body.confidence,
    )
    if not found:
        raise HTTPException(status_code=404, detail="Term not found")
    return {"ok": True}


# ------------------------------------------------------------------
# Wikidata term lookup
# ------------------------------------------------------------------

@router.post("/terms/wikidata/search", response_model=WikidataSearchResponse)
def wikidata_search(body: WikidataSearchRequest):
    """Search Wikidata for a term and return multilingual translations."""
    from app.backend.services.wikidata_lookup import search_wikidata

    candidates = search_wikidata(
        term=body.term,
        source_lang=body.source_lang,
        target_langs=body.target_langs,
    )
    return WikidataSearchResponse(
        term=body.term,
        candidates=[WikidataCandidate(**c) for c in candidates],
    )


@router.post("/terms/wikidata/import")
def wikidata_import(body: WikidataImportRequest):
    """Import a single Wikidata lookup result into the term database."""
    from app.backend.models.term import Term

    term = Term(
        source_text=body.source_text,
        target_text=body.target_text,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
        domain=body.domain,
        context_snippet=f"wikidata:{body.entity_id}" if body.entity_id else "",
        confidence=0.9,
        status="unverified",
    )
    result = _term_db.insert(term, strategy="merge")
    return {"ok": True, "result": result}


# ---------------------------------------------------------------------------
# Provider API routes (settings-page-cloud-redesign, BR-63/BR-64/BR-65)
# ---------------------------------------------------------------------------


@router.get("/providers/health", response_model=List[ProviderHealthItem], response_model_exclude_none=True)
def providers_health(request: Request) -> List[ProviderHealthItem]:
    """Return health status for each configured provider (BR-63).

    PANJIT is always probed with a lightweight GET /v1/models call.
    DeepSeek is probed only when the ``X-DeepSeek-Api-Key`` request header is
    non-empty; otherwise status is ``"not_configured"`` and NO network call is
    made.  The key is read from a header (not a query param) to prevent exposure
    in server access logs and browser history.
    Gracefully returns [] when ``_providers_config`` is None.
    """
    deepseek_api_key: Optional[str] = request.headers.get("X-DeepSeek-Api-Key") or None
    if not _providers_config:
        return []

    results: List[ProviderHealthItem] = []
    providers = _providers_config.get("providers", [])

    for provider in providers:
        pid = provider.get("id", "")
        if not pid:
            continue

        # Probe disabled DeepSeek when a caller-supplied key is present so the
        # user can verify their key even if DEEPSEEK_ENABLED=false in providers.yml.
        # All other disabled providers are still skipped.
        if not provider.get("enabled", False):
            if pid == "deepseek" and (deepseek_api_key or "").strip():
                pass  # allow probe below
            else:
                continue

        base_url = provider.get("base_url", "")
        api_key = provider.get("api_key", "")

        if pid == "deepseek":
            # BR-63 / BR-65: probe only when caller supplies a key
            supplied_key = (deepseek_api_key or "").strip()
            if not supplied_key:
                results.append(ProviderHealthItem(provider=pid, status="not_configured"))
                continue
            probe_key = supplied_key
        else:
            probe_key = api_key

        # Skip providers without a base_url (misconfigured)
        if not base_url:
            results.append(ProviderHealthItem(provider=pid, status="offline"))
            continue

        # PANJIT uses verify_ssl=False (self-signed internal cert, per existing pattern)
        verify_ssl = pid != "panjit"

        client = OpenAICompatibleClient(
            base_url=base_url,
            api_key=probe_key,
            model="",
            provider_id=pid,
            # Use shorter timeouts for health probes to keep the UI responsive
            connect_timeout=10.0,
            read_timeout=30.0,
            verify_ssl=verify_ssl,
        )
        t0 = time.monotonic()
        try:
            ok, _msg = client.health()
            latency_ms = (time.monotonic() - t0) * 1000.0
            status = "online" if ok else "offline"
        except Exception:
            latency_ms = (time.monotonic() - t0) * 1000.0
            status = "offline"

        results.append(ProviderHealthItem(
            provider=pid,
            status=status,
            latency_ms=round(latency_ms, 1),
        ))

    return results


@router.get("/providers/models", response_model=List[ProviderModelEntry], response_model_exclude_none=True)
def providers_models() -> List[ProviderModelEntry]:
    """Return model names from the in-memory providers config (BR-63).

    Sources ``models.translate`` → ``translate_model`` and
    ``models.long_doc`` → ``long_doc_model`` from each enabled provider entry.
    NO live /v1/models network call is made.
    Gracefully returns [] when ``_providers_config`` is None.
    """
    if not _providers_config:
        return []

    results: List[ProviderModelEntry] = []
    providers = _providers_config.get("providers", [])

    for provider in providers:
        pid = provider.get("id", "")
        if not pid:
            continue
        if not provider.get("enabled", False):
            continue

        models_map = provider.get("models") or {}
        translate_model: Optional[str] = models_map.get("translate") or None
        long_doc_model: Optional[str] = models_map.get("long_doc") or None

        results.append(ProviderModelEntry(
            provider=pid,
            translate_model=translate_model,
            long_doc_model=long_doc_model,
        ))

    return results


@router.post("/providers/test-translation", response_model=List[TestTranslationResult], response_model_exclude_none=True, status_code=200)
async def providers_test_translation(req: TestTranslationRequest) -> List[TestTranslationResult]:
    """Run a parallel test translation across requested models (BR-64, BR-65).

    - Synchronous response (no job_id, no BackgroundTasks).
    - All model slots run in parallel via asyncio.gather.
    - Blocking requests-based client calls are wrapped in asyncio.to_thread.
    - Partial failure is isolated per slot; HTTP 200 always returned when body parses.
    - DeepSeek slot without a key returns error without any network call (BR-65).
    - COMET score added when QE_ENABLED=True (BR-64).
    - Response serialised with exclude_none=True so comet_score is absent when
      QE_ENABLED=False (not null, per contract).

    SECURITY (BR-65):
    - deepseek_api_key comes ONLY from req.deepseek_api_key — never from .env.
    - The key is NEVER logged at any level.
    - The key is discarded at the end of this request.
    """
    if not _providers_config:
        return []

    providers_by_id = {
        p["id"]: p
        for p in _providers_config.get("providers", [])
        if p.get("id") and p.get("enabled", False)
    }

    # Resolve (model_id, provider_id) slots to run.
    # If req.models is supplied, use those; otherwise default to all enabled providers.
    if req.models:
        # Map requested model strings to providers.  Accept either a model name
        # (e.g. "gpt-oss:120b") found in a provider's models map, or a provider
        # id shortcut (e.g. "panjit") which resolves to that provider's
        # translate model.  If neither matches, emit an error slot.
        slots: List[tuple] = []
        for model_id in req.models:
            found = False
            for pid, pdata in providers_by_id.items():
                pmodels = pdata.get("models") or {}
                if model_id in pmodels.values():
                    slots.append((model_id, pid))
                    found = True
                    break
                if model_id == pid:
                    translate_model = pmodels.get("translate")
                    if translate_model:
                        slots.append((translate_model, pid))
                    found = True
                    break
            if not found:
                # Unknown model — include an error slot so the caller sees it
                slots.append((model_id, "unknown"))
    else:
        # Default: one slot per enabled provider using its translate model
        slots = []
        for pid, pdata in providers_by_id.items():
            pmodels = pdata.get("models") or {}
            translate_model = pmodels.get("translate")
            if translate_model:
                slots.append((translate_model, pid))

    async def _run_slot(model_id: str, provider_id: str) -> dict:
        """Execute one translation slot and return a result dict."""
        t_start = time.monotonic()

        # Unknown provider — error immediately, no network call
        if provider_id == "unknown":
            return TestTranslationResult(
                model_id=model_id,
                provider=provider_id,
                duration_ms=0.0,
                error=f"Model '{model_id}' not found in any enabled provider",
            ).model_dump(exclude_none=True)

        pdata = providers_by_id.get(provider_id, {})

        # DeepSeek: require caller-supplied key (BR-65) — no .env fallback
        if provider_id == "deepseek":
            supplied_key = (req.deepseek_api_key or "").strip()
            if not supplied_key:
                return TestTranslationResult(
                    model_id=model_id,
                    provider=provider_id,
                    duration_ms=0.0,
                    error="DeepSeek API key not provided",
                ).model_dump(exclude_none=True)
            effective_api_key = supplied_key
        else:
            effective_api_key = pdata.get("api_key", "")

        base_url = pdata.get("base_url", "")
        if not base_url:
            return TestTranslationResult(
                model_id=model_id,
                provider=provider_id,
                duration_ms=round((time.monotonic() - t_start) * 1000.0, 1),
                error=f"Provider '{provider_id}' has no base_url configured",
            ).model_dump(exclude_none=True)

        verify_ssl = provider_id != "panjit"

        client = OpenAICompatibleClient(
            base_url=base_url,
            api_key=effective_api_key,
            model=model_id,
            provider_id=provider_id,
            connect_timeout=120.0,
            read_timeout=300.0,
            verify_ssl=verify_ssl,
        )

        # Translate each target language; collect the first successful result
        # (test translation is a single sentence — we take the first target).
        target = req.targets[0] if req.targets else "en"
        try:
            ok, translation_text = await asyncio.to_thread(
                client.translate_once, req.text, target, req.src_lang
            )
        except Exception as exc:
            duration_ms = round((time.monotonic() - t_start) * 1000.0, 1)
            return TestTranslationResult(
                model_id=model_id,
                provider=provider_id,
                duration_ms=duration_ms,
                error=str(exc),
            ).model_dump(exclude_none=True)

        duration_ms = round((time.monotonic() - t_start) * 1000.0, 1)

        if not ok:
            return TestTranslationResult(
                model_id=model_id,
                provider=provider_id,
                duration_ms=duration_ms,
                error=translation_text,
            ).model_dump(exclude_none=True)

        # Successful translation — optionally score with COMET (BR-64)
        comet_score: Optional[float] = None
        if QE_ENABLED and translation_text:
            try:
                from app.backend.services import quality_evaluator as _qe
                model_obj = await asyncio.to_thread(
                    _qe.load_model, QE_MODEL_NAME, QE_DEVICE
                )
                scores = await asyncio.to_thread(
                    _qe.score_blocks,
                    model_obj,
                    [(req.text, translation_text)],
                    QE_DEVICE,
                )
                if scores:
                    comet_score = scores[0]
            except Exception as exc:
                logger.warning(
                    "[providers/test-translation] QE scoring failed for model=%s: %s: %s",
                    model_id, type(exc).__name__, exc,
                )

        return TestTranslationResult(
            model_id=model_id,
            provider=provider_id,
            duration_ms=duration_ms,
            translation=translation_text,
            comet_score=comet_score,
        ).model_dump(exclude_none=True)

    # Fan out all slots in parallel
    coros = [_run_slot(model_id, provider_id) for model_id, provider_id in slots]
    results_raw = await asyncio.gather(*coros, return_exceptions=True)

    # Convert any unexpected exceptions to error slots
    final_results: List[dict] = []
    for (model_id, provider_id), raw in zip(slots, results_raw):
        if isinstance(raw, Exception):
            final_results.append(
                TestTranslationResult(
                    model_id=model_id,
                    provider=provider_id,
                    duration_ms=0.0,
                    error=f"Unexpected error: {raw}",
                ).model_dump(exclude_none=True)
            )
        else:
            final_results.append(raw)

    return final_results
