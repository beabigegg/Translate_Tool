"""Contract test: BR-96 legacy-format lossy-conversion disclosure (support-legacy-office-formats).

Verifies job.warnings receives exactly one entry per successfully converted
legacy file (.doc/.xls/.ppt), with the exact canonical disclosure string from
business-rules.md BR-96 / api-contract.md `warnings` field note (L158).

Anti-tautology (per CLAUDE.md / test-plan.md):
- Asserts EXACT string content (byte-for-byte), not merely list non-emptiness.
- A .doc converted via win32com (no LibreOffice) must NOT emit the
  LibreOffice-specific disclosure string (BR-96's string names LibreOffice
  explicitly) — this guards the Known Risks gap called out in
  implementation-plan.md.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_mock_ollama_client():
    mock = MagicMock()
    mock.system_prompt = ""
    mock.model_type = "general"
    mock._is_translation_dedicated.return_value = False
    mock._is_translategemma_model.return_value = False
    return mock


def test_warnings_has_one_disclosure_entry_per_converted_file_with_exact_format(tmp_path):
    from app.backend.processors.orchestrator import process_files

    doc_path = tmp_path / "report.doc"
    doc_path.write_bytes(b"x")
    ppt_path = tmp_path / "slides.ppt"
    ppt_path.write_bytes(b"x")
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    def _fake_doc_to_docx(input_path, output_path):
        Path(output_path).write_bytes(b"converted")

    def _fake_ppt_to_pptx(input_path, output_path):
        Path(output_path).write_bytes(b"converted")

    def _fake_translate_docx(src_path, out_path, *a, **kw):
        Path(out_path).write_bytes(b"translated")
        return False

    def _fake_translate_pptx(src_path, out_path, *a, **kw):
        Path(out_path).write_bytes(b"translated")
        return False

    warnings_received: list = []

    with (
        patch("app.backend.processors.orchestrator.is_libreoffice_available", return_value=True),
        patch(
            "app.backend.processors.orchestrator.doc_to_docx",
            side_effect=_fake_doc_to_docx,
        ),
        patch(
            "app.backend.processors.orchestrator.ppt_to_pptx",
            side_effect=_fake_ppt_to_pptx,
        ),
        patch(
            "app.backend.processors.orchestrator.translate_docx",
            side_effect=_fake_translate_docx,
        ),
        patch(
            "app.backend.processors.orchestrator.translate_pptx",
            side_effect=_fake_translate_pptx,
        ),
        patch(
            "app.backend.processors.orchestrator.OllamaClient",
            return_value=_make_mock_ollama_client(),
        ),
    ):
        process_files(
            files=[doc_path, ppt_path],
            output_dir=output_dir,
            targets=["vi"],
            src_lang="en",
            include_headers_shapes_via_com=False,
            ollama_model="qwen2.5:32b",
            log=lambda s: None,
            warnings_callback=warnings_received.append,
        )

    assert len(warnings_received) == 2, (
        f"Expected exactly one disclosure entry per converted legacy file, "
        f"got: {warnings_received}"
    )
    assert warnings_received[0] == (
        "report.doc converted from a legacy format via LibreOffice; "
        "layout fidelity may be lower than a native format."
    )
    assert warnings_received[1] == (
        "slides.ppt converted from a legacy format via LibreOffice; "
        "layout fidelity may be lower than a native format."
    )


def test_no_disclosure_when_doc_converted_via_com_not_libreoffice(tmp_path):
    """A .doc converted via win32com (no LibreOffice) must not emit the
    LibreOffice-specific BR-96 disclosure string."""
    from app.backend.processors.orchestrator import process_files

    doc_path = tmp_path / "report.doc"
    doc_path.write_bytes(b"x")
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True, exist_ok=True)

    def _fake_translate_docx(src_path, out_path, *a, **kw):
        Path(out_path).write_bytes(b"translated")
        return False

    warnings_received: list = []

    with (
        patch("app.backend.processors.orchestrator.is_libreoffice_available", return_value=False),
        patch("app.backend.processors.orchestrator.is_win32com_available", return_value=True),
        patch("app.backend.processors.orchestrator.word_convert"),
        patch(
            "app.backend.processors.orchestrator.translate_docx",
            side_effect=_fake_translate_docx,
        ),
        patch(
            "app.backend.processors.orchestrator.OllamaClient",
            return_value=_make_mock_ollama_client(),
        ),
    ):
        process_files(
            files=[doc_path],
            output_dir=output_dir,
            targets=["vi"],
            src_lang="en",
            include_headers_shapes_via_com=False,
            ollama_model="qwen2.5:32b",
            log=lambda s: None,
            warnings_callback=warnings_received.append,
        )

    assert warnings_received == [], (
        f"COM-converted .doc must not emit the LibreOffice disclosure string, "
        f"got: {warnings_received}"
    )
