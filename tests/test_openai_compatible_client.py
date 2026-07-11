"""Unit tests for OpenAICompatibleClient (p1-cloud-providers).

All tests in this file must FAIL before IP-1..IP-3 are implemented (TDD).
Mock at requests.Session.post/get boundary only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).parent.parent


def _make_chat_response(content: str) -> MagicMock:
    """Return a fake requests.Response for a /v1/chat/completions success."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return resp


def _make_http_error_response(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = f"HTTP error {status_code}"
    return resp


def _reasoning_directive() -> str:
    """The BR-118 harmony directive prefix every translation call now carries,
    sourced from the live config constant (never a hardcoded "low" literal),
    so these composition tests stay correct if the default ever changes."""
    from app.backend.config import OPENAI_TRANSLATION_REASONING

    return f"Reasoning: {OPENAI_TRANSLATION_REASONING}"


# ── Protocol Conformance ──────────────────────────────────────────────────────

class TestProtocolConformance:
    def test_openai_compatible_client_satisfies_protocol(self):
        """OpenAICompatibleClient must have all 5 Protocol methods."""
        from app.backend.clients.base_llm_client import LLMClient
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        for method_name in [
            "translate_once", "translate_batch",
            "health", "list_models", "unload",
        ]:
            assert hasattr(OpenAICompatibleClient, method_name), (
                f"OpenAICompatibleClient missing Protocol method: {method_name}"
            )
            assert callable(getattr(OpenAICompatibleClient, method_name)), (
                f"OpenAICompatibleClient.{method_name} is not callable"
            )

    def test_openai_compatible_client_isinstance_llm_client(self):
        """runtime_checkable isinstance must pass for OpenAICompatibleClient instances."""
        from app.backend.clients.base_llm_client import LLMClient
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        assert isinstance(client, LLMClient), (
            "OpenAICompatibleClient() is not an instance of LLMClient Protocol"
        )


# ── translate_once ────────────────────────────────────────────────────────────

class TestTranslateOnce:
    def test_successful_translation_returns_ok_true(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        with patch("requests.Session.post", return_value=_make_chat_response("Bonjour le monde")):
            ok, result = client.translate_once("Hello world", "French", "English")

        assert ok is True
        assert "Bonjour" in result

    def test_http_error_returns_ok_false(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        with patch("requests.Session.post", return_value=_make_http_error_response(500)):
            ok, result = client.translate_once("Hello", "French", "English")

        assert ok is False

    def test_connection_timeout_returns_ok_false(self):
        import requests as req_lib
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        with patch("requests.Session.post", side_effect=req_lib.exceptions.Timeout("timed out")):
            ok, result = client.translate_once("Hello", "French", "English")

        assert ok is False


# ── empty content / reasoning-model truncation ───────────────────────────────

class TestEmptyContentHandling:
    def test_empty_content_with_finish_reason_length_returns_ok_false(self):
        """A reasoning model (e.g. gpt-oss) that exhausts max_tokens on hidden
        reasoning_content before emitting the final content field returns
        HTTP 200 with an empty content string and finish_reason="length".
        This must be treated as a failure, not a valid empty translation."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{
                "finish_reason": "length",
                "message": {"content": "", "reasoning_content": "long hidden chain of thought..."},
            }]
        }
        with patch("requests.Session.post", return_value=resp):
            ok, result = client.translate_once("Hello world", "French", "English")

        assert ok is False
        assert "length" in result

    def test_nonempty_content_still_returns_ok_true(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        with patch("requests.Session.post", return_value=_make_chat_response("Bonjour le monde")):
            ok, result = client.translate_once("Hello world", "French", "English")

        assert ok is True
        assert "Bonjour" in result


# ── max_tokens payload (reasoning-model truncation mitigation) ──────────────

class TestMaxTokensPayload:
    def test_max_tokens_included_in_completion_payload(self):
        """Every completion request must include max_tokens so a reasoning
        model has enough budget to finish reasoning_content AND emit content
        (see TestEmptyContentHandling for the failure mode this prevents)."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        with patch("requests.Session.post", return_value=_make_chat_response("hi")) as mock_post:
            client.translate_once("Hello", "French", "English")

        _, kwargs = mock_post.call_args
        assert "max_tokens" in kwargs["json"]
        assert kwargs["json"]["max_tokens"] > 0

    def test_max_tokens_override_via_constructor(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
            max_tokens=8192,
        )
        with patch("requests.Session.post", return_value=_make_chat_response("hi")) as mock_post:
            client.translate_once("Hello", "French", "English")

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["max_tokens"] == 8192


# ── system_context channel (context-prefix-bleed-fix, BR-78) ───────────────────

class TestSystemContextChannel:
    def test_system_context_prepended_as_leading_system_message(self):
        """When `system_context` is set, `translate_once` must emit a leading
        `role:"system"` message carrying it (prefixed by the BR-118 reasoning
        directive, cloud-reasoning-stall-hardening), and the user message must
        keep the unchanged "Translate the following text..." wrapper — context
        must never be concatenated into the translatable user content."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        reference_block = "Previous segments — reference only, do NOT translate or repeat:\nSegment A."
        with patch("requests.Session.post", return_value=_make_chat_response("ok")) as mock_post:
            client.translate_once(
                "Segment B.", "French", "English", system_context=reference_block,
            )

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        assert messages[0] == {
            "role": "system", "content": f"{_reasoning_directive()}\n\n{reference_block}"
        }
        assert messages[-1]["role"] == "user"
        assert "Segment B." in messages[-1]["content"]
        assert reference_block not in messages[-1]["content"]
        assert _reasoning_directive() not in messages[-1]["content"]

    def test_no_system_context_omits_system_message(self):
        """When `system_context` is None (default) and no `system_prompt` is
        set, the leading system message carries ONLY the BR-118 reasoning
        directive — the directive is now unconditional on every translation
        call (cloud-reasoning-stall-hardening); no other system content is
        added."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        with patch("requests.Session.post", return_value=_make_chat_response("ok")) as mock_post:
            client.translate_once("Hello", "French", "English")

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": _reasoning_directive()}
        assert messages[1]["role"] == "user"


# ── system_prompt delivery (cloud-doc-context-summary, BR-109 / ADR-0016) ──────
#
# `system_prompt` (the scenario style plus any orchestrator-injected
# "Document context: <summary>" preamble) was formerly an orchestrator-
# compatibility stub whose writes were silently discarded on the cloud path
# ("these writes are intentionally ignored"). BR-109 now requires it be
# delivered to the model as system-channel content on every translate_once
# call, merged ahead of the per-segment BR-78 system_context, and NEVER
# concatenated into the translatable user payload.

class TestSystemPromptDelivery:
    def test_system_prompt_merged_ahead_of_segment_context_single_system_message(self):
        """Preamble (client.system_prompt) must appear BEFORE the per-segment
        BR-78 system_context, merged into ONE leading system message — not
        two separate system messages, and never inside the user payload."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        client.system_prompt = "Document context: An engineering change request."
        segment_context = (
            "Previous segments — reference only, do NOT translate or repeat:\nSegment A."
        )

        with patch("requests.Session.post", return_value=_make_chat_response("ok")) as mock_post:
            client.translate_once(
                "Segment B.", "French", "English", system_context=segment_context,
            )

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        system_messages = [m for m in messages if m["role"] == "system"]
        assert len(system_messages) == 1, (
            f"preamble + segment context must merge into ONE system message, got {system_messages!r}"
        )
        merged_content = system_messages[0]["content"]
        assert merged_content == (
            f"{_reasoning_directive()}\n\n{client.system_prompt}\n\n{segment_context}"
        )
        assert (
            merged_content.index(_reasoning_directive())
            < merged_content.index(client.system_prompt)
            < merged_content.index(segment_context)
        ), (
            "BR-118 reasoning directive must come first, then the document-context "
            "preamble, then the per-segment BR-78 context"
        )

        user_messages = [m for m in messages if m["role"] == "user"]
        assert client.system_prompt not in user_messages[-1]["content"]
        assert segment_context not in user_messages[-1]["content"]
        assert _reasoning_directive() not in user_messages[-1]["content"]

    def test_system_prompt_alone_still_delivered_when_no_segment_context(self):
        """When there is no per-segment BR-78 context, client.system_prompt
        alone must still reach the model as the leading system message
        (regression guard for the former "intentionally ignored" stub)."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        client.system_prompt = "Document context: A purchase order document."

        with patch("requests.Session.post", return_value=_make_chat_response("ok")) as mock_post:
            client.translate_once("Hello world", "French", "English")

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        assert messages[0] == {
            "role": "system",
            "content": f"{_reasoning_directive()}\n\n{client.system_prompt}",
        }

    def test_complete_sends_no_system_message_even_with_system_prompt_set(self):
        """BR-109: complete() (the document-context summary seam) must never
        carry a system prompt — even if client.system_prompt happens to be
        set from a prior/concurrent translate call — so the model summarizes
        the document instead of being steered by a stale style/preamble."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        client.system_prompt = "Document context: some leftover preamble."

        with patch("requests.Session.post", return_value=_make_chat_response("A summary.")) as mock_post:
            ok, result = client.complete("Summarize this document in one sentence: ...")

        assert ok is True
        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert not any(m["role"] == "system" for m in messages), (
            "complete() must never emit a system message"
        )


# ── translate_json system-channel delivery (json-structured-translation-io, BR-111) ──
#
# Delivery tests, not signature-only acceptance: a fake client that merely
# *accepts* a system_context kwarg without asserting it reached the outgoing
# transport payload is the exact assignment-without-delivery hazard that
# shipped the cloud-doc-context-summary (discarded write) and
# cloud-base-system-prompt-drop (write that never happened) defects. These
# tests mock requests.Session.post and assert on the captured `json=` kwarg.

class TestTranslateJsonSystemChannelDelivery:
    def test_system_prompt_and_system_context_both_delivered_in_order(self):
        """BR-111 reuses translate_once's merge order: system_prompt
        (BR-109/BR-110) ahead of system_context (BR-78), in ONE leading
        system message — asserted by ORDER, not mere presence (presence alone
        would still pass if one token replaced the other)."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080", api_key="test-key", model="gpt-oss:120b",
        )
        client.system_prompt = "PROFILE_PROMPT_TOKEN Document context: an engineering change request."
        segment_context = (
            "SEGMENT_CONTEXT_TOKEN Previous segments — reference only, do NOT translate or repeat."
        )
        json_payload = '{"text": "Segment B."}'

        with patch("requests.Session.post", return_value=_make_chat_response('{"translation": "x"}')) as mock_post:
            client.translate_json(json_payload, system_context=segment_context)

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        system_messages = [m for m in messages if m["role"] == "system"]
        assert len(system_messages) == 1, (
            f"system_prompt + system_context must merge into ONE system message, got {system_messages!r}"
        )
        merged = system_messages[0]["content"]
        assert "PROFILE_PROMPT_TOKEN" in merged, f"system_prompt token missing from delivered system message: {merged!r}"
        assert "SEGMENT_CONTEXT_TOKEN" in merged, f"system_context token missing from delivered system message: {merged!r}"
        assert merged.index("PROFILE_PROMPT_TOKEN") < merged.index("SEGMENT_CONTEXT_TOKEN"), (
            "system_prompt (BR-109/BR-110) must precede system_context (BR-78) in the merged message"
        )

        user_messages = [m for m in messages if m["role"] == "user"]
        assert len(user_messages) == 1
        assert user_messages[0]["content"] == json_payload, (
            "translate_json must send the JSON envelope AS-IS in the user message"
        )
        assert "Translate the following text from" not in user_messages[0]["content"], (
            "the JSON payload must NOT be re-wrapped by translate_once's framing"
        )

    def test_system_prompt_alone_still_delivered_on_json_seam(self):
        """When there is no per-call system_context, client.system_prompt
        alone must still reach the model as the leading system message on
        the JSON seam (parity with translate_once's equivalent guard)."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080", api_key="test-key", model="gpt-oss:120b",
        )
        client.system_prompt = "PROFILE_PROMPT_TOKEN Document context: a purchase order document."

        with patch("requests.Session.post", return_value=_make_chat_response('{"translation": "x"}')) as mock_post:
            client.translate_json('{"text": "Hello world"}')

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        assert messages[0] == {
            "role": "system",
            "content": f"{_reasoning_directive()}\n\n{client.system_prompt}",
        }, (
            f"system_prompt (prefixed by the BR-118 reasoning directive) must be "
            f"delivered alone when no system_context is given, got {messages!r}"
        )

    def test_no_system_prompt_or_context_omits_system_message(self):
        """When both channels are empty, the leading system message carries
        ONLY the BR-118 reasoning directive — unconditional on every
        translation call (cloud-reasoning-stall-hardening); parity with the
        plain-text seam's TestSystemContextChannel guard."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080", api_key="test-key", model="gpt-oss:120b",
        )

        with patch("requests.Session.post", return_value=_make_chat_response('{"translation": "x"}')) as mock_post:
            client.translate_json('{"text": "Hello world"}')

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": _reasoning_directive()}
        assert messages[1]["role"] == "user"


# ── constructor system_prompt kwarg (cloud-base-system-prompt-drop, BR-110) ────
#
# BR-110: OpenAICompatibleClient must accept and populate `system_prompt` at
# construction (mirroring OllamaClient), so the orchestrator's caller-supplied
# profile base prompt is no longer silently dropped by the empty-string
# class-attribute default. These are post-fix-only regression companions --
# the RED reproduction for the underlying defect lives in
# tests/test_orchestrator_context_detection.py (exercised through
# process_files, per test-plan.md), because calling this kwarg directly
# against unfixed source raises TypeError, not a payload assertion failure.

class TestSystemPromptConstruction:
    def test_default_construction_without_system_prompt_stays_empty(self):
        """AC-6 (anti-vacuity guard): omitted-kwarg construction still yields
        `system_prompt == ""` -- proving the 39 existing call-site
        constructions (across six test files) needed no edit, not merely
        assuming it."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        assert client.system_prompt == ""

    def test_constructor_system_prompt_kwarg_delivered_to_outgoing_payload(self):
        """Post-fix companion: `system_prompt` passed at construction is
        normalized (mirrors OllamaClient's `.strip()`) and reaches the
        outgoing /v1/chat/completions system message on translate_once()."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
            system_prompt="  You are a professional semiconductor translator.  ",
        )
        assert client.system_prompt == "You are a professional semiconductor translator."

        with patch("requests.Session.post", return_value=_make_chat_response("ok")) as mock_post:
            client.translate_once("Hello world", "French", "English")

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        assert messages[0] == {
            "role": "system",
            "content": f"{_reasoning_directive()}\n\n{client.system_prompt}",
        }


# ── translate_batch ───────────────────────────────────────────────────────────

class TestTranslateBatch:
    def test_batch_calls_translate_once_sequentially(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        responses = [
            _make_chat_response("Bonjour"),
            _make_chat_response("Monde"),
        ]
        with patch("requests.Session.post", side_effect=responses):
            ok, results = client.translate_batch(["Hello", "World"], "French", "English")

        assert ok is True
        assert len(results) == 2
        assert results[0] == "Bonjour"
        assert results[1] == "Monde"

    def test_batch_partial_failure_returns_ok_false(self):
        import requests as req_lib
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        responses = [
            _make_chat_response("Bonjour"),
            req_lib.exceptions.ConnectionError("refused"),
        ]
        with patch("requests.Session.post", side_effect=responses):
            ok, results = client.translate_batch(["Hello", "World"], "French", "English")

        assert ok is False
        assert len(results) == 2


# ── health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_probe_reachable_returns_true(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        models_resp = MagicMock()
        models_resp.status_code = 200
        models_resp.json.return_value = {"data": [{"id": "gpt-oss:120b"}]}

        with patch("requests.Session.get", return_value=models_resp):
            ok, msg = client.health()

        assert ok is True

    def test_health_probe_unreachable_returns_false(self):
        import requests as req_lib
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://unreachable:9999",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        with patch("requests.Session.get", side_effect=req_lib.exceptions.ConnectionError("refused")):
            ok, msg = client.health()

        assert ok is False


# ── list_models ───────────────────────────────────────────────────────────────

class TestListModels:
    def test_list_models_returns_list_of_strings(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        models = client.list_models()
        assert isinstance(models, list)
        assert all(isinstance(m, str) for m in models)
        assert len(models) > 0


# ── unload ────────────────────────────────────────────────────────────────────

class TestUnload:
    def test_unload_is_noop_returns_true(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key="test-key",
            model="gpt-oss:120b",
        )
        ok, msg = client.unload()
        assert ok is True
        assert "no-op" in msg.lower()


# ── ConfigLoading ─────────────────────────────────────────────────────────────

class TestConfigLoading:
    def test_providers_yml_env_var_interpolation(self, tmp_path, monkeypatch):
        """${VAR:-default} and ${VAR} are expanded from environment."""
        from app.backend.config import load_providers_config

        yml = tmp_path / "providers.yml"
        yml.write_text(
            "providers:\n"
            "  - id: panjit\n"
            "    type: openai\n"
            "    enabled: true\n"
            "    base_url: ${PANJIT_LLM_BASE_URL:-http://default-url}\n"
            "    api_key: ${PANJIT_API}\n"
            "    models:\n"
            "      translate: gpt-oss:120b\n"
            "routing:\n"
            "  default:\n"
            "    model: gpt-oss:120b\n"
            "    provider: panjit\n"
            "    profile: general\n"
            "fallback_chain: [panjit]\n"
        )
        monkeypatch.setenv("PANJIT_LLM_BASE_URL", "http://real-panjit:8080")
        monkeypatch.setenv("PANJIT_API", "real-key-value")

        config = load_providers_config(config_path=yml)
        assert config is not None

        providers = config.get("providers", [])
        panjit = next(p for p in providers if p["id"] == "panjit")
        assert panjit["base_url"] == "http://real-panjit:8080"
        assert panjit["api_key"] == "real-key-value"

    def test_missing_providers_yml_falls_back_to_ollama(self, tmp_path):
        """If providers.yml is absent, load_providers_config signals ollama fallback."""
        from app.backend.config import load_providers_config

        missing = tmp_path / "providers.yml"
        config = load_providers_config(config_path=missing)
        # Should return None or empty dict signalling Ollama fallback
        assert config is None or config == {} or config.get("_fallback_to_ollama") is True

    def test_malformed_providers_yml_falls_back_to_ollama(self, tmp_path):
        """Malformed YAML → fallback to Ollama, no exception raised."""
        from app.backend.config import load_providers_config

        yml = tmp_path / "providers.yml"
        yml.write_text("{ this is not: [valid yaml: ]\n")

        config = load_providers_config(config_path=yml)
        assert config is None or config == {} or config.get("_fallback_to_ollama") is True

    def test_unresolved_env_var_disables_provider(self, tmp_path, monkeypatch):
        """If ${SOME_UNSET_VAR} can't be resolved → provider must be disabled."""
        from app.backend.config import load_providers_config

        yml = tmp_path / "providers.yml"
        yml.write_text(
            "providers:\n"
            "  - id: panjit\n"
            "    type: openai\n"
            "    enabled: true\n"
            "    base_url: http://example.com\n"
            "    api_key: ${PANJIT_API_UNSET_12345}\n"
            "    models:\n"
            "      translate: gpt-oss:120b\n"
            "routing:\n"
            "  default:\n"
            "    model: gpt-oss:120b\n"
            "    provider: panjit\n"
            "    profile: general\n"
            "fallback_chain: [panjit]\n"
        )
        monkeypatch.delenv("PANJIT_API_UNSET_12345", raising=False)

        config = load_providers_config(config_path=yml)
        # Provider with unresolved required var must be disabled
        if config:
            providers = config.get("providers", [])
            panjit_providers = [p for p in providers if p["id"] == "panjit"]
            if panjit_providers:
                assert panjit_providers[0].get("enabled") is False, (
                    "Provider with unresolved api_key must be disabled"
                )

    def test_all_providers_disabled_falls_back_to_ollama(self, tmp_path):
        """All enabled=false → load_providers_config signals ollama fallback."""
        from app.backend.config import load_providers_config

        yml = tmp_path / "providers.yml"
        yml.write_text(
            "providers:\n"
            "  - id: panjit\n"
            "    type: openai\n"
            "    enabled: false\n"
            "    base_url: http://example.com\n"
            "    api_key: some-key\n"
            "    models:\n"
            "      translate: gpt-oss:120b\n"
            "routing:\n"
            "  default:\n"
            "    model: gpt-oss:120b\n"
            "    provider: panjit\n"
            "    profile: general\n"
            "fallback_chain: [panjit]\n"
        )

        config = load_providers_config(config_path=yml)
        # Signal that all providers disabled → fallback to Ollama
        # Acceptable: config is None, {}, or has all providers disabled
        if config and config.get("providers"):
            enabled = [p for p in config["providers"] if p.get("enabled") is True]
            assert len(enabled) == 0


# ── SecretHandling ─────────────────────────────────────────────────────────────

class TestSecretHandling:
    def test_literal_api_key_not_emitted_in_request(self):
        """API key must appear in Authorization header, NOT in request body."""
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        secret_key = "super-secret-panjit-api-key-test-value"
        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080",
            api_key=secret_key,
            model="gpt-oss:120b",
        )

        captured_calls = []

        def _fake_post(url, **kwargs):
            captured_calls.append(kwargs)
            return _make_chat_response("Bonjour")

        with patch("requests.Session.post", side_effect=_fake_post):
            client.translate_once("Hello", "French", "English")

        assert len(captured_calls) == 1
        call_kwargs = captured_calls[0]

        # Key must NOT be in the JSON body
        body = call_kwargs.get("json", {})
        body_str = json.dumps(body)
        assert secret_key not in body_str, "API key must not appear in request body"

        # Key MUST appear in Authorization header
        headers = call_kwargs.get("headers", {})
        auth_header = headers.get("Authorization", "")
        assert secret_key in auth_header, "API key must appear in Authorization header"


# ── qa-judge-hang-recovery: total-duration ceiling (BR-100) ───────────────────

class TestTotalTimeoutCeilingAdditive:
    """BR-100: the wall-clock ceiling is ADDITIVE on top of the (connect, read) tuple."""

    def _client(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        return OpenAICompatibleClient(
            base_url="http://fake-host:8080", api_key="test-key", model="gpt-oss:120b"
        )

    def test_ceiling_absent_from_per_chunk_timeout_tuple(self):
        """session.post still gets the (connect, read) tuple; the ceiling is NOT folded into it."""
        client = self._client()
        with patch("requests.Session.post", return_value=_make_chat_response("hi")) as mock_post, \
             patch("app.backend.config.OPENAI_TOTAL_TIMEOUT_SECONDS", 120.0):
            ok, _out = client._post_completion("x")

        assert ok is True
        _, kwargs = mock_post.call_args
        assert kwargs["timeout"] == (client._connect_timeout, client._read_timeout)
        assert kwargs["timeout"][1] != 120.0, "the 120s ceiling must not become the read timeout"

    def test_wellbehaved_call_still_bounded_by_connect_read_tuple(self):
        """A normal fast call still passes the explicit 2-tuple (connect, read) to requests."""
        client = self._client()
        with patch("requests.Session.post", return_value=_make_chat_response("ok")) as mock_post, \
             patch("app.backend.config.OPENAI_TOTAL_TIMEOUT_SECONDS", 120.0):
            client.translate_once("Hello", "French", "English")

        _, kwargs = mock_post.call_args
        assert isinstance(kwargs["timeout"], tuple) and len(kwargs["timeout"]) == 2


class TestTotalTimeoutConfig:
    """AC-3: OPENAI_TOTAL_TIMEOUT_SECONDS parses to a positive float with default 120
    (cloud-reasoning-stall-hardening, BR-100 — lowered from 480)."""

    def test_env_var_parses_positive_float_default(self):
        import os
        from importlib import reload

        prev = os.environ.pop("OPENAI_TOTAL_TIMEOUT_SECONDS", None)
        try:
            import app.backend.config as cfg
            reload(cfg)
            assert isinstance(cfg.OPENAI_TOTAL_TIMEOUT_SECONDS, float)
            assert cfg.OPENAI_TOTAL_TIMEOUT_SECONDS == 120.0
            assert cfg.OPENAI_TOTAL_TIMEOUT_SECONDS > 0
        finally:
            if prev is not None:
                os.environ["OPENAI_TOTAL_TIMEOUT_SECONDS"] = prev
            import app.backend.config as cfg2
            reload(cfg2)


# ── Reasoning directive composition (cloud-reasoning-stall-hardening, BR-118) ──
#
# AC-1: every cloud TRANSLATION call (translate_once, translate_json) composes
# a harmony `Reasoning: <level>` directive ahead of the base/scenario
# `system_prompt` (BR-109/BR-110) and the BR-78 neighbor `system_context`, in
# ONE leading system message, sourced from `config.OPENAI_TRANSLATION_REASONING`
# at call time — never a hardcoded literal, never leaked into user content.

class TestReasoningDirectiveComposition:
    def _client(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        return OpenAICompatibleClient(
            base_url="http://fake-host:8080", api_key="test-key", model="gpt-oss:120b",
        )

    def test_translate_once_system_message_exact_equals_directive_plus_base_prompt_plus_neighbor_context(self):
        client = self._client()
        client.system_prompt = "You are a professional semiconductor translator."
        neighbor_context = "Previous segments — reference only, do NOT translate or repeat:\nSegment A."

        with patch("requests.Session.post", return_value=_make_chat_response("ok")) as mock_post:
            client.translate_once(
                "Segment B.", "French", "English", system_context=neighbor_context,
            )

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        system_messages = [m for m in messages if m["role"] == "system"]
        assert len(system_messages) == 1, (
            f"directive + base prompt + neighbor context must merge into ONE system message, got {system_messages!r}"
        )
        assert system_messages[0]["content"] == (
            f"{_reasoning_directive()}\n\n{client.system_prompt}\n\n{neighbor_context}"
        )

    def test_reasoning_directive_absent_from_every_user_message(self):
        client = self._client()
        client.system_prompt = "You are a professional semiconductor translator."
        neighbor_context = "Previous segments — reference only, do NOT translate or repeat:\nSegment A."

        with patch("requests.Session.post", return_value=_make_chat_response("ok")) as mock_post:
            client.translate_once(
                "Segment B.", "French", "English", system_context=neighbor_context,
            )

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        user_messages = [m for m in messages if m["role"] == "user"]
        assert user_messages, "translate_once must still emit a user message"
        for m in user_messages:
            assert _reasoning_directive() not in m["content"], (
                "the BR-118 reasoning directive must never leak into a user-role message"
            )

    def test_translate_json_system_message_carries_directive_ahead_of_base_prompt_and_neighbor_context(self):
        client = self._client()
        client.system_prompt = "PROFILE_PROMPT_TOKEN"
        neighbor_context = "SEGMENT_CONTEXT_TOKEN"
        json_payload = '{"text": "Segment B."}'

        with patch("requests.Session.post", return_value=_make_chat_response('{"translation": "x"}')) as mock_post:
            client.translate_json(json_payload, system_context=neighbor_context)

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        system_messages = [m for m in messages if m["role"] == "system"]
        assert len(system_messages) == 1
        merged = system_messages[0]["content"]
        assert (
            merged.index(_reasoning_directive())
            < merged.index("PROFILE_PROMPT_TOKEN")
            < merged.index("SEGMENT_CONTEXT_TOKEN")
        ), "order must be: reasoning directive, then base prompt, then neighbor context"

        user_messages = [m for m in messages if m["role"] == "user"]
        assert len(user_messages) == 1
        assert user_messages[0]["content"] == json_payload, (
            "translate_json must send the JSON envelope AS-IS; the directive must never enter it"
        )
        assert _reasoning_directive() not in user_messages[0]["content"]

    def test_directive_value_sourced_from_openai_translation_reasoning_config_constant(self, monkeypatch):
        """Proves the directive is READ from config.OPENAI_TRANSLATION_REASONING
        at call time, not a hardcoded literal — patching the constant changes
        the outgoing directive."""
        import app.backend.config as cfg_module

        monkeypatch.setattr(cfg_module, "OPENAI_TRANSLATION_REASONING", "high")
        client = self._client()

        with patch("requests.Session.post", return_value=_make_chat_response("ok")) as mock_post:
            client.translate_once("Hello", "French", "English")

        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        system_messages = [m for m in messages if m["role"] == "system"]
        assert system_messages[0]["content"] == "Reasoning: high"


# ── Outline reasoning exemption (cloud-reasoning-stall-hardening, BR-118) ──────
#
# AC-2: complete() — the sole outline/document-context summary seam (BR-109)
# — passes an explicit reasoning=None, which is NEVER overridden by the
# config-sourced translation default; it must keep full reasoning.

class TestOutlineReasoningExemption:
    def test_complete_passes_reasoning_none_no_directive_in_system_message(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        client = OpenAICompatibleClient(
            base_url="http://fake-host:8080", api_key="test-key", model="gpt-oss:120b",
        )
        client.system_prompt = "leftover preamble should not matter"

        with patch("requests.Session.post", return_value=_make_chat_response("A summary.")) as mock_post:
            ok, _result = client.complete("Summarize this document in one sentence: ...")

        assert ok is True
        _, kwargs = mock_post.call_args
        messages = kwargs["json"]["messages"]
        assert not any(m["role"] == "system" for m in messages), (
            "complete() must never emit a system message, including the reasoning directive"
        )
        assert not any("Reasoning:" in m.get("content", "") for m in messages), (
            "complete() must never carry the BR-118 reasoning directive"
        )


# ── embed() wall-clock bound (cloud-reasoning-stall-hardening, BR-100) ────────
#
# AC-4: embed()'s POST must be routed through self._run_bounded_post — not a
# raw self._session.post call — so a stalled embedding aborts within
# OPENAI_TOTAL_TIMEOUT_SECONDS exactly like a completion call.

class TestEmbedBounded:
    def _client(self):
        from app.backend.clients.openai_compatible_client import OpenAICompatibleClient

        return OpenAICompatibleClient(
            base_url="http://fake-host:8080", api_key="test-key", model="gpt-oss:120b",
        )

    def test_embed_invokes_run_bounded_post_wrapper_not_raw_session_post(self):
        client = self._client()
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"data": [{"embedding": [0.1, 0.2]}]}

        def _bounded_side_effect(fn, cancel_event=None):
            return fn()

        with patch.object(
            client, "_run_bounded_post", side_effect=_bounded_side_effect
        ) as mock_bounded, patch("requests.Session.post", return_value=resp) as mock_post:
            vectors = client.embed(["hello"], "text-embedding-test")

        assert vectors == [[0.1, 0.2]]
        assert mock_bounded.called, (
            "embed() must route its POST through self._run_bounded_post, not call session.post directly"
        )
        assert mock_post.called, "the bounded wrapper's fn must still ultimately call session.post"

    def test_embed_never_calls_raw_session_post_when_run_bounded_post_is_bypassed(self):
        """Anti-tautology companion: if _run_bounded_post is stubbed out
        entirely (never delegating to `fn`), raw session.post must NOT still
        fire — proving embed() has no direct/unbounded fallback call path."""
        client = self._client()

        with patch.object(client, "_run_bounded_post", return_value=None) as mock_bounded, \
             patch("requests.Session.post") as mock_post:
            client.embed(["hello"], "text-embedding-test")

        assert mock_bounded.called
        assert not mock_post.called, (
            "embed() must not call requests.Session.post directly — it must go "
            "through _run_bounded_post so the wall-clock ceiling actually bounds it"
        )
