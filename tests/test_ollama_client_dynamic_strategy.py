"""Tests for OllamaClient dynamic strategy related behavior."""

from __future__ import annotations

from unittest.mock import patch

from app.backend.clients.ollama_client import OllamaClient
from app.backend.config import ModelType


def test_runtime_options_override_is_merged() -> None:
    client = OllamaClient(model_type=ModelType.GENERAL.value)
    base = client._build_options()
    assert base.get("temperature") == 0.05  # GENERAL type includes temperature at default

    client.set_runtime_options_override({"temperature": 0.25, "repeat_penalty": 1.1})
    merged = client._build_options()
    assert merged["temperature"] == 0.25
    assert merged["repeat_penalty"] == 1.1

    client.set_runtime_options_override(None)
    reset = client._build_options()
    assert reset.get("temperature") == 0.05  # back to model-type default after clearing override


def test_cache_model_key_includes_variant_when_set() -> None:
    client = OllamaClient(model="qwen3.5:4b", profile_id="semiconductor")
    assert client.cache_model_key == "qwen3.5:4b::semiconductor"

    client.set_cache_variant("semiconductor_oi_cp_sop_ctx")
    assert client.cache_model_key == "qwen3.5:4b::semiconductor::scenario=semiconductor_oi_cp_sop_ctx"

    client.set_cache_variant(None)
    assert client.cache_model_key == "qwen3.5:4b::semiconductor"


def test_translation_dedicated_payload_uses_system_prompt_when_present() -> None:
    client = OllamaClient(
        model="dedicated-translation-model:q4",
        model_type=ModelType.TRANSLATION.value,
        system_prompt="Glossary: 切弯脚 -> trim & form",
    )
    payload = client._build_single_translate_payload("切弯脚", "English", "Simplified Chinese")
    assert payload.get("system") == "Glossary: 切弯脚 -> trim & form"

    client_no_system = OllamaClient(
        model="dedicated-translation-model:q4",
        model_type=ModelType.TRANSLATION.value,
        system_prompt="",
    )
    payload_no_system = client_no_system._build_single_translate_payload("切弯脚", "English", "Simplified Chinese")
    assert "system" not in payload_no_system


def test_system_context_merged_into_system_field() -> None:
    """translate_once(system_context=...) merges the reference block into the
    _call_ollama payload's `system` field — parity with the OpenAI-compatible
    client's system-channel placement (context-prefix-bleed-fix, BR-78).
    Mock boundary: _call_ollama (HTTP boundary), never an internal method."""
    client = OllamaClient(model="qwen3.5:4b")
    reference_block = "Previous segments — reference only, do NOT translate or repeat:\nSegment A."

    with patch.object(client, "_call_ollama", return_value=(True, "ok")) as mock_call:
        client.translate_once("Segment B.", "zh-TW", "English", system_context=reference_block)

    payload = mock_call.call_args[0][0]
    assert payload["system"] == reference_block
    assert "Segment A." not in payload["prompt"]
    assert "Segment B." in payload["prompt"]


def test_ollama_outgoing_payload_base_system_prompt_unchanged() -> None:
    """AC-4 (cloud-base-system-prompt-drop): local Ollama's outgoing-payload
    delivery of the base system_prompt must stay byte-for-byte unchanged by
    the additive `system_prompt` kwarg added to OpenAICompatibleClient in
    this change. Captured at the real `_call_ollama` transport-boundary
    call, not merely re-confirming `OllamaClient.__init__` still accepts the
    kwarg (which it already did before this change)."""
    client = OllamaClient(model="qwen3.5:4b", system_prompt="Base prompt for translation.")

    with patch.object(client, "_call_ollama", return_value=(True, "ok")) as mock_call:
        client.translate_once("Segment text.", "French", "English")

    payload = mock_call.call_args[0][0]
    assert payload["system"] == "Base prompt for translation."


def test_system_context_merged_with_existing_system_prompt() -> None:
    """When the client already carries a self.system_prompt (e.g. glossary),
    system_context is appended rather than overwriting it."""
    client = OllamaClient(
        model="dedicated-translation-model:q4",
        model_type=ModelType.TRANSLATION.value,
        system_prompt="Glossary: 切弯脚 -> trim & form",
    )
    reference_block = "Previous segments — reference only, do NOT translate or repeat:\nSegment A."

    with patch.object(client, "_call_ollama", return_value=(True, "ok")) as mock_call:
        client.translate_once("Segment B.", "English", "Simplified Chinese", system_context=reference_block)

    payload = mock_call.call_args[0][0]
    assert "Glossary: 切弯脚 -> trim & form" in payload["system"]
    assert reference_block in payload["system"]
