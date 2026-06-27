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

    def test_chunk_overlap_tokens_declared(self):
        """AC-3: CHUNK_OVERLAP_TOKENS must be declared in env-contract.md (BR-47, BR-49)."""
        text = _contract_text()
        assert "CHUNK_OVERLAP_TOKENS" in text, (
            "CHUNK_OVERLAP_TOKENS is not declared in "
            f"{ENV_CONTRACT_PATH}. "
            "Add it to the env-contract table per AC-3 / BR-47 requirement."
        )

    def test_qe_enabled_declared(self):
        """AC-6: QE_ENABLED must be declared in env-contract.md (p2-comet-qe)."""
        text = _contract_text()
        assert "QE_ENABLED" in text, (
            "QE_ENABLED is not declared in "
            f"{ENV_CONTRACT_PATH}. "
            "Add it to the env-contract table per AC-6 / BR-57 requirement."
        )

    def test_qe_model_name_declared(self):
        """AC-6: QE_MODEL_NAME must be declared in env-contract.md (p2-comet-qe)."""
        text = _contract_text()
        assert "QE_MODEL_NAME" in text, (
            "QE_MODEL_NAME is not declared in "
            f"{ENV_CONTRACT_PATH}. "
            "Add it to the env-contract table per AC-6 requirement."
        )

    def test_qe_device_declared(self):
        """AC-6: QE_DEVICE must be declared in env-contract.md (p2-comet-qe)."""
        text = _contract_text()
        assert "QE_DEVICE" in text, (
            "QE_DEVICE is not declared in "
            f"{ENV_CONTRACT_PATH}. "
            "Add it to the env-contract table per AC-6 requirement."
        )

    def test_deepseek_enabled_declared(self):
        """AC-4: DEEPSEEK_ENABLED must be declared in env-contract.md (fallback-chain-cloud-providers)."""
        text = _contract_text()
        assert "DEEPSEEK_ENABLED" in text, (
            "DEEPSEEK_ENABLED is not declared in "
            f"{ENV_CONTRACT_PATH}. "
            "Add it to the env-contract table per AC-4 requirement."
        )

    def test_term_embedding_model_declared(self):
        """AC-env: TERM_EMBEDDING_MODEL must be declared in env-contract.md (term-extraction-db-first)."""
        text = _contract_text()
        assert "TERM_EMBEDDING_MODEL" in text, (
            "TERM_EMBEDDING_MODEL is not declared in "
            f"{ENV_CONTRACT_PATH}. "
            "Add it to the env-contract table per term-extraction-db-first."
        )

    def test_term_embedding_threshold_declared(self):
        """AC-env: TERM_EMBEDDING_THRESHOLD must be declared in env-contract.md (term-extraction-db-first)."""
        text = _contract_text()
        assert "TERM_EMBEDDING_THRESHOLD" in text, (
            "TERM_EMBEDDING_THRESHOLD is not declared in "
            f"{ENV_CONTRACT_PATH}. "
            "Add it to the env-contract table per term-extraction-db-first."
        )

    def test_term_extraction_model_declared(self):
        """AC-env: TERM_EXTRACTION_MODEL must be declared in env-contract.md (term-extraction-db-first)."""
        text = _contract_text()
        assert "TERM_EXTRACTION_MODEL" in text, (
            "TERM_EXTRACTION_MODEL is not declared in "
            f"{ENV_CONTRACT_PATH}. "
            "Add it to the env-contract table per term-extraction-db-first."
        )

    def test_term_embedding_model_wired_in_config(self):
        """TERM_EMBEDDING_MODEL must be read in config.py."""
        from app.backend import config
        assert hasattr(config, "TERM_EMBEDDING_MODEL"), (
            "TERM_EMBEDDING_MODEL constant missing from config.py"
        )
        assert isinstance(config.TERM_EMBEDDING_MODEL, str)
        assert config.TERM_EMBEDDING_MODEL  # non-empty

    def test_term_embedding_threshold_wired_in_config(self):
        """TERM_EMBEDDING_THRESHOLD must be a float in config.py."""
        from app.backend import config
        assert hasattr(config, "TERM_EMBEDDING_THRESHOLD"), (
            "TERM_EMBEDDING_THRESHOLD constant missing from config.py"
        )
        assert isinstance(config.TERM_EMBEDDING_THRESHOLD, float)

    def test_term_extraction_model_wired_in_config(self):
        """TERM_EXTRACTION_MODEL must be read in config.py."""
        from app.backend import config
        assert hasattr(config, "TERM_EXTRACTION_MODEL"), (
            "TERM_EXTRACTION_MODEL constant missing from config.py"
        )
        assert isinstance(config.TERM_EXTRACTION_MODEL, str)
        assert config.TERM_EXTRACTION_MODEL  # non-empty


