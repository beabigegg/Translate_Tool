"""Integration tests for translate_document() parity with translate_texts() (AC-9, AC-10, AC-11).

Verifies that translate_document() delegates chunk translation to translate_texts() so that
term substitution (AC-9), critique loop (AC-10), and overlap-as-context (AC-11) are inherited.

Anti-tautology guards (CLAUDE.md):
- Patch the consumer-module binding: `app.backend.services.translation_service.translate_texts`
  (NOT translate_document itself — that is the wrong-entry-point trap).
- Assert call args / kwargs, not just output text.
- For AC-11: assert successive chunk calls receive different chunk_context kwargs.
"""

from __future__ import annotations

import types
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock, call, patch

import pytest

# Capture consumer module at collection time (immune to reload contamination).
import app.backend.services.translation_service as _ts_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_doc(num_elements: int = 2):
    """Build a minimal TranslatableDocument with `num_elements` text elements."""
    from app.backend.models.translatable_document import (
        ElementType,
        TranslatableDocument,
        TranslatableElement,
    )

    elements = []
    for i in range(num_elements):
        elem = TranslatableElement(
            element_id=f"elem-{i}",
            content=f"Source text {i}.",
            element_type=ElementType.TEXT,
            page_num=1,
            should_translate=True,
        )
        elements.append(elem)

    doc = TranslatableDocument.__new__(TranslatableDocument)
    doc.source_path = "test.docx"
    doc.source_type = "docx"
    doc.elements = elements
    doc.pages = []
    doc.metadata = MagicMock()
    return doc


def _make_translate_texts_mock(tmap_override: Optional[Dict] = None):
    """Return a mock for translate_texts that builds a realistic tmap."""
    def _fake_translate_texts(
        texts, targets, src_lang, client,
        max_batch_chars=None, stop_flag=None, log=None,
        terms=None, status_callback=None, chunk_context="",
    ):
        tmap: Dict[Tuple[str, str], str] = {}
        for tgt in targets:
            for text in texts:
                tmap[(tgt, text)] = f"[Translated:{tgt}] {text}"
        return tmap, len(texts), 0, False

    if tmap_override is not None:
        return MagicMock(return_value=tmap_override)

    return MagicMock(side_effect=_fake_translate_texts)


# ---------------------------------------------------------------------------
# AC-9: translate_document calls translate_texts with terms kwarg
# ---------------------------------------------------------------------------

def test_translate_document_calls_term_substitution():
    """AC-9: translate_document delegates to translate_texts with terms= kwarg.

    Anti-tautology: mock translate_texts (consumer-module binding) and assert
    it was called with a non-None terms argument — NOT checking output text.
    """
    from app.backend.services.translation_service import translate_document
    from unittest.mock import MagicMock, patch

    doc = _make_minimal_doc(num_elements=2)
    mock_client = MagicMock()
    mock_client.cache_model_key = "test-model"

    # Minimal term-like objects
    term1 = MagicMock()
    term1.source_text = "Source text"

    mock_tt = _make_translate_texts_mock()

    # split_document and reassemble_document are lazy-imported inside translate_document,
    # so we must patch at the definition module (doc_chunker), not translation_service.
    with patch.object(_ts_mod, "translate_texts", mock_tt):
        with patch("app.backend.services.doc_chunker.split_document") as mock_split, \
             patch("app.backend.services.doc_chunker.reassemble_document"):
            # Build a single chunk pointing at our doc elements
            chunk = MagicMock()
            chunk.chunk_index = 0
            chunk.elements = doc.elements
            mock_split.return_value = [chunk]

            translate_document(
                doc,
                targets=["fr"],
                src_lang="en",
                client=mock_client,
                terms=[term1],
            )

    # translate_texts must have been called
    assert mock_tt.called, "translate_texts must be called from translate_document"

    # terms kwarg must be non-None (or positional terms param must be [term1])
    call_kwargs = mock_tt.call_args
    assert call_kwargs is not None
    # terms may be passed as kwarg or positional arg[7] — check both
    kwargs = call_kwargs.kwargs
    args = call_kwargs.args

    terms_passed = kwargs.get("terms") or (args[7] if len(args) > 7 else None)
    assert terms_passed is not None and len(terms_passed) > 0, (
        f"translate_texts must receive terms kwarg; got kwargs={kwargs}, args={args}"
    )


