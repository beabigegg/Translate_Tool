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


# ---------------------------------------------------------------------------
# translate_json system-channel delivery (json-structured-translation-io,
# BR-111). Delivery tests at the real `_call_ollama` transport boundary, not
# signature-only acceptance of the system_context kwarg — an accepted-but-
# discarded kwarg is the exact assignment-without-delivery hazard that
# shipped the cloud-doc-context-summary / cloud-base-system-prompt-drop
# defects. Symmetry with OpenAICompatibleClient is NOT assumed here.
# ---------------------------------------------------------------------------

def test_translate_json_merges_system_prompt_ahead_of_system_context() -> None:
    """BR-111: translate_json must reuse translate_once's merge order —
    system_prompt (BR-109/BR-110) ahead of system_context (BR-78) — asserted
    by ORDER within payload["system"], not mere presence."""
    client = OllamaClient(model="qwen3.5:4b", system_prompt="PROFILE_PROMPT_TOKEN base prompt.")
    segment_context = "SEGMENT_CONTEXT_TOKEN reference-only neighbor block."
    json_payload = '{"text": "Segment B."}'

    with patch.object(client, "_call_ollama", return_value=(True, '{"translation": "x"}')) as mock_call:
        client.translate_json(json_payload, system_context=segment_context)

    payload = mock_call.call_args[0][0]
    assert "system" in payload, "translate_json dropped the system channel entirely"
    merged = payload["system"]
    assert "PROFILE_PROMPT_TOKEN" in merged, f"system_prompt token missing: {merged!r}"
    assert "SEGMENT_CONTEXT_TOKEN" in merged, f"system_context token missing: {merged!r}"
    assert merged.index("PROFILE_PROMPT_TOKEN") < merged.index("SEGMENT_CONTEXT_TOKEN"), (
        "system_prompt must precede system_context in the merged payload['system']"
    )
    assert payload["prompt"] == json_payload, (
        "translate_json must send the JSON envelope AS-IS via the prompt field"
    )


def test_translate_json_system_prompt_alone_still_delivered() -> None:
    """When there is no per-call system_context, client.system_prompt alone
    must still reach payload["system"] on the JSON seam."""
    client = OllamaClient(model="qwen3.5:4b", system_prompt="PROFILE_PROMPT_TOKEN base prompt.")

    with patch.object(client, "_call_ollama", return_value=(True, '{"translation": "x"}')) as mock_call:
        client.translate_json('{"text": "Hello world"}')

    payload = mock_call.call_args[0][0]
    assert payload.get("system") == "PROFILE_PROMPT_TOKEN base prompt."


def test_translate_json_no_system_prompt_or_context_omits_system_key() -> None:
    """When both channels are empty, payload["system"] must be absent
    entirely (parity with _build_no_system_payload's base shape)."""
    client = OllamaClient(model="qwen3.5:4b")

    with patch.object(client, "_call_ollama", return_value=(True, '{"translation": "x"}')) as mock_call:
        client.translate_json('{"text": "Hello world"}')

    payload = mock_call.call_args[0][0]
    assert "system" not in payload
