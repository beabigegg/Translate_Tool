"""XLSX/XLS translation processor."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import Alignment

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import DEFAULT_MAX_BATCH_CHARS, EXCEL_FORMULA_MODE, MAX_SEGMENTS, MAX_TEXT_LENGTH
from app.backend.processors.com_helpers import excel_convert, is_win32com_available
from app.backend.services.translation_service import translate_texts
from app.backend.utils.exceptions import check_document_size_limits
from app.backend.utils.logging_utils import logger
from app.backend.utils.text_utils import normalize_text, should_translate


def _get_display_text_for_translation(ws: Any, ws_vals: Optional[Any], r: int, c: int) -> Optional[str]:
    val = ws.cell(row=r, column=c).value
    if isinstance(val, str) and val.startswith("="):
        if ws_vals is not None:
            shown = ws_vals.cell(row=r, column=c).value
            return shown if isinstance(shown, str) and shown.strip() else None
        return None
    if isinstance(val, str) and val.strip():
        return val
    if ws_vals is not None:
        shown = ws_vals.cell(row=r, column=c).value
        if isinstance(shown, str) and shown.strip():
            return shown
    return None


def translate_xlsx_xls(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    client: OllamaClient,
    excel_formula_mode: str = EXCEL_FORMULA_MODE,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
    max_segments: int = MAX_SEGMENTS,
    max_text_length: int = MAX_TEXT_LENGTH,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
) -> bool:
    ext = Path(in_path).suffix.lower()
    out_xlsx = Path(out_path).with_suffix(".xlsx")
    if ext == ".xls" and is_win32com_available():
        tmp = str(Path(out_path).with_suffix("")) + "__from_xls.xlsx"
        try:
            log("[XLS] Converting to .xlsx via COM")
            excel_convert(in_path, tmp)
            return translate_xlsx_xls(
                tmp,
                out_path,
                targets,
                src_lang,
                client,
                excel_formula_mode=excel_formula_mode,
                stop_flag=stop_flag,
                log=log,
                max_segments=max_segments,
                max_text_length=max_text_length,
                max_batch_chars=max_batch_chars,
            )
        finally:
            try:
                os.remove(tmp)
            except OSError as exc:
                logger.debug("Failed to remove temp file %s: %s", tmp, exc)
    if ext not in (".xlsx", ".xls"):
        raise RuntimeError("Unsupported Excel type")

    wb = openpyxl.load_workbook(in_path, data_only=False)
    try:
        wb_vals = openpyxl.load_workbook(in_path, data_only=True)
    except (OSError, ValueError, KeyError) as exc:
        logger.debug("Failed to load workbook with data_only=True: %s", exc)
        wb_vals = None

    segs: List[Tuple[str, int, int, str, bool]] = []
    total_text_length = 0
    for ws in wb.worksheets:
        ws_vals = wb_vals[ws.title] if wb_vals and ws.title in wb_vals.sheetnames else None
        max_row, max_col = ws.max_row, ws.max_column
        for r in range(1, max_row + 1):
            for c in range(1, max_col + 1):
                src_text = _get_display_text_for_translation(ws, ws_vals, r, c)
                if not src_text:
                    continue
                if not should_translate(src_text, (src_lang or "auto")):
                    continue
                val = ws.cell(row=r, column=c).value
                is_formula = isinstance(val, str) and val.startswith("=")
                segs.append((ws.title, r, c, src_text, is_formula))
                total_text_length += len(src_text)

    check_document_size_limits(
        segment_count=len(segs),
        total_text_length=total_text_length,
        max_segments=max_segments,
        max_text_length=max_text_length,
        document_type="Excel document",
    )

    log(f"[Excel] cells: {len(segs)}")
    uniq = sorted(set(s[3] for s in segs))
    tmap, _, _, stopped = translate_texts(
        uniq,
        targets,
        src_lang,
        client,
        max_batch_chars=max_batch_chars,
        stop_flag=stop_flag,
        log=log,
    )

    for sheet_name, r, c, src_text, is_formula in segs:
        if not all((tgt, src_text) in tmap for tgt in targets):
            continue
        ws = wb[sheet_name]
        trs = [tmap[(tgt, src_text)] for tgt in targets]
        if is_formula:
            if excel_formula_mode == "skip":
                continue
            if excel_formula_mode == "comment":
                txt_comment = "\n".join([f"[{t}] {res}" for t, res in zip(targets, trs)])
                cell = ws.cell(row=r, column=c)
                exist = cell.comment
                if not exist or normalize_text(exist.text) != normalize_text(txt_comment):
                    cell.comment = Comment(txt_comment, "translator")
                continue
            continue
        combined = "\n".join([src_text] + trs)
        cell = ws.cell(row=r, column=c)
        if isinstance(cell.value, str) and normalize_text(cell.value) == normalize_text(combined):
            continue
        cell.value = combined
        try:
            if cell.alignment:
                cell.alignment = Alignment(
                    horizontal=cell.alignment.horizontal,
                    vertical=cell.alignment.vertical,
                    wrap_text=True,
                )
            else:
                cell.alignment = Alignment(wrap_text=True)
        except (TypeError, AttributeError) as exc:
            logger.debug("Cell alignment copy failed: %s", exc)
            cell.alignment = Alignment(wrap_text=True)

    wb.save(out_xlsx)

    if stopped:
        log(f"[Excel] partial output: {out_xlsx.name}")
    else:
        log(f"[Excel] output: {out_xlsx.name}")

    return stopped
