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
    """Represents a segment of text to be translated in a document.

    For table cells (kind="cell"):
        col       — 0-based column index (used as tmap dedup key; BR-81)
        row       — 0-based row index (used for serializer grid building)
        table_id  — id() of the table XML element (used for per-table grouping; AC-1)

    For non-table segments (kind="para", "txbx"):
        col, row, table_id are all None (tmap key uses col=None; BR-81).
    """

    def __init__(
        self,
        kind: str,
        ref: Any,
        ctx: str,
        text: str,
        col: Optional[int] = None,
        row: Optional[int] = None,
        table_id: Optional[int] = None,
    ) -> None:
        self.kind = kind
        self.ref = ref
        self.ctx = ctx
        self.text = text
        self.col = col
        self.row = row
        self.table_id = table_id


def _get_paragraph_key(p: Paragraph) -> int:
    """Return a key that uniquely identifies a paragraph XML element.

    Uses ``id()`` so that *different* elements with identical content are
    treated as separate segments (fixes missing translations in repeated
    table columns), while the *same* element visited twice (e.g. merged
    cells in a table) is still de-duplicated.
    """
    return id(p._p)


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
        nonlocal total_text_length  # needed to update length for table cell segments
        if container._element is None:
            return
        for child_element in container._element:
            qname = child_element.tag
            if qname.endswith("}p"):
                p = Paragraph(child_element, container)
                _add_paragraph(p, ctx)
            elif qname.endswith("}tbl"):
                # IP-4: materialize table cells as "cell" segments (one per cell)
                # rather than recursing into per-paragraph segments.
                # Each cell carries (row, col, table_id) for per-table grouping
                # and (tgt, text, col) dedup key (BR-81).
                table = Table(child_element, container)
                tid = id(child_element)
                for r_idx, row in enumerate(table.rows):  # 0-based
                    for c_idx, cell in enumerate(row.cells):  # 0-based
                        cell_ctx = f"{ctx} > Tbl(r{r_idx},c{c_idx})"
                        # Aggregate all paragraph text in this cell
                        cell_text_parts = []
                        for p in cell.paragraphs:
                            try:
                                txt = _p_text_with_breaks(p)
                                if txt.strip() and not _is_our_insert_block(p):
                                    cell_text_parts.append(txt)
                            except Exception:
                                pass
                        cell_text = "\n".join(cell_text_parts)
                        # Collect cell even if empty (positional placeholder for serializer)
                        segs.append(Segment(
                            "cell", cell, cell_ctx, cell_text,
                            col=c_idx, row=r_idx, table_id=tid,
                        ))
                        total_text_length += len(cell_text)
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
    tmap: Dict[Tuple, str],
    targets: List[str],
    log: Callable[[str], None] = lambda s: None,
    output_mode: str = "append",
) -> Tuple[int, int]:
    """Insert translations from *tmap* into the document segments.

    tmap key schema (IP-4 / BR-81):
        - table cell segments: (tgt, src_text, col)   — col is 0-based column index
        - non-table segments:  (tgt, src_text, None)  — col=None for paragraphs/textboxes
    """
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
        # IP-4 (BR-81): tmap key uses (tgt, text, col) for table cells (col=int)
        # and (tgt, text, None) for non-table segments (para/txbx).
        _seg_key = (seg.text, seg.col)  # col is None for non-table segs
        has_any_translation = any((tgt, seg.text, seg.col) in tmap for tgt in targets)
        if not has_any_translation:
            log(f"[SKIP] No translation: {seg.ctx} | {seg.text[:50]}...")
            continue

        translations = []
        for tgt in targets:
            if (tgt, seg.text, seg.col) in tmap:
                translations.append(tmap[(tgt, seg.text, seg.col)])
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
                    if output_mode == "replace":
                        # Overwrite run text in-place; only the first translation is used
                        # (multi-target is clamped to append by the orchestrator, BR-67).
                        replacement = translations[0]
                        runs = p.runs
                        if runs:
                            runs[0].text = replacement
                            for r in runs[1:]:
                                r.text = ""
                        else:
                            p.add_run(replacement)
                        ok_cnt += 1
                    else:
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
        elif seg.kind == "cell":
            # IP-4: whole-cell translation from the serializer path.
            # seg.ref is the _Cell object; translations are keyed by (tgt, text, col).
            cell = seg.ref
            try:
                # Check if translation already inserted (has INSERT_MARKER paragraph)
                if any(_is_our_insert_block(p) for p in cell.paragraphs):
                    skip_cnt += 1
                    log(f"[SKIP] Cell already has translations: {seg.text[:30]}...")
                    continue
                if output_mode == "replace":
                    # Replace first paragraph text in-place with the first translation
                    replacement = translations[0]
                    paras = list(cell.paragraphs)
                    if paras and paras[0].runs:
                        paras[0].runs[0].text = replacement
                        for run in paras[0].runs[1:]:
                            run.text = ""
                    elif paras:
                        paras[0].text = replacement
                    else:
                        new_p = cell.add_paragraph()
                        new_p.add_run(replacement)
                else:
                    # Append each translation as a new italic paragraph in the cell
                    for block in translations:
                        new_p = cell.add_paragraph()
                        _add_formatted_run(new_p, block, italic=True, font_size_pt=INSERT_FONT_SIZE_PT)
                ok_cnt += 1
            except Exception as exc:
                log(f"[ERROR] Cell translation insert failed: {exc}")
                continue
    log(f"[DOCX] Inserted: {ok_cnt} segments, skipped: {skip_cnt}")
    return ok_cnt, skip_cnt


