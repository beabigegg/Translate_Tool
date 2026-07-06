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
from typing import Any, Dict, List, Optional, Tuple

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import (
    CLEANUP_INTERVAL_MINUTES,
    DEFAULT_MAX_BATCH_CHARS,
    DEFAULT_MODEL,
    JOB_TTL_HOURS,
    JOBS_DIR,
    JUDGE_ENABLED,
    JUDGE_MODEL,
    MAX_JOBS_IN_MEMORY,
    QE_DEVICE,
    QE_ENABLED,
    QE_MODEL_NAME,
    TimeoutConfig,
)
import app.backend.config as config
from app.backend.processors.orchestrator import process_files
from app.backend.services.model_router import RouteGroup
from app.backend.services.quality_evaluator import load_model, score_blocks
from app.backend.services.term_audit import audit_terms, TerminologyAuditResult
from app.backend.services.term_db import TermDB
from app.backend.translation_profiles import get_profile as _get_translation_profile
from app.backend.utils.logging_utils import logger
from app.backend.utils.resource_utils import release_resources


@dataclass
class BlockQualityScore:
    """Per-block quality score (in-memory only, D-2)."""
    block_id: str
    score: float
    model: str


@dataclass
class JobQualityRecord:
    """Quality evaluation record attached to a completed job (in-memory only, D-2).

    qe_status mirrors the HTTP status enum: available | pending | disabled | unavailable.
    """
    job_id: str
    scores: List[BlockQualityScore]
    qe_status: str  # available | pending | disabled | unavailable
    model: Optional[str]


@dataclass
class JudgeResult:
    """In-memory judge result attached to a completed job (p3-llm-judge).

    judge_status mirrors the HTTP status enum: available | disabled | unavailable.
    """
    job_id: str
    judge_status: str  # available | disabled | unavailable
    score: Optional[str] = None           # 高 | 中 | 低; null unless judge_status = available
    source_text: Optional[str] = None     # representative joined source text
    translated_text: Optional[str] = None # display-only joined final translation
    feedback: Optional[str] = None        # judge natural-language feedback
    attempts: int = 0                     # total judge-loop iterations performed
    model: Optional[str] = None          # JUDGE_MODEL used for this pass
    retranslated_blocks: Optional[Dict[str, str]] = None  # {block_id: retranslated_text}


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
    layout_viz_path: Optional[Path] = None
    mode: str = "translation"
    term_summary: Optional[Dict] = None
    provider: Optional[str] = None  # p1-cloud-providers: winning provider ID
    quality: Optional[JobQualityRecord] = None  # p2-comet-qe: QE result
    audit: Optional[TerminologyAuditResult] = None  # p2-term-audit: terminology audit result
    judge: Optional[JudgeResult] = None  # p3-llm-judge: judge result
    judge_apply_status: Optional[str] = None  # applying | applied | failed | None
    status_detail: Optional[str] = None  # current stage label shown in UI during "running"
    warnings: Optional[List[str]] = None  # pdf-renderer-fallback-warn: render-quality degradation warnings
    api_key_override: Optional[str] = None  # user-supplied API key (e.g. DeepSeek); never persisted