class TestQeDefault:
    """quality-metrics-gating: AC-3 (QE_ENABLED default true) and AC-4 (QE_RESCORE_THRESHOLD)."""

    def test_qe_enabled_default_true_in_contract(self):
        """AC-3: QE_ENABLED must have default 'true' (not 'false') in env-contract.md."""
        text = _contract_text()
        # Find the QE_ENABLED row and check it says "true" as default (not "false")
        assert "QE_ENABLED" in text, "QE_ENABLED must be in env-contract.md"
        # The contract default column should now say "true"
        # Simple check: the row should not say "false | false" for QE_ENABLED anymore
        # (the default was changed from false→true in quality-metrics-gating AC-3)
        lines = [ln for ln in text.splitlines() if "QE_ENABLED" in ln and "|" in ln]
        assert lines, "QE_ENABLED row not found in env-contract.md table"
        qe_enabled_row = lines[0]
        # After the change the row should contain "true" as default, not "false | false"
        assert "true" in qe_enabled_row.lower(), (
            f"QE_ENABLED row must have default 'true' (AC-3); row: {qe_enabled_row!r}"
        )

    def test_qe_rescore_threshold_declared_in_contract(self):
        """AC-4: QE_RESCORE_THRESHOLD must be declared in env-contract.md."""
        text = _contract_text()
        assert "QE_RESCORE_THRESHOLD" in text, (
            "QE_RESCORE_THRESHOLD is not declared in "
            f"{ENV_CONTRACT_PATH}. "
            "Add it to the env-contract table per quality-metrics-gating AC-4."
        )

    def test_qe_rescore_threshold_in_schema(self):
        """AC-4: QE_RESCORE_THRESHOLD must be in env.schema.json."""
        import json

        schema_path = ENV_CONTRACT_PATH.parent / "env.schema.json"
        assert schema_path.exists(), f"env.schema.json not found at {schema_path}"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        props = schema.get("properties", {})
        assert "QE_RESCORE_THRESHOLD" in props, (
            "QE_RESCORE_THRESHOLD missing from env.schema.json properties"
        )
        assert props["QE_RESCORE_THRESHOLD"].get("default") == "0.5", (
            "QE_RESCORE_THRESHOLD default in schema should be '0.5'"
        )

    def test_qe_rescore_threshold_in_env_template(self):
        """AC-4: QE_RESCORE_THRESHOLD must be in .env.example.template."""
        template_path = ENV_CONTRACT_PATH.parent / ".env.example.template"
        assert template_path.exists(), f".env.example.template not found at {template_path}"
        template_text = template_path.read_text(encoding="utf-8")
        assert "QE_RESCORE_THRESHOLD" in template_text, (
            "QE_RESCORE_THRESHOLD missing from .env.example.template"
        )

    def test_qe_rescore_threshold_wired_in_config(self):
        """AC-4: QE_RESCORE_THRESHOLD must be a float constant in config.py."""
        from app.backend import config

        assert hasattr(config, "QE_RESCORE_THRESHOLD"), (
            "QE_RESCORE_THRESHOLD missing from config.py"
        )
        assert isinstance(config.QE_RESCORE_THRESHOLD, float), (
            f"QE_RESCORE_THRESHOLD must be float; got {type(config.QE_RESCORE_THRESHOLD)}"
        )

    def test_qe_enabled_default_true_in_config(self):
        """AC-3: QE_ENABLED must default to True in config.py (no QE_ENABLED env override)."""
        import os
        from importlib import reload

        prev = os.environ.pop("QE_ENABLED", None)
        try:
            import app.backend.config as cfg
            reload(cfg)
            assert cfg.QE_ENABLED is True, (
                f"QE_ENABLED default must be True (AC-3); got {cfg.QE_ENABLED}"
            )
        finally:
            if prev is not None:
                os.environ["QE_ENABLED"] = prev
            reload(cfg)
