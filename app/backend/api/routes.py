"""FastAPI routes with optimized SSE streaming."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.backend.api.schemas import JobCreateResponse, JobStatus, ModelsResponse
from app.backend.clients.ollama_client import list_ollama_models
from app.backend.config import SSE_IDLE_TIMEOUT_SECONDS
from app.backend.services.job_manager import JobManager

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


@router.post("/jobs", response_model=JobCreateResponse)
async def create_job(
    files: List[UploadFile] = File(...),
    targets: str = Form(...),
    src_lang: Optional[str] = Form(None),
    include_headers: bool = Form(False),
    model: Optional[str] = Form(None),
) -> JobCreateResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    target_list = [t.strip() for t in targets.split(",") if t.strip()]
    if not target_list:
        raise HTTPException(status_code=400, detail="No target languages provided")

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
            targets=target_list,
            src_lang=src_lang,
            include_headers=include_headers,
            model=model or "",
        )
        return JobCreateResponse(job_id=job.job_id)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Read output_ready within lock to ensure consistency
    with job.lock:
        output_zip = job.output_zip
        status = job.status
        processed = job.processed_files
        total = job.total_files
        error = job.error

    output_ready = output_zip is not None and output_zip.exists()

    return JobStatus(
        job_id=job.job_id,
        status=status,
        processed_files=processed,
        total_files=total,
        error=error,
        output_ready=output_ready,
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


@router.get("/jobs/{job_id}/logs")
async def stream_logs(job_id: str, request: Request, from_index: int = 0):
    """Stream job logs with client disconnect detection and idle timeout."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        idx = max(from_index, 0)
        idle_count = 0
        # Calculate max idle iterations (0.5s per iteration)
        max_idle = SSE_IDLE_TIMEOUT_SECONDS * 2

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            with job.lock:
                logs = list(job.logs)
                status = job.status

            # Send any new log entries
            if idx < len(logs):
                idle_count = 0
                while idx < len(logs):
                    line = logs[idx]
                    idx += 1
                    yield f"data: {line}\n\n"
            else:
                idle_count += 1
                # Terminate if idle for too long
                if idle_count > max_idle:
                    yield f"data: [SSE timeout after {SSE_IDLE_TIMEOUT_SECONDS}s idle]\n\n"
                    break

            # Check if job is done
            if status in {"completed", "failed", "stopped"}:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/stats")
def get_stats() -> dict:
    """Get system statistics for monitoring."""
    return {
        "jobs": job_manager.get_stats(),
    }
