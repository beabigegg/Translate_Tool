"""Media (STT + translation) FastAPI routes."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.backend.api.media_schemas import (
    MediaJobCreateResponse,
    MediaJobStatus,
    TranscriptResponse,
    TranscriptSegmentOut,
)
from app.backend.api.routes import _sanitize_filename
from app.backend.config import MEDIA_DENOISE_DEFAULT, MEDIA_MAX_UPLOAD_MB
from app.backend.services.media_job_manager import media_job_manager

router = APIRouter(prefix="/api/media")

_UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB
_MEDIA_MAX_UPLOAD_BYTES = MEDIA_MAX_UPLOAD_MB * 1024 * 1024


def _copy_upload_within_limit(upload: UploadFile, dest: Path, max_bytes: int) -> None:
    """Stream upload to disk, aborting (413) once max_bytes is exceeded.

    The document upload path (routes.py:250-258) has no such guard; media
    files are far larger, so this checks actual bytes written rather than
    trusting a client-supplied Content-Length.
    """
    written = 0
    try:
        with dest.open("wb") as f:
            while True:
                chunk = upload.file.read(_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds MEDIA_MAX_UPLOAD_MB limit ({MEDIA_MAX_UPLOAD_MB} MB)",
                    )
                f.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise


@router.post("/jobs", response_model=MediaJobCreateResponse)
async def create_media_job(
    file: UploadFile = File(...),
    targets: str = Form(...),
    provider_override: Optional[str] = Form(None),
    model_override: Optional[str] = Form(None),
    profile: Optional[str] = Form(None),
    denoise: bool = Form(MEDIA_DENOISE_DEFAULT),
) -> MediaJobCreateResponse:
    target_list = [t.strip() for t in targets.split(",") if t.strip()]
    if not target_list:
        raise HTTPException(status_code=400, detail="No target languages provided")

    temp_dir = Path(tempfile.mkdtemp(prefix="media_upload_"))
    try:
        dest = temp_dir / _sanitize_filename(file.filename or "upload")
        _copy_upload_within_limit(file, dest, _MEDIA_MAX_UPLOAD_BYTES)
        await file.close()

        job = media_job_manager.create_job(
            dest,
            targets=target_list,
            provider_override=provider_override,
            model_override=model_override,
            profile=profile,
            denoise=denoise,
        )
        return MediaJobCreateResponse(job_id=job.job_id)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/jobs/{job_id}", response_model=MediaJobStatus)
def media_job_status(job_id: str) -> MediaJobStatus:
    job = media_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    with job.lock:
        return MediaJobStatus(
            job_id=job.job_id,
            stage=job.stage,
            status=job.status,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


@router.get("/jobs/{job_id}/transcript", response_model=TranscriptResponse)
def media_job_transcript(job_id: str) -> TranscriptResponse:
    job = media_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    with job.lock:
        status = job.status
        transcript = job.transcript
    if status != "completed":
        raise HTTPException(status_code=409, detail="Job not yet completed")
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not available")
    return TranscriptResponse(
        job_id=job_id,
        duration=transcript.duration,
        segments=[
            TranscriptSegmentOut(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                language=seg.language,
                translated_text=seg.translated_text,
            )
            for seg in transcript.segments
        ],
    )


@router.get("/jobs/{job_id}/download")
def media_job_download(job_id: str):
    job = media_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    with job.lock:
        output_txt_path = job.output_txt_path

    if not output_txt_path or not output_txt_path.exists():
        raise HTTPException(status_code=404, detail="Output not ready")
    return FileResponse(output_txt_path, media_type="text/plain", filename=output_txt_path.name)


@router.post("/jobs/{job_id}/cancel")
def media_job_cancel(job_id: str) -> dict:
    if not media_job_manager.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "cancelled"}
