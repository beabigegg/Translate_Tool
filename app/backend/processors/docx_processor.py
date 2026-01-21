"""DOCX translation processor."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, TYPE_CHECKING

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import (
    DEFAULT_MAX_BATCH_CHARS,
    INSERT_FONT_SIZE_PT,
    MAX_SEGMENTS,
    MAX_TEXT_LENGTH,
)
from app.backend.processors.com_helpers import is_win32com_available, postprocess_docx_shapes_with_word
from app.backend.services.translation_service import translate_texts
from app.backend.utils.exceptions import ApiError, check_document_size_limits
from app.backend.utils.logging_utils import logger
from app.backend.utils.text_utils import has_cjk, normalize_text, should_translate

if TYPE_CHECKING:
    from docx.document import Document as DocxDocument

INSERT_MARKER = "\u200b"


def _p_text_with_breaks(p: Paragraph) -> str:
    parts = []
    for node in p._p.xpath(".//*[local-name()='t' or local-name()='br' or local-name()='tab']"):
        tag = node.tag.split("}", 1)[-1]
        if tag == "t":
            parts.append(node.text or "")
        elif tag == "br":
            parts.append("\n")
        else:
            parts.append(" ")
    return "".join(parts).strip()


def _append_after(p: Paragraph, text_block: str, italic: bool = True, font_size_pt: int = INSERT_FONT_SIZE_PT) -> Paragraph:
    new_p = OxmlElement("w:p")
    p._p.addnext(new_p)
    np = Paragraph(new_p, p._parent)
    lines = text_block.split("\n")
    for i, line in enumerate(lines):
        run = np.add_run(line)
        if italic:
            run.italic = True
        if font_size_pt:
            run.font.size = Pt(font_size_pt)
        if i < len(lines) - 1:
            run.add_break()
    tag = np.add_run(INSERT_MARKER)
    if italic:
        tag.italic = True
    if font_size_pt:
        tag.font.size = Pt(font_size_pt)
    return np


def _is_our_insert_block(p: Paragraph) -> bool:
    return any(INSERT_MARKER in (r.text or "") for r in p.runs)


def _find_last_inserted_after(p: Paragraph, limit: int = 8) -> Optional[Paragraph]:
    ptr = p._p.getnext()
    last = None
    steps = 0
    while ptr is not None and steps < limit:
        if ptr.tag.endswith("}p"):
            q = Paragraph(ptr, p._parent)
            if _is_our_insert_block(q):
                last = q
                steps += 1
                ptr = ptr.getnext()
                continue
        break
    return last


def _scan_our_tail_texts(p: Paragraph, limit: int = 8) -> List[str]:
    ptr = p._p.getnext()
    out = []
    steps = 0
    while ptr is not None and steps < limit:
        if ptr.tag.endswith("}p"):
            q = Paragraph(ptr, p._parent)
            if _is_our_insert_block(q):
                out.append(_p_text_with_breaks(q))
                steps += 1
                ptr = ptr.getnext()
                continue
        break
    return out


def _txbx_iter_texts(doc: Any) -> Iterator[Tuple[Any, str]]:
    def _p_text_flags(p_el):
        parts = []
        for node in p_el.xpath(".//*[local-name()='t' or local-name()='br' or local-name()='tab']"):
            tag = node.tag.split("}", 1)[-1]
            if tag == "t":
                parts.append(node.text or "")
            elif tag == "br":
                parts.append("\n")
            else:
                parts.append(" ")
        text = "".join(parts)
        has_zero = INSERT_MARKER in text
        runs = p_el.xpath(".//*[local-name()='r']")
        visible, ital = [], []
        for run in runs:
            rt = "".join([(t.text or "") for t in run.xpath(".//*[local-name()='t']")])
            if (rt or "").strip():
                visible.append(rt)
                ital.append(bool(run.xpath(".//*[local-name()='i']")))
        all_italic = len(visible) > 0 and all(ital)
        return text, has_zero, all_italic

    for tx in doc._element.xpath(".//*[local-name()='txbxContent']"):
        kept = []
        for p in tx.xpath(".//*[local-name()='p']"):
            text, has_zero, _ = _p_text_flags(p)
            if not (text or "").strip():
                continue
            if has_zero:
                continue
            for line in text.split("\n"):
                if line.strip():
                    kept.append(line.strip())
        if kept:
            joined = "\n".join(kept)
            yield tx, joined


def _txbx_append_paragraph(tx: Any, text_block: str, italic: bool = True, font_size_pt: int = INSERT_FONT_SIZE_PT) -> None:
    p = OxmlElement("w:p")
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    if italic:
        rpr.append(OxmlElement("w:i"))
    if font_size_pt:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(font_size_pt * 2)))
        rpr.append(sz)
    r.append(rpr)
    lines = text_block.split("\n")
    for i, line in enumerate(lines):
        if i > 0:
            r.append(OxmlElement("w:br"))
        t = OxmlElement("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = line
        r.append(t)
    tag = OxmlElement("w:t")
    tag.set(qn("xml:space"), "preserve")
    tag.text = INSERT_MARKER
    r.append(tag)
    p.append(r)
    tx.append(p)


def _txbx_tail_equals(tx: Any, translations: List[str]) -> bool:
    paras = tx.xpath("./*[local-name()='p']")
    if len(paras) < len(translations):
        return False
    tail = paras[-len(translations):]
    for q, expect in zip(tail, translations):
        parts = []
        for node in q.xpath(".//*[local-name()='t' or local-name()='br']"):
            tag = node.tag.split("}", 1)[-1]
            parts.append("\n" if tag == "br" else (node.text or ""))
        if normalize_text("".join(parts).strip()) != normalize_text(expect):
            return False
    return True


class Segment:
    """Represents a segment of text to be translated in a document."""

    def __init__(self, kind: str, ref: Any, ctx: str, text: str) -> None:
        self.kind = kind
        self.ref = ref
        self.ctx = ctx
        self.text = text


def _get_paragraph_key(p: Paragraph) -> str:
    try:
        xml_content = p._p.xml if hasattr(p._p, "xml") else str(p._p)
        text_content = _p_text_with_breaks(p)
        combined = f"{hash(xml_content)}_{len(text_content)}_{text_content[:50]}"
        return combined
    except (AttributeError, TypeError) as exc:
        logger.debug("Paragraph key generation fallback due to: %s", exc)
        text_content = _p_text_with_breaks(p)
        return f"fallback_{hash(text_content)}_{len(text_content)}"


def _collect_docx_segments(
    doc: Any,
    max_segments: int = MAX_SEGMENTS,
    max_text_length: int = MAX_TEXT_LENGTH,
) -> List[Segment]:
    segs: List[Segment] = []
    seen_par_keys = set()
    total_text_length = 0

    def _add_paragraph(p: Paragraph, ctx: str) -> None:
        nonlocal total_text_length
        try:
            p_key = _get_paragraph_key(p)
            if p_key in seen_par_keys:
                return
            txt = _p_text_with_breaks(p)
            if txt.strip() and not _is_our_insert_block(p):
                segs.append(Segment("para", p, ctx, txt))
                seen_par_keys.add(p_key)
                total_text_length += len(txt)
        except Exception as exc:
            logger.warning("Paragraph processing error: %s", exc)

    def _process_container_content(container, ctx: str) -> None:
        if container._element is None:
            return
        for child_element in container._element:
            qname = child_element.tag
            if qname.endswith("}p"):
                p = Paragraph(child_element, container)
                _add_paragraph(p, ctx)
            elif qname.endswith("}tbl"):
                table = Table(child_element, container)
                for r_idx, row in enumerate(table.rows, 1):
                    for c_idx, cell in enumerate(row.cells, 1):
                        cell_ctx = f"{ctx} > Tbl(r{r_idx},c{c_idx})"
                        _process_container_content(cell, cell_ctx)
            elif qname.endswith("}sdt"):
                sdt_ctx = f"{ctx} > SDT"
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                placeholder_texts = []
                for t in child_element.xpath(".//w:placeholder//w:t", namespaces=ns):
                    if t.text:
                        placeholder_texts.append(t.text)
                if placeholder_texts:
                    full_placeholder = "".join(placeholder_texts).strip()
                    if full_placeholder:
                        segs.append(Segment("para", child_element, f"{sdt_ctx}-Placeholder", full_placeholder))
                list_items = []
                for item in child_element.xpath(".//w:dropDownList/w:listItem", namespaces=ns):
                    display_text = item.get(qn("w:displayText"))
                    if display_text:
                        list_items.append(display_text)
                if list_items:
                    items_as_text = "\n".join(list_items)
                    segs.append(Segment("para", child_element, f"{sdt_ctx}-Dropdown", items_as_text))
                sdt_content_element = child_element.find(qn("w:sdtContent"))
                if sdt_content_element is not None:
                    class SdtContentWrapper:
                        def __init__(self, element, parent):
                            self._element = element
                            self._parent = parent
                    sdt_content_wrapper = SdtContentWrapper(sdt_content_element, container)
                    _process_container_content(sdt_content_wrapper, sdt_ctx)

    _process_container_content(doc._body, "Body")

    for tx, s in _txbx_iter_texts(doc):
        if s.strip() and (has_cjk(s) or should_translate(s, "auto")):
            segs.append(Segment("txbx", tx, "TextBox", s))
            total_text_length += len(s)

    check_document_size_limits(
        segment_count=len(segs),
        total_text_length=total_text_length,
        max_segments=max_segments,
        max_text_length=max_text_length,
        document_type="Word document",
    )

    return segs


def _insert_docx_translations(
    doc: Any,
    segs: List[Segment],
    tmap: Dict[Tuple[str, str], str],
    targets: List[str],
    log: Callable[[str], None] = lambda s: None,
) -> Tuple[int, int]:
    ok_cnt = skip_cnt = 0

    def _add_formatted_run(p: Paragraph, text: str, italic: bool, font_size_pt: int) -> None:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            run = p.add_run(line)
            if italic:
                run.italic = True
            if font_size_pt:
                run.font.size = Pt(font_size_pt)
            if i < len(lines) - 1:
                run.add_break()
        tag_run = p.add_run(INSERT_MARKER)
        if italic:
            tag_run.italic = True
        if font_size_pt:
            tag_run.font.size = Pt(font_size_pt)

    for seg in segs:
        has_any_translation = any((tgt, seg.text) in tmap for tgt in targets)
        if not has_any_translation:
            log(f"[SKIP] No translation: {seg.ctx} | {seg.text[:50]}...")
            continue

        translations = []
        for tgt in targets:
            if (tgt, seg.text) in tmap:
                translations.append(tmap[(tgt, seg.text)])
            else:
                log(f"[WARN] Missing {tgt} translation: {seg.text[:30]}...")
                translations.append(f"[Translation missing|{tgt}] {seg.text[:50]}...")

        if seg.kind == "para":
            if hasattr(seg.ref, "tag") and seg.ref.tag.endswith("}sdt"):
                sdt_element = seg.ref
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                sdt_content = sdt_element.find(qn("w:sdtContent"))
                if sdt_content is not None:
                    existing_paras = sdt_content.xpath(".//w:p", namespaces=ns)
                    existing_texts = []
                    for ep in existing_paras:
                        p_obj = Paragraph(ep, None)
                        if _is_our_insert_block(p_obj):
                            existing_texts.append(_p_text_with_breaks(p_obj))
                    if len(existing_texts) >= len(translations):
                        if all(normalize_text(e) == normalize_text(t) for e, t in zip(existing_texts[:len(translations)], translations)):
                            skip_cnt += 1
                            log(f"[SKIP] SDT translation exists: {seg.text[:30]}...")
                            continue
                    for t in translations:
                        if not any(normalize_text(t) == normalize_text(e) for e in existing_texts):
                            new_p_element = OxmlElement("w:p")
                            sdt_content.append(new_p_element)
                            new_p = Paragraph(new_p_element, None)
                            _add_formatted_run(new_p, t, italic=True, font_size_pt=INSERT_FONT_SIZE_PT)
                    ok_cnt += 1
                    continue
            p: Paragraph = seg.ref
            if isinstance(p._parent, _Cell):
                cell = p._parent
                try:
                    cell_paragraphs = list(cell.paragraphs)
                    p_index = -1
                    for idx, cell_p in enumerate(cell_paragraphs):
                        if cell_p._element == p._element:
                            p_index = idx
                            break
                    if p_index == -1:
                        log("[WARN] Paragraph not found in cell; fallback insertion")
                        for block in translations:
                            new_p = cell.add_paragraph()
                            _add_formatted_run(new_p, block, italic=True, font_size_pt=INSERT_FONT_SIZE_PT)
                        ok_cnt += 1
                        continue
                    existing_texts = []
                    check_limit = min(p_index + 1 + len(translations), len(cell_paragraphs))
                    for idx in range(p_index + 1, check_limit):
                        if _is_our_insert_block(cell_paragraphs[idx]):
                            existing_texts.append(_p_text_with_breaks(cell_paragraphs[idx]))
                    if len(existing_texts) >= len(translations):
                        if all(normalize_text(e) == normalize_text(t) for e, t in zip(existing_texts[:len(translations)], translations)):
                            skip_cnt += 1
                            log(f"[SKIP] Cell already has translations: {seg.text[:30]}...")
                            continue
                    to_add = []
                    for t in translations:
                        if not any(normalize_text(t) == normalize_text(e) for e in existing_texts):
                            to_add.append(t)
                    if not to_add:
                        skip_cnt += 1
                        log(f"[SKIP] Cell translations already present: {seg.text[:30]}...")
                        continue
                    insert_after = p
                    for block in to_add:
                        try:
                            new_p_element = OxmlElement("w:p")
                            insert_after._element.addnext(new_p_element)
                            new_p = Paragraph(new_p_element, cell)
                            _add_formatted_run(new_p, block, italic=True, font_size_pt=INSERT_FONT_SIZE_PT)
                            insert_after = new_p
                        except Exception as exc:
                            log(f"[ERROR] Cell insertion failed: {exc}")
                            try:
                                new_p = cell.add_paragraph()
                                _add_formatted_run(new_p, block, italic=True, font_size_pt=INSERT_FONT_SIZE_PT)
                            except Exception as exc2:
                                log(f"[ERROR] Fallback insertion failed: {exc2}")
                                continue
                    ok_cnt += 1
                except Exception as exc:
                    log(f"[ERROR] Cell processing failed: {exc}")
                    continue
            else:
                try:
                    existing_texts = _scan_our_tail_texts(p, limit=max(len(translations), 4))
                    if existing_texts and len(existing_texts) >= len(translations):
                        if all(normalize_text(e) == normalize_text(t) for e, t in zip(existing_texts[:len(translations)], translations)):
                            skip_cnt += 1
                            log(f"[SKIP] Paragraph already has translations: {seg.text[:30]}...")
                            continue
                    to_add = []
                    for t in translations:
                        if not any(normalize_text(t) == normalize_text(e) for e in existing_texts):
                            to_add.append(t)
                    if not to_add:
                        skip_cnt += 1
                        log(f"[SKIP] Paragraph translations already present: {seg.text[:30]}...")
                        continue
                    last = _find_last_inserted_after(p, limit=max(len(translations), 4))
                    anchor = last if last else p
                    for block in to_add:
                        try:
                            anchor = _append_after(anchor, block, italic=True, font_size_pt=INSERT_FONT_SIZE_PT)
                        except Exception as exc:
                            log(f"[ERROR] Paragraph insertion failed: {exc}")
                            try:
                                new_p = p._parent.add_paragraph(block)
                                if new_p.runs:
                                    new_p.runs[0].italic = True
                            except Exception as exc2:
                                log(f"[ERROR] Fallback insertion failed: {exc2}")
                                continue
                    ok_cnt += 1
                except Exception as exc:
                    log(f"[ERROR] Paragraph processing failed: {exc}")
                    continue
        elif seg.kind == "txbx":
            tx = seg.ref
            if _txbx_tail_equals(tx, translations):
                skip_cnt += 1
                continue
            paras = tx.xpath("./*[local-name()='p']")
            tail_texts = []
            scan = paras[-max(len(translations), 4):] if len(paras) else []
            for q in scan:
                has_zero = any(((t.text or "").find(INSERT_MARKER) >= 0) for t in q.xpath(".//*[local-name()='t']"))
                if has_zero:
                    qtxt = "".join([(node.text or "") for node in q.xpath(".//*[local-name()='t' or local-name()='br']")]).strip()
                    tail_texts.append(qtxt)
            to_add = []
            for t in translations:
                if not any(normalize_text(t) == normalize_text(e) for e in tail_texts):
                    to_add.append(t)
            if not to_add:
                skip_cnt += 1
                continue
            for block in to_add:
                _txbx_append_paragraph(tx, block, italic=True, font_size_pt=INSERT_FONT_SIZE_PT)
            ok_cnt += 1
    log(f"[DOCX] Inserted: {ok_cnt} segments, skipped: {skip_cnt}")
    return ok_cnt, skip_cnt


def translate_docx(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    include_headers_shapes_via_com: bool,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
) -> bool:
    from shutil import copyfile

    copyfile(in_path, out_path)
    doc = docx.Document(out_path)

    ok, msg = client.health_check()
    log(f"[API] {msg}")
    if not ok:
        raise ApiError("Ollama service unavailable")

    segs = _collect_docx_segments(doc)
    log(f"[DOCX] segments: {len(segs)}")

    uniq_texts = [t for t in sorted(set(s.text for s in segs)) if should_translate(t, (src_lang or "auto"))]
    tmap, _, fail_cnt, stopped = translate_texts(
        uniq_texts,
        targets,
        src_lang,
        cache,
        client,
        max_batch_chars=max_batch_chars,
        stop_flag=stop_flag,
        log=log,
    )

    if fail_cnt:
        log(f"[DOCX] failed translations: {fail_cnt}")

    if tmap:
        _insert_docx_translations(doc, segs, tmap, targets, log=log)

    doc.save(out_path)
    if stopped:
        log(f"[DOCX] partial output: {os.path.basename(out_path)}")
    else:
        log(f"[DOCX] output: {os.path.basename(out_path)}")

    if not stopped and include_headers_shapes_via_com and is_win32com_available():
        postprocess_docx_shapes_with_word(out_path, targets, src_lang, cache, client, include_headers=True, log=log)

    return stopped
