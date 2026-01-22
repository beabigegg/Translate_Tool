"""Translation job orchestrator."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import (
    DEFAULT_MAX_BATCH_CHARS,
    LAYOUT_PRESERVATION_MODE,
    PDF_SKIP_HEADER_FOOTER,
    SUPPORTED_EXTENSIONS,
    TimeoutConfig,
)
from app.backend.processors.com_helpers import is_win32com_available, word_convert
from app.backend.processors.docx_processor import translate_docx
from app.backend.processors.pdf_processor import translate_pdf
from app.backend.processors.pptx_processor import translate_pptx
from app.backend.processors.xlsx_processor import translate_xlsx_xls


def _output_name(src: Path, output_format: Optional[str] = None) -> str:
    """Generate output filename for translated file.

    Args:
        src: Source file path.
        output_format: Optional output format override (e.g., 'pdf' for PDF output).

    Returns:
        Output filename with _translated suffix.
    """
    ext = src.suffix.lower()
    stem = src.stem
    if ext in (".docx", ".pptx", ".xlsx"):
        return f"{stem}_translated{ext}"
    if ext == ".pdf":
        # Support PDF-to-PDF output when output_format is "pdf"
        if output_format == "pdf":
            return f"{stem}_translated.pdf"
        return f"{stem}_translated.docx"
    if ext in (".doc", ".xls"):
        return f"{stem}_translated.docx" if ext == ".doc" else f"{stem}_translated.xlsx"
    return f"{stem}_translated{ext}"


def process_files(
    files: List[Path],
    output_dir: Path,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    include_headers_shapes_via_com: bool,
    ollama_model: str,
    timeout_config: Optional[TimeoutConfig] = None,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
    layout_mode: Optional[str] = None,
    output_format: Optional[str] = None,
) -> Tuple[int, int, bool, Optional[OllamaClient]]:
    """Process files for translation.

    Args:
        files: List of files to process.
        output_dir: Output directory for translated files.
        targets: Target languages.
        src_lang: Source language (or None for auto-detect).
        cache: Translation cache instance.
        include_headers_shapes_via_com: Use COM for headers/shapes (Windows).
        ollama_model: Ollama model name.
        timeout_config: Optional timeout configuration.
        stop_flag: Optional stop flag for cancellation.
        log: Logging callback.
        max_batch_chars: Maximum characters per batch.
        layout_mode: Layout preservation mode (inline|overlay|side_by_side).
        output_format: Output format for PDF (docx|pdf).

    Returns:
        Tuple of (processed_count, total_count, stopped, client).
    """
    # Use defaults from config if not specified
    if layout_mode is None:
        layout_mode = LAYOUT_PRESERVATION_MODE
    output_dir.mkdir(parents=True, exist_ok=True)
    client = OllamaClient(model=ollama_model, timeout=timeout_config, log=log)
    processed_count = 0
    total_count = len(files)
    stopped = False

    for src in files:
        if stop_flag and stop_flag.is_set():
            log(f"[STOP] stopped at {processed_count}/{total_count} files")
            stopped = True
            break
        ext = src.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            log(f"[SKIP] Unsupported file: {src.name}")
            continue
        # Determine output format for PDF files
        pdf_output_fmt = output_format if ext == ".pdf" else None
        out_path = output_dir / _output_name(src, output_format=pdf_output_fmt)
        log("=" * 24)
        log(f"Processing: {src.name} ({processed_count + 1}/{total_count})")
        try:
            if ext == ".docx":
                stopped = translate_docx(
                    str(src),
                    str(out_path),
                    targets,
                    src_lang,
                    cache,
                    client,
                    include_headers_shapes_via_com=include_headers_shapes_via_com,
                    stop_flag=stop_flag,
                    log=log,
                    max_batch_chars=max_batch_chars,
                )
            elif ext == ".doc":
                if not is_win32com_available():
                    log("[DOC] Word COM not available; convert to .docx first")
                    continue
                tmp_docx = str(output_dir / f"{src.stem}__tmp.docx")
                word_convert(str(src), tmp_docx, 16)
                stopped = translate_docx(
                    tmp_docx,
                    str(out_path),
                    targets,
                    src_lang,
                    cache,
                    client,
                    include_headers_shapes_via_com=include_headers_shapes_via_com,
                    stop_flag=stop_flag,
                    log=log,
                    max_batch_chars=max_batch_chars,
                )
                try:
                    os.remove(tmp_docx)
                except OSError:
                    pass
            elif ext == ".pptx":
                stopped = translate_pptx(
                    str(src),
                    str(out_path),
                    targets,
                    src_lang,
                    cache,
                    client,
                    stop_flag=stop_flag,
                    log=log,
                    max_batch_chars=max_batch_chars,
                )
            elif ext in (".xlsx", ".xls"):
                stopped = translate_xlsx_xls(
                    str(src),
                    str(out_path),
                    targets,
                    src_lang,
                    cache,
                    client,
                    stop_flag=stop_flag,
                    log=log,
                    max_batch_chars=max_batch_chars,
                )
            elif ext == ".pdf":
                log(f"[PDF] Using output_format={output_format}, layout_mode={layout_mode}")
                stopped = translate_pdf(
                    str(src),
                    str(out_path),
                    targets,
                    src_lang,
                    cache,
                    client,
                    stop_flag=stop_flag,
                    log=log,
                    skip_header_footer=PDF_SKIP_HEADER_FOOTER,
                    output_format=output_format or "docx",
                    layout_mode=layout_mode,
                )
            else:
                log(f"[SKIP] Unsupported file: {src.name}")
                continue
            processed_count += 1
            if stopped:
                log(f"[STOP] file interrupted: {src.name}")
                break
            log(f"Done: {src.name} -> {out_path.name}")
        except Exception as exc:
            log(f"[ERROR] {src.name}: {exc}")
    if stopped:
        log(f"[STOP] job stopped after {processed_count}/{total_count} files")
    else:
        log(f"[DONE] job complete: {processed_count}/{total_count} files")
    return processed_count, total_count, stopped, client
