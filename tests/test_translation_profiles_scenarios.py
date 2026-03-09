"""Tests for user-facing scenario profiles."""

from __future__ import annotations

from app.backend.config import ModelType
from app.backend.translation_profiles import get_profile, list_profiles


def test_user_scenario_profiles_exist() -> None:
    profiles = {p.id: p for p in list_profiles()}
    required = {
        "technical_process",
        "business_finance",
        "legal_contract",
        "marketing_pr",
        "daily_communication",
    }
    assert required.issubset(profiles.keys())


def test_technical_process_profile_uses_translation_model_type() -> None:
    profile = get_profile("technical_process")
    assert profile.model_type == ModelType.TRANSLATION.value
    assert profile.system_prompt


def test_business_finance_and_marketing_profiles_use_translation_model_type() -> None:
    assert get_profile("business_finance").model_type == ModelType.TRANSLATION.value
    assert get_profile("marketing_pr").model_type == ModelType.TRANSLATION.value
