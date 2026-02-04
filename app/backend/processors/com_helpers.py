"""Optional Windows COM helpers."""

from __future__ import annotations

import os
from typing import Any, Callable, Iterator, List, Optional

from app.backend.config import MAX_SHAPE_CHARS
from app.backend.utils.logging_utils import logger
from app.backend.utils.translation_helpers import translate_block_sentencewise
from app.backend.clients.ollama_client import OllamaClient

try:
    import pythoncom
    import win32com.client as win32
    from win32com.client import constants as c
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False


def is_win32com_available() -> bool:
    return WIN32COM_AVAILABLE


def _com_iter(coll: Any) -> Iterator[Any]:
    try:
        count = coll.Count
    except AttributeError:
        return
    for i in range(1, count + 1):
        yield coll.Item(i)


def word_convert(input_path: str, output_path: str, target_format: int) -> None:
    if not WIN32COM_AVAILABLE:
        raise RuntimeError("Word COM not available")
    pythoncom.CoInitialize()
    try:
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(os.path.abspath(input_path))
        doc.SaveAs2(os.path.abspath(output_path), FileFormat=target_format)
        doc.Close(False)
    finally:
        word.Quit()
        pythoncom.CoUninitialize()


def excel_convert(input_path: str, output_path: str) -> None:
    if not WIN32COM_AVAILABLE:
        raise RuntimeError("Excel COM not available")
    pythoncom.CoInitialize()
    try:
        excel = win32.Dispatch("Excel.Application")
        excel.Visible = False
        try:
            excel.DisplayAlerts = False
        except AttributeError:
            pass
        wb = excel.Workbooks.Open(os.path.abspath(input_path))
        wb.SaveAs(os.path.abspath(output_path), FileFormat=51)
        wb.Close(SaveChanges=False)
    finally:
        excel.Quit()
        pythoncom.CoUninitialize()


def postprocess_docx_shapes_with_word(
    docx_path: str,
    targets: List[str],
    src_lang: Optional[str],
    client: OllamaClient,
    include_headers: bool = False,
    log: Callable[[str], None] = lambda s: None,
) -> None:
    if not WIN32COM_AVAILABLE or not include_headers:
        return
    pythoncom.CoInitialize()
    try:
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        try:
            word.ScreenUpdating = False
        except AttributeError:
            pass
        try:
            word.DisplayAlerts = 0
        except AttributeError:
            pass
        doc = word.Documents.Open(os.path.abspath(docx_path))

        def _proc_shapes(shapes):
            for shp in _com_iter(shapes):
                try:
                    tf = getattr(shp, "TextFrame", None)
                    if tf and getattr(tf, "HasText", False):
                        src = tf.TextRange.Text
                        if not src or not src.strip():
                            continue
                        if len(src) > MAX_SHAPE_CHARS:
                            log(f"[SKIP] shape too long ({len(src)} chars)")
                            continue
                        blocks = []
                        for tgt in targets:
                            ok, translated = translate_block_sentencewise(src, tgt, src_lang, client)
                            if not ok:
                                translated = f"[Translation failed|{tgt}] {src}"
                            blocks.append(translated)
                        suffix = "\r" + "\r".join(blocks)
                        full = tf.TextRange.Text or ""
                        if full.endswith(suffix):
                            continue
                        tf.TextRange.InsertAfter(suffix)
                        try:
                            dup = tf.TextRange.Duplicate
                            start = len(full) + 1
                            end = dup.Characters.Count
                            dup.SetRange(start, end)
                            dup.Font.Italic = True
                        except AttributeError as exc:
                            logger.debug("COM font styling failed: %s", exc)
                except (AttributeError, RuntimeError) as exc:
                    log(f"[COM shape error] {exc}")

        for sec in _com_iter(doc.Sections):
            try:
                _proc_shapes(sec.Headers(c.wdHeaderFooterPrimary).Shapes)
                _proc_shapes(sec.Headers(c.wdHeaderFooterFirstPage).Shapes)
                _proc_shapes(sec.Headers(c.wdHeaderFooterEvenPages).Shapes)
                _proc_shapes(sec.Footers(c.wdHeaderFooterPrimary).Shapes)
                _proc_shapes(sec.Footers(c.wdHeaderFooterFirstPage).Shapes)
                _proc_shapes(sec.Footers(c.wdHeaderFooterEvenPages).Shapes)
            except (AttributeError, RuntimeError) as exc:
                logger.debug("Failed to process section headers/footers: %s", exc)

        doc.Save()
        doc.Close(False)
    finally:
        try:
            word.ScreenUpdating = True
        except AttributeError:
            pass
        word.Quit()
        pythoncom.CoUninitialize()
