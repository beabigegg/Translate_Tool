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


def test_technical_process_profile_has_system_prompt() -> None:
    """technical_process profile must have a non-empty system prompt; model_type is now general (R-2)."""
    profile = get_profile("technical_process")
    assert profile.model_type == ModelType.GENERAL.value
    assert profile.system_prompt


def test_business_finance_and_marketing_profiles_exist() -> None:
    """business_finance and marketing_pr profiles exist; model_type is now general (R-2)."""
    assert get_profile("business_finance").model_type == ModelType.GENERAL.value
    assert get_profile("marketing_pr").model_type == ModelType.GENERAL.value
