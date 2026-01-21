"""PDF translation processor."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable, List, Optional

import docx
from PyPDF2 import PdfReader

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.processors.com_helpers import is_win32com_available, word_convert
from app.backend.processors.docx_processor import translate_docx
from app.backend.utils.translation_helpers import translate_block_sentencewise


def translate_pdf(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
) -> bool:
    temp_docx = str(Path(out_path).with_suffix("")) + "__from_pdf.docx"
    if is_win32com_available():
        try:
            word_convert(in_path, temp_docx, 16)
            stopped = translate_docx(
                temp_docx,
                out_path,
                targets,
                src_lang,
                cache,
                client,
                include_headers_shapes_via_com=False,
                stop_flag=stop_flag,
                log=log,
            )
            try:
                os.remove(temp_docx)
            except OSError:
                pass
            return stopped
        except (OSError, RuntimeError) as exc:
            log(f"[PDF] Word import failed, fallback to text extract: {exc}")

    doc = docx.Document()
    stopped = False
    total_pages = 0
    processed_pages = 0

    try:
        reader = PdfReader(in_path)
        total_pages = len(reader.pages)

        for i, page in enumerate(reader.pages, start=1):
            if stop_flag and stop_flag.is_set():
                log(f"[STOP] PDF stopped at {processed_pages}/{total_pages} pages")
                stopped = True
                break
            doc.add_heading(f"-- Page {i} --", level=1)
            text = page.extract_text() or ""
            if text.strip():
                doc.add_paragraph(text)
                for tgt in targets:
                    if stop_flag and stop_flag.is_set():
                        log(f"[STOP] PDF stopped at {processed_pages}/{total_pages} pages")
                        stopped = True
                        break
                    ok, tr = translate_block_sentencewise(text, tgt, src_lang, cache, client)
                    if not ok:
                        tr = f"[Translation failed|{tgt}] {text}"
                    doc.add_paragraph(tr)
            processed_pages += 1
            if stopped:
                break

    except Exception as exc:
        doc.add_paragraph(f"[PDF extract error] {exc}")

    doc.save(out_path)
    if stopped:
        log(f"[PDF] partial output: {os.path.basename(out_path)}")
    else:
        log(f"[PDF] output: {os.path.basename(out_path)}")

    return stopped
