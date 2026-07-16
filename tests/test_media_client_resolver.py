"""Tests for media_client_resolver.py's minimal client-resolution logic.

Mock seam: app.backend.services.media_client_resolver.load_providers_config
(module-attribute access — patched via patch.object on the module captured at
collection time, per this repo's mock.patch resolution-timing convention).

Anti-tautology: assert which client TYPE/provider was actually built (isinstance
+ constructor args), not just that resolve_media_client() returned without
raising.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.backend.clients.ollama_client import OllamaClient
from app.backend.clients.openai_compatible_client import OpenAICompatibleClient
from app.backend.services import media_client_resolver as mcr


def _providers_config(providers, fallback_chain=None):
    return {"providers": providers, "fallback_chain": fallback_chain or []}


# ---------------------------------------------------------------------------
# No providers.yml configured -> always Ollama
# ---------------------------------------------------------------------------

def test_auto_routing_with_no_providers_config_falls_back_to_ollama():
    with patch.object(mcr, "load_providers_config", return_value=None):
        client, model = mcr.resolve_media_client(None, None, None, None, ["en"])

    assert isinstance(client, OllamaClient)


# ---------------------------------------------------------------------------
# Manual provider_override
# ---------------------------------------------------------------------------

def test_manual_override_unknown_provider_raises():
    config = _providers_config([{"id": "panjit", "enabled": True, "base_url": "https://x", "api_key": "k"}])
    with patch.object(mcr, "load_providers_config", return_value=config):
        with pytest.raises(ValueError, match="Unknown provider"):
            mcr.resolve_media_client("not-a-real-provider", None, None, None, ["en"])


def test_manual_override_ollama_local_builds_ollama_client():
    # providers.yml conventionally lists "ollama-local" as an explicit
    # provider entry too (see config/providers.yml.example) — the manual
    # override path looks it up the same way as any other provider id.
    config = _providers_config([
        {"id": "panjit", "enabled": True, "base_url": "https://x", "api_key": "k"},
        {"id": "ollama-local", "enabled": True},
    ])
    with patch.object(mcr, "load_providers_config", return_value=config):
        client, model = mcr.resolve_media_client("ollama-local", "llama3", None, None, ["en"])

    assert isinstance(client, OllamaClient)
    assert model == "llama3"


def test_manual_override_enabled_provider_builds_cloud_client():
    config = _providers_config([{
        "id": "panjit", "enabled": True, "base_url": "https://panjit.example/v1",
        "api_key": "real-key", "models": {"translate": "panjit-model"},
    }])
    with patch.object(mcr, "load_providers_config", return_value=config):
        client, model = mcr.resolve_media_client("panjit", None, None, None, ["en"])

    assert isinstance(client, OpenAICompatibleClient)
    assert model == "panjit-model"


def test_manual_override_disabled_provider_falls_back_to_ollama_not_bypassed():
    """Regression test: a provider explicitly disabled in providers.yml
    (enabled: false) must NOT be reachable just because the caller manually
    named it via provider_override — the manual-override branch must apply
    the same enabled-flag check as the auto-routing branch, mirroring
    orchestrator.py's document-pipeline behavior for a disabled provider
    (silent fallback to Ollama, not a live client against the disabled
    provider and not a hard error either)."""
    config = _providers_config([{
        "id": "panjit", "enabled": False, "base_url": "https://panjit.example/v1",
        "api_key": "stale-key", "models": {"translate": "panjit-model"},
    }])
    with patch.object(mcr, "load_providers_config", return_value=config):
        client, model = mcr.resolve_media_client("panjit", None, None, None, ["en"])

    assert isinstance(client, OllamaClient), (
        "a disabled provider must never be used to build a live cloud client, "
        "even when explicitly named via provider_override"
    )


def test_manual_override_disabled_provider_with_api_key_override_is_still_usable():
    """An explicit api_key_override (caller-supplied key, e.g. from the
    frontend's own localStorage key) is a deliberate escape hatch — it must
    still work even if providers.yml marks the provider disabled, exactly
    like _build_cloud_client's `enabled or api_key_override` condition."""
    config = _providers_config([{
        "id": "deepseek", "enabled": False, "base_url": "https://deepseek.example/v1",
        "api_key": "", "models": {"translate": "deepseek-chat"},
    }])
    with patch.object(mcr, "load_providers_config", return_value=config):
        client, model = mcr.resolve_media_client(
            "deepseek", None, None, "user-supplied-key", ["en"]
        )

    assert isinstance(client, OpenAICompatibleClient)


# ---------------------------------------------------------------------------
# Auto-routing (provider_override=None/"auto")
# ---------------------------------------------------------------------------

def test_auto_routing_uses_resolved_route_group_provider():
    config = _providers_config([{
        "id": "panjit", "enabled": True, "base_url": "https://panjit.example/v1",
        "api_key": "k", "models": {"translate": "panjit-model"},
    }])
    fake_group = MagicMock(model="panjit-model", provider="panjit", profile_id="general", targets=["en"])

    with patch.object(mcr, "load_providers_config", return_value=config), \
         patch.object(mcr, "resolve_route_groups", return_value=[fake_group]):
        client, model = mcr.resolve_media_client(None, None, None, None, ["en"])

    assert isinstance(client, OpenAICompatibleClient)
    assert model == "panjit-model"


def test_auto_routing_falls_back_to_ollama_when_cloud_client_build_fails():
    config = _providers_config([{
        "id": "panjit", "enabled": True, "base_url": "https://panjit.example/v1",
        "api_key": "k", "models": {"translate": "panjit-model"},
    }])
    fake_group = MagicMock(model="panjit-model", provider="panjit", profile_id="general", targets=["en"])

    with patch.object(mcr, "load_providers_config", return_value=config), \
         patch.object(mcr, "resolve_route_groups", return_value=[fake_group]), \
         patch.object(mcr, "OpenAICompatibleClient", side_effect=RuntimeError("connect failed")):
        client, model = mcr.resolve_media_client(None, None, None, None, ["en"])

    assert isinstance(client, OllamaClient)