def _record_job_warning(job: "JobRecord", message: str) -> None:
    """Append a warning to job.warnings with dedup guard.

    Initialises job.warnings to [] when None. Skips append if the exact
    message is already present (idempotent — same callback may fire twice
    if the same doc is retried).
    """
    if job.warnings is None:
        job.warnings = []
    if message not in job.warnings:
        job.warnings.append(message)


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
        enable_term_extraction: bool = True,
        output_mode: str = "append",
        api_key_override: Optional[str] = None,
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

        job = JobRecord(job_id=job_id, input_dir=input_dir, output_dir=output_dir, mode=mode, api_key_override=api_key_override)
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
            winning_provider: Optional[str] = None
            try:
                timeout_config = TimeoutConfig()
                multi_group = len(route_groups) > 1

                # p2-comet-qe: per-job block accumulator (one list, mutated by single worker thread)
                qe_blocks: List[Tuple[str, str, str]] = []

                # Initialise shared TermDB for Phase 0 (skipped when enable_term_extraction=False)
                term_db = TermDB() if enable_term_extraction else None

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
                    result_tuple = process_files(
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
                        mode=mode,
                        term_db=term_db,
                        provider_id=group.provider,
                        api_key_override=job.api_key_override,
                        post_translate_hook=qe_blocks.extend,
                        output_mode=output_mode,
                        status_callback=lambda detail: setattr(job, "status_detail", detail),
                        warnings_callback=lambda w: _record_job_warning(job, w),
                    )
                    # process_files returns (processed, total, stopped, last_client,
                    # term_summary[, winning_provider]) — unpack flexibly for forward compat
                    if len(result_tuple) >= 6:
                        processed, _total, stopped, last_client, grp_term_summary, grp_provider = result_tuple[:6]
                        if grp_provider and winning_provider is None:
                            winning_provider = grp_provider
                    else:
                        processed, _total, stopped, last_client, grp_term_summary = result_tuple[:5]
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
                    job.status_detail = "整理輸出中…"
                    archive_path = self._archive_outputs(job)

                # p2-comet-qe: score blocks before status → completed (BR-55, BR-56)
                if QE_ENABLED and mode != "extraction_only":
                    job.status_detail = "品質評估中…"
                    try:
                        qe_model = load_model(QE_MODEL_NAME, QE_DEVICE)
                        scores_raw = score_blocks(qe_model, [(src, mt) for _, src, mt in qe_blocks], device=QE_DEVICE)
                        if scores_raw:
                            qe_score_list = [
                                BlockQualityScore(block_id=bid, score=s, model=QE_MODEL_NAME)
                                for (bid, _, _), s in zip(qe_blocks, scores_raw)
                            ]
                            job.quality = JobQualityRecord(
                                job_id=job_id,
                                scores=qe_score_list,
                                qe_status="available",
                                model=QE_MODEL_NAME,
                            )
                        else:
                            job.quality = JobQualityRecord(
                                job_id=job_id, scores=[], qe_status="unavailable", model=None
                            )
                    except Exception as qe_exc:
                        log(f"[QE] job {job_id}: {type(qe_exc).__name__}: {qe_exc}")
                        job.quality = JobQualityRecord(
                            job_id=job_id, scores=[], qe_status="unavailable", model=None
                        )
                elif not QE_ENABLED:
                    job.quality = JobQualityRecord(
                        job_id=job_id, scores=[], qe_status="disabled", model=None
                    )

                # p2-term-audit: audit terminology hits/rejections over qe_blocks (BR-59..BR-61)
                # Mirrors the QE extraction_only guard so audit only runs on translation jobs.
                # Also skip when term_db is None (enable_term_extraction=False, job_manager.py
                # line ~349) — audit_terms() has no approved/rejected terms to query in that
                # case, so there is nothing to audit rather than an error condition.
                if mode != "extraction_only" and term_db is not None:
                    job.status_detail = "術語審核中…"
                    try:
                        # Collect targets and domain from the route groups used in this job
                        all_targets = list({t for g in route_groups for t in g.targets})
                        job.audit = audit_terms(
                            qe_blocks,
                            targets=all_targets,
                            domain=None,
                            term_db=term_db,
                        )
                    except Exception as audit_exc:
                        logger.warning(
                            "[TermAudit] audit_terms failed job_id=%s: %s: %s",
                            job_id, type(audit_exc).__name__, audit_exc,
                        )
                        job.audit = None

                # p3-llm-judge: run judge loop after QE+audit, before status→completed (D1)
                # Skip when the translation itself already ran on the DeepSeek cloud
                # provider — an extra judge pass on already-cloud-translated output is
                # considered redundant for that provider specifically (other providers,
                # including panjit, still run the judge pass as usual).
                _skip_judge_provider = str(winning_provider or "").lower() == "deepseek"
                if _skip_judge_provider:
                    log(f"[Judge] skipped: translation provider was '{winning_provider}'")
                if (
                    config.JUDGE_ENABLED
                    and mode != "extraction_only"
                    and qe_blocks
                    and not _skip_judge_provider
                ):
                    job.status_detail = "品質評審中…"
                    try:
                        from app.backend.services.quality_judge import QualityJudge
                        _judge = QualityJudge()
                        _judge_total = len(qe_blocks)
                        _judge_retranslate_count = [0]

                        def _translate_fn(src_text: str, feedback: str) -> str:
                            """Re-translate a single block with judge feedback in prompt."""
                            _judge_retranslate_count[0] += 1
                            job.status_detail = f"品質評審中… (重譯 {_judge_retranslate_count[0]}/{_judge_total})"
                            # Use the same client that handled the last group; fall back
                            # to a new OllamaClient if last_client is unavailable.
                            _cli = last_client
                            if _cli is None:
                                _cli = OllamaClient(model=DEFAULT_MODEL)
                            feedback_prefix = (
                                f"[Quality feedback]: {feedback}\n\n" if feedback else ""
                            )
                            targets_list = list({t for g in route_groups for t in g.targets})
                            tgt = targets_list[0] if targets_list else "English"
                            ok, result = _cli.translate_once(
                                f"{feedback_prefix}{src_text}", tgt, src_lang
                            )
                            return result if ok else src_text

                        job.judge = _judge.run_judge_loop(job_id, qe_blocks, _translate_fn)
                    except Exception as judge_exc:
                        logger.warning(
                            "[Judge] hook failed job_id=%s: %s: %s",
                            job_id, type(judge_exc).__name__, judge_exc,
                        )
                        job.judge = None

                with job.lock:
                    job.processed_files = total_processed
                    job.output_zip = archive_path
                    job.layout_viz_path = JOBS_DIR / job_id / "layout_viz.json"
                    job.status = "stopped" if overall_stopped else "completed"
                    job.status_detail = None
                    job.term_summary = agg_term_summary
                    job.provider = winning_provider  # p1-cloud-providers: BR-16
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

    def get_quality(self, job_id: str) -> Optional[JobQualityRecord]:
        """Return the quality record for a job, or None if the job is unknown."""
        job = self.jobs.get(job_id)
        if job is None:
            return None
        return job.quality

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

    def apply_judge(self, job_id: str) -> None:
        """Dispatch a daemon thread to re-render the job output using judge's per-block map.

        Preconditions must be validated before calling (BR-76). This method:
        1. Sets judge_apply_status="applying" under lock.
        2. Dispatches a daemon thread that calls process_files with block_overrides.
        3. On success: rebuilds zip, swaps job.output_zip → sets "applied".
        4. On failure: leaves original output_zip untouched → sets "failed".
        """
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        with job.lock:
            job.judge_apply_status = "applying"

        def _apply_worker() -> None:
            import tempfile as _tempfile

            try:
                assert job.judge is not None
                assert job.judge.retranslated_blocks

                # Re-run process_files against the original source files with the
                # per-block override map so no LLM call is made (D7).
                input_files = sorted(job.input_dir.iterdir())
                if not input_files:
                    raise RuntimeError(f"No source files in {job.input_dir}")

                # Write to a temp output dir so original is untouched on failure.
                tmp_out = Path(_tempfile.mkdtemp(prefix="judge_apply_"))
                try:
                    from app.backend.services.model_router import RouteGroup

                    # Build a minimal route group for re-render (no translation calls).
                    _targets_str = (
                        job.output_zip.stem.replace(f"{job_id}_output", "").strip("_")
                        if job.output_zip
                        else "en"
                    )
                    # Use first file's name to infer output details — crude but workable
                    # since block_overrides bypasses all LLM calls.
                    dummy_route = RouteGroup(
                        targets=["en"],
                        model=DEFAULT_MODEL,
                        profile_id="general",
                        model_type="general",
                    )

                    process_files(
                        input_files,
                        tmp_out,
                        targets=["en"],
                        src_lang=None,
                        include_headers_shapes_via_com=False,
                        ollama_model=DEFAULT_MODEL,
                        block_overrides=job.judge.retranslated_blocks,
                    )

                    # Rebuild zip into temp path, then swap on success.
                    tmp_zip_path = tmp_out.parent / f"{job_id}_output_new"
                    new_zip = Path(shutil.make_archive(str(tmp_zip_path), "zip", tmp_out))

                    with job.lock:
                        # Atomically swap the output zip.
                        old_zip = job.output_zip
                        job.output_zip = new_zip
                        job.judge_apply_status = "applied"
                        job.updated_at = time.time()

                    # Clean up old zip if it differs from new.
                    if old_zip and old_zip != new_zip and old_zip.exists():
                        try:
                            old_zip.unlink()
                        except OSError:
                            pass

                except Exception as inner_exc:
                    logger.warning(
                        "[JudgeApply] re-render failed job_id=%s: %s: %s",
                        job_id,
                        type(inner_exc).__name__,
                        inner_exc,
                    )
                    with job.lock:
                        job.judge_apply_status = "failed"
                        job.updated_at = time.time()
                finally:
                    shutil.rmtree(str(tmp_out), ignore_errors=True)

            except Exception as exc:
                logger.warning(
                    "[JudgeApply] worker failed job_id=%s: %s: %s",
                    job_id,
                    type(exc).__name__,
                    exc,
                )
                with job.lock:
                    job.judge_apply_status = "failed"
                    job.updated_at = time.time()

        t = threading.Thread(target=_apply_worker, daemon=True, name=f"judge-apply-{job_id}")
        t.start()

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
