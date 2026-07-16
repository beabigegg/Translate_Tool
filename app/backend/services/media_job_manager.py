"""Media (audio/video) STT + translation job lifecycle management.

OrderedDict store, TTL/capacity cleanup, thread-per-job dispatch, lock +
stop_flag mechanics copied from job_manager.py. create_job/_run_job bodies
are new: they run the extract -> VAD -> denoise (optional, per VAD speech
span) -> STT -> translate -> render pipeline instead of the document
pipeline. VAD runs BEFORE denoise (not after) so denoising can chunk by
VAD's silence/pause boundaries instead of a fixed time window — see
media_preprocess.denoise_audio's docstring.
"""

from __future__ import annotations

import atexit
import shutil
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.backend.config import JOBS_DIR, MEDIA_JOB_TTL_HOURS, MEDIA_MAX_JOBS_IN_MEMORY
from app.backend.models.media_transcript import MediaTranscript
from app.backend.services import media_preprocess, media_translation, stt_engine, transcript_writer, vad_segmenter
from app.backend.services.media_client_resolver import resolve_media_client
from app.backend.utils.logging_utils import logger
from app.backend.utils.resource_utils import release_resources

# Sibling of JOBS_DIR (document pipeline) under the same data root — never
# shares a directory tree with the document JobManager.
MEDIA_JOBS_DIR: Path = JOBS_DIR.parent / "media"


@dataclass
class MediaJobRecord:
    job_id: str
    media_path: Path
    stage: str = "queued"
    status: str = "queued"
    transcript: Optional[MediaTranscript] = None
    output_txt_path: Optional[Path] = None
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    stop_flag: threading.Event = field(default_factory=threading.Event)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None


class _StopPipeline(Exception):
    """Internal control-flow signal: stop_flag was set between stages."""


