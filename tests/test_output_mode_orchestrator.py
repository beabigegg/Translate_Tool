"""Integration tests: output_mode threading through process_files().

AC-6: process_files() passes output_mode to translate_docx / translate_pptx.
AC-7: with len(targets) > 1, process_files() clamps output_mode to "append".

Anti-tautology:
- Patch at consumer-bound names (app.backend.processors.orchestrator.translate_docx,
  …translate_pptx) — module-level import pattern per CLAUDE.md.
- Assert call_args.kwargs["output_mode"] value (selection assertion, not count).
- Call process_files() directly, not translate_document() (avoids tautology via
  wrong entry-point pattern per CLAUDE.md).

Stubs accept terms_getter=None AND output_mode=None kwargs per implementation-plan.md
handoff constraints.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_FIXTURE_DOCX = Path(__file__).parent / "fixtures" / "minimal_phase0.docx"


def _make_mock_client():
    mock = MagicMock()
    mock.system_prompt = ""
    mock.model_type = "general"
    mock._is_translation_dedicated.return_value = False
    mock._is_translategemma_model.return_value = False
    mock.health_check.return_value = (True, "ok")
    return mock


def _make_mock_pptx(tmp_path: Path) -> Path:
    """Create a minimal PPTX fixture for pptx tests."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    blank_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank_layout)
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2))
    txBox.text_frame.text = "Hello world"
    p = tmp_path / "test.pptx"
    prs.save(str(p))
    return p


def _fake_translate_docx(
    src_path,
    out_path,
    targets,
    src_lang,
    client,
    *,
    stop_flag=None,
    log=None,
    max_batch_chars=None,
    pre_translate_hook=None,
    post_translate_hook=None,
    include_headers_shapes_via_com=False,
    terms_getter=None,
    output_mode=None,
):
    """Minimal translate_docx stub that satisfies the orchestrator call signature."""
    import shutil
    shutil.copy2(src_path, out_path)
    return False


def _fake_translate_pptx(
    src_path,
    out_path,
    targets,
    src_lang,
    client,
    *,
    stop_flag=None,
    log=None,
    max_batch_chars=None,
    pre_translate_hook=None,
    post_translate_hook=None,
    terms_getter=None,
    output_mode=None,
):
    """Minimal translate_pptx stub that satisfies the orchestrator call signature."""
    import shutil
    shutil.copy2(src_path, out_path)
    return False


# ---------------------------------------------------------------------------
# AC-6: output_mode threaded to translate_docx
# ---------------------------------------------------------------------------

def test_orchestrator_threads_output_mode_to_translate_docx(tmp_path):
    """process_files with output_mode='replace' passes output_mode='replace' to translate_docx."""
    from app.backend.processors.orchestrator import process_files

    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    with (
        patch(
            "app.backend.processors.orchestrator.translate_docx",
            side_effect=_fake_translate_docx,
        ) as mock_docx,
        patch(
            "app.backend.processors.orchestrator.OllamaClient",
            return_value=_make_mock_client(),
        ),
    ):
        process_files(
            files=[_FIXTURE_DOCX],
            output_dir=output_dir,
            targets=["vi"],
            src_lang="en",
            include_headers_shapes_via_com=False,
            ollama_model="qwen2.5:32b",
            output_mode="replace",
            log=lambda s: None,
        )

    assert mock_docx.called, "translate_docx was not called"
    call_kwargs = mock_docx.call_args.kwargs
    assert call_kwargs.get("output_mode") == "replace", (
        f"Expected output_mode='replace' but got: {call_kwargs.get('output_mode')!r}"
    )


# ---------------------------------------------------------------------------
# AC-6: output_mode threaded to translate_pptx
# ---------------------------------------------------------------------------

def test_orchestrator_threads_output_mode_to_translate_pptx(tmp_path):
    """process_files with output_mode='replace' passes output_mode='replace' to translate_pptx."""
    from app.backend.processors.orchestrator import process_files

    pptx_path = _make_mock_pptx(tmp_path)
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    with (
        patch(
            "app.backend.processors.orchestrator.translate_pptx",
            side_effect=_fake_translate_pptx,
        ) as mock_pptx,
        patch(
            "app.backend.processors.orchestrator.OllamaClient",
            return_value=_make_mock_client(),
        ),
    ):
        process_files(
            files=[pptx_path],
            output_dir=output_dir,
            targets=["vi"],
            src_lang="en",
            include_headers_shapes_via_com=False,
            ollama_model="qwen2.5:32b",
            output_mode="replace",
            log=lambda s: None,
        )

    assert mock_pptx.called, "translate_pptx was not called"
    call_kwargs = mock_pptx.call_args.kwargs
    assert call_kwargs.get("output_mode") == "replace", (
        f"Expected output_mode='replace' but got: {call_kwargs.get('output_mode')!r}"
    )


# ---------------------------------------------------------------------------
# AC-7: multi-target clamps replace → append
# ---------------------------------------------------------------------------

def test_orchestrator_clamps_replace_to_append_for_multi_target(tmp_path):
    """BR-67: with >1 targets, process_files clamps output_mode='replace' to 'append'."""
    from app.backend.processors.orchestrator import process_files

    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    with (
        patch(
            "app.backend.processors.orchestrator.translate_docx",
            side_effect=_fake_translate_docx,
        ) as mock_docx,
        patch(
            "app.backend.processors.orchestrator.OllamaClient",
            return_value=_make_mock_client(),
        ),
    ):
        process_files(
            files=[_FIXTURE_DOCX],
            output_dir=output_dir,
            targets=["vi", "de"],
            src_lang="en",
            include_headers_shapes_via_com=False,
            ollama_model="qwen2.5:32b",
            output_mode="replace",
            log=lambda s: None,
        )

    assert mock_docx.called, "translate_docx was not called"
    call_kwargs = mock_docx.call_args.kwargs
    # BR-67: multi-target forces append
    assert call_kwargs.get("output_mode") == "append", (
        f"Expected output_mode clamped to 'append' for multi-target, "
        f"got: {call_kwargs.get('output_mode')!r}"
    )
