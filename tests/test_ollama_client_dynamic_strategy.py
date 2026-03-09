"""Tests for OllamaClient dynamic strategy related behavior."""

from __future__ import annotations

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import ModelType


def test_runtime_options_override_is_merged() -> None:
    client = OllamaClient(model_type=ModelType.GENERAL.value)
    base = client._build_options()
    assert "temperature" not in base

    client.set_runtime_options_override({"temperature": 0.25, "repeat_penalty": 1.1})
    merged = client._build_options()
    assert merged["temperature"] == 0.25
    assert merged["repeat_penalty"] == 1.1

    client.set_runtime_options_override(None)
    reset = client._build_options()
    assert "temperature" not in reset


def test_cache_model_key_includes_variant_when_set() -> None:
    client = OllamaClient(model="qwen3.5:4b", profile_id="semiconductor")
    assert client.cache_model_key == "qwen3.5:4b::semiconductor"

    client.set_cache_variant("semiconductor_oi_cp_sop_ctx")
    assert client.cache_model_key == "qwen3.5:4b::semiconductor::scenario=semiconductor_oi_cp_sop_ctx"

    client.set_cache_variant(None)
    assert client.cache_model_key == "qwen3.5:4b::semiconductor"


def test_translation_dedicated_payload_uses_system_prompt_when_present() -> None:
    client = OllamaClient(
        model="demonbyron/HY-MT1.5-7B:Q4_K_M",
        model_type=ModelType.TRANSLATION.value,
        system_prompt="Glossary: 切弯脚 -> trim & form",
    )
    payload = client._build_single_translate_payload("切弯脚", "English", "Simplified Chinese")
    assert payload.get("system") == "Glossary: 切弯脚 -> trim & form"

    client_no_system = OllamaClient(
        model="demonbyron/HY-MT1.5-7B:Q4_K_M",
        model_type=ModelType.TRANSLATION.value,
        system_prompt="",
    )
    payload_no_system = client_no_system._build_single_translate_payload("切弯脚", "English", "Simplified Chinese")
    assert "system" not in payload_no_system
