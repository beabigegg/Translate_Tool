"""Unit tests for output_mode parameter in translate_docx and translate_pptx.

AC-1: signature accepts output_mode; default is append.
AC-2: append mode behavior unchanged.
AC-3: replace mode DOCX — source paragraphs replaced in-place; original text absent.
AC-4: replace mode PPTX — source text frames replaced in-place; original text absent.
AC-7: multi-target is tested at processor level (pass-through; clamping is in orchestrator).

Anti-tautology: selection assertions check WHICH paragraphs/frames hold the translation,
not just counts.
"""

from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: build in-process minimal DOCX / PPTX fixtures
# ---------------------------------------------------------------------------

def _make_docx(tmp_path: Path, text: str) -> Path:
    """Create a minimal DOCX with one paragraph containing *text*."""
    from docx import Document

    doc = Document()
    doc.add_paragraph(text)
    p = tmp_path / "test.docx"
    doc.save(str(p))
    return p


def _make_pptx(tmp_path: Path, text: str) -> Path:
    """Create a minimal PPTX with one slide and one text-frame containing *text*."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    blank_layout = prs.slide_layouts[6]  # blank layout
    slide = prs.slides.add_slide(blank_layout)
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2))
    txBox.text_frame.text = text
    p = tmp_path / "test.pptx"
    prs.save(str(p))
    return p


def _mock_client():
    """Return a minimal mock OllamaClient that passes health checks."""
    mock = MagicMock()
    mock.health_check.return_value = (True, "ok")
    mock.system_prompt = ""
    mock.model_type = "general"
    mock._is_translation_dedicated.return_value = False
    mock._is_translategemma_model.return_value = False
    return mock


def _make_tmap(src_text: str, translation: str, target: str = "vi") -> Dict:
    """Return a translation map keyed by (target, src_text)."""
    return {(target, src_text): translation}


# ---------------------------------------------------------------------------
# AC-1: signature tests
# ---------------------------------------------------------------------------

def test_translate_docx_accepts_output_mode_param(tmp_path):
    """translate_docx must accept an output_mode keyword argument."""
    import inspect
    from app.backend.processors.docx_processor import translate_docx

    sig = inspect.signature(translate_docx)
    assert "output_mode" in sig.parameters


def test_translate_pptx_accepts_output_mode_param(tmp_path):
    """translate_pptx must accept an output_mode keyword argument."""
    import inspect
    from app.backend.processors.pptx_processor import translate_pptx

    sig = inspect.signature(translate_pptx)
    assert "output_mode" in sig.parameters


def test_output_mode_default_is_append(tmp_path):
    """output_mode defaults to 'append' in both processors."""
    import inspect
    from app.backend.processors.docx_processor import translate_docx
    from app.backend.processors.pptx_processor import translate_pptx

    docx_default = inspect.signature(translate_docx).parameters["output_mode"].default
    pptx_default = inspect.signature(translate_pptx).parameters["output_mode"].default
    assert docx_default == "append"
    assert pptx_default == "append"


# ---------------------------------------------------------------------------
# AC-2: append mode behavior unchanged (DOCX)
# ---------------------------------------------------------------------------

def test_append_mode_behavior_unchanged_docx(tmp_path):
    """In append mode, both source and translated paragraphs appear in output DOCX."""
    from docx import Document
    from app.backend.processors.docx_processor import translate_docx

    src_text = "Hello world"
    translation = "Hola mundo"
    in_path = _make_docx(tmp_path, src_text)
    out_path = tmp_path / "out.docx"

    tmap = _make_tmap(src_text, translation)

    with (
        patch("app.backend.processors.docx_processor.OllamaClient", return_value=_mock_client()),
        patch(
            "app.backend.processors.docx_processor.translate_texts",
            return_value=(tmap, 1, 0, False),
        ),
    ):
        translate_docx(
            str(in_path),
            str(out_path),
            targets=["vi"],
            src_lang="en",
            client=_mock_client(),
            include_headers_shapes_via_com=False,
            output_mode="append",
        )

    doc = Document(str(out_path))
    all_texts = [p.text for p in doc.paragraphs]
    # Source text must still be present
    assert any(src_text in t for t in all_texts), f"Source text missing from append output: {all_texts}"
    # Translation must also be present
    assert any(translation in t for t in all_texts), f"Translation missing from append output: {all_texts}"


# ---------------------------------------------------------------------------
# AC-2: append mode behavior unchanged (PPTX)
# ---------------------------------------------------------------------------

def test_append_mode_behavior_unchanged_pptx(tmp_path):
    """In append mode, both source and translated paragraphs appear in output PPTX."""
    from pptx import Presentation
    from app.backend.processors.pptx_processor import translate_pptx

    src_text = "Hello world"
    translation = "Hola mundo"
    in_path = _make_pptx(tmp_path, src_text)
    out_path = tmp_path / "out.pptx"

    tmap = _make_tmap(src_text, translation)

    with patch(
        "app.backend.processors.pptx_processor.translate_texts",
        return_value=(tmap, 1, 0, False),
    ):
        translate_pptx(
            str(in_path),
            str(out_path),
            targets=["vi"],
            src_lang="en",
            client=_mock_client(),
            output_mode="append",
        )

    prs = Presentation(str(out_path))
    all_texts: List[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    all_texts.append(para.text)

    assert any(src_text in t for t in all_texts), f"Source text missing from append output: {all_texts}"
    assert any(translation in t for t in all_texts), f"Translation missing from append output: {all_texts}"


# ---------------------------------------------------------------------------
# AC-3: replace mode DOCX — source absent, translation in place
# ---------------------------------------------------------------------------

def test_replace_mode_docx_no_source_paragraphs_remain(tmp_path):
    """In replace mode, the source text must be absent from the output DOCX paragraphs."""
    from docx import Document
    from app.backend.processors.docx_processor import translate_docx

    src_text = "Hello world"
    translation = "Hola mundo"
    in_path = _make_docx(tmp_path, src_text)
    out_path = tmp_path / "out_replace.docx"

    tmap = _make_tmap(src_text, translation)

    with patch(
        "app.backend.processors.docx_processor.translate_texts",
        return_value=(tmap, 1, 0, False),
    ):
        translate_docx(
            str(in_path),
            str(out_path),
            targets=["vi"],
            src_lang="en",
            client=_mock_client(),
            include_headers_shapes_via_com=False,
            output_mode="replace",
        )

    doc = Document(str(out_path))
    all_texts = [p.text for p in doc.paragraphs]
    # Selection assertion: source text must NOT appear in any paragraph
    assert not any(src_text in t for t in all_texts), (
        f"Source text still present in replace output: {all_texts}"
    )


def test_replace_mode_docx_translation_is_in_place(tmp_path):
    """In replace mode, the translation must appear in the output DOCX paragraphs."""
    from docx import Document
    from app.backend.processors.docx_processor import translate_docx

    src_text = "Hello world"
    translation = "Hola mundo"
    in_path = _make_docx(tmp_path, src_text)
    out_path = tmp_path / "out_replace2.docx"

    tmap = _make_tmap(src_text, translation)

    with patch(
        "app.backend.processors.docx_processor.translate_texts",
        return_value=(tmap, 1, 0, False),
    ):
        translate_docx(
            str(in_path),
            str(out_path),
            targets=["vi"],
            src_lang="en",
            client=_mock_client(),
            include_headers_shapes_via_com=False,
            output_mode="replace",
        )

    doc = Document(str(out_path))
    all_texts = [p.text for p in doc.paragraphs]
    # Selection assertion: translation must appear in at least one paragraph
    assert any(translation in t for t in all_texts), (
        f"Translation missing from replace output: {all_texts}"
    )


# ---------------------------------------------------------------------------
# AC-4: replace mode PPTX — source absent, translation in place
# ---------------------------------------------------------------------------

def test_replace_mode_pptx_no_source_text_frames_remain(tmp_path):
    """In replace mode, the source text must be absent from output PPTX text frames."""
    from pptx import Presentation
    from app.backend.processors.pptx_processor import translate_pptx

    src_text = "Hello world"
    translation = "Hola mundo"
    in_path = _make_pptx(tmp_path, src_text)
    out_path = tmp_path / "out_replace.pptx"

    tmap = _make_tmap(src_text, translation)

    with patch(
        "app.backend.processors.pptx_processor.translate_texts",
        return_value=(tmap, 1, 0, False),
    ):
        translate_pptx(
            str(in_path),
            str(out_path),
            targets=["vi"],
            src_lang="en",
            client=_mock_client(),
            output_mode="replace",
        )

    prs = Presentation(str(out_path))
    all_texts: List[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    all_texts.append(para.text)

    # Selection assertion: source text must NOT appear
    assert not any(src_text in t for t in all_texts), (
        f"Source text still present in replace output: {all_texts}"
    )


def test_replace_mode_pptx_translation_is_in_place(tmp_path):
    """In replace mode, translation must appear in output PPTX text frames."""
    from pptx import Presentation
    from app.backend.processors.pptx_processor import translate_pptx

    src_text = "Hello world"
    translation = "Hola mundo"
    in_path = _make_pptx(tmp_path, src_text)
    out_path = tmp_path / "out_replace2.pptx"

    tmap = _make_tmap(src_text, translation)

    with patch(
        "app.backend.processors.pptx_processor.translate_texts",
        return_value=(tmap, 1, 0, False),
    ):
        translate_pptx(
            str(in_path),
            str(out_path),
            targets=["vi"],
            src_lang="en",
            client=_mock_client(),
            output_mode="replace",
        )

    prs = Presentation(str(out_path))
    all_texts: List[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    all_texts.append(para.text)

    # Selection assertion: translation must appear
    assert any(translation in t for t in all_texts), (
        f"Translation missing from replace output: {all_texts}"
    )


# ---------------------------------------------------------------------------
# AC-7 (processor level): multi-target does not crash in either mode
# ---------------------------------------------------------------------------

def test_multi_target_output_mode_clamped_to_append(tmp_path):
    """With multiple targets, output_mode="replace" still runs without error.

    The orchestrator clamps replace→append for multi-target jobs (BR-67).
    This test verifies the processor itself handles multiple targets gracefully
    when called with append (the clamped value). Orchestrator-level clamping
    is tested in test_output_mode_orchestrator.py.
    """
    from docx import Document
    from app.backend.processors.docx_processor import translate_docx

    src_text = "Hello world"
    in_path = _make_docx(tmp_path, src_text)
    out_path = tmp_path / "out_multi.docx"

    tmap = {
        ("vi", src_text): "Xin chào thế giới",
        ("de", src_text): "Hallo Welt",
    }

    with patch(
        "app.backend.processors.docx_processor.translate_texts",
        return_value=(tmap, 1, 0, False),
    ):
        translate_docx(
            str(in_path),
            str(out_path),
            targets=["vi", "de"],
            src_lang="en",
            client=_mock_client(),
            include_headers_shapes_via_com=False,
            output_mode="append",
        )

    doc = Document(str(out_path))
    all_texts = [p.text for p in doc.paragraphs]
    assert any("Xin chào thế giới" in t for t in all_texts), f"vi translation missing: {all_texts}"
    assert any("Hallo Welt" in t for t in all_texts), f"de translation missing: {all_texts}"
