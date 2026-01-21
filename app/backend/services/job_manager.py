"""Job lifecycle management with automatic cleanup."""

from __future__ import annotations

import atexit
import shutil
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import (
    CLEANUP_INTERVAL_MINUTES,
    DEFAULT_MAX_BATCH_CHARS,
    DEFAULT_MODEL,
    JOB_TTL_HOURS,
    JOBS_DIR,
    MAX_JOBS_IN_MEMORY,
    TimeoutConfig,
)
from app.backend.processors.orchestrator import process_files
from app.backend.utils.logging_utils import logger
from app.backend.utils.resource_utils import release_resources


@dataclass
class JobRecord:
    job_id: str
    input_dir: Path
    output_dir: Path
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    processed_files: int = 0
    total_files: int = 0
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    stop_flag: threading.Event = field(default_factory=threading.Event)
    thread: Optional[threading.Thread] = None
    output_zip: Optional[Path] = None


class JobLogger:
    def __init__(self, job: JobRecord) -> None:
        self.job = job

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        line = f"{timestamp} {message}"
        with self.job.lock:
            self.job.logs.append(line)
            self.job.updated_at = time.time()
        logger.info("[%s] %s", self.job.job_id, message)


class JobManager:
    def __init__(self) -> None:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self.jobs: OrderedDict[str, JobRecord] = OrderedDict()
        self._cleanup_lock = threading.Lock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        # Cleanup orphaned directories on startup
        self._cleanup_orphaned_dirs()

        # Start background cleanup thread
        self._start_cleanup_thread()

        # Register cleanup on exit
        atexit.register(self._shutdown)

    def _shutdown(self) -> None:
        """Shutdown cleanup thread gracefully."""
        self._shutdown_event.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)

    def _start_cleanup_thread(self) -> None:
        """Start background thread for periodic cleanup."""
        def cleanup_loop():
            interval_seconds = CLEANUP_INTERVAL_MINUTES * 60
            while not self._shutdown_event.is_set():
                # Wait for interval or shutdown
                if self._shutdown_event.wait(timeout=interval_seconds):
                    break
                self._cleanup_expired_jobs()

        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True, name="job-cleanup")
        self._cleanup_thread.start()
        logger.info("Started job cleanup thread (interval: %d minutes)", CLEANUP_INTERVAL_MINUTES)

    def _cleanup_orphaned_dirs(self) -> None:
        """Remove job directories without corresponding job records."""
        if not JOBS_DIR.exists():
            return

        cleaned = 0
        for job_dir in JOBS_DIR.iterdir():
            if job_dir.is_dir() and job_dir.name not in self.jobs:
                try:
                    shutil.rmtree(job_dir, ignore_errors=True)
                    cleaned += 1
                except Exception as exc:
                    logger.warning("Failed to cleanup orphaned dir %s: %s", job_dir.name, exc)

        if cleaned > 0:
            logger.info("Cleaned %d orphaned job directories on startup", cleaned)

    def _cleanup_expired_jobs(self) -> None:
        """Remove jobs that have exceeded TTL."""
        with self._cleanup_lock:
            now = time.time()
            ttl_seconds = JOB_TTL_HOURS * 3600
            expired_ids = []

            for job_id, job in self.jobs.items():
                if job.status in {"completed", "failed", "stopped"}:
                    age = now - job.updated_at
                    if age > ttl_seconds:
                        expired_ids.append(job_id)

            for job_id in expired_ids:
                self._remove_job(job_id, reason="TTL expired")

    def _cleanup_by_capacity(self) -> None:
        """Remove oldest completed jobs if exceeding capacity."""
        with self._cleanup_lock:
            while len(self.jobs) > MAX_JOBS_IN_MEMORY:
                # Find oldest completed job
                oldest_id = None
                for job_id, job in self.jobs.items():
                    if job.status in {"completed", "failed", "stopped"}:
                        oldest_id = job_id
                        break

                if oldest_id:
                    self._remove_job(oldest_id, reason="capacity limit")
                else:
                    # All jobs are still running, can't remove any
                    break

    def _remove_job(self, job_id: str, reason: str = "") -> None:
        """Remove a job and its associated directories."""
        job = self.jobs.pop(job_id, None)
        if job:
            job_dir = job.input_dir.parent
            if job_dir.exists():
                try:
                    shutil.rmtree(job_dir, ignore_errors=True)
                except Exception as exc:
                    logger.warning("Failed to remove job dir %s: %s", job_dir, exc)
            logger.debug("Removed job %s (%s)", job_id, reason)

    def create_job(
        self,
        uploaded_files: List[Path],
        targets: List[str],
        src_lang: Optional[str],
        include_headers: bool,
        model: str,
    ) -> JobRecord:
        # Cleanup by capacity before creating new job
        self._cleanup_by_capacity()

        job_id = uuid.uuid4().hex
        job_dir = JOBS_DIR / job_id
        input_dir = job_dir / "input"
        output_dir = job_dir / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        stored_files: List[Path] = []
        for src in uploaded_files:
            dest = input_dir / src.name
            shutil.copy2(src, dest)
            stored_files.append(dest)

        job = JobRecord(job_id=job_id, input_dir=input_dir, output_dir=output_dir)
        job.total_files = len(stored_files)
        self.jobs[job_id] = job

        log = JobLogger(job).log

        def _run_job() -> None:
            cache = TranslationCache(output_dir / "translation_cache.db")
            client: Optional[OllamaClient] = None
            with job.lock:
                job.status = "running"
            log(f"Job started with {len(stored_files)} files")
            try:
                timeout_config = TimeoutConfig()
                processed, total, stopped, client = process_files(
                    stored_files,
                    output_dir,
                    targets,
                    src_lang,
                    cache,
                    include_headers_shapes_via_com=include_headers,
                    ollama_model=model or DEFAULT_MODEL,
                    timeout_config=timeout_config,
                    stop_flag=job.stop_flag,
                    log=log,
                    max_batch_chars=DEFAULT_MAX_BATCH_CHARS,
                )

                # Archive outputs and update state atomically
                archive_path = self._archive_outputs(job)
                with job.lock:
                    job.processed_files = processed
                    job.total_files = total
                    job.output_zip = archive_path  # Set within lock to avoid race condition
                    job.status = "stopped" if stopped else "completed"
                    job.updated_at = time.time()

            except Exception as exc:
                with job.lock:
                    job.status = "failed"
                    job.error = str(exc)
                    job.updated_at = time.time()
                log(f"[ERROR] {exc}")
            finally:
                cache.close()
                release_resources(client, log=log)

        job.thread = threading.Thread(target=_run_job, daemon=True)
        job.thread.start()
        return job

    def _archive_outputs(self, job: JobRecord) -> Path:
        """Create zip archive of outputs and return the path."""
        output_dir = job.output_dir
        zip_path = output_dir.parent / f"{job.job_id}_output"
        archive = shutil.make_archive(str(zip_path), "zip", output_dir)
        return Path(archive)

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job:
            return False
        job.stop_flag.set()
        with job.lock:
            job.logs.append("Stop requested")
        return True

    def list_jobs(self) -> List[JobRecord]:
        return list(self.jobs.values())

    def get_stats(self) -> Dict[str, int]:
        """Get job manager statistics for monitoring."""
        with self._cleanup_lock:
            total = len(self.jobs)
            running = sum(1 for j in self.jobs.values() if j.status == "running")
            completed = sum(1 for j in self.jobs.values() if j.status == "completed")
            failed = sum(1 for j in self.jobs.values() if j.status == "failed")
            stopped = sum(1 for j in self.jobs.values() if j.status == "stopped")

        return {
            "total_jobs": total,
            "running": running,
            "completed": completed,
            "failed": failed,
            "stopped": stopped,
            "max_jobs": MAX_JOBS_IN_MEMORY,
        }
