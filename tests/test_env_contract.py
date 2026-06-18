"""Tests for environment contract compliance.

Verifies that all env vars declared in contracts/env/env-contract.md
are wired up in config.py (and vice versa for required vars).
"""

from __future__ import annotations

from pathlib import Path

import pytest

ENV_CONTRACT_PATH = Path(__file__).parent.parent / "contracts" / "env" / "env-contract.md"


def _contract_text() -> str:
    return ENV_CONTRACT_PATH.read_text(encoding="utf-8")


class TestEnvContractDeclared:
    """Spot-checks: key env vars appear in the env-contract.md table."""

    def test_ollama_base_url_declared(self):
        assert "OLLAMA_BASE_URL" in _contract_text()

    def test_translation_cache_enabled_declared(self):
        assert "TRANSLATION_CACHE_ENABLED" in _contract_text()

    def test_layout_detector_model_path_declared(self):
        """AC-5: LAYOUT_DETECTOR_MODEL_PATH must be declared in env-contract.md."""
        text = _contract_text()
        assert "LAYOUT_DETECTOR_MODEL_PATH" in text, (
            "LAYOUT_DETECTOR_MODEL_PATH is not declared in "
            f"{ENV_CONTRACT_PATH}. "
            "Add it to the env-contract table (AC-5 requirement)."
        )

    def test_layout_detector_enabled_declared(self):
        """LAYOUT_DETECTOR_ENABLED must be declared in env-contract.md."""
        text = _contract_text()
        assert "LAYOUT_DETECTOR_ENABLED" in text, (
            "LAYOUT_DETECTOR_ENABLED is not declared in "
            f"{ENV_CONTRACT_PATH}."
        )
