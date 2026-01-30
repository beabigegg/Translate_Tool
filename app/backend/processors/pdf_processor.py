"""PDF translation processor.

Supports two modes:
1. PyMuPDF mode (default): Extracts text with bbox, enables layout preservation
2. PyPDF2 fallback: Simple text extraction for compatibility
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable, List, Optional

import docx
from PyPDF2 import PdfReader

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import (
    MAX_SEGMENTS,
    MAX_TEXT_LENGTH,
    PDF_DRAW_MASK,
    PDF_HEADER_FOOTER_MARGIN_PT,
    PDF_PARSER_ENGINE,
    PDF_SKIP_HEADER_FOOTER,
)
from app.backend.processors.com_helpers import is_win32com_available, word_convert
from app.backend.processors.docx_processor import translate_docx
from app.backend.utils.exceptions import check_document_size_limits
from app.backend.utils.translation_helpers import translate_blocks_batch

if TYPE_CHECKING:
    from app.backend.models.translatable_document import TranslatableDocument
    from app.backend.models.translatable_document import TranslatableDocument

logger = logging.getLogger(__name__)


# Lazy import for PyMuPDF parser
_pymupdf_parser = None


def _get_pymupdf_parser():
    """Lazy-load PyMuPDF parser to avoid import errors if not installed."""
    global _pymupdf_parser
    if _pymupdf_parser is None:
        try:
            from app.backend.parsers.pdf_parser import PyMuPDFParser

            _pymupdf_parser = PyMuPDFParser(
                skip_header_footer=PDF_SKIP_HEADER_FOOTER,
                header_footer_margin_pt=PDF_HEADER_FOOTER_MARGIN_PT,
            )
        except ImportError:
            logger.warning("PyMuPDF not installed, using PyPDF2 fallback")
            _pymupdf_parser = False  # Mark as unavailable
    return _pymupdf_parser if _pymupdf_parser else None


def translate_pdf(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
    use_pymupdf: Optional[bool] = None,
    skip_header_footer: Optional[bool] = None,
    output_format: str = "docx",
    layout_mode: str = "inline",
    draw_mask: Optional[bool] = None,
) -> bool:
    """Translate a PDF file.

    Args:
        in_path: Input PDF file path.
        out_path: Output file path (DOCX or PDF depending on output_format).
        targets: List of target languages.
        src_lang: Source language (or None for auto-detect).
        cache: Translation cache instance.
        client: Ollama client for translation.
        stop_flag: Optional threading event to signal stop.
        log: Logging callback function.
        use_pymupdf: Force PyMuPDF (True) or PyPDF2 (False). None uses config.
        skip_header_footer: Override header/footer skipping. None uses config.
        output_format: Output format - "docx" (default) or "pdf" (requires Phase 3).
        layout_mode: Layout mode - "inline" (default), "overlay", or "side_by_side".
        draw_mask: Draw white mask over original text in overlay mode. None uses config.

    Returns:
        True if stopped early, False if completed.

    Raises:
        ValueError: If output_format="pdf" with layout_mode="inline".
    """
    # Validate output_format and layout_mode combination
    if output_format == "pdf" and layout_mode == "inline":
        raise ValueError(
            "PDF output format is not supported with inline layout mode. "
            "Use layout_mode='overlay' or 'side_by_side' for PDF output, "
            "or use output_format='docx' for inline mode."
        )

    # PDF output with overlay/side_by_side - use PDFGenerator
    if output_format == "pdf" and layout_mode in ("overlay", "side_by_side"):
        return _translate_pdf_to_pdf(
            in_path,
            out_path,
            targets,
            src_lang,
            cache,
            client,
            stop_flag,
            log,
            skip_header_footer,
            layout_mode,
            draw_mask,
        )

    # Try Windows COM conversion first (highest quality)
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

    # Determine which parser to use
    should_use_pymupdf = use_pymupdf if use_pymupdf is not None else (PDF_PARSER_ENGINE == "pymupdf")
    parser = _get_pymupdf_parser() if should_use_pymupdf else None

    if parser:
        return _translate_pdf_with_pymupdf(
            in_path,
            out_path,
            targets,
            src_lang,
            cache,
            client,
            stop_flag,
            log,
            skip_header_footer,
        )
    else:
        return _translate_pdf_with_pypdf2(
            in_path,
            out_path,
            targets,
            src_lang,
            cache,
            client,
            stop_flag,
            log,
        )


def _translate_pdf_with_pymupdf(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    stop_flag: Optional[threading.Event],
    log: Callable[[str], None],
    skip_header_footer: Optional[bool],
) -> bool:
    """Translate PDF using PyMuPDF parser with bbox support.

    This method provides:
    - Correct reading order
    - Header/footer detection and optional skipping
    - Table region awareness
    - Better text block handling
    """
    from app.backend.models.translatable_document import ElementType
    from app.backend.parsers.pdf_parser import PyMuPDFParser

    # Create parser with appropriate settings
    should_skip_hf = skip_header_footer if skip_header_footer is not None else PDF_SKIP_HEADER_FOOTER
    parser = PyMuPDFParser(
        skip_header_footer=should_skip_hf,
        header_footer_margin_pt=PDF_HEADER_FOOTER_MARGIN_PT,
    )

    try:
        # Parse PDF
        log(f"[PDF] Parsing with PyMuPDF: {os.path.basename(in_path)}")
        doc = parser.parse(in_path)

        if not doc.metadata.has_text_layer:
            log("[PDF] Warning: PDF appears to be scanned (low text content)")

        # Get elements in reading order
        elements = doc.get_elements_in_reading_order()
        translatable = [e for e in elements if e.should_translate and e.content.strip()]

        log(f"[PDF] Found {len(translatable)} translatable blocks across {doc.metadata.page_count} pages")

        # Calculate total text length for size limit check
        total_text_length = sum(len(e.content.strip()) for e in translatable)

        # Check document size limits
        check_document_size_limits(
            segment_count=len(translatable),
            total_text_length=total_text_length,
            max_segments=MAX_SEGMENTS,
            max_text_length=MAX_TEXT_LENGTH,
            document_type="PDF document",
        )

        # Collect unique texts for batch translation
        unique_texts = list(set(e.content.strip() for e in translatable if e.content.strip()))
        log(f"[PDF] Translating {len(unique_texts)} unique texts")

        # Batch translate for each target language
        stopped = False
        translations_by_target = {}

        for tgt in targets:
            if stop_flag and stop_flag.is_set():
                log(f"[STOP] PDF stopped before translating to {tgt}")
                stopped = True
                break

            log(f"[PDF] Batch translating to {tgt}...")
            results = translate_blocks_batch(
                unique_texts, tgt, src_lang, cache, client
            )
            translations_by_target[tgt] = {
                text: (translated if ok else f"[Translation failed|{tgt}] {text}")
                for text, (ok, translated) in zip(unique_texts, results)
            }

        # Create output document
        output_doc = docx.Document()
        current_page = 0

        for i, element in enumerate(translatable):
            if stop_flag and stop_flag.is_set():
                log(f"[STOP] PDF stopped at element {i}/{len(translatable)}")
                stopped = True
                break

            # Add page header when page changes
            if element.page_num != current_page:
                current_page = element.page_num
                output_doc.add_heading(f"-- Page {current_page} --", level=1)

            # Add original text with element type indicator
            type_indicator = ""
            if element.element_type == ElementType.HEADER:
                type_indicator = "[Header] "
            elif element.element_type == ElementType.FOOTER:
                type_indicator = "[Footer] "
            elif element.element_type == ElementType.TABLE_CELL:
                type_indicator = "[Table] "

            original_text = element.content.strip()
            output_doc.add_paragraph(f"{type_indicator}{original_text}")

            # Add translations for each target language
            for tgt in targets:
                if tgt in translations_by_target and original_text in translations_by_target[tgt]:
                    translated = translations_by_target[tgt][original_text]
                else:
                    translated = f"[No translation|{tgt}] {original_text}"
                output_doc.add_paragraph(translated)

            if stopped:
                break

        output_doc.save(out_path)

        if stopped:
            log(f"[PDF] Partial output: {os.path.basename(out_path)}")
        else:
            log(f"[PDF] Output: {os.path.basename(out_path)}")

        return stopped

    except Exception as exc:
        log(f"[PDF] PyMuPDF parsing failed, falling back to PyPDF2: {exc}")
        return _translate_pdf_with_pypdf2(
            in_path, out_path, targets, src_lang, cache, client, stop_flag, log
        )


def _translate_pdf_with_pypdf2(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    stop_flag: Optional[threading.Event],
    log: Callable[[str], None],
) -> bool:
    """Translate PDF using PyPDF2 (fallback method).

    This is the original implementation kept for compatibility.
    Uses batch translation for better context preservation.
    """
    doc = docx.Document()
    stopped = False

    try:
        reader = PdfReader(in_path)
        total_pages = len(reader.pages)

        # Extract all page texts first
        page_texts = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            page_texts.append((i, text.strip()))

        # Calculate total text length for size limit check
        total_text_length = sum(len(text) for _, text in page_texts if text)

        # Check document size limits
        check_document_size_limits(
            segment_count=len([t for _, t in page_texts if t]),
            total_text_length=total_text_length,
            max_segments=MAX_SEGMENTS,
            max_text_length=MAX_TEXT_LENGTH,
            document_type="PDF document",
        )

        # Collect unique texts for batch translation
        unique_texts = list(set(text for _, text in page_texts if text))
        log(f"[PDF] PyPDF2: {total_pages} pages, {len(unique_texts)} unique texts")

        # Batch translate for each target language
        translations_by_target = {}
        for tgt in targets:
            if stop_flag and stop_flag.is_set():
                log(f"[STOP] PDF stopped before translating to {tgt}")
                stopped = True
                break

            log(f"[PDF] Batch translating to {tgt}...")
            results = translate_blocks_batch(
                unique_texts, tgt, src_lang, cache, client
            )
            translations_by_target[tgt] = {
                text: (translated if ok else f"[Translation failed|{tgt}] {text}")
                for text, (ok, translated) in zip(unique_texts, results)
            }

        # Build output document
        for page_num, text in page_texts:
            if stop_flag and stop_flag.is_set():
                stopped = True
                break

            doc.add_heading(f"-- Page {page_num} --", level=1)
            if text:
                doc.add_paragraph(text)
                for tgt in targets:
                    if tgt in translations_by_target and text in translations_by_target[tgt]:
                        tr = translations_by_target[tgt][text]
                    else:
                        tr = f"[No translation|{tgt}] {text}"
                    doc.add_paragraph(tr)

    except Exception as exc:
        doc.add_paragraph(f"[PDF extract error] {exc}")

    doc.save(out_path)
    if stopped:
        log(f"[PDF] partial output: {os.path.basename(out_path)}")
    else:
        log(f"[PDF] output: {os.path.basename(out_path)}")

    return stopped


def _translate_pdf_to_pdf(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    stop_flag: Optional[threading.Event],
    log: Callable[[str], None],
    skip_header_footer: Optional[bool],
    layout_mode: str,
    draw_mask: Optional[bool] = None,
) -> bool:
    """Translate PDF to PDF with layout preservation.

    Uses PDFGenerator to create overlay or side-by-side output.
    Supports multiple target languages by generating separate PDF files.

    Args:
        in_path: Input PDF path.
        out_path: Output PDF path (base path for multiple languages).
        targets: Target languages.
        src_lang: Source language.
        cache: Translation cache.
        client: Ollama client.
        stop_flag: Stop flag.
        log: Logging callback.
        skip_header_footer: Whether to skip header/footer.
        layout_mode: 'overlay' or 'side_by_side'.
        draw_mask: Whether to draw white mask over original text. None uses config default.

    Returns:
        True if stopped early, False if completed.
    """
    from app.backend.parsers.pdf_parser import PyMuPDFParser
    from app.backend.renderers.base import RenderMode
    from app.backend.renderers.pdf_generator import PDFGenerator

    # Create parser
    should_skip_hf = skip_header_footer if skip_header_footer is not None else PDF_SKIP_HEADER_FOOTER
    parser = PyMuPDFParser(
        skip_header_footer=should_skip_hf,
        header_footer_margin_pt=PDF_HEADER_FOOTER_MARGIN_PT,
    )

    try:
        # Parse PDF
        log(f"[PDF] Parsing with PyMuPDF: {os.path.basename(in_path)}")
        doc = parser.parse(in_path)

        if not doc.metadata.has_text_layer:
            log("[PDF] Warning: PDF appears to be scanned (low text content)")

        # Get translatable elements
        elements = doc.get_elements_in_reading_order()
        translatable = [e for e in elements if e.should_translate and e.content.strip()]

        log(f"[PDF] Found {len(translatable)} translatable blocks across {doc.metadata.page_count} pages")

        # Calculate total text length for size limit check
        total_text_length = sum(len(e.content.strip()) for e in translatable)

        # Check document size limits
        check_document_size_limits(
            segment_count=len(translatable),
            total_text_length=total_text_length,
            max_segments=MAX_SEGMENTS,
            max_text_length=MAX_TEXT_LENGTH,
            document_type="PDF document",
        )

        # Collect unique texts for translation
        # Note: For PDF overlay mode, we translate lines individually to preserve layout
        # The translation quality is improved by using paragraph-level granularity in translate_blocks_batch
        unique_texts = list(set(e.content.strip() for e in translatable))
        log(f"[PDF] Translating {len(unique_texts)} unique text blocks")

        # Determine render mode
        mode_enum = RenderMode.OVERLAY if layout_mode == "overlay" else RenderMode.SIDE_BY_SIDE

        # Use draw_mask parameter or fall back to config default
        should_draw_mask = draw_mask if draw_mask is not None else PDF_DRAW_MASK

        stopped = False
        output_files = []

        # Generate PDF for each target language
        if len(targets) > 1:
            log(f"[PDF] Generating {len(targets)} PDF files for languages: {', '.join(targets)}")

        for tgt_idx, tgt in enumerate(targets):
            if stop_flag and stop_flag.is_set():
                log(f"[STOP] PDF stopped before translating to {tgt}")
                stopped = True
                break

            # Generate language-specific output path
            if len(targets) > 1:
                out_stem = Path(out_path).stem
                out_dir = Path(out_path).parent
                lang_suffix = f"_{tgt.replace(' ', '_').replace('-', '_')}"
                lang_out_path = str(out_dir / f"{out_stem}{lang_suffix}.pdf")
            else:
                lang_out_path = out_path

            # Translate texts for this language
            log(f"[PDF] [{tgt_idx + 1}/{len(targets)}] Translating to {tgt}...")
            results = translate_blocks_batch(
                unique_texts, tgt, src_lang, cache, client
            )

            # Build text -> translation mapping
            translations = {}
            missing_count = 0
            for text, (ok, translated) in zip(unique_texts, results):
                if ok:
                    translations[text] = translated
                else:
                    translations[text] = f"[翻譯失敗] {text[:30]}..."
                    missing_count += 1

            if missing_count > 0:
                log(f"[PDF] Warning: {missing_count} texts failed to translate to {tgt}")

            # Generate PDF for this language
            generator = PDFGenerator(
                target_lang=tgt,
                draw_mask=should_draw_mask,
                log=log,
            )
            generator.generate(doc, translations, lang_out_path, mode_enum)
            output_files.append(lang_out_path)
            log(f"[PDF] Generated: {Path(lang_out_path).name}")

        if stopped:
            log(f"[PDF] Partial output: {len(output_files)} of {len(targets)} files generated")
        else:
            log(f"[PDF] Completed: {len(output_files)} PDF file(s) generated")

        return stopped

    except Exception as exc:
        log(f"[PDF] PDF-to-PDF generation failed: {exc}")
        # Fallback to DOCX output
        log("[PDF] Falling back to DOCX output")
        docx_out = str(Path(out_path).with_suffix(".docx"))
        return _translate_pdf_with_pymupdf(
            in_path, docx_out, targets, src_lang, cache, client, stop_flag, log, skip_header_footer
        )


def parse_pdf_to_document(
    file_path: str,
    skip_header_footer: Optional[bool] = None,
) -> "TranslatableDocument":
    """Parse a PDF file to TranslatableDocument (for advanced use).

    This function exposes the parsed document structure for custom processing.

    Args:
        file_path: Path to the PDF file.
        skip_header_footer: Whether to mark header/footer as non-translatable.

    Returns:
        TranslatableDocument with extracted elements and bbox info.

    Raises:
        ImportError: If PyMuPDF is not installed.
        FileNotFoundError: If file does not exist.
    """
    from app.backend.parsers.pdf_parser import PyMuPDFParser

    should_skip = skip_header_footer if skip_header_footer is not None else PDF_SKIP_HEADER_FOOTER
    parser = PyMuPDFParser(
        skip_header_footer=should_skip,
        header_footer_margin_pt=PDF_HEADER_FOOTER_MARGIN_PT,
    )
    return parser.parse(file_path)
