"""Translation job orchestrator."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import (
    CONTEXT_DETECTION_ENABLED,
    CONTEXT_SAMPLE_CHARS,
    CROSS_MODEL_REFINEMENT_ENABLED,
    DEFAULT_MAX_BATCH_CHARS,
    DEFAULT_MODEL,
    DYNAMIC_SCENARIO_STRATEGY_ENABLED,
    LAYOUT_PRESERVATION_MODE,
    OLLAMA_BASE_URL,
    PDF_SKIP_HEADER_FOOTER,
    QWEN_CONTEXT_FLOW_ENABLED,
    SCENARIO_CACHE_VARIANT_ENABLED,
    SUPPORTED_EXTENSIONS,
    TimeoutConfig,
)
from app.backend.processors.com_helpers import is_win32com_available, word_convert
from app.backend.processors.docx_processor import translate_docx
from app.backend.processors.libreoffice_helpers import doc_to_docx, is_libreoffice_available
from app.backend.processors.pdf_processor import translate_pdf
from app.backend.processors.pptx_processor import translate_pptx
from app.backend.processors.xlsx_processor import translate_xlsx_xls
from app.backend.services.translation_strategy import (
    build_strategy,
    build_terminology_block,
    detect_translation_scenario,
    scenario_from_profile,
)

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


_PHASE0_CHUNK_SIZE = 2000  # Max chars per segment sent to Phase 0 extraction


def _extract_all_segments(file_path: Path, chunk_size: int = _PHASE0_CHUNK_SIZE) -> List[str]:
    """Extract all text from a document and split into fixed-size chunks for Phase 0."""
    ext = file_path.suffix.lower()
    parts: List[str] = []
    try:
        if ext == ".docx":
            from docx import Document
            doc = Document(str(file_path))
            for para in doc.paragraphs:
                t = para.text.strip()
                if t:
                    parts.append(t)
        elif ext == ".pptx":
            from pptx import Presentation
            prs = Presentation(str(file_path))
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            t = para.text.strip()
                            if t:
                                parts.append(t)
        elif ext in (".xlsx", ".xls"):
            from openpyxl import load_workbook
            wb = load_workbook(str(file_path), read_only=True, data_only=True)
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    for cell in row:
                        if cell is not None:
                            t = str(cell).strip()
                            if t:
                                parts.append(t)
            wb.close()
        elif ext == ".pdf":
            parts.append(file_path.stem.replace("_", " ").replace("-", " "))
        elif ext == ".doc":
            parts.append(file_path.stem.replace("_", " ").replace("-", " "))
    except Exception as exc:
        logger.debug("Phase 0 text extraction failed for %s: %s", file_path.name, exc)

    # Join all parts and split into chunks
    full_text = "\n".join(parts)
    if not full_text.strip():
        return []

    chunks: List[str] = []
    for i in range(0, len(full_text), chunk_size):
        chunk = full_text[i : i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


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


def _output_name(src: Path, output_format: Optional[str] = None, output_suffix: str = "") -> str:
    """Generate output filename for translated file.

    Args:
        src: Source file path.
        output_format: Optional output format override (e.g., 'pdf' for PDF output).
        output_suffix: Optional suffix inserted before the extension (e.g., '_en', '_vi').

    Returns:
        Output filename with _translated suffix.
    """
    ext = src.suffix.lower()
    stem = src.stem
    tag = f"_{output_suffix}" if output_suffix else ""
    if ext in (".docx", ".pptx", ".xlsx"):
        return f"{stem}_translated{tag}{ext}"
    if ext == ".pdf":
        if output_format == "pdf":
            return f"{stem}_translated{tag}.pdf"
        return f"{stem}_translated{tag}.docx"
    if ext in (".doc", ".xls"):
        return f"{stem}_translated{tag}.docx" if ext == ".doc" else f"{stem}_translated{tag}.xlsx"
    return f"{stem}_translated{tag}{ext}"


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
    output_suffix: str = "",
    refine_model: Optional[str] = None,
    refiner_num_ctx: Optional[int] = None,
    mode: str = "translation",
    term_db=None,
) -> Tuple[int, int, bool, Optional[OllamaClient], Dict]:
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
        mode: Job mode: 'translation' (default) or 'extraction_only'.
        term_db: Optional TermDB instance for terminology extraction and injection.

    Returns:
        Tuple of (processed_count, total_count, stopped, client, term_summary).
    """
    # Use defaults from config if not specified
    if layout_mode is None:
        layout_mode = LAYOUT_PRESERVATION_MODE
    output_dir.mkdir(parents=True, exist_ok=True)

    extraction_only = mode == "extraction_only"
    aggregate_term_summary: Dict = {"extracted": 0, "skipped": 0, "added": 0}

    client = OllamaClient(
        model=ollama_model,
        model_type=model_type,
        system_prompt=system_prompt,
        profile_id=profile_id,
        num_ctx_override=num_ctx_override,
        timeout=timeout_config,
        log=log,
    )

    # Build cross-model refine client (Qwen) for HY-MT/TranslateGemma jobs
    refine_client: Optional[OllamaClient] = None
    if refine_model and CROSS_MODEL_REFINEMENT_ENABLED and targets:
        refine_system_prompt = OllamaClient._build_refine_system_prompt(targets[0], profile_id)
        refine_client = OllamaClient(
            model=refine_model,
            model_type="general",
            system_prompt=refine_system_prompt,
            num_ctx_override=refiner_num_ctx,
            timeout=timeout_config,
            log=log,
        )
        log(f"[REFINE] Cross-model refiner configured: {refine_model} (profile={profile_id}, tgt={targets[0]})")

    processed_count = 0
    total_count = len(files)
    stopped = False
    base_system_prompt = client.system_prompt

    forced_scenario = scenario_from_profile(profile_id)
    if DYNAMIC_SCENARIO_STRATEGY_ENABLED and forced_scenario:
        log(f"[STRATEGY] fixed scenario from profile={profile_id}: {forced_scenario.value}")

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
        out_path = output_dir / _output_name(src, output_format=pdf_output_fmt, output_suffix=output_suffix)
        log("=" * 24)
        log(f"Processing: {src.name} ({processed_count + 1}/{total_count})")

        sample = _sample_file_text(src)
        doc_context = ""
        if (
            CONTEXT_DETECTION_ENABLED
            and QWEN_CONTEXT_FLOW_ENABLED
            and not client._is_translation_dedicated()
            and sample
        ):
            doc_context = _detect_document_context(client, sample, log)

        # For dedicated primary models (e.g. HY-MT), defer context detection to
        # Phase 2 so it runs after HY-MT is evicted from VRAM.
        if (
            refine_client is not None
            and client._is_translation_dedicated()
            and CONTEXT_DETECTION_ENABLED
            and QWEN_CONTEXT_FLOW_ENABLED
            and sample
        ):
            refine_client._deferred_context_sample = sample
            refine_client._deferred_context_profile = profile_id
            refine_client._deferred_context_target = targets[0] if targets else ""

        if DYNAMIC_SCENARIO_STRATEGY_ENABLED:
            scenario = forced_scenario or detect_translation_scenario(src.name, sample_text=sample, detected_context=doc_context)
            decision = build_strategy(
                base_system_prompt=base_system_prompt,
                model_type=client.model_type,
                scenario=scenario,
                detected_context=doc_context,
                enable_context_flow=QWEN_CONTEXT_FLOW_ENABLED,
            )
            client.system_prompt = decision.system_prompt
            client.set_runtime_options_override(decision.options_override)
            if SCENARIO_CACHE_VARIANT_ENABLED:
                client.set_cache_variant(decision.cache_variant)
            log(
                f"[STRATEGY] mode={'forced' if forced_scenario else 'auto'}, "
                f"scenario={decision.scenario.value}, "
                f"cache_variant={decision.cache_variant}, "
                f"options_override={decision.options_override}"
            )
        else:
            if doc_context:
                client.system_prompt = f"{base_system_prompt}\n\nDocument context: {doc_context}"
            else:
                client.system_prompt = base_system_prompt

        # ------------------------------------------------------------------
        # Phase 0: Term Extraction
        # ------------------------------------------------------------------
        if term_db is not None:
            from app.backend.services.term_extractor import run_phase0, SCENARIO_TO_DOMAIN
            phase0_segments = _extract_all_segments(src)
            _scenario_name = (
                (scenario.value if hasattr(scenario, "value") else str(scenario))
                if DYNAMIC_SCENARIO_STRATEGY_ENABLED else "general"
            )
            _domain = SCENARIO_TO_DOMAIN.get(_scenario_name, "general")
            _source_lang = src_lang or "Chinese"
            _target_lang = targets[0] if targets else "English"
            try:
                term_summary = run_phase0(
                    segments=phase0_segments,
                    source_lang=_source_lang,
                    target_lang=_target_lang,
                    scenario=_scenario_name,
                    document_context=doc_context,
                    term_db=term_db,
                    model=DEFAULT_MODEL,
                    base_url=OLLAMA_BASE_URL,
                    timeout=timeout_config,
                    log=log,
                )
                for k in aggregate_term_summary:
                    aggregate_term_summary[k] += term_summary.get(k, 0)
            except Exception as _ph0_exc:
                log(f"[PHASE0] Unexpected error (non-fatal): {_ph0_exc}")
                logger.warning("[PHASE0] Unexpected error: %s", _ph0_exc)

            # Inject top terms into Phase 1 and Phase 2 system prompts
            top_terms = term_db.get_top_terms(_target_lang, _domain)
            if top_terms:
                term_block = build_terminology_block(top_terms)
                # Phase 1: inject unless TranslateGemma (no system prompt support)
                if not client._is_translategemma_model():
                    client.system_prompt = (
                        client.system_prompt.rstrip() + "\n\n" + term_block
                        if client.system_prompt.strip()
                        else term_block
                    )
                # Phase 2 Refiner: always inject
                if refine_client is not None:
                    refine_client.system_prompt = (
                        refine_client.system_prompt.rstrip() + "\n\n" + term_block
                        if refine_client.system_prompt.strip()
                        else term_block
                    )

        # extraction_only mode: skip translation
        if extraction_only:
            processed_count += 1
            log(f"[EXTRACTION] Done: {src.name} (extraction only)")
            continue

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
                    refine_client=refine_client,
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
                        refine_client=refine_client,
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
                    refine_client=refine_client,
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
                    refine_client=refine_client,
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
            client.set_runtime_options_override(None)
            client.set_cache_variant(None)
    if stopped:
        log(f"[STOP] job stopped after {processed_count}/{total_count} files")
    else:
        log(f"[DONE] job complete: {processed_count}/{total_count} files")
    return processed_count, total_count, stopped, client, aggregate_term_summary
