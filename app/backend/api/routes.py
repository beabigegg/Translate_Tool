"""FastAPI routes."""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.backend.api.schemas import JobCreateResponse, JobStatus, ModelConfigItem, ModelsResponse, ProfileItem, RouteInfoEntry, RouteInfoResponse
from app.backend.clients.ollama_client import list_ollama_models
from app.backend.config import ModelType, VRAM_METADATA
from app.backend.services.model_router import RouteGroup, get_route_info, resolve_route_groups
from app.backend.translation_profiles import get_profile, list_profiles
from app.backend.services.job_manager import JobManager
from app.backend.services.translation_cache import get_cache

router = APIRouter()
job_manager = JobManager()


def _sanitize_filename(name: str) -> str:
    return Path(name).name or "upload"


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


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
    entries = [RouteInfoEntry(**entry) for entry in get_route_info(target_list)]
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
) -> JobCreateResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    target_list = [t.strip() for t in targets.split(",") if t.strip()]
    if not target_list:
        raise HTTPException(status_code=400, detail="No target languages provided")

    # Auto-routing: group targets by benchmark-optimal model, or use manual override
    route_groups_result = resolve_route_groups(target_list, profile_override=profile)
    if route_groups_result is None:
        # Manual profile override: all targets in one group with explicit profile's model
        explicit_profile = get_profile(profile)
        route_groups = [RouteGroup(
            targets=target_list,
            model=explicit_profile.model,
            profile_id=explicit_profile.id,
            model_type=explicit_profile.model_type,
        )]
        ref_model_type = explicit_profile.model_type
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
    )


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    if not job_manager.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "cancelled"}


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
