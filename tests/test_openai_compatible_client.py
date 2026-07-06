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
