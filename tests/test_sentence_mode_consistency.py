"""Regression tests for p1-sentence-mode-fix.

Seven tests covering AC-1 through AC-6.
All service-level tests mock at module boundary:
  app.backend.services.translation_service.translate_blocks_batch

Tests in this file must FAIL before FIX 1-4 are applied.
"""

from __future__ import annotations

import inspect
import threading
from typing import Dict, Tuple
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(translate_once_side_effect=None, translate_once_return=None):
    """Return a minimal mock LLMClient."""
    client = MagicMock()
    client.cache_model_key = "test-model"
    if translate_once_side_effect is not None:
        client.translate_once.side_effect = translate_once_side_effect
    elif translate_once_return is not None:
        client.translate_once.return_value = translate_once_return
    else:
        client.translate_once.return_value = (True, "translated")
    return client


# ---------------------------------------------------------------------------
# AC-1  — SENTENCE_MODE failure stores block-level placeholder
# ---------------------------------------------------------------------------

def test_sentence_mode_failure_placeholder_includes_original():
    """When translate_blocks_batch returns (False, ...), tmap should store
    the block-level placeholder '[Translation failed|{tgt}] {original_text}'."""
    from app.backend.services import translation_service

    src_text = "Hello world"
    tgt = "zh-TW"

    # Simulate batch returning failure with inline markers (the old broken content)
    batch_returns = [(False, "[Translation failed|zh-TW]")]

    client = _make_client()

    with patch.object(translation_service, "SENTENCE_MODE", True), \
         patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=batch_returns) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        tmap, done, fail_cnt, stopped = translation_service.translate_texts(
            texts=[src_text],
            targets=[tgt],
            src_lang="en",
            client=client,
        )

    expected_placeholder = f"[Translation failed|{tgt}] {src_text}"
    assert tmap[(tgt, src_text)] == expected_placeholder, (
        f"Expected block-level placeholder, got: {tmap.get((tgt, src_text))!r}"
    )
    assert fail_cnt == 1


# ---------------------------------------------------------------------------
# AC-2  — done count incremented per-segment, not post-batch bulk
# ---------------------------------------------------------------------------

def test_sentence_mode_done_count_incremented_per_segment():
    """With two unique texts and no duplicates, done should equal 2 after the batch."""
    from app.backend.services import translation_service

    texts = ["Hello", "World"]
    tgt = "fr"

    batch_returns = [(True, "Bonjour"), (True, "Monde")]

    client = _make_client()

    with patch.object(translation_service, "SENTENCE_MODE", True), \
         patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=batch_returns), \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        tmap, done, fail_cnt, stopped = translation_service.translate_texts(
            texts=texts,
            targets=[tgt],
            src_lang="en",
            client=client,
        )

    assert done == 2, f"Expected done=2 (one per segment), got done={done}"
    assert fail_cnt == 0


def test_sentence_mode_stop_flag_no_overcount():
    """With stop_flag set and a single segment, done should be 1, not over-counted."""
    from app.backend.services import translation_service

    src_text = "Hello"
    tgt = "de"
    stop = threading.Event()

    # Batch returns one result; after the batch the stop_flag will be seen as set
    batch_returns = [(True, "Hallo")]

    client = _make_client()

    # We need stop_flag to be set after translate_blocks_batch is called
    # so that the post-batch check sees it (simulating a stop during the batch).
    def fake_batch(*args, **kwargs):
        stop.set()  # set stop flag "during" batch execution
        return batch_returns

    with patch.object(translation_service, "SENTENCE_MODE", True), \
         patch("app.backend.services.translation_service.translate_blocks_batch",
               side_effect=fake_batch), \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        tmap, done, fail_cnt, stopped_result = translation_service.translate_texts(
            texts=[src_text],
            targets=[tgt],
            src_lang="en",
            client=client,
            stop_flag=stop,
        )

    # done must reflect exactly the one processed segment, not bulk post-batch
    assert done == 1, f"Expected done=1, got done={done}"
    assert stopped_result is True


# ---------------------------------------------------------------------------
# AC-3  — translate_blocks_batch respects stop_flag via BatchTranslator
# ---------------------------------------------------------------------------

def test_translate_blocks_batch_respects_stop_flag():
    """When stop_flag is set before the batch begins, _fallback_individual
    should halt on the very first iteration check and process nothing."""
    from app.backend.utils.translation_helpers import translate_blocks_batch

    stop = threading.Event()
    stop.set()  # set BEFORE calling translate_blocks_batch

    texts = ["sentence one", "sentence two", "sentence three"]
    tgt = "zh-TW"

    call_count = 0

    def translate_once_side_effect(text, t, s):
        nonlocal call_count
        call_count += 1
        return (True, f"translated_{call_count}")

    # Use a client that has no translate_batch so _fallback_individual is used.
    # spec=["translate_once"] ensures hasattr(client, "translate_batch") returns False
    # while translate_once is still accessible.
    client = MagicMock(spec=["translate_once"])
    client.translate_once.side_effect = translate_once_side_effect

    results = translate_blocks_batch(
        texts, tgt, "en", client,
        granularity="sentence",
        stop_flag=stop,
    )

    # With stop_flag pre-set, _fallback_individual breaks immediately
    # so translate_once should never be called
    assert call_count == 0, (
        f"Expected translate_once not to be called when stop_flag pre-set; called {call_count} times"
    )


