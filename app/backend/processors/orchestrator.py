"""Translation job orchestrator."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import DEFAULT_MAX_BATCH_CHARS, SUPPORTED_EXTENSIONS, TimeoutConfig
from app.backend.processors.com_helpers import is_win32com_available, word_convert
from app.backend.processors.docx_processor import translate_docx
from app.backend.processors.pdf_processor import translate_pdf
from app.backend.processors.pptx_processor import translate_pptx
from app.backend.processors.xlsx_processor import translate_xlsx_xls


def _output_name(src: Path) -> str:
    ext = src.suffix.lower()
    stem = src.stem
    if ext in (".docx", ".pptx", ".xlsx"):
        return f"{stem}_translated{ext}"
    if ext in (".doc", ".pdf", ".xls"):
        return f"{stem}_translated.docx" if ext in (".doc", ".pdf") else f"{stem}_translated.xlsx"
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
) -> Tuple[int, int, bool, Optional[OllamaClient]]:
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
        out_path = output_dir / _output_name(src)
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
                stopped = translate_pdf(
                    str(src),
                    str(out_path),
                    targets,
                    src_lang,
                    cache,
                    client,
                    stop_flag=stop_flag,
                    log=log,
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
