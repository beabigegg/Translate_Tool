"""PPTX translation processor."""

from __future__ import annotations

import os
import re
import threading
import zipfile
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from xml.etree import ElementTree as ET

import pptx
from pptx.table import _Cell
from pptx.util import Pt as PPTPt

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import DEFAULT_MAX_BATCH_CHARS, MAX_SEGMENTS, MAX_TEXT_LENGTH
from app.backend.services.translation_service import translate_texts
from app.backend.utils.exceptions import check_document_size_limits
from app.backend.utils.text_utils import normalize_text, should_translate


# Segment types for tracking
SEGMENT_TEXT_FRAME = "text_frame"
SEGMENT_TABLE_CELL = "table_cell"
SEGMENT_SMARTART = "smartart"

# XML namespaces for SmartArt
SMARTART_NS = {
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


def _ppt_text_of_tf(tf: Any) -> str:
    return "\n".join([p.text for p in tf.paragraphs])


def _ppt_tail_equals(tf: Any, translations: List[str]) -> bool:
    if len(tf.paragraphs) < len(translations):
        return False
    tail = tf.paragraphs[-len(translations):]
    for para, expect in zip(tail, translations):
        if normalize_text(para.text) != normalize_text(expect):
            return False
        if any((r.font.italic is not True) and (r.text or "").strip() for r in para.runs):
            return False
    return True


def _ppt_append(tf: Any, text_block: str) -> None:
    p = tf.add_paragraph()
    p.text = text_block
    for r in p.runs:
        r.font.italic = True
        r.font.size = PPTPt(12)


def _cell_text(cell: _Cell) -> str:
    """Get text from a table cell."""
    return cell.text.strip()


def _cell_tail_equals(cell: _Cell, translations: List[str]) -> bool:
    """Check if translation already appended to cell."""
    tf = cell.text_frame
    if len(tf.paragraphs) < len(translations):
        return False
    tail = tf.paragraphs[-len(translations):]
    for para, expect in zip(tail, translations):
        if normalize_text(para.text) != normalize_text(expect):
            return False
        if any((r.font.italic is not True) and (r.text or "").strip() for r in para.runs):
            return False
    return True


def _cell_append(cell: _Cell, text_block: str) -> None:
    """Append translated text to a table cell."""
    tf = cell.text_frame
    p = tf.add_paragraph()
    p.text = text_block
    for r in p.runs:
        r.font.italic = True
        r.font.size = PPTPt(10)  # Slightly smaller for table cells


def _extract_smartart_texts(pptx_path: str) -> List[Tuple[str, str, str]]:
    """Extract text from SmartArt diagrams in a PPTX file.

    Args:
        pptx_path: Path to the PPTX file.

    Returns:
        List of tuples: (diagram_file, xpath, text)
    """
    smartart_texts: List[Tuple[str, str, str]] = []

    with zipfile.ZipFile(pptx_path, "r") as zf:
        # Find all diagram data files
        diagram_files = [f for f in zf.namelist() if f.startswith("ppt/diagrams/data") and f.endswith(".xml")]

        for diagram_file in diagram_files:
            try:
                xml_content = zf.read(diagram_file).decode("utf-8")
                root = ET.fromstring(xml_content)

                # Find all text elements in the diagram
                # SmartArt text is typically in <a:t> tags within <dgm:t> or directly
                for idx, t_elem in enumerate(root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t")):
                    text = t_elem.text
                    if text and text.strip():
                        # Store file, index, and text
                        smartart_texts.append((diagram_file, str(idx), text.strip()))
            except (ET.ParseError, KeyError, UnicodeDecodeError):
                continue

    return smartart_texts


def _update_smartart_texts(
    pptx_path: str,
    out_path: str,
    translations: Dict[str, str],
) -> None:
    """Update SmartArt texts with translations.

    Args:
        pptx_path: Path to the original PPTX file.
        out_path: Path to save the updated PPTX file.
        translations: Dict mapping original text to translated text (appended).
    """
    import shutil
    import tempfile

    # Copy to temp file first
    temp_dir = tempfile.mkdtemp()
    temp_pptx = os.path.join(temp_dir, "temp.pptx")
    shutil.copy2(pptx_path, temp_pptx)

    # Read and modify the PPTX
    with zipfile.ZipFile(temp_pptx, "r") as zf_in:
        # Get all file contents
        file_contents = {}
        for name in zf_in.namelist():
            file_contents[name] = zf_in.read(name)

    # Modify SmartArt diagram files
    for filename, content in list(file_contents.items()):
        if filename.startswith("ppt/diagrams/data") and filename.endswith(".xml"):
            try:
                xml_content = content.decode("utf-8")
                root = ET.fromstring(xml_content)
                modified = False

                for t_elem in root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t"):
                    text = t_elem.text
                    if text and text.strip() in translations:
                        original = text.strip()
                        translated = translations[original]
                        # Append translation in parentheses
                        t_elem.text = f"{text}\n({translated})"
                        modified = True

                if modified:
                    # Re-serialize with proper XML declaration
                    ET.register_namespace("", "http://schemas.openxmlformats.org/drawingml/2006/diagram")
                    ET.register_namespace("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
                    file_contents[filename] = ET.tostring(root, encoding="unicode").encode("utf-8")
            except (ET.ParseError, UnicodeDecodeError):
                continue

    # Write the modified PPTX
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
        for name, content in file_contents.items():
            zf_out.writestr(name, content)

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


def translate_pptx(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    client: OllamaClient,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
    max_segments: int = MAX_SEGMENTS,
    max_text_length: int = MAX_TEXT_LENGTH,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
) -> bool:
    prs = pptx.Presentation(in_path)
    # segs: List of (segment_type, object_ref, text)
    segs: List[Tuple[str, Any, str]] = []
    total_text_length = 0

    for slide in prs.slides:
        for shape in slide.shapes:
            # Handle tables - use has_table property instead of hasattr
            if getattr(shape, "has_table", False):
                try:
                    table = shape.table
                    for row in table.rows:
                        for cell in row.cells:
                            txt = _cell_text(cell)
                            if txt:
                                segs.append((SEGMENT_TABLE_CELL, cell, txt))
                                total_text_length += len(txt)
                    continue
                except Exception:
                    # Shape reports has_table but doesn't contain one
                    pass

            # Handle text frames
            if not getattr(shape, "has_text_frame", False):
                continue
            tf = shape.text_frame
            txt = _ppt_text_of_tf(tf)
            if txt.strip():
                segs.append((SEGMENT_TEXT_FRAME, tf, txt))
                total_text_length += len(txt)

    # Extract SmartArt texts
    smartart_texts = _extract_smartart_texts(in_path)
    smartart_segs: List[Tuple[str, str, str]] = []  # (file, idx, text)
    for diagram_file, idx, text in smartart_texts:
        smartart_segs.append((diagram_file, idx, text))
        total_text_length += len(text)

    total_segs = len(segs) + len(smartart_segs)

    check_document_size_limits(
        segment_count=total_segs,
        total_text_length=total_text_length,
        max_segments=max_segments,
        max_text_length=max_text_length,
        document_type="PowerPoint document",
    )

    # Count segments by type for logging
    tf_count = sum(1 for seg_type, _, _ in segs if seg_type == SEGMENT_TEXT_FRAME)
    cell_count = sum(1 for seg_type, _, _ in segs if seg_type == SEGMENT_TABLE_CELL)
    smartart_count = len(smartart_segs)
    log(f"[PPTX] segments: {total_segs} (text frames: {tf_count}, table cells: {cell_count}, SmartArt: {smartart_count})")

    # Collect all unique texts for translation
    all_texts = [s for _, _, s in segs] + [s for _, _, s in smartart_segs]
    uniq = [s for s in sorted(set(all_texts)) if should_translate(s, (src_lang or "auto"))]

    tmap, _, _, stopped = translate_texts(
        uniq,
        targets,
        src_lang,
        client,
        max_batch_chars=max_batch_chars,
        stop_flag=stop_flag,
        log=log,
    )

    # Apply translations to text frames and table cells
    ok_cnt = skip_cnt = 0
    for seg_type, obj_ref, s in segs:
        if not all((tgt, s) in tmap for tgt in targets):
            continue
        trs = [tmap[(tgt, s)] for tgt in targets]

        if seg_type == SEGMENT_TEXT_FRAME:
            if _ppt_tail_equals(obj_ref, trs):
                skip_cnt += 1
                continue
            for block in trs:
                _ppt_append(obj_ref, block)
            ok_cnt += 1
        elif seg_type == SEGMENT_TABLE_CELL:
            if _cell_tail_equals(obj_ref, trs):
                skip_cnt += 1
                continue
            for block in trs:
                _cell_append(obj_ref, block)
            ok_cnt += 1

    prs.save(out_path)

    # Apply SmartArt translations (requires direct XML manipulation)
    if smartart_segs:
        # Build translation map for SmartArt: original -> combined translations
        smartart_tmap: Dict[str, str] = {}
        for _, _, text in smartart_segs:
            if all((tgt, text) in tmap for tgt in targets):
                translations = [tmap[(tgt, text)] for tgt in targets]
                smartart_tmap[text] = " / ".join(translations)

        if smartart_tmap:
            _update_smartart_texts(out_path, out_path, smartart_tmap)
            log(f"[PPTX] SmartArt translated: {len(smartart_tmap)} items")

    if stopped:
        log(f"[PPTX] partial output: {os.path.basename(out_path)}")
    else:
        log(f"[PPTX] output: {os.path.basename(out_path)}")

    return stopped
