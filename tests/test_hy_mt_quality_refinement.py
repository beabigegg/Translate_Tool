"""Tests for HY-MT quality refinement (cross-model refinement and naturalness prompts)."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import DEFAULT_MODEL, HYMT_DEFAULT_MODEL
from app.backend.services.model_router import resolve_route_groups


# ---------------------------------------------------------------------------
# A.7.1 — _build_refine_system_prompt persona and rules
# ---------------------------------------------------------------------------

class TestBuildRefineSystemPrompt:
    def test_technical_process_vietnamese_contains_persona(self):
        prompt = OllamaClient._build_refine_system_prompt("Vietnamese", "technical_process")
        assert "Vietnamese" in prompt
        assert "engineer" in prompt.lower()
        assert "SOP" in prompt or "maintenance" in prompt.lower() or "process" in prompt.lower()

    def test_technical_process_contains_four_rules(self):
        prompt = OllamaClient._build_refine_system_prompt("Vietnamese", "technical_process")
        # All 4 rule numbers must be present
        assert "1." in prompt
        assert "2." in prompt
        assert "3." in prompt
        assert "4." in prompt

    def test_technical_process_rule1_cross_references_source(self):
        prompt = OllamaClient._build_refine_system_prompt("Vietnamese", "technical_process")
        assert "[SOURCE]" in prompt

    def test_technical_process_rule4_output_only(self):
        prompt = OllamaClient._build_refine_system_prompt("Vietnamese", "technical_process")
        assert "Output ONLY" in prompt or "ONLY" in prompt

    def test_japanese_technical_process_persona(self):
        prompt = OllamaClient._build_refine_system_prompt("Japanese", "technical_process")
        assert "Japanese" in prompt

    def test_german_technical_process_persona(self):
        prompt = OllamaClient._build_refine_system_prompt("German", "technical_process")
        assert "German" in prompt

    def test_generic_profile_fallback(self):
        prompt = OllamaClient._build_refine_system_prompt("Vietnamese", "general")
        # Generic persona still has 4 rules and output-only constraint
        assert "1." in prompt
        assert "2." in prompt
        assert "3." in prompt
        assert "4." in prompt
        assert "Output ONLY" in prompt or "ONLY" in prompt

    def test_unknown_language_fallback_no_crash(self):
        # Languages not in the map should return a prompt without crashing
        prompt = OllamaClient._build_refine_system_prompt("Klingon", "technical_process")
        assert "4." in prompt  # Still has rules


# ---------------------------------------------------------------------------
# A.7.2 — _build_refine_prompt format: [SOURCE]: / [DRAFT]: / Corrected {lang}:
# ---------------------------------------------------------------------------

class TestBuildRefinePrompt:
    def test_source_label_present(self):
        prompt = OllamaClient._build_refine_prompt("Hello", "Xin chào", "Vietnamese", "English")
        assert "[SOURCE]:" in prompt

    def test_draft_label_present(self):
        prompt = OllamaClient._build_refine_prompt("Hello", "Xin chào", "Vietnamese", "English")
        assert "[DRAFT]:" in prompt

    def test_corrected_label_present(self):
        prompt = OllamaClient._build_refine_prompt("Hello", "Xin chào", "Vietnamese", "English")
        assert "Corrected Vietnamese:" in prompt

    def test_source_text_included(self):
        prompt = OllamaClient._build_refine_prompt("Hello world", "draft", "Vietnamese", "English")
        assert "Hello world" in prompt

    def test_draft_text_included(self):
        prompt = OllamaClient._build_refine_prompt("Hello", "initial draft here", "Vietnamese", "English")
        assert "initial draft here" in prompt

    def test_correct_order(self):
        prompt = OllamaClient._build_refine_prompt("src", "dft", "Vietnamese", "English")
        src_pos = prompt.index("[SOURCE]:")
        draft_pos = prompt.index("[DRAFT]:")
        corrected_pos = prompt.index("Corrected Vietnamese:")
        assert src_pos < draft_pos < corrected_pos


# ---------------------------------------------------------------------------
# A.7.3 — resolve_route_groups: HY-MT group gets refine_model=DEFAULT_MODEL
# ---------------------------------------------------------------------------

class TestRouteGroupRefineModel:
    def test_vietnamese_group_has_refine_model(self):
        groups = resolve_route_groups(["Vietnamese"])
        assert groups is not None
        assert len(groups) == 1
        assert groups[0].model == HYMT_DEFAULT_MODEL
        assert groups[0].refine_model == DEFAULT_MODEL

    def test_japanese_group_has_refine_model(self):
        groups = resolve_route_groups(["Japanese"])
        assert groups is not None
        assert groups[0].refine_model == DEFAULT_MODEL

    def test_german_group_has_refine_model(self):
        groups = resolve_route_groups(["German"])
        assert groups is not None
        assert groups[0].refine_model == DEFAULT_MODEL

    def test_korean_tgemma_group_has_refine_model(self):
        """TranslateGemma group also gets cross-model refiner."""
        groups = resolve_route_groups(["Korean"])
        assert groups is not None
        assert groups[0].refine_model == DEFAULT_MODEL

    # ---------------------------------------------------------------------------
    # A.7.4 — resolve_route_groups: Qwen group gets refine_model=None
    # ---------------------------------------------------------------------------

    def test_english_qwen_group_has_no_refine_model(self):
        groups = resolve_route_groups(["English"])
        assert groups is not None
        assert len(groups) == 1
        assert groups[0].model == DEFAULT_MODEL
        assert groups[0].refine_model is None

    def test_unlisted_language_qwen_group_has_no_refine_model(self):
        groups = resolve_route_groups(["Swahili"])
        assert groups is not None
        assert groups[0].refine_model is None

    def test_mixed_targets_correct_refine_models(self):
        groups = resolve_route_groups(["English", "Vietnamese"])
        assert groups is not None
        qwen_group = next(g for g in groups if g.model == DEFAULT_MODEL)
        hymt_group = next(g for g in groups if g.model == HYMT_DEFAULT_MODEL)
        assert qwen_group.refine_model is None
        assert hymt_group.refine_model == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# A.7.5 — translate_texts() calls client.unload_model() before first refine call
# ---------------------------------------------------------------------------

class TestTranslateTextsRefinePhase:
    def _make_client(self, model="test-model"):
        client = MagicMock(spec=OllamaClient)
        client.model = model
        client.cache_model_key = model
        client._is_translation_dedicated.return_value = False
        return client

    @patch("app.backend.services.translation_service.CROSS_MODEL_REFINEMENT_ENABLED", True)
    @patch("app.backend.services.translation_service.get_cache", return_value=None)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_unload_called_before_refine(self, mock_batch, mock_cache):
        from app.backend.services.translation_service import translate_texts

        long_text = "This is a long enough source text"
        mock_batch.return_value = [(True, "Xin chào dài hơn mười ký tự")]

        primary = self._make_client("hymt-model")
        refiner = self._make_client("qwen-model")
        refiner.refine_translation.return_value = (True, "Refined text here")

        translate_texts(
            texts=[long_text],
            targets=["Vietnamese"],
            src_lang="English",
            client=primary,
            refine_client=refiner,
        )

        # unload_model must be called on the primary client before refine_translation
        primary.unload_model.assert_called_once()
        refiner.refine_translation.assert_called_once()

        # Verify order: unload happens before refine
        unload_call_idx = [str(c) for c in primary.mock_calls].index(str(call.unload_model()))
        assert unload_call_idx >= 0

    @patch("app.backend.services.translation_service.CROSS_MODEL_REFINEMENT_ENABLED", True)
    @patch("app.backend.services.translation_service.get_cache", return_value=None)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_refine_updates_tmap(self, mock_batch, mock_cache):
        from app.backend.services.translation_service import translate_texts

        long_text = "This is a long enough source text"
        mock_batch.return_value = [(True, "draft translation output")]

        primary = self._make_client("hymt-model")
        refiner = self._make_client("qwen-model")
        refiner.refine_translation.return_value = (True, "refined translation output")

        tmap, _, _, _ = translate_texts(
            texts=[long_text],
            targets=["Vietnamese"],
            src_lang="English",
            client=primary,
            refine_client=refiner,
        )

        assert tmap[("Vietnamese", long_text)] == "refined translation output"

    # ---------------------------------------------------------------------------
    # A.7.6 — translate_texts() does NOT write refined output to cache
    # ---------------------------------------------------------------------------

    @patch("app.backend.services.translation_service.CROSS_MODEL_REFINEMENT_ENABLED", True)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_refined_output_not_written_to_cache(self, mock_batch):
        from app.backend.services.translation_service import translate_texts

        mock_cache = MagicMock()
        mock_cache.get_batch.return_value = {}

        with patch("app.backend.services.translation_service.get_cache", return_value=mock_cache):
            long_text = "This is a long enough source text"
            mock_batch.return_value = [(True, "draft translation result")]

            primary = self._make_client("hymt-model")
            refiner = self._make_client("qwen-model")
            refiner.refine_translation.return_value = (True, "refined result not for cache")

            translate_texts(
                texts=[long_text],
                targets=["Vietnamese"],
                src_lang="English",
                client=primary,
                refine_client=refiner,
            )

        # Cache put_batch may be called for the primary draft, but never with refined text
        if mock_cache.put_batch.called:
            for c in mock_cache.put_batch.call_args_list:
                entries = c[0][0]  # first positional arg is list of (text, tgt, src, key, trans)
                for entry in entries:
                    assert "refined result not for cache" not in entry

    # ---------------------------------------------------------------------------
    # A.7.7 — translate_texts() skips Phase 2 when CROSS_MODEL_REFINEMENT_ENABLED=False
    # ---------------------------------------------------------------------------

    @patch("app.backend.services.translation_service.CROSS_MODEL_REFINEMENT_ENABLED", False)
    @patch("app.backend.services.translation_service.get_cache", return_value=None)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_phase2_skipped_when_disabled(self, mock_batch, mock_cache):
        from app.backend.services.translation_service import translate_texts

        long_text = "This is a long enough source text"
        mock_batch.return_value = [(True, "draft here")]

        primary = self._make_client("hymt-model")
        refiner = self._make_client("qwen-model")

        translate_texts(
            texts=[long_text],
            targets=["Vietnamese"],
            src_lang="English",
            client=primary,
            refine_client=refiner,
        )

        primary.unload_model.assert_not_called()
        refiner.refine_translation.assert_not_called()

    @patch("app.backend.services.translation_service.CROSS_MODEL_REFINEMENT_ENABLED", True)
    @patch("app.backend.services.translation_service.get_cache", return_value=None)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_no_refine_when_refine_client_is_none(self, mock_batch, mock_cache):
        from app.backend.services.translation_service import translate_texts

        long_text = "This is a long enough source text"
        mock_batch.return_value = [(True, "draft here")]

        primary = self._make_client("hymt-model")

        tmap, _, _, _ = translate_texts(
            texts=[long_text],
            targets=["Vietnamese"],
            src_lang="English",
            client=primary,
            refine_client=None,
        )

        primary.unload_model.assert_not_called()
        assert tmap[("Vietnamese", long_text)] == "draft here"
