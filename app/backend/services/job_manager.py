"""Job lifecycle management with automatic cleanup."""

from __future__ import annotations

import atexit
import re
import shutil
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from app.backend.services.model_router import RouteGroup
from app.backend.translation_profiles import get_profile as _get_translation_profile
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
    current_file: str = ""
    segments_done: int = 0
    segments_total: int = 0
    file_segments_done: int = 0
    file_segments_total: int = 0
    started_at: Optional[float] = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    stop_flag: threading.Event = field(default_factory=threading.Event)
    thread: Optional[threading.Thread] = None
    output_zip: Optional[Path] = None
    mode: str = "translation"
    term_summary: Optional[Dict] = None


class JobLogger:
    _RE_PROCESSING = re.compile(r"^Processing:\s+(.+?)\s+\((\d+)/(\d+)\)$")
    _RE_TR = re.compile(r"^\[TR\]\s+(\d+)/(\d+)\s+")
    _RE_DONE = re.compile(r"^Done:\s+(.+?)\s+->")

    def __init__(self, job: JobRecord) -> None:
        self.job = job
        self._file_seg_offset: int = 0
        self._processed_offset: int = 0

    def advance_processed_offset(self, n: int) -> None:
        """Advance the processed-files offset after a route group completes."""
        self._processed_offset += n

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        line = f"{timestamp} {message}"
        with self.job.lock:
            self.job.logs.append(line)
            self.job.updated_at = time.time()
            self._parse_progress(message)
        logger.info("[%s] %s", self.job.job_id, message)

    def _parse_progress(self, message: str) -> None:
        """Parse known log patterns to update progress fields (called within lock)."""
        job = self.job

        m = self._RE_PROCESSING.match(message)
        if m:
            job.current_file = m.group(1)
            index = int(m.group(2))
            # Don't overwrite total_files — it is set upfront by create_job
            job.processed_files = self._processed_offset + (index - 1)
            # Save cumulative offset before resetting per-file counters
            self._file_seg_offset = job.segments_done
            job.file_segments_done = 0
            job.file_segments_total = 0
            return

        m = self._RE_TR.match(message)
        if m:
            done = int(m.group(1))
            total = int(m.group(2))
            job.file_segments_done = done
            job.file_segments_total = total
            job.segments_done = self._file_seg_offset + done
            job.segments_total = self._file_seg_offset + total
            return

        m = self._RE_DONE.match(message)
        if m:
            # Mark per-file segments as fully complete
            if job.file_segments_total > 0:
                job.file_segments_done = job.file_segments_total
                job.segments_done = self._file_seg_offset + job.file_segments_total
            job.processed_files += 1
            return


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
        route_groups: List[RouteGroup],
        src_lang: Optional[str],
        include_headers: bool,
        num_ctx: Optional[int] = None,
        pdf_output_format: str = "docx",
        pdf_layout_mode: str = "overlay",
        mode: str = "translation",
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

        job = JobRecord(job_id=job_id, input_dir=input_dir, output_dir=output_dir, mode=mode)
        # total_files = files × groups (each group translates all files to its target languages)
        job.total_files = len(stored_files) * len(route_groups)
        self.jobs[job_id] = job

        job_logger = JobLogger(job)
        log = job_logger.log
        num_ctx_log = f", num_ctx={num_ctx} (override)" if num_ctx is not None else ""
        group_summary = ", ".join(
            f"{g.model}→[{','.join(g.targets)}]" for g in route_groups
        )
        log(
            f"[CONFIG] groups={len(route_groups)}: {group_summary}, "
            f"PDF output_format={pdf_output_format}, layout_mode={pdf_layout_mode}{num_ctx_log}"
        )

        def _run_job() -> None:
            with job.lock:
                job.status = "running"
                job.started_at = time.time()
            log(f"Job started with {len(stored_files)} files × {len(route_groups)} route group(s)")
            total_processed = 0
            overall_stopped = False
            last_client: Optional[OllamaClient] = None
            agg_term_summary: Dict = {"extracted": 0, "skipped": 0, "added": 0}
            try:
                timeout_config = TimeoutConfig()
                multi_group = len(route_groups) > 1

                # Initialise shared TermDB for Phase 0
                from app.backend.services.term_db import TermDB
                term_db = TermDB()

                for group in route_groups:
                    if job.stop_flag.is_set():
                        overall_stopped = True
                        break

                    system_prompt = _get_translation_profile(group.profile_id).system_prompt
                    # When multiple groups exist, tag output files with target language codes
                    # to avoid filename collisions (e.g. doc_translated_en.docx, doc_translated_vi.docx)
                    output_suffix = "_".join(t[:2].lower() for t in group.targets) if multi_group else ""
                    log(
                        f"[GROUP] model={group.model}, profile={group.profile_id}, "
                        f"targets={group.targets}"
                    )
                    processed, _total, stopped, last_client, grp_term_summary = process_files(
                        stored_files,
                        output_dir,
                        group.targets,
                        src_lang,
                        include_headers_shapes_via_com=include_headers,
                        ollama_model=group.model,
                        model_type=group.model_type,
                        system_prompt=system_prompt,
                        profile_id=group.profile_id,
                        num_ctx_override=num_ctx,
                        timeout_config=timeout_config,
                        stop_flag=job.stop_flag,
                        log=log,
                        max_batch_chars=DEFAULT_MAX_BATCH_CHARS,
                        layout_mode=pdf_layout_mode,
                        output_format=pdf_output_format,
                        output_suffix=output_suffix,
                        refine_model=group.refine_model,
                        mode=mode,
                        term_db=term_db,
                    )
                    for k in agg_term_summary:
                        agg_term_summary[k] += grp_term_summary.get(k, 0)
                    total_processed += processed
                    job_logger.advance_processed_offset(len(stored_files))

                    # Release VRAM between groups (8GB constraint)
                    release_resources(last_client, log=log)
                    last_client = None

                    if stopped:
                        overall_stopped = True
                        break

                # Archive outputs (skip for extraction_only — no translated files produced)
                archive_path: Optional[Path] = None
                if mode != "extraction_only":
                    archive_path = self._archive_outputs(job)
                with job.lock:
                    job.processed_files = total_processed
                    job.output_zip = archive_path
                    job.status = "stopped" if overall_stopped else "completed"
                    job.term_summary = agg_term_summary
                    job.updated_at = time.time()

            except Exception as exc:
                with job.lock:
                    job.status = "failed"
                    job.error = str(exc)
                    job.updated_at = time.time()
                log(f"[ERROR] {exc}")
            finally:
                if last_client is not None:
                    release_resources(last_client, log=log)

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