# ---------------------------------------------------------------------------
# AC-10: translate_document calls translate_texts (critique runs automatically)
# ---------------------------------------------------------------------------

def test_translate_document_calls_critique_loop():
    """AC-10: translate_document invokes translate_texts; critique is inside translate_texts.

    Since critique runs inside translate_texts, if translate_texts is called,
    critique runs. We verify translate_texts IS called (not just the output).
    """
    from app.backend.services.translation_service import translate_document

    doc = _make_minimal_doc(num_elements=2)
    mock_client = MagicMock()
    mock_client.cache_model_key = "test-model"

    mock_tt = _make_translate_texts_mock()

    with patch.object(_ts_mod, "translate_texts", mock_tt):
        with patch("app.backend.services.doc_chunker.split_document") as mock_split, \
             patch("app.backend.services.doc_chunker.reassemble_document"):
            chunk = MagicMock()
            chunk.chunk_index = 0
            chunk.elements = doc.elements
            mock_split.return_value = [chunk]

            translate_document(doc, targets=["fr"], src_lang="en", client=mock_client)

    assert mock_tt.call_count >= 1, (
        f"translate_texts must be called at least once; got {mock_tt.call_count} calls"
    )


# ---------------------------------------------------------------------------
# AC-11: translate_document passes overlap tokens as context to translate_texts
# ---------------------------------------------------------------------------

def test_translate_document_passes_overlap_tokens_as_context():
    """AC-11: successive translate_texts calls for chunk N+1 receive chunk N's overlap as context.

    Anti-tautology: mock translate_texts (consumer-module binding); inspect
    call_args[1] (kwargs) for `chunk_context` parameter.
    """
    from app.backend.services.translation_service import translate_document
    from app.backend.models.translatable_document import (
        ElementType,
        TranslatableDocument,
        TranslatableElement,
    )

    # Build doc with 4 elements
    elements = [
        TranslatableElement(
            element_id=f"elem-{i}",
            content=f"Chunk text {i} with enough words.",
            element_type=ElementType.TEXT,
            page_num=1,
            should_translate=True,
        )
        for i in range(4)
    ]
    doc = TranslatableDocument.__new__(TranslatableDocument)
    doc.source_path = "test.docx"
    doc.source_type = "docx"
    doc.elements = elements
    doc.pages = []
    doc.metadata = MagicMock()

    mock_client = MagicMock()
    mock_client.cache_model_key = "test-model"

    mock_tt = _make_translate_texts_mock()

    with patch.object(_ts_mod, "translate_texts", mock_tt):
        with patch("app.backend.services.doc_chunker.split_document") as mock_split, \
             patch("app.backend.services.doc_chunker.reassemble_document"):
            # Create 2 chunks
            chunk0 = MagicMock()
            chunk0.chunk_index = 0
            chunk0.elements = elements[:2]

            chunk1 = MagicMock()
            chunk1.chunk_index = 1
            chunk1.elements = elements[2:]

            mock_split.return_value = [chunk0, chunk1]

            translate_document(doc, targets=["fr"], src_lang="en", client=mock_client)

    # Must have been called at least twice (once per chunk)
    assert mock_tt.call_count >= 2, (
        f"translate_texts should be called once per chunk; got {mock_tt.call_count}"
    )

    # First chunk: chunk_context should be empty (no predecessor)
    first_call = mock_tt.call_args_list[0]
    first_ctx = first_call.kwargs.get("chunk_context", "")
    assert first_ctx == "", (
        f"First chunk should have empty chunk_context; got {first_ctx!r}"
    )

    # Second chunk: chunk_context should be non-empty (overlap from first chunk)
    second_call = mock_tt.call_args_list[1]
    second_ctx = second_call.kwargs.get("chunk_context", "")
    assert second_ctx != "", (
        "Second chunk must receive non-empty chunk_context (overlap from first chunk)"
    )
    # The overlap context should contain text from the first chunk
    first_chunk_texts = [e.content for e in elements[:2] if e.should_translate]
    # At least one of the first chunk's texts should appear in the context
    assert any(t in second_ctx for t in first_chunk_texts), (
        f"chunk_context for second chunk should contain text from first chunk; "
        f"got {second_ctx!r}, first chunk texts={first_chunk_texts}"
    )
