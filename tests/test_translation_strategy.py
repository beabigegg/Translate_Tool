"""Tests for dynamic translation strategy module."""

from __future__ import annotations

from app.backend.config import ModelType
from app.backend.services.translation_strategy import (
    TranslationScenario,
    build_strategy,
    detect_translation_scenario,
    scenario_from_profile,
)


def test_detect_translation_scenario_technical_keywords() -> None:
    scenario = detect_translation_scenario(
        filename="SOP_stationA_rev3.docx",
        sample_text="制程參數、扭矩、批號追溯與校正紀錄",
        detected_context="這是技術製程文件，要求可操作且參數準確。",
    )
    assert scenario == TranslationScenario.TECHNICAL_PROCESS


def test_detect_translation_scenario_business_finance_keywords() -> None:
    scenario = detect_translation_scenario(
        filename="q4_forecast_report.xlsx",
        sample_text="毛利率、現金流、ROI、IFRS",
        detected_context="商務金融文件",
    )
    assert scenario == TranslationScenario.BUSINESS_FINANCE


def test_build_strategy_adds_context_and_options_for_general_model() -> None:
    decision = build_strategy(
        base_system_prompt="You are a professional translator.",
        model_type=ModelType.GENERAL.value,
        scenario=TranslationScenario.LEGAL_CONTRACT,
        detected_context="國際法規與合約條款，包含 shall/must。",
        enable_context_flow=True,
    )
    assert decision.scenario == TranslationScenario.LEGAL_CONTRACT
    assert "Document context:" in decision.system_prompt
    assert decision.options_override.get("temperature") == 0.18
    assert decision.cache_variant.endswith("_ctx")


def test_build_strategy_for_translation_model_technical_process_includes_glossary_hint() -> None:
    decision = build_strategy(
        base_system_prompt="",
        model_type=ModelType.TRANSLATION.value,
        scenario=TranslationScenario.TECHNICAL_PROCESS,
        detected_context="",
        enable_context_flow=True,
    )
    assert "work instruction" in decision.system_prompt
    assert decision.options_override.get("temperature") == 0.2
    assert decision.cache_variant.endswith("_glossary")


def test_scenario_from_profile_supports_new_and_legacy_profile_ids() -> None:
    assert scenario_from_profile("technical_process") == TranslationScenario.TECHNICAL_PROCESS
    assert scenario_from_profile("business_finance") == TranslationScenario.BUSINESS_FINANCE
    assert scenario_from_profile("legal") == TranslationScenario.LEGAL_CONTRACT
    assert scenario_from_profile("unknown_profile") is None


def test_build_strategy_legacy_scenario_is_canonicalized() -> None:
    decision = build_strategy(
        base_system_prompt="",
        model_type=ModelType.GENERAL.value,
        scenario=TranslationScenario.BUSINESS_EMAIL,
        detected_context="",
        enable_context_flow=False,
    )
    assert decision.scenario == TranslationScenario.BUSINESS_FINANCE
