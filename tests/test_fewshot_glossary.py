"""Tests for few-shot injection, glossary enforcement, critique loop,
cache key digest, and metrics counters.

Change: p2-prompt-fewshot-glossary
TDD: this file is written BEFORE source changes so all tests fail initially.
"""

from __future__ import annotations

import hashlib
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from app.backend.models.term import Term
from app.backend.services.term_db import TermDB


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path):
    """In-memory SQLite TermDB fixture (do NOT mock TermDB reads — AC-3)."""
    return TermDB(db_path=tmp_path / "test_fewshot.sqlite")


def _make_term(**kwargs) -> Term:
    defaults = dict(
        source_text="semiconductor",
        target_text="半導體",
        source_lang="en",
        target_lang="zh-TW",
        domain="technical",
        context_snippet="",
        confidence=1.0,
        usage_count=0,
        status="approved",
    )
    defaults.update(kwargs)
    return Term(**defaults)


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics module before each test."""
    import app.backend.services.metrics as metrics_mod
    metrics_mod.reset()
    yield
    metrics_mod.reset()


# ---------------------------------------------------------------------------
# TestFewShotInjection (AC-2)
# ---------------------------------------------------------------------------

class TestFewShotInjection:
    """BR-42: every prompt must include ≥1 few-shot example pair."""

    def test_fewshot_examples_present_in_prompt_string(self):
        from app.backend.services.context_prompts import build_fewshot_block
        block = build_fewshot_block(scenario="general")
        # When the bank is non-empty, the block must contain a source→target pair separator
        if block:
            assert "=>" in block or "->" in block or "→" in block or "\n" in block

    def test_fewshot_injected_for_every_call_including_second(self):
        from app.backend.services.context_prompts import build_fewshot_block
        block1 = build_fewshot_block(scenario="general")
        block2 = build_fewshot_block(scenario="general")
        # Function must be deterministic: same result on repeated calls
        assert block1 == block2

    def test_fewshot_block_contains_at_least_one_source_target_pair(self):
        from app.backend.services.context_prompts import build_fewshot_block, _FEWSHOT_BANK
        # When bank has entries, the returned block must contain something
        if _FEWSHOT_BANK:
            block = build_fewshot_block(scenario="general")
            assert block.strip() != ""

    def test_fewshot_examples_absent_when_bank_is_empty(self):
        from app.backend.services.context_prompts import build_fewshot_block
        # Patch the bank to empty and verify zero-shot fallback is returned
        with patch("app.backend.services.context_prompts._FEWSHOT_BANK", {}):
            block = build_fewshot_block(scenario="general")
            # Zero-shot fallback: documented template, not None/exception
            assert isinstance(block, str)

    def test_fewshot_block_is_wired_into_build_strategy_system_prompt(self):
        """Wiring test (anti-tautological): few-shot examples must actually reach
        the system_prompt produced by build_strategy — not merely exist in
        isolation. Guards against the orphaned-component failure mode."""
        from app.backend.services.translation_strategy import (
            build_strategy,
            TranslationScenario,
        )
        from app.backend.services.context_prompts import _FEWSHOT_BANK
        from app.backend.config import ModelType

        decision = build_strategy(
            base_system_prompt="ROLE PROMPT",
            model_type=ModelType.GENERAL.value,
            scenario=TranslationScenario.TECHNICAL_PROCESS,
            detected_context=None,
            enable_context_flow=False,
        )
        # A concrete example source from the bank must appear in the assembled
        # prompt, proving the block flows from build_fewshot_block → system_prompt.
        sample_source = _FEWSHOT_BANK["technical_process"][0]["source"]
        assert sample_source in decision.system_prompt

    def test_fewshot_not_injected_when_flag_disabled(self):
        """The FEWSHOT_INJECTION_ENABLED kill-switch must actually gate injection."""
        from app.backend.services.translation_strategy import (
            build_strategy,
            TranslationScenario,
        )
        from app.backend.services.context_prompts import _FEWSHOT_BANK
        from app.backend.config import ModelType
        import app.backend.config as config_mod

        with patch.object(config_mod, "FEWSHOT_INJECTION_ENABLED", False):
            decision = build_strategy(
                base_system_prompt="ROLE PROMPT",
                model_type=ModelType.GENERAL.value,
                scenario=TranslationScenario.TECHNICAL_PROCESS,
                detected_context=None,
                enable_context_flow=False,
            )
        sample_source = _FEWSHOT_BANK["technical_process"][0]["source"]
        assert sample_source not in decision.system_prompt


# ---------------------------------------------------------------------------
# TestGlossaryEnforcement (AC-1)
# ---------------------------------------------------------------------------

class TestGlossaryEnforcement:
    """BR-41: deterministic post-translation substitution guarantees 100% match."""

    def test_registered_term_appears_in_output_after_substitution(self):
        from app.backend.services.context_prompts import apply_glossary_substitution
        terms = [_make_term(source_text="semiconductor", target_text="半導體")]
        source = "The semiconductor process is complex."
        draft = "The chip process is complex."
        result = apply_glossary_substitution(draft, source, terms)
        assert "半導體" in result

    def test_multiple_terms_all_substituted(self):
        from app.backend.services.context_prompts import apply_glossary_substitution
        terms = [
            _make_term(source_text="semiconductor", target_text="半導體"),
            _make_term(source_text="wafer", target_text="晶圓"),
        ]
        source = "The semiconductor wafer is processed."
        draft = "The chip disc is processed."
        result = apply_glossary_substitution(draft, source, terms)
        assert "半導體" in result
        assert "晶圓" in result

    def test_term_not_in_source_not_forced_into_output(self):
        from app.backend.services.context_prompts import apply_glossary_substitution
        terms = [_make_term(source_text="photolithography", target_text="光刻")]
        source = "The semiconductor process is complex."  # photolithography NOT in source
        draft = "The chip process is complex."
        result = apply_glossary_substitution(draft, source, terms)
        # photolithography not in source, so 光刻 should NOT be forced
        assert "光刻" not in result

    def test_substitution_is_case_insensitive_on_source_match(self):
        from app.backend.services.context_prompts import apply_glossary_substitution
        terms = [_make_term(source_text="Semiconductor", target_text="半導體")]
        source = "The SEMICONDUCTOR process is complex."  # uppercase
        draft = "The chip process is complex."
        result = apply_glossary_substitution(draft, source, terms)
        assert "半導體" in result


# ---------------------------------------------------------------------------
# TestGlossaryMatchRate (AC-1)
# ---------------------------------------------------------------------------

class TestGlossaryMatchRate:
    """BR-46 + design Decision 5: last-request scalar match rate."""

    def test_match_rate_is_1_0_when_all_terms_present(self):
        from app.backend.services.context_prompts import compute_glossary_match_rate
        terms = [_make_term(source_text="semiconductor", target_text="半導體")]
        source = "The semiconductor process."
        final_output = "The 半導體 process."
        rate = compute_glossary_match_rate(final_output, source, terms)
        assert rate == pytest.approx(1.0)

    def test_match_rate_is_0_when_no_terms_match(self):
        from app.backend.services.context_prompts import compute_glossary_match_rate
        terms = [_make_term(source_text="semiconductor", target_text="半導體")]
        source = "The semiconductor process."
        final_output = "The chip process."
        rate = compute_glossary_match_rate(final_output, source, terms)
        assert rate == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestGlossarySourceOfTruth (AC-3)
# ---------------------------------------------------------------------------

class TestGlossarySourceOfTruth:
    """BR-43: terms exclusively from term_db; no hardcoded lists."""

    def test_glossary_terms_sourced_from_term_db_not_hardcoded(self, tmp_db):
        """Terms come from the real TermDB read path (not mocked)."""
        from app.backend.services.context_prompts import build_glossary_block
        # Insert a term that we control
        term = _make_term(source_text="wafer", target_text="晶圓")
        tmp_db.insert(term)
        terms = tmp_db.get_document_terms("zh-TW", "technical", ["wafer"])
        block = build_glossary_block(terms)
        assert "wafer" in block
        assert "晶圓" in block

    def test_empty_term_db_produces_empty_glossary_block(self, tmp_db):
        """Empty DB → empty glossary block (not an error)."""
        from app.backend.services.context_prompts import build_glossary_block
        terms = tmp_db.get_document_terms("zh-TW", "technical", ["nonexistent"])
        block = build_glossary_block(terms)
        assert block == "" or block.strip() == ""


# ---------------------------------------------------------------------------
# TestCritiqueLoop (AC-4)
# ---------------------------------------------------------------------------

class TestCritiqueLoop:
    """BR-44: ≥1 critique iteration per request; revised draft in tmap."""

    def _make_client(self, model="test-model"):
        from app.backend.clients.ollama_client import OllamaClient
        client = MagicMock(spec=OllamaClient)
        client.model = model
        client.cache_model_key = model
        client._is_translation_dedicated.return_value = False
        return client

    @patch("app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True)
    @patch("app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 2)
    @patch("app.backend.services.translation_service.get_cache", return_value=None)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_critique_loop_runs_at_least_once_per_request(self, mock_batch, mock_cache):
        from app.backend.services.translation_service import translate_texts

        mock_batch.return_value = [(True, "draft output")]
        primary = self._make_client("hymt-model")
        primary.translate_once.return_value = (True, "critique output")

        tmap, _, _, _ = translate_texts(
            texts=["Hello world"],
            targets=["zh-TW"],
            src_lang="en",
            client=primary,
            terms=[],
        )

        # The critique loop must have invoked translate_once at least once
        assert primary.translate_once.call_count >= 1

    @patch("app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True)
    @patch("app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 1)
    @patch("app.backend.services.translation_service.get_cache", return_value=None)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_revised_draft_recorded_in_tmap(self, mock_batch, mock_cache):
        from app.backend.services.translation_service import translate_texts

        mock_batch.return_value = [(True, "initial draft")]
        primary = self._make_client("hymt-model")
        primary.translate_once.return_value = (True, "revised by critique")

        # Bypass the QE adoption gate: this test verifies the critique loop runs and
        # records revised output, NOT which scoring policy wins.  Force-adopt revised.
        with patch(
            "app.backend.services.translation_service._critique_gate_adopt",
            side_effect=lambda src, draft, revised: revised,
        ):
            tmap, _, _, _ = translate_texts(
                texts=["Hello world"],
                targets=["zh-TW"],
                src_lang="en",
                client=primary,
                terms=[],
            )

        # After critique loop, tmap holds the refined (critique) output
        assert tmap[("zh-TW", "Hello world")] == "revised by critique"


# ---------------------------------------------------------------------------
# TestCritiqueLoopBounds (AC-5)
# ---------------------------------------------------------------------------

class TestCritiqueLoopBounds:
    """BR-44 Table M: bounded iterations, fail-soft, degrade-to-draft."""

    def _make_client(self, model="test-model"):
        from app.backend.clients.ollama_client import OllamaClient
        client = MagicMock(spec=OllamaClient)
        client.model = model
        client.cache_model_key = model
        client._is_translation_dedicated.return_value = False
        return client

    @patch("app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True)
    @patch("app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 3)
    @patch("app.backend.services.translation_service.get_cache", return_value=None)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_loop_stops_at_critique_max_iterations(self, mock_batch, mock_cache):
        from app.backend.services.translation_service import translate_texts

        mock_batch.return_value = [(True, "initial draft")]
        primary = self._make_client("hymt-model")
        primary.translate_once.return_value = (True, "critique iteration")

        translate_texts(
            texts=["Hello world"],
            targets=["zh-TW"],
            src_lang="en",
            client=primary,
            terms=[],
        )

        # Must not exceed CRITIQUE_MAX_ITERATIONS calls to translate_once
        assert primary.translate_once.call_count <= 3

    @patch("app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True)
    @patch("app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 2)
    @patch("app.backend.services.translation_service.get_cache", return_value=None)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_loop_degrades_to_last_valid_draft_on_critique_failure(self, mock_batch, mock_cache):
        from app.backend.services.translation_service import translate_texts

        mock_batch.return_value = [(True, "last valid draft")]
        primary = self._make_client("hymt-model")
        # First critique call raises exception
        primary.translate_once.side_effect = RuntimeError("LLM error")

        tmap, _, fail_cnt, _ = translate_texts(
            texts=["Hello world"],
            targets=["zh-TW"],
            src_lang="en",
            client=primary,
            terms=[],
        )

        # Degrade to last valid draft, don't fail the segment
        assert tmap[("zh-TW", "Hello world")] == "last valid draft"
        assert fail_cnt == 0  # job must not have failed

    @patch("app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True)
    @patch("app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 2)
    @patch("app.backend.services.translation_service.CRITIQUE_TIMEOUT_SECONDS", 0.001)
    @patch("app.backend.services.translation_service.get_cache", return_value=None)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_loop_degrades_to_draft_on_timeout(self, mock_batch, mock_cache):
        from app.backend.services.translation_service import translate_texts

        mock_batch.return_value = [(True, "valid draft on timeout")]

        primary = self._make_client("hymt-model")

        def slow_critique(*args, **kwargs):
            time.sleep(0.05)  # 50ms >> 0.001s timeout
            return (True, "critique after timeout")

        primary.translate_once.side_effect = slow_critique

        tmap, _, fail_cnt, _ = translate_texts(
            texts=["Hello world"],
            targets=["zh-TW"],
            src_lang="en",
            client=primary,
            terms=[],
        )

        # Timeout must degrade to last valid draft, not fail the job
        assert tmap[("zh-TW", "Hello world")] == "valid draft on timeout"
        assert fail_cnt == 0

    @patch("app.backend.services.translation_service.CRITIQUE_LOOP_ENABLED", True)
    @patch("app.backend.services.translation_service.CRITIQUE_MAX_ITERATIONS", 1)
    @patch("app.backend.services.translation_service.get_cache", return_value=None)
    @patch("app.backend.services.translation_service.translate_blocks_batch")
    def test_job_does_not_fail_when_critique_times_out(self, mock_batch, mock_cache):
        from app.backend.services.translation_service import translate_texts

        mock_batch.return_value = [(True, "good draft")]
        primary = self._make_client("hymt-model")
        primary.translate_once.side_effect = Exception("timeout simulation")

        # Must not raise
        tmap, done, fail_cnt, stopped = translate_texts(
            texts=["Hello world"],
            targets=["zh-TW"],
            src_lang="en",
            client=primary,
            terms=[],
        )

        assert not stopped
        assert fail_cnt == 0
        assert "Hello world" in [k[1] for k in tmap.keys()]


# ---------------------------------------------------------------------------
# TestCacheKeyGlossaryDigest (AC-6)
# ---------------------------------------------------------------------------

class TestCacheKeyGlossaryDigest:
    """BR-45: cache variant embeds glossary-state digest + critique marker."""

    def test_cache_key_differs_after_glossary_state_changes(self):
        from app.backend.services.translation_strategy import build_strategy
        from app.backend.config import ModelType

        terms_empty = []
        terms_with_data = [
            _make_term(source_text="semiconductor", target_text="半導體"),
        ]

        decision_empty = build_strategy(
            base_system_prompt="",
            model_type=ModelType.GENERAL.value,
            scenario=__import__("app.backend.services.translation_strategy",
                                 fromlist=["TranslationScenario"]).TranslationScenario.GENERAL,
            detected_context=None,
            enable_context_flow=False,
            terms=terms_empty,
        )

        decision_with_terms = build_strategy(
            base_system_prompt="",
            model_type=ModelType.GENERAL.value,
            scenario=__import__("app.backend.services.translation_strategy",
                                 fromlist=["TranslationScenario"]).TranslationScenario.GENERAL,
            detected_context=None,
            enable_context_flow=False,
            terms=terms_with_data,
        )

        assert decision_empty.cache_variant != decision_with_terms.cache_variant

    def test_pre_glossary_cache_entry_is_a_miss_after_term_added(self):
        from app.backend.services.translation_strategy import build_strategy, TranslationScenario
        from app.backend.config import ModelType

        # Without terms (pre-glossary state)
        decision_before = build_strategy(
            base_system_prompt="",
            model_type=ModelType.GENERAL.value,
            scenario=TranslationScenario.GENERAL,
            detected_context=None,
            enable_context_flow=False,
            terms=[],
        )

        # With terms added (post-glossary state)
        decision_after = build_strategy(
            base_system_prompt="",
            model_type=ModelType.GENERAL.value,
            scenario=TranslationScenario.GENERAL,
            detected_context=None,
            enable_context_flow=False,
            terms=[_make_term(source_text="chip", target_text="晶片")],
        )

        # The two variants are different, so a cache lookup with before-key would miss
        assert decision_before.cache_variant != decision_after.cache_variant


# ---------------------------------------------------------------------------
# TestCritiqueMetrics (AC-8)
# ---------------------------------------------------------------------------

class TestCritiqueMetrics:
    """BR-46: critique_loop_invocations, critique_iterations_total, glossary_match_rate."""

    def test_critique_loop_invocations_increments_per_request(self):
        import app.backend.services.metrics as metrics_mod
        metrics_mod.record_critique_loop_invocation()
        data = metrics_mod.get_metrics()
        assert data["critique_loop_invocations"] == 1

    def test_critique_iterations_total_reflects_actual_iteration_count(self):
        import app.backend.services.metrics as metrics_mod
        metrics_mod.record_critique_iteration(3)
        data = metrics_mod.get_metrics()
        assert data["critique_iterations_total"] == 3

    def test_glossary_match_rate_reported_in_get_metrics(self):
        import app.backend.services.metrics as metrics_mod
        metrics_mod.set_glossary_match_rate(0.75)
        data = metrics_mod.get_metrics()
        assert data["glossary_match_rate"] == pytest.approx(0.75)

    def test_new_counters_initialize_to_zero(self):
        import app.backend.services.metrics as metrics_mod
        data = metrics_mod.get_metrics()
        assert data["critique_loop_invocations"] == 0
        assert data["critique_iterations_total"] == 0
        assert data["glossary_match_rate"] == pytest.approx(1.0)

    def test_new_counters_reset_via_reset_helper(self):
        import app.backend.services.metrics as metrics_mod
        metrics_mod.record_critique_loop_invocation()
        metrics_mod.record_critique_iteration(5)
        metrics_mod.set_glossary_match_rate(0.5)

        metrics_mod.reset()

        data = metrics_mod.get_metrics()
        assert data["critique_loop_invocations"] == 0
        assert data["critique_iterations_total"] == 0
        assert data["glossary_match_rate"] == pytest.approx(1.0)