def _translate_docx_via_doc2doc(
    texts: List[str],
    target: str,
    src_lang: Optional[str],
    client,
    stop_flag=None,
    log: Callable[[str], None] = lambda s: None,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
    terms=None,
    in_path: str = "",
    status_callback: Optional[Callable[[Optional[str]], None]] = None,
) -> Tuple[Dict[Tuple[str, str], str], int, int, bool]:
    """Use semantic chunking (translate_document) for long single-target DOCX docs."""
    from app.backend.models.translatable_document import (
        TranslatableDocument,
        TranslatableElement,
        ElementType,
        PageInfo,
        DocumentMetadata,
    )
    from app.backend.services.translation_service import translate_document

    elements = [
        TranslatableElement(
            element_id=f"seg-{i}",
            content=t,
            element_type=ElementType.TEXT,
            page_num=1,
        )
        for i, t in enumerate(texts)
    ]
    doc_ir = TranslatableDocument(
        source_path=in_path,
        source_type="docx",
        elements=elements,
        pages=[PageInfo(page_num=1, width=595.0, height=842.0)],
        metadata=DocumentMetadata(),
    )

    try:
        translate_document(
            doc_ir, [target], src_lang, client,
            stop_flag=stop_flag, log=log,
            terms=terms, max_batch_chars=max_batch_chars,
        )
    except RuntimeError as exc:
        log(f"[DOCX] Doc2Doc chunking failed, falling back to batch: {exc}")
        return translate_texts(
            texts, [target], src_lang, client,
            max_batch_chars=max_batch_chars, stop_flag=stop_flag, log=log, terms=terms,
            status_callback=status_callback,
        )

    tmap: Dict[Tuple[str, str], str] = {}
    fail_cnt = 0
    for elem in doc_ir.elements:
        key = (target, elem.content)
        val = elem.translated_content
        if val and not val.startswith("[Translation failed"):
            tmap[key] = val
        else:
            tmap[key] = val or f"[Translation failed|{elem.content[:20]}]"
            fail_cnt += 1
    return tmap, len(texts) - fail_cnt, fail_cnt, False


