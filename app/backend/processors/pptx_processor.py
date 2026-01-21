"""PPTX translation processor."""

from __future__ import annotations

import os
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

import pptx
from pptx.util import Pt as PPTPt

from app.backend.cache.translation_cache import TranslationCache
from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import DEFAULT_MAX_BATCH_CHARS, MAX_SEGMENTS, MAX_TEXT_LENGTH
from app.backend.services.translation_service import translate_texts
from app.backend.utils.exceptions import check_document_size_limits
from app.backend.utils.text_utils import normalize_text, should_translate


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


def translate_pptx(
    in_path: str,
    out_path: str,
    targets: List[str],
    src_lang: Optional[str],
    cache: TranslationCache,
    client: OllamaClient,
    stop_flag: Optional[threading.Event] = None,
    log: Callable[[str], None] = lambda s: None,
    max_segments: int = MAX_SEGMENTS,
    max_text_length: int = MAX_TEXT_LENGTH,
    max_batch_chars: int = DEFAULT_MAX_BATCH_CHARS,
) -> bool:
    prs = pptx.Presentation(in_path)
    segs: List[Tuple[Any, str]] = []
    total_text_length = 0
    for slide in prs.slides:
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False):
                continue
            tf = shape.text_frame
            txt = _ppt_text_of_tf(tf)
            if txt.strip():
                segs.append((tf, txt))
                total_text_length += len(txt)

    check_document_size_limits(
        segment_count=len(segs),
        total_text_length=total_text_length,
        max_segments=max_segments,
        max_text_length=max_text_length,
        document_type="PowerPoint document",
    )

    log(f"[PPTX] segments: {len(segs)}")
    uniq = [s for s in sorted(set(s for _, s in segs)) if should_translate(s, (src_lang or "auto"))]
    tmap, _, _, stopped = translate_texts(
        uniq,
        targets,
        src_lang,
        cache,
        client,
        max_batch_chars=max_batch_chars,
        stop_flag=stop_flag,
        log=log,
    )

    ok_cnt = skip_cnt = 0
    for tf, s in segs:
        if not all((tgt, s) in tmap for tgt in targets):
            continue
        trs = [tmap[(tgt, s)] for tgt in targets]
        if _ppt_tail_equals(tf, trs):
            skip_cnt += 1
            continue
        for block in trs:
            _ppt_append(tf, block)
        ok_cnt += 1

    prs.save(out_path)

    if stopped:
        log(f"[PPTX] partial output: {os.path.basename(out_path)}")
    else:
        log(f"[PPTX] output: {os.path.basename(out_path)}")

    return stopped