def _log(job: MediaJobRecord, message: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    line = f"{timestamp} {message}"
    with job.lock:
        job.logs.append(line)
        job.updated_at = time.time()
    logger.info("[%s] %s", job.job_id, message)


class MediaJobManager:
    def __init__(self) -> None:
        MEDIA_JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self.jobs: "OrderedDict[str, MediaJobRecord]" = OrderedDict()
        self._cleanup_lock = threading.Lock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        self._cleanup_orphaned_dirs()
        self._start_cleanup_thread()
        atexit.register(self._shutdown)

    def _shutdown(self) -> None:
        self._shutdown_event.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)

    def _start_cleanup_thread(self) -> None:
        def cleanup_loop():
            interval_seconds = 30 * 60  # mirrors job_manager.py's CLEANUP_INTERVAL_MINUTES default
            while not self._shutdown_event.is_set():
                if self._shutdown_event.wait(timeout=interval_seconds):
                    break
                self._cleanup_expired_jobs()

        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True, name="media-job-cleanup")
        self._cleanup_thread.start()
        logger.info("Started media job cleanup thread")

    def _cleanup_orphaned_dirs(self) -> None:
        if not MEDIA_JOBS_DIR.exists():
            return
        cleaned = 0
        for job_dir in MEDIA_JOBS_DIR.iterdir():
            if job_dir.is_dir() and job_dir.name not in self.jobs:
                try:
                    shutil.rmtree(job_dir, ignore_errors=True)
                    cleaned += 1
                except Exception as exc:
                    logger.warning("Failed to cleanup orphaned media dir %s: %s", job_dir.name, exc)
        if cleaned > 0:
            logger.info("Cleaned %d orphaned media job directories on startup", cleaned)

    def _cleanup_expired_jobs(self) -> None:
        with self._cleanup_lock:
            now = time.time()
            ttl_seconds = MEDIA_JOB_TTL_HOURS * 3600
            expired_ids = [
                job_id
                for job_id, job in self.jobs.items()
                if job.status in {"completed", "failed", "cancelled"} and (now - job.updated_at) > ttl_seconds
            ]
            for job_id in expired_ids:
                self._remove_job(job_id, reason="TTL expired")

    def _cleanup_by_capacity(self) -> None:
        with self._cleanup_lock:
            while len(self.jobs) > MEDIA_MAX_JOBS_IN_MEMORY:
                oldest_id = next(
                    (jid for jid, j in self.jobs.items() if j.status in {"completed", "failed", "cancelled"}),
                    None,
                )
                if oldest_id:
                    self._remove_job(oldest_id, reason="capacity limit")
                else:
                    break  # all jobs still running, can't remove any

    def _remove_job(self, job_id: str, reason: str = "") -> None:
        job = self.jobs.pop(job_id, None)
        if job:
            job_dir = MEDIA_JOBS_DIR / job_id
            if job_dir.exists():
                try:
                    shutil.rmtree(job_dir, ignore_errors=True)
                except Exception as exc:
                    logger.warning("Failed to remove media job dir %s: %s", job_dir, exc)
            logger.debug("Removed media job %s (%s)", job_id, reason)

    def create_job(
        self,
        media_path: Path,
        targets: List[str],
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
        profile: Optional[str] = None,
        denoise: bool = True,
    ) -> MediaJobRecord:
        self._cleanup_by_capacity()

        job_id = uuid.uuid4().hex
        job_dir = MEDIA_JOBS_DIR / job_id
        input_dir = job_dir / "input"
        output_dir = job_dir / "output"
        work_dir = job_dir / "work"  # extract_audio/denoise_audio intermediates
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)

        media_path = Path(media_path)
        stored_media_path = input_dir / media_path.name
        shutil.copy2(media_path, stored_media_path)

        job = MediaJobRecord(job_id=job_id, media_path=stored_media_path)
        self.jobs[job_id] = job

        def _check_stop() -> None:
            if job.stop_flag.is_set():
                raise _StopPipeline()

        def _run_job() -> None:
            with job.lock:
                job.status = "running"
                job.started_at = time.time()
            _log(job, f"Media job started: {stored_media_path.name}")
            client = None
            try:
                _check_stop()
                job.stage = "extracting"
                _log(job, "[STAGE] extracting")
                wav_path = media_preprocess.extract_audio(stored_media_path, work_dir)

                _check_stop()
                job.stage = "vad_segmenting"
                _log(job, "[STAGE] vad_segmenting")
                vad_segments = vad_segmenter.segment_by_voice_activity(str(wav_path))
                vad_segmenter.unload_model()

                _check_stop()
                if denoise:
                    job.stage = "denoising"
                    _log(job, "[STAGE] denoising")
                    wav_path = media_preprocess.denoise_audio(wav_path, work_dir, vad_segments)

                _check_stop()
                job.stage = "transcribing"
                _log(job, "[STAGE] transcribing")
                segments = stt_engine.transcribe(str(wav_path), vad_segments)
                stt_engine.unload_model()
                duration = max((s.end for s in segments), default=0.0)
                transcript = MediaTranscript(segments=segments, duration=duration)
                job.transcript = transcript

                _check_stop()
                job.stage = "translating"
                _log(job, "[STAGE] translating")
                client, _model = resolve_media_client(
                    provider_override, model_override, profile, None, targets,
                    log=lambda m: _log(job, m),
                )
                media_translation.translate_transcript(
                    transcript, targets, client,
                    stop_flag=job.stop_flag, log=lambda m: _log(job, m),
                )

                _check_stop()
                job.stage = "rendering"
                _log(job, "[STAGE] rendering")
                text = transcript_writer.write_bilingual_transcript(transcript.segments, targets)
                out_path = output_dir / f"{stored_media_path.stem}_bilingual.txt"
                out_path.write_text(text, encoding="utf-8")
                job.output_txt_path = out_path

                with job.lock:
                    job.status = "completed"
                    job.stage = "completed"
                    job.updated_at = time.time()
                _log(job, "Media job completed")

            except _StopPipeline:
                with job.lock:
                    job.status = "cancelled"
                    job.stage = "cancelled"
                    job.updated_at = time.time()
                _log(job, "Media job cancelled")
            except Exception as exc:
                with job.lock:
                    job.status = "failed"
                    job.stage = "failed"
                    job.error = str(exc)
                    job.updated_at = time.time()
                _log(job, f"[ERROR] {exc}")
            finally:
                if client is not None:
                    release_resources(client, log=lambda m: _log(job, m))

        threading.Thread(target=_run_job, daemon=True, name=f"media-job-{job_id}").start()
        return job

    def get_job(self, job_id: str) -> Optional[MediaJobRecord]:
        return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job:
            return False
        job.stop_flag.set()
        _log(job, "Stop requested")
        return True

    def list_jobs(self) -> List[MediaJobRecord]:
        return list(self.jobs.values())


media_job_manager = MediaJobManager()