def translate_docx(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    client: OllamaClient,
    include_headers_shapes_via_com: bool,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
    pre_translate_hook: Optional[Callable[[List[str]], None]] = None,
    post_translate_hook: Optional[Callable[[List[Tuple[str, str, str]]], None]] = None,
    terms_getter: Optional[Callable[[], list]] = None,
    output_mode: str = "append",
    block_overrides: Optional[Dict[str, str]] = None,
    status_callback: Optional[Callable[[Optional[str]], None]] = None,
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

    # IP-4: separate non-table segments (para/txbx) from table cell segments.
    # Table cells are translated per-table via the shared serializer (one LLM call
    # per table); non-table segments use the existing translate_texts path.
    para_segs = [s for s in segs if s.table_id is None]
    cell_segs = [s for s in segs if s.table_id is not None]

    # Deduplicate non-table segment texts for translation batch
    seen_texts: set[str] = set()
    uniq_texts: list[str] = []  # kept for post_translate_hook indexing
    for s in para_segs:
        if s.text not in seen_texts and should_translate(s.text, (src_lang or "auto")):
            seen_texts.add(s.text)
            uniq_texts.append(s.text)
    if pre_translate_hook:
        pre_translate_hook(uniq_texts)
    _terms = terms_getter() if terms_getter else None

    # p3-llm-judge: block_overrides seam — when provided, use stored re-translated text
    # instead of calling the LLM (D7). Block ids use the same key as post_translate_hook.
    import os as _os
    file_stem = _os.path.splitext(_os.path.basename(in_path))[0]
    stopped = False

    # para_tmap uses 2-element keys (tgt, text) — standard translate_texts output.
    # final_tmap uses 3-element keys (tgt, text, col) for the restore pass (BR-81).
    para_tmap: Dict = {}
    fail_cnt = 0

    if block_overrides is not None:
        # Build para_tmap from overrides map; applies to non-table segments only.
        for idx, src_text in enumerate(uniq_texts):
            block_id = f"docx:{file_stem}:{idx}"
            if block_id in block_overrides:
                for tgt in targets:
                    para_tmap[(tgt, src_text)] = block_overrides[block_id]
            else:
                for tgt in targets:
                    para_tmap[(tgt, src_text)] = src_text
        log(f"[DOCX] block_overrides applied: {len(block_overrides)} overrides, {len(uniq_texts)} blocks")
    else:
        # Long-document semantic chunking path (P2-6): use translate_document for
        # single-target docs over the char threshold so doc_chunker actually runs.
        _LONG_DOC_CHARS = 40_000
        _total_chars = sum(len(t) for t in uniq_texts)
        if len(targets) == 1 and _total_chars > _LONG_DOC_CHARS:
            para_tmap, _, fail_cnt, stopped = _translate_docx_via_doc2doc(
                uniq_texts, targets[0], src_lang, client,
                stop_flag=stop_flag, log=log,
                max_batch_chars=max_batch_chars, terms=_terms,
                in_path=in_path, status_callback=status_callback,
            )
        else:
            para_tmap, _, fail_cnt, stopped = translate_texts(
                uniq_texts,
                targets,
                src_lang,
                client,
                max_batch_chars=max_batch_chars,
                stop_flag=stop_flag,
                log=log,
                terms=_terms,
                status_callback=status_callback,
            )

        if fail_cnt:
            log(f"[DOCX] failed translations: {fail_cnt}")

        if fail_cnt and not stopped:
            from app.backend.utils.translation_verification import verify_and_fill_tmap
            verify_and_fill_tmap(para_tmap, client, src_lang, stop_flag=stop_flag, log=log)

    # Build 3-element final_tmap from para_tmap (re-key col=None) and table cell tmap.
    final_tmap: Dict = {}
    for (tgt, text), tr in para_tmap.items():
        final_tmap[(tgt, text, None)] = tr

    # IP-4: translate each table group via serializer → one translate_once call per table.
    if cell_segs and not stopped:
        from collections import defaultdict
        from app.backend.utils import table_serializer

        # Group cell segments by table_id
        table_groups: Dict = defaultdict(list)
        for s in cell_segs:
            table_groups[s.table_id].append(s)

        # Duck-typed proxy for table_serializer.serialize() (needs .row/.col/.content/.is_numeric)
        from dataclasses import dataclass as _dc

        @_dc
        class _CellProxy:
            row: int
            col: int
            content: str
            is_numeric: bool = False

        for table_id, t_segs in table_groups.items():
            if stop_flag and stop_flag.is_set():
                stopped = True
                break
            # Determine grid dimensions from segments
            num_rows = max(s.row for s in t_segs) + 1
            num_cols = max(s.col for s in t_segs) + 1
            # Build cells compatible with table_serializer

            # Include ALL grid positions (including empty cells as positional placeholders)
            cells_by_pos: Dict = {(s.row, s.col): s.text for s in t_segs}
            proxy_cells = [
                _CellProxy(row=r, col=c, content=cells_by_pos.get((r, c), ""))
                for r in range(num_rows) for c in range(num_cols)
            ]

            for tgt in targets:
                if stop_flag and stop_flag.is_set():
                    stopped = True
                    break
                src_for_prompt = src_lang or "auto"
                serialized = table_serializer.serialize(proxy_cells)
                prompt = client._build_table_translate_prompt(serialized, src_for_prompt, tgt)
                # grid stays None on any error → fallback always runs (BR-82)
                grid = None
                try:
                    ok, response = client.translate_once(prompt, tgt, src_lang)
                    if ok:
                        grid = table_serializer.parse(response, num_rows, num_cols)
                        if grid is None:
                            logger.warning(
                                "[DOCX] Table group %s: parse() returned None (expected %d×%d); "
                                "falling back to per-cell batch for target=%s",
                                table_id, num_rows, num_cols, tgt,
                            )
                except Exception as exc:
                    logger.warning(
                        "[DOCX] Table group %s translate_once failed (target=%s): %s; "
                        "falling back to per-cell batch",
                        table_id, tgt, exc,
                    )
                if grid is not None:
                    for s in t_segs:
                        r, c = s.row, s.col
                        if s.text.strip() and 0 <= r < num_rows and 0 <= c < num_cols:
                            final_tmap[(tgt, s.text, c)] = grid[r][c]
                else:
                    # Fallback: translate each unique cell text individually (BR-82)
                    uniq_cell_texts = list(dict.fromkeys(
                        s.text for s in t_segs if s.text.strip()
                        and should_translate(s.text, src_for_prompt)
                    ))
                    if uniq_cell_texts:
                        fallback_tmap, _, _, _ = translate_texts(
                            uniq_cell_texts, [tgt], src_lang, client,
                            max_batch_chars=max_batch_chars,
                            stop_flag=stop_flag, log=log,
                        )
                        for (fb_tgt, fb_text), fb_tr in fallback_tmap.items():
                            # Apply to ALL cells with this text across their actual columns
                            for s in t_segs:
                                if s.text == fb_text:
                                    final_tmap[(fb_tgt, fb_text, s.col)] = fb_tr

    if final_tmap:
        # R1: doc2doc long-doc path always uses append; output_mode="replace" is a follow-up.
        effective_mode = "append" if (len(targets) == 1 and sum(len(t) for t in uniq_texts) > 40_000) else output_mode
        _insert_docx_translations(doc, segs, final_tmap, targets, log=log, output_mode=effective_mode)

    if post_translate_hook is not None:
        tuples: List[Tuple[str, str, str]] = []
        for idx, src_text in enumerate(uniq_texts):
            for tgt in targets:
                if (tgt, src_text) in para_tmap:  # use para_tmap (2-element) for hook
                    tuples.append((f"docx:{file_stem}:{idx}", src_text, para_tmap[(tgt, src_text)]))
        if tuples:
            post_translate_hook(tuples)

    doc.save(out_path)
    if stopped:
        log(f"[DOCX] partial output: {os.path.basename(out_path)}")
    else:
        log(f"[DOCX] output: {os.path.basename(out_path)}")

    if not stopped and include_headers_shapes_via_com and is_win32com_available():
        postprocess_docx_shapes_with_word(out_path, targets, src_lang, client, include_headers=True, log=log)

    return stopped