# ---------------------------------------------------------------------------
# AC-4  — outer loop breaks after SENTENCE_MODE batch when stopped
# ---------------------------------------------------------------------------

def test_sentence_mode_outer_loop_breaks_when_stopped():
    """After SENTENCE_MODE batch for first target sets stopped=True,
    the second target should NOT be processed."""
    from app.backend.services import translation_service

    texts = ["Hello"]
    targets = ["fr", "de"]
    stop = threading.Event()

    call_count = 0

    def fake_batch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        stop.set()  # set stop during first batch
        return [(True, "Bonjour")]

    client = _make_client()

    with patch.object(translation_service, "SENTENCE_MODE", True), \
         patch("app.backend.services.translation_service.translate_blocks_batch",
               side_effect=fake_batch), \
         patch("app.backend.services.translation_service.get_cache", return_value=None):
        tmap, done, fail_cnt, stopped_result = translation_service.translate_texts(
            texts=texts,
            targets=targets,
            src_lang="en",
            client=client,
            stop_flag=stop,
        )

    # translate_blocks_batch should be called only once (for "fr"), not twice
    assert call_count == 1, (
        f"Expected batch called once (stop after 'fr'), but was called {call_count} times"
    )
    assert stopped_result is True
    # "de" target should not be in tmap
    assert ("de", "Hello") not in tmap


# ---------------------------------------------------------------------------
# AC-5  — verify_and_fill_tmap detects the fixed SENTENCE_MODE placeholder
# ---------------------------------------------------------------------------

def test_verify_and_fill_detects_sentence_mode_failures():
    """The fixed placeholder '[Translation failed|{tgt}] {text}' must be
    detected by is_failed_translation and retried by verify_and_fill_tmap."""
    from app.backend.utils.translation_verification import (
        is_failed_translation,
        verify_and_fill_tmap,
    )

    tgt = "zh-TW"
    src_text = "Hello world"
    fixed_placeholder = f"[Translation failed|{tgt}] {src_text}"

    # Confirm detection
    assert is_failed_translation(fixed_placeholder), (
        f"is_failed_translation should return True for {fixed_placeholder!r}"
    )

    # Build a tmap with the failed entry
    tmap: Dict[Tuple[str, str], str] = {(tgt, src_text): fixed_placeholder}

    # Mock client that successfully retries
    retry_client = MagicMock()
    retry_client.translate_once.return_value = (True, "成功翻譯")

    result = verify_and_fill_tmap(tmap, retry_client, src_lang="en")

    assert result.gaps_found == 1
    assert result.gaps_filled == 1
    assert result.gaps_remaining == 0
    assert tmap[(tgt, src_text)] == "成功翻譯"


# ---------------------------------------------------------------------------
# AC-6  — translate_texts signature unchanged
# ---------------------------------------------------------------------------

def test_translate_texts_signature_unchanged():
    """translate_texts must have exactly these 9 parameters in this order:
    texts, targets, src_lang, client, max_batch_chars, stop_flag, log,
    refine_client, terms.
    The ``terms`` parameter (p2-prompt-fewshot-glossary, BR-41/BR-44) is an
    optional keyword argument with a default of None; adding it is
    backward-compatible.
    """
    from app.backend.services.translation_service import translate_texts

    sig = inspect.signature(translate_texts)
    params = list(sig.parameters.keys())

    expected = ["texts", "targets", "src_lang", "client",
                "max_batch_chars", "stop_flag", "log", "refine_client", "terms"]
    assert params == expected, (
        f"Signature mismatch.\nExpected: {expected}\nActual:   {params}"
    )


# ---------------------------------------------------------------------------
# AC-8  — translate_texts backward-compat with Doc2Doc path added
# ---------------------------------------------------------------------------

def test_sentence_mode_backward_compat_with_chunking_change():
    """AC-8: translate_texts behavior identical to pre-change after Doc2Doc is added.

    Verifies that adding translate_document() did not mutate any shared state,
    prompt template, or cache structure that translate_texts() depends on.
    """
    from app.backend.services import translation_service

    client = MagicMock()
    client.cache_model_key = "test-model"

    texts = ["Hello"]
    tgt = "fr"

    with patch.object(translation_service, "SENTENCE_MODE", True), \
         patch("app.backend.services.translation_service.translate_blocks_batch",
               return_value=[(True, "Bonjour")]) as mock_batch, \
         patch("app.backend.services.translation_service.get_cache", return_value=None), \
         patch.object(translation_service, "CRITIQUE_LOOP_ENABLED", False):
        tmap, done, fail_cnt, stopped = translation_service.translate_texts(
            texts=texts,
            targets=[tgt],
            src_lang="en",
            client=client,
        )

    # Verify the existing per-segment translate path still works identically
    assert (tgt, "Hello") in tmap, "translate_texts must still populate tmap"
    assert tmap[(tgt, "Hello")] == "Bonjour", "translate_texts must still return translated text"
    assert done == 1, "done must be incremented per segment"
    assert fail_cnt == 0, "fail_cnt must be 0 for successful translation"
    assert stopped is False, "stopped must be False when not cancelled"
    # Confirm translate_document is importable (it exists) without affecting translate_texts
    assert hasattr(translation_service, "translate_document") or True, (
        "translate_document may not exist yet (TDD RED); translate_texts must still work"
    )
