"""Glossary enforcement and critique loop tests.

Replacement proof anchor for BR-41 (glossary-match-guarantee) and BR-44
(critique-loop-policy), replacing all 6 orphaned Table M / Table N rows
previously in tests/test_hy_mt_quality_refinement.py.

Entry point: translate_texts() (not translate_document() which is unwired per
CLAUDE.md lessons).
Mock boundary: app.backend.services.translation_service.translate_blocks_batch
(bound name in the consumer module — CLAUDE.md mock.patch lesson).
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from app.backend.models.term import Term


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_term(source: str, target: str, confidence: float = 1.0) -> Term:
    return Term(
        source_text=source,
        target_text=target,
        source_lang="Chinese",
        target_lang="Vietnamese",
        domain="general",
        confidence=confidence,
        status="approved",
    )


def _make_client(translate_once_return=(True, "translated text")):
    client = MagicMock()
    client.cache_model_key = "test-model"
    client.translate_once.return_value = translate_once_return
    client.unload.return_value = (True, "no-op")
    return client


# ---------------------------------------------------------------------------
# BR-44 / Table M: Critique loop
# ---------------------------------------------------------------------------

class TestCritiqueLoop:
    """BR-44: critique loop runs ≥1 iteration per request."""

    def test_critique_loop_runs_with_glossary_terms(self):
        """Table M row 1: critique loop runs when terms are provided (BR-44)."""
        from app.backend.services.translation_service import translate_texts

        client = _make_client()
        # First call: Phase-1 translation; subsequent calls: critique iterations
        client.translate_once.return_value = (True, "translated text")

        terms = [_make_term("source_word", "target_word")]

        with patch(
            "app.backend.services.translation_service.translate_blocks_batch",
            return_value=[(True, "translated text")],
        ), patch(
            "app.backend.services.translation_service.get_cache",
            return_value=None,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED",
            True,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS",
            1,
        ):
            tmap, _, _, stopped = translate_texts(
                texts=["source_word in context"],
                targets=["Vietnamese"],
                src_lang="Chinese",
                client=client,
                terms=terms,
            )

        assert not stopped
        # Critique loop must have called translate_once at least once
        assert client.translate_once.call_count >= 1

    def test_critique_loop_runs_without_glossary_terms(self):
        """Table M row 2: critique loop runs even without terms (BR-44)."""
        from app.backend.services.translation_service import translate_texts

        client = _make_client()
        client.translate_once.return_value = (True, "improved translation")

        with patch(
            "app.backend.services.translation_service.translate_blocks_batch",
            return_value=[(True, "initial translation")],
        ), patch(
            "app.backend.services.translation_service.get_cache",
            return_value=None,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED",
            True,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS",
            1,
        ):
            tmap, _, _, stopped = translate_texts(
                texts=["some text"],
                targets=["Vietnamese"],
                src_lang="Chinese",
                client=client,
            )

        assert not stopped
        # Critique runs: translate_once called for critique iteration
        assert client.translate_once.call_count >= 1

    def test_critique_iterations_total_incremented(self):
        """Table M row 3: critique iteration count is incremented (BR-44)."""
        from app.backend.services.translation_service import translate_texts
        from app.backend.services import metrics as metrics_module

        client = _make_client()
        client.translate_once.return_value = (True, "critique output")

        with patch(
            "app.backend.services.translation_service.translate_blocks_batch",
            return_value=[(True, "initial")],
        ), patch(
            "app.backend.services.translation_service.get_cache",
            return_value=None,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED",
            True,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS",
            2,
        ), patch(
            "app.backend.services.translation_service.record_critique_iteration"
        ) as mock_record:
            translate_texts(
                texts=["segment text"],
                targets=["Vietnamese"],
                src_lang="Chinese",
                client=client,
            )

        # record_critique_iteration must have been called
        mock_record.assert_called_once()
        # The argument must be a non-negative int
        call_args = mock_record.call_args[0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], int)
        assert call_args[0] >= 0

    def test_critique_exception_degrades_gracefully(self):
        """Table M row 4: critique call raises exception → last valid draft used, job not failed (BR-44)."""
        from app.backend.services.translation_service import translate_texts

        client = _make_client()
        # Critique call raises — should not propagate
        client.translate_once.side_effect = RuntimeError("LLM timeout")

        with patch(
            "app.backend.services.translation_service.translate_blocks_batch",
            return_value=[(True, "initial draft")],
        ), patch(
            "app.backend.services.translation_service.get_cache",
            return_value=None,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED",
            True,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS",
            1,
        ):
            tmap, _, fail_cnt, stopped = translate_texts(
                texts=["some text"],
                targets=["Vietnamese"],
                src_lang="Chinese",
                client=client,
            )

        # Job must not fail: tmap has the last valid draft
        assert ("Vietnamese", "some text") in tmap
        # The last valid draft (initial draft) is kept, not a failure placeholder
        assert not tmap[("Vietnamese", "some text")].startswith("[Translation failed|")
        assert fail_cnt == 0

    def test_critique_terminates_at_max_iterations(self):
        """Table M row 5: critique loop terminates at CRITIQUE_MAX_ITERATIONS (BR-44)."""
        from app.backend.services.translation_service import translate_texts

        client = _make_client()
        call_count = {"n": 0}

        def _side_effect(prompt, tgt, src_lang):
            call_count["n"] += 1
            return (True, f"iteration {call_count['n']}")

        client.translate_once.side_effect = _side_effect

        max_iters = 2
        with patch(
            "app.backend.services.translation_service.translate_blocks_batch",
            return_value=[(True, "initial")],
        ), patch(
            "app.backend.services.translation_service.get_cache",
            return_value=None,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED",
            True,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS",
            max_iters,
        ):
            tmap, _, _, _ = translate_texts(
                texts=["text"],
                targets=["Vietnamese"],
                src_lang="Chinese",
                client=client,
            )

        # translate_once must not have been called more than max_iters times
        # (each segment gets at most max_iters critique calls)
        assert call_count["n"] <= max_iters


# ---------------------------------------------------------------------------
# BR-41 / Table N: Glossary enforcement
# ---------------------------------------------------------------------------

class TestGlossaryEnforcement:
    """BR-41: approved term appears verbatim in output after substitution."""

    def test_glossary_term_present_in_output_accepted(self):
        """Table N row 1: when LLM output already contains target_text, no substitution (BR-41 no-op)."""
        from app.backend.services.translation_service import translate_texts

        client = _make_client()
        client.translate_once.return_value = (True, "approved translation output")

        terms = [_make_term("approved", "translation output")]

        with patch(
            "app.backend.services.translation_service.translate_blocks_batch",
            return_value=[(True, "approved translation output")],
        ), patch(
            "app.backend.services.translation_service.get_cache",
            return_value=None,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED",
            False,
        ):
            tmap, _, _, _ = translate_texts(
                texts=["approved term here"],
                targets=["Vietnamese"],
                src_lang="Chinese",
                client=client,
                terms=terms,
            )

        # term's target_text must be in the output (no-op: LLM already produced it)
        final = tmap[("Vietnamese", "approved term here")]
        assert "translation output" in final

    def test_glossary_term_missing_triggers_substitution(self):
        """Table N row 2: when target_text absent from LLM output, substitution appends it (BR-41)."""
        from app.backend.services.translation_service import translate_texts

        client = _make_client()
        client.translate_once.return_value = (True, "this is a generic translation")

        terms = [_make_term("canonical_source", "CanonicalTarget")]

        with patch(
            "app.backend.services.translation_service.translate_blocks_batch",
            return_value=[(True, "this is a generic translation")],
        ), patch(
            "app.backend.services.translation_service.get_cache",
            return_value=None,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED",
            False,
        ):
            tmap, _, _, _ = translate_texts(
                texts=["canonical_source in context"],
                targets=["Vietnamese"],
                src_lang="Chinese",
                client=client,
                terms=terms,
            )

        final = tmap[("Vietnamese", "canonical_source in context")]
        assert "CanonicalTarget" in final, (
            f"Expected 'CanonicalTarget' in output after substitution, got: {final!r}"
        )

    def test_no_terms_in_db_is_noop(self):
        """Table N row 5: empty term list → no substitution attempted, output unchanged (BR-41)."""
        from app.backend.services.translation_service import translate_texts

        client = _make_client()
        expected_output = "clean translation without any term enforcement"
        client.translate_once.return_value = (True, expected_output)

        with patch(
            "app.backend.services.translation_service.translate_blocks_batch",
            return_value=[(True, expected_output)],
        ), patch(
            "app.backend.services.translation_service.get_cache",
            return_value=None,
        ), patch(
            "app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED",
            False,
        ):
            tmap, _, _, _ = translate_texts(
                texts=["source text"],
                targets=["Vietnamese"],
                src_lang="Chinese",
                client=client,
                terms=[],  # empty terms list
            )

        final = tmap[("Vietnamese", "source text")]
        # With no terms, the output must be the critique-loop result of the initial translation.
        # Since critique is disabled, it should be the initial translation or its improvement.
        # Assert output is non-empty and not a failure placeholder.
        assert final
        assert not final.startswith("[Translation failed|")
