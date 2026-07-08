"""Unit tests for PDF-path current-segment stage snapshot wiring
(pdf-stage-detail-snapshot).

Bug: PDF jobs never populated JobRecord.current_segment because
translate_pdf -> translate_blocks_batch bypassed
translation_service.translate_texts (the only call site wired for the
CurrentSegmentSnapshot by translation-progress-detail-ui), and translate_pdf
had no status_callback parameter at all.

Fix: thread an optional status_callback through translate_pdf and its three
sub-functions (_translate_pdf_with_pymupdf, _translate_pdf_with_pypdf2,
_translate_pdf_to_pdf); at the flatten translate_blocks_batch(...) call in
each, pass on_segment_done=<wrapper> that builds
CurrentSegmentSnapshot(stage="translate", source=src, draft=translated) and
calls status_callback(detail, snapshot).

Mock boundary: only translate_blocks_batch (or PdfReader/PyMuPDFParser to
fake the parse step) is mocked, mirroring
tests/test_pdf_layout_viz_persistence.py's existing pattern -- never
CurrentSegmentSnapshot or job_manager internals.

Anti-tautology: the translate_blocks_batch side_effect below always fires
on_segment_done itself (a mock that merely returns results would pass without
exercising the wiring), and assertions check exact stage/source/draft VALUES
per call, not mere non-null presence, with N distinct correctly-ordered
snapshots for N segments.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.backend.models.translatable_document import (
    BoundingBox,
    DocumentMetadata,
    ElementType,
    PageInfo,
    TranslatableDocument,
    TranslatableElement,
)


def _make_multi_element_doc(source_path: str, texts):
    elements = [
        TranslatableElement(
            element_id=f"e{i}",
            content=text,
            element_type=ElementType.TEXT,
            page_num=1,
            bbox=BoundingBox(x0=72, y0=72 + i * 20, x1=300, y1=90 + i * 20),
            should_translate=True,
            reading_order=i,
        )
        for i, text in enumerate(texts)
    ]
    return TranslatableDocument(
        source_path=source_path,
        source_type="pdf",
        elements=elements,
        pages=[PageInfo(page_num=1, width=612, height=792)],
        metadata=DocumentMetadata(page_count=1, has_text_layer=True),
    )


def _fake_translate_blocks_batch(texts, tgt, src_lang, client, log=None, on_segment_done=None, **kwargs):
    """Anti-tautology: mirrors the REAL translate_blocks_batch contract by
    firing on_segment_done(src, translated) for every text before returning."""
    results = []
    for text in texts:
        translated = f"[{tgt}] {text}"
        if on_segment_done is not None:
            on_segment_done(text, translated)
        results.append((True, translated))
    return results


class _FakePdfPage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakePdfReader:
    def __init__(self, texts):
        self.pages = [_FakePdfPage(t) for t in texts]


# ---------------------------------------------------------------------------
# AC-3: translate_pdf threads status_callback into all 3 dispatch targets
# ---------------------------------------------------------------------------

def test_translate_pdf_signature_accepts_status_callback(tmp_path):
    import app.backend.processors.pdf_processor as pdf_processor_module

    sentinel = object()
    in_path = str(tmp_path / "sample.pdf")
    Path(in_path).write_bytes(b"")

    # Branch 1: docx-output + PyMuPDF parser available -> _translate_pdf_with_pymupdf
    with patch.object(pdf_processor_module, "is_win32com_available", return_value=False), \
         patch.object(pdf_processor_module, "_get_pymupdf_parser", return_value=MagicMock()), \
         patch.object(pdf_processor_module, "_translate_pdf_with_pymupdf", return_value=False) as mock_pymupdf:
        pdf_processor_module.translate_pdf(
            in_path=in_path,
            out_path=str(tmp_path / "out1.docx"),
            targets=["English"],
            src_lang=None,
            client=MagicMock(),
            output_format="docx",
            layout_mode="inline",
            status_callback=sentinel,
        )
    assert mock_pymupdf.call_args.kwargs.get("status_callback") is sentinel, (
        "translate_pdf did not thread status_callback into _translate_pdf_with_pymupdf"
    )

    # Branch 2: docx-output + no PyMuPDF parser -> _translate_pdf_with_pypdf2
    with patch.object(pdf_processor_module, "is_win32com_available", return_value=False), \
         patch.object(pdf_processor_module, "_get_pymupdf_parser", return_value=None), \
         patch.object(pdf_processor_module, "_translate_pdf_with_pypdf2", return_value=False) as mock_pypdf2:
        pdf_processor_module.translate_pdf(
            in_path=in_path,
            out_path=str(tmp_path / "out2.docx"),
            targets=["English"],
            src_lang=None,
            client=MagicMock(),
            output_format="docx",
            layout_mode="inline",
            status_callback=sentinel,
        )
    assert mock_pypdf2.call_args.kwargs.get("status_callback") is sentinel, (
        "translate_pdf did not thread status_callback into _translate_pdf_with_pypdf2"
    )

    # Branch 3: pdf-output overlay -> _translate_pdf_to_pdf
    with patch.object(pdf_processor_module, "_translate_pdf_to_pdf", return_value=False) as mock_to_pdf:
        pdf_processor_module.translate_pdf(
            in_path=in_path,
            out_path=str(tmp_path / "out3.pdf"),
            targets=["English"],
            src_lang=None,
            client=MagicMock(),
            output_format="pdf",
            layout_mode="overlay",
            status_callback=sentinel,
        )
    assert mock_to_pdf.call_args.kwargs.get("status_callback") is sentinel, (
        "translate_pdf did not thread status_callback into _translate_pdf_to_pdf"
    )


# ---------------------------------------------------------------------------
# AC-2, AC-8: PyMuPDF flatten-batch path emits CurrentSegmentSnapshot per
# segment (this is the ADR-0006 RED->GREEN reproduction test).
# ---------------------------------------------------------------------------

def test_pymupdf_path_on_segment_done_emits_translate_stage_snapshot(tmp_path):
    import app.backend.processors.pdf_processor as pdf_processor_module
    from app.backend.services.job_manager import CurrentSegmentSnapshot

    in_dir = tmp_path / "input"
    out_dir = tmp_path / "output"
    in_dir.mkdir()
    out_dir.mkdir()
    in_path = str(in_dir / "sample.pdf")
    Path(in_path).write_bytes(b"")
    out_path = str(out_dir / "sample_translated.docx")

    texts = ["Hello World", "Second paragraph of text"]
    fake_doc = _make_multi_element_doc(in_path, texts)
    fake_parser = MagicMock()
    fake_parser.parse.return_value = fake_doc

    captured = []

    def fake_status_callback(detail, segment=None):
        captured.append((detail, segment))

    with patch("app.backend.parsers.pdf_parser.PyMuPDFParser", return_value=fake_parser):
        with patch.object(pdf_processor_module, "translate_blocks_batch", side_effect=_fake_translate_blocks_batch):
            pdf_processor_module._translate_pdf_with_pymupdf(
                in_path,
                out_path,
                ["English"],
                None,
                MagicMock(),
                None,
                lambda s: None,
                False,
                status_callback=fake_status_callback,
            )

    snapshots = [seg for _, seg in captured if seg is not None]
    assert len(snapshots) == len(texts), (
        f"expected {len(texts)} distinct snapshot writes (one per segment), got {len(snapshots)}"
    )
    for expected_source, seg in zip(texts, snapshots):
        assert isinstance(seg, CurrentSegmentSnapshot)
        assert seg.stage == "translate"
        assert seg.source == expected_source
        assert seg.draft == f"[English] {expected_source}"


# ---------------------------------------------------------------------------
# AC-4: PyPDF2 and PDF-to-PDF (overlay) flatten-batch paths emit the same
# snapshot shape.
# ---------------------------------------------------------------------------

def test_pypdf2_and_to_pdf_paths_on_segment_done_emit_translate_stage_snapshot(tmp_path):
    import app.backend.processors.pdf_processor as pdf_processor_module
    from app.backend.services.job_manager import CurrentSegmentSnapshot

    # --- PyPDF2 path ---
    texts_pypdf2 = ["Page one text", "Page two text"]
    fake_reader = _FakePdfReader(texts_pypdf2)
    captured_pypdf2 = []

    def status_cb_pypdf2(detail, segment=None):
        captured_pypdf2.append((detail, segment))

    in_path_pypdf2 = str(tmp_path / "pypdf2_sample.pdf")
    Path(in_path_pypdf2).write_bytes(b"")
    out_path_pypdf2 = str(tmp_path / "pypdf2_out.docx")

    with patch.object(pdf_processor_module, "PdfReader", return_value=fake_reader):
        with patch.object(pdf_processor_module, "translate_blocks_batch", side_effect=_fake_translate_blocks_batch):
            pdf_processor_module._translate_pdf_with_pypdf2(
                in_path_pypdf2,
                out_path_pypdf2,
                ["English"],
                None,
                MagicMock(),
                None,
                lambda s: None,
                status_callback=status_cb_pypdf2,
            )

    snapshots_pypdf2 = [seg for _, seg in captured_pypdf2 if seg is not None]
    assert len(snapshots_pypdf2) == len(texts_pypdf2), (
        f"PyPDF2 path: expected {len(texts_pypdf2)} snapshot writes, got {len(snapshots_pypdf2)}"
    )
    for expected_source, seg in zip(texts_pypdf2, snapshots_pypdf2):
        assert isinstance(seg, CurrentSegmentSnapshot)
        assert seg.stage == "translate"
        assert seg.source == expected_source
        assert seg.draft == f"[English] {expected_source}"

    # --- PDF-to-PDF (overlay) path ---
    texts_to_pdf = ["Overlay block one", "Overlay block two"]
    in_path_to_pdf = str(tmp_path / "to_pdf_sample.pdf")
    Path(in_path_to_pdf).write_bytes(b"")
    out_path_to_pdf = str(tmp_path / "to_pdf_out.pdf")

    fake_doc = _make_multi_element_doc(in_path_to_pdf, texts_to_pdf)
    fake_parser = MagicMock()
    fake_parser.parse.return_value = fake_doc

    captured_to_pdf = []

    def status_cb_to_pdf(detail, segment=None):
        captured_to_pdf.append((detail, segment))

    with patch("app.backend.parsers.pdf_parser.PyMuPDFParser", return_value=fake_parser):
        with patch.object(pdf_processor_module, "translate_blocks_batch", side_effect=_fake_translate_blocks_batch):
            with patch.object(pdf_processor_module, "_dispatch_render"):
                pdf_processor_module._translate_pdf_to_pdf(
                    in_path_to_pdf,
                    out_path_to_pdf,
                    ["English"],
                    None,
                    MagicMock(),
                    None,
                    lambda s: None,
                    False,
                    "overlay",
                    status_callback=status_cb_to_pdf,
                )

    snapshots_to_pdf = [seg for _, seg in captured_to_pdf if seg is not None]
    assert len(snapshots_to_pdf) == len(texts_to_pdf), (
        f"PDF-to-PDF path: expected {len(texts_to_pdf)} snapshot writes, got {len(snapshots_to_pdf)}"
    )
    for expected_source, seg in zip(texts_to_pdf, snapshots_to_pdf):
        assert isinstance(seg, CurrentSegmentSnapshot)
        assert seg.stage == "translate"
        assert seg.source == expected_source
        assert seg.draft == f"[English] {expected_source}"
