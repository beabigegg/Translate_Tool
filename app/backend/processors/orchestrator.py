"""Translation job orchestrator."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import (
    CONTEXT_DETECTION_ENABLED,
    CONTEXT_SAMPLE_CHARS,
    DEFAULT_MAX_BATCH_CHARS,
    LAYOUT_PRESERVATION_MODE,
    PDF_SKIP_HEADER_FOOTER,
    SUPPORTED_EXTENSIONS,
    TimeoutConfig,
)
from app.backend.processors.com_helpers import is_win32com_available, word_convert
from app.backend.processors.docx_processor import translate_docx
from app.backend.processors.libreoffice_helpers import doc_to_docx, is_libreoffice_available
from app.backend.processors.pdf_processor import translate_pdf
from app.backend.processors.pptx_processor import translate_pptx
from app.backend.processors.xlsx_processor import translate_xlsx_xls

logger = logging.getLogger(__name__)


def _sample_file_text(file_path: Path, max_chars: int = CONTEXT_SAMPLE_CHARS) -> str:
    """Extract the first ~max_chars of text from a file for context detection."""
    ext = file_path.suffix.lower()
    try:
        if ext == ".docx":
            from docx import Document
            doc = Document(str(file_path))
            parts: List[str] = []
            total = 0
            for para in doc.paragraphs:
                t = para.text.strip()
                if not t:
                    continue
                parts.append(t)
                total += len(t)
                if total >= max_chars:
                    break
            return "\n".join(parts)[:max_chars]
        elif ext == ".pptx":
            from pptx import Presentation
            prs = Presentation(str(file_path))
            parts = []
            total = 0
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            t = para.text.strip()
                            if not t:
                                continue
                            parts.append(t)
                            total += len(t)
                            if total >= max_chars:
                                break
                    if total >= max_chars:
                        break
                if total >= max_chars:
                    break
            return "\n".join(parts)[:max_chars]
        elif ext in (".xlsx", ".xls"):
            from openpyxl import load_workbook
            wb = load_workbook(str(file_path), read_only=True, data_only=True)
            parts = []
            total = 0
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    for cell in row:
                        if cell is not None:
                            t = str(cell).strip()
                            if t:
                                parts.append(t)
                                total += len(t)
                                if total >= max_chars:
                                    break
                    if total >= max_chars:
                        break
                if total >= max_chars:
                    break
            wb.close()
            return "\n".join(parts)[:max_chars]
        elif ext == ".pdf":
            # PDF parsing is expensive; use filename as sample
            return file_path.stem.replace("_", " ").replace("-", " ")
        elif ext == ".doc":
            # .doc gets converted to .docx later; use filename
            return file_path.stem.replace("_", " ").replace("-", " ")
    except Exception as exc:
        logger.debug(f"Context sampling failed for {file_path.name}: {exc}")
    return ""


def _detect_document_context(
    client: OllamaClient,
    sample: str,
    log: Callable[[str], None],
) -> str:
    """Ask LLM to describe the document in one sentence (Chinese prompt)."""
    prompt = (
        "以下是一份文件的開頭內容，請用一句話描述這份文件的類型、所屬領域和主題。"
        "只輸出描述，不要解釋。\n\n"
        f"{sample}"
    )
    payload = client._build_no_system_payload(prompt)
    try:
        ok, result = client._call_ollama(payload)
        if ok and result.strip():
            context = result.strip()[:200]
            log(f"[CONTEXT] Detected: {context}")
            return context
    except Exception as exc:
        logger.debug(f"Context detection failed: {exc}")
    return ""


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
    include_headers_shapes_via_com: bool,
    ollama_model: str,
    model_type: str = "general",
    system_prompt: str = "",
    profile_id: str = "general",
    num_ctx_override: Optional[int] = None,
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
        include_headers_shapes_via_com: Use COM for headers/shapes (Windows).
        ollama_model: Ollama model name.
        model_type: Profile-resolved model type.
        system_prompt: Domain-specific system prompt.
        profile_id: Resolved profile id.
        num_ctx_override: Optional per-job num_ctx override.
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
    client = OllamaClient(
        model=ollama_model,
        model_type=model_type,
        system_prompt=system_prompt,
        profile_id=profile_id,
        num_ctx_override=num_ctx_override,
        timeout=timeout_config,
        log=log,
    )
    processed_count = 0
    total_count = len(files)
    stopped = False
    base_system_prompt = client.system_prompt

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
        # Auto-detect document context for general models
        if CONTEXT_DETECTION_ENABLED and not client._is_translation_dedicated():
            sample = _sample_file_text(src)
            if sample:
                doc_context = _detect_document_context(client, sample, log)
                if doc_context:
                    client.system_prompt = f"{base_system_prompt}\n\nDocument context: {doc_context}"
                else:
                    client.system_prompt = base_system_prompt
            else:
                client.system_prompt = base_system_prompt
        try:
            if ext == ".docx":
                stopped = translate_docx(
                    str(src),
                    str(out_path),
                    targets,
                    src_lang,
                    client,
                    include_headers_shapes_via_com=include_headers_shapes_via_com,
                    stop_flag=stop_flag,
                    log=log,
                    max_batch_chars=max_batch_chars,
                )
            elif ext == ".doc":
                tmp_docx = str(output_dir / f"{src.stem}__tmp.docx")
                if is_libreoffice_available():
                    log("[DOC] Converting to .docx via LibreOffice")
                    doc_to_docx(str(src), tmp_docx)
                elif is_win32com_available():
                    log("[DOC] Converting to .docx via COM")
                    word_convert(str(src), tmp_docx, 16)
                else:
                    log(
                        "[DOC] Cannot convert .doc: neither LibreOffice nor "
                        "Word COM is available. Install LibreOffice: "
                        "sudo apt install libreoffice-core (Linux) / "
                        "brew install --cask libreoffice (macOS)"
                    )
                    continue
                try:
                    stopped = translate_docx(
                        tmp_docx,
                        str(out_path),
                        targets,
                        src_lang,
                        client,
                        include_headers_shapes_via_com=include_headers_shapes_via_com,
                        stop_flag=stop_flag,
                        log=log,
                        max_batch_chars=max_batch_chars,
                    )
                finally:
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
        finally:
            client.system_prompt = base_system_prompt
    if stopped:
        log(f"[STOP] job stopped after {processed_count}/{total_count} files")
    else:
        log(f"[DONE] job complete: {processed_count}/{total_count} files")
    return processed_count, total_count, stopped, client
